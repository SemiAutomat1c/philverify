"""
PhilVerify — URL Preview Route
GET /preview?url=<encoded_url>

Fetches Open Graph / meta tags from the given URL and returns a lightweight
article card payload: title, description, image, site name, favicon, and domain.
Used by the frontend to show a "link unfurl" preview before/after verification.
"""
import logging
import re
from urllib.parse import urlparse

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/preview", tags=["Preview"])


class URLPreview(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image: Optional[str] = None
    site_name: Optional[str] = None
    favicon: Optional[str] = None
    domain: Optional[str] = None


def _slug_to_title(url: str) -> Optional[str]:
    """Convert URL path slug to a readable title.
    e.g. 'remulla-chides-bulacan-guv-for-alleged-road-abuse-dont-act-like-a-king' →
         'Remulla Chides Bulacan Guv For Alleged Road Abuse Dont Act Like A King'
    """
    parsed = urlparse(url)
    segments = [s for s in parsed.path.split("/") if s and not s.isdigit() and len(s) > 4]
    if segments:
        slug = segments[-1]
        # Remove common file extensions
        slug = re.sub(r'\.(html?|php|aspx?)$', '', slug, flags=re.IGNORECASE)
        # Strip UTM / query artifacts that leaked into path
        slug = slug.split('?')[0]
        return ' '.join(w.capitalize() for w in slug.replace('-', ' ').replace('_', ' ').split())
    return None


def _extract_preview(html: str, base_url: str, original_url: str = "") -> URLPreview:
    """Parse OG / meta tags from raw HTML."""
    from bs4 import BeautifulSoup

    parsed_base = urlparse(base_url)
    domain = parsed_base.netloc.replace("www.", "")
    origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

    # Parse head first for speed, then fall back to full doc if needed
    head_end = html.find("</head>")
    head_html = html[:head_end + 7] if head_end != -1 else html[:8000]
    soup_head = BeautifulSoup(head_html, "lxml")
    # Also keep full soup for body-level og: tags some CDNs inject
    soup_full = BeautifulSoup(html[:60_000], "lxml") if head_end == -1 or head_end > 60_000 else soup_head

    def meta(soup, prop=None, name=None):
        if prop:
            el = soup.find("meta", property=prop) or soup.find("meta", attrs={"property": prop})
        else:
            el = soup.find("meta", attrs={"name": name})
        return (el.get("content") or "").strip() if el else None

    def m(prop=None, name=None):
        return meta(soup_head, prop=prop, name=name) or meta(soup_full, prop=prop, name=name)

    title = (
        m(prop="og:title")
        or m(name="twitter:title")
        or (soup_head.title.get_text(strip=True) if soup_head.title else None)
        or _slug_to_title(original_url or base_url)
    )
    description = (
        m(prop="og:description")
        or m(name="twitter:description")
        or m(name="description")
    )
    image = (
        m(prop="og:image")
        or m(name="twitter:image")
        or m(name="twitter:image:src")
    )
    site_name = m(prop="og:site_name") or domain

    # Resolve relative image URLs
    if image and image.startswith("//"):
        image = f"{parsed_base.scheme}:{image}"
    elif image and image.startswith("/"):
        image = f"{origin}{image}"

    # Favicon: try link[rel=icon], fallback to /favicon.ico
    favicon = None
    icon_el = (
        soup_head.find("link", rel="icon")
        or soup_head.find("link", rel="shortcut icon")
        or soup_head.find("link", rel=lambda v: v and "icon" in v)
    )
    if icon_el and icon_el.get("href"):
        href = icon_el["href"].strip()
        if href.startswith("//"):
            favicon = f"{parsed_base.scheme}:{href}"
        elif href.startswith("/"):
            favicon = f"{origin}{href}"
        else:
            favicon = href
    else:
        favicon = f"{origin}/favicon.ico"

    return URLPreview(
        title=title or None,
        description=description or None,
        image=image or None,
        site_name=site_name or None,
        favicon=favicon,
        domain=domain,
    )


_BOT_TITLES = {
    "just a moment", "attention required", "access denied", "please wait",
    "checking your browser", "ddos-guard", "enable javascript", "403 forbidden",
    "404 not found", "503 service unavailable",
}


@router.get("", response_model=URLPreview, summary="Fetch article preview (OG meta)")
async def get_preview(url: str = Query(..., description="Article URL to preview")) -> URLPreview:
    try:
        import httpx
    except ImportError:
        raise HTTPException(status_code=500, detail="httpx not installed")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    origin = f"{parsed.scheme}://{parsed.netloc}"
    slug_title = _slug_to_title(url)

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code >= 400:
                logger.warning("Preview fetch returned %d for %s", resp.status_code, url)
                return URLPreview(
                    domain=domain,
                    site_name=domain,
                    title=slug_title,
                    favicon=f"{origin}/favicon.ico",
                )
            preview = _extract_preview(resp.text, str(resp.url), original_url=url)
            # If OG parsing returned no title, or got a bot-challenge page title, fall back to slug
            if not preview.title or preview.title.lower().strip() in _BOT_TITLES:
                preview.title = slug_title
                # Don't keep description/image from a bot-challenge page
                preview.description = None
                preview.image = None
            return preview
    except Exception as exc:
        logger.warning("Preview fetch failed for %s: %s", url, exc)
        return URLPreview(
            domain=domain,
            site_name=domain,
            title=slug_title,
            favicon=f"{origin}/favicon.ico",
        )
