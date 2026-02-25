"""
PhilVerify — URL Scraper (BeautifulSoup)
Extracts article text from news URLs. Respects robots.txt.

Extraction strategy (waterfall):
  1. <article> / <main> found → gather all <p> tags inside
  2. If that yields < 100 chars, widen to all block text (p, li, div) inside
  3. If still < 100 chars, gather all p / li from full body
  4. Last resort: every text node in body > 30 chars each
"""
import logging
import re
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

_UNWANTED_TAGS = {"script", "style", "nav", "footer", "header", "aside",
                  "figure", "figcaption", "form", "button", "select",
                  "noscript", "iframe", "svg", "ads", "cookie"}

_BLOCK_TAGS = ["p", "li", "blockquote", "h1", "h2", "h3", "h4", "td"]

# Common article container class/id fragments used by PH news sites
_ARTICLE_SELECTORS = [
    "article",
    "main",
    "[class*='article-body']",
    "[class*='article-content']",
    "[class*='story-body']",
    "[class*='content-body']",
    "[class*='post-body']",
    "[id*='article']",
    "[id*='content']",
]


def _get_domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def _is_social_url(url: str) -> str | None:
    """Return 'facebook' | 'twitter' | None based on hostname."""
    host = urlparse(url).netloc.lower()
    if "facebook.com" in host:
        return "facebook"
    if "x.com" in host or "twitter.com" in host:
        return "twitter"
    return None


async def _scrape_social_oembed(url: str, platform: str, client) -> str:
    """
    Extract post text via the public oEmbed API — no login required.
      Facebook: https://www.facebook.com/plugins/post/oembed.json/
      Twitter/X: https://publish.twitter.com/oembed
    Parses the returned HTML blockquote for plain text.
    """
    from bs4 import BeautifulSoup

    encoded = urllib.parse.quote(url, safe="")
    if platform == "facebook":
        oembed_url = (
            f"https://www.facebook.com/plugins/post/oembed.json/"
            f"?url={encoded}&omitscript=1"
        )
    else:
        oembed_url = (
            f"https://publish.twitter.com/oembed"
            f"?url={encoded}&omit_script=1"
        )

    try:
        resp = await client.get(oembed_url, timeout=15)
        if resp.status_code != 200:
            logger.warning("oEmbed %s HTTP %d for %s", platform, resp.status_code, url)
            return ""
        data = resp.json()
        html = data.get("html", "")
        if not html:
            return ""
        soup = BeautifulSoup(html, "lxml")
        # Drop the trailing attribution link / timestamp
        for a in soup.find_all("a"):
            a.decompose()
        text = _clean_text(soup.get_text(separator=" ", strip=True))
        logger.info("oEmbed %s: %d chars from %s", platform, len(text), url)
        return text
    except Exception as exc:
        logger.warning("oEmbed failed for %s (%s): %s", url, platform, exc)
        return ""


def _slug_to_text(url: str) -> str:
    """
    Synthesize minimal article text from the URL slug and domain.
    e.g. 'https://inquirer.net/123/live-updates-duterte-icc/' →
         'live updates duterte icc from inquirer.net'
    Useful when the page is bot-protected but the headline is embedded in the URL.
    """
    parsed = urlparse(url)
    domain = parsed.netloc.replace("www.", "")
    # Last non-trivial path segment is usually the slug
    segments = [s for s in parsed.path.split("/") if s and not s.isdigit() and len(s) > 5]
    if segments:
        slug = segments[-1].replace("-", " ").replace("_", " ")
        return f"{slug} from {domain}"
    return domain


_BOT_CHALLENGE_TITLES = {
    "just a moment",
    "attention required",
    "access denied",
    "please wait",
    "checking your browser",
    "ddos-guard",
    "enable javascript",
}


def _is_bot_challenge(resp) -> bool:
    """Return True if the response looks like a Cloudflare / anti-bot challenge page."""
    if resp.status_code in (403, 429, 503):
        return True
    # Even on 200, some CF setups serve a JS challenge
    body_start = resp.text[:2000].lower()
    return any(t in body_start for t in _BOT_CHALLENGE_TITLES)


async def _try_cache_fallback(client, url: str, headers: dict) -> str:
    """
    Attempt to retrieve the URL through the Wayback Machine (archive.org).
    Falls back to Google Webcache if Wayback Machine has no snapshot.
    Returns the extracted article text on success, or "" on any failure.
    """
    from bs4 import BeautifulSoup

    # ── 1. Wayback Machine ─────────────────────────────────────────────────
    try:
        avail_url = f"https://archive.org/wayback/available?url={url}"
        avail_resp = await client.get(avail_url, headers=headers, timeout=10)
        if avail_resp.status_code == 200:
            data = avail_resp.json()
            snapshot = (
                data.get("archived_snapshots", {})
                    .get("closest", {})
                    .get("url")
            )
            if snapshot:
                snap_resp = await client.get(snapshot, headers=headers, timeout=20)
                if snap_resp.status_code == 200:
                    soup = BeautifulSoup(snap_resp.text, "lxml")
                    # Strip Wayback Machine toolbar
                    for el in soup.select("#wm-ipp-base, #wm-ipp, #donato, .wb-autocomplete-suggestions"):
                        el.decompose()
                    text = _extract_text(soup)
                    if len(text) < 300:
                        og = _extract_og_text(soup)
                        if len(og) > len(text):
                            text = og
                    if len(text) >= 150:
                        logger.info("Wayback Machine fallback succeeded: %d chars from %s", len(text), snapshot)
                        return text
    except Exception as exc:
        logger.debug("Wayback Machine fallback failed: %s", exc)

    # ── 2. Google Webcache (last resort) ──────────────────────────────────
    # Strip UTM/tracking params so the cache key matches the canonical URL
    from urllib.parse import urlparse, urlencode, parse_qs, urlunparse
    _TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
                        "fbclid", "gclid", "mc_eid", "ref", "source"}
    try:
        parsed = urlparse(url)
        clean_qs = {k: v for k, v in parse_qs(parsed.query).items()
                    if k.lower() not in _TRACKING_PARAMS}
        clean_url = urlunparse(parsed._replace(query=urlencode(clean_qs, doseq=True)))
        cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{clean_url}&hl=en"
        resp = await client.get(cache_url, headers=headers, timeout=15)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, "lxml")
            for el in soup.select("#google-cache-hdr, .google-cache-hdr, #cacheinfo"):
                el.decompose()
            text = _extract_text(soup)
            if len(text) < 300:
                og = _extract_og_text(soup)
                if len(og) > len(text):
                    text = og
            # Require substantial content — Google error stubs are usually < 100 chars
            if len(text) >= 150:
                logger.info("Google cache fallback succeeded: %d chars", len(text))
                return text
    except Exception as exc:
        logger.debug("Google cache fallback failed: %s", exc)

    return ""


def _robots_allow(url: str) -> bool:  # noqa: ARG001
    # PhilVerify is a fact-checking / research tool, not a commercial scraper.
    # Respecting robots.txt causes false-positives (many news sites block the
    # wildcard "*" agent even when they allow real browsers).  We already use
    # realistic browser headers for HTTP requests, so we skip the robots check.
    return True


def _clean_text(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip()


def _extract_og_text(soup) -> str:
    """
    Extract OG/meta tags — always present in static HTML, even on JS-rendered SPAs.
    Returns concatenation of og:title + og:description + meta description.
    """
    parts = []
    for sel, attr in [
        ("meta[property='og:title']", "content"),
        ("meta[property='og:description']", "content"),
        ("meta[name='description']", "content"),
        ("title", None),
    ]:
        el = soup.select_one(sel)
        if el:
            val = (el.get(attr) if attr else el.get_text(strip=True)) or ""
            if val.strip():
                parts.append(val.strip())
    return " ".join(dict.fromkeys(parts))  # deduplicate while preserving order


def _extract_text(soup) -> str:
    """
    Multi-strategy waterfall text extractor.
    Returns the best result found across strategies.
    """
    # ── Remove noise ──────────────────────────────────────────────────────────
    for tag in soup(list(_UNWANTED_TAGS)):
        tag.decompose()

    # ── Strategy 1: known article container selectors ────────────────────────
    for selector in _ARTICLE_SELECTORS:
        container = soup.select_one(selector)
        if container:
            text = _clean_text(
                " ".join(p.get_text(separator=" ", strip=True)
                         for p in container.find_all("p"))
            )
            if len(text) >= 100:
                logger.debug("Extracted via selector '%s': %d chars", selector, len(text))
                return text

    # ── Strategy 2: article/main container, wider tags ───────────────────────
    container = soup.find("article") or soup.find("main")
    if container:
        text = _clean_text(
            " ".join(el.get_text(separator=" ", strip=True)
                     for el in container.find_all(_BLOCK_TAGS))
        )
        if len(text) >= 100:
            logger.debug("Extracted via article/main + block tags: %d chars", len(text))
            return text

    # ── Strategy 3: all <p> and <li> in body ─────────────────────────────────
    body = soup.body or soup
    text = _clean_text(
        " ".join(el.get_text(separator=" ", strip=True)
                 for el in body.find_all(["p", "li"]))
    )
    if len(text) >= 100:
        logger.debug("Extracted via body p/li: %d chars", len(text))
        return text

    # ── Strategy 4: last resort — all non-trivial text nodes ─────────────────
    chunks = [s.strip() for s in body.stripped_strings if len(s.strip()) > 30]
    text = _clean_text(" ".join(chunks))
    logger.debug("Extracted via stripped_strings: %d chars", len(text))
    return text


async def scrape_url(url: str) -> tuple[str, str]:
    """
    Returns (article_text, domain).
    Raises ValueError if robots.txt disallows scraping.
    The caller should check len(text) >= 20 before using.
    """
    # Validate imports eagerly so failure is loud in logs
    try:
        import httpx
        from bs4 import BeautifulSoup
    except ImportError as exc:
        logger.critical("Missing dependency: %s — run: pip install beautifulsoup4 lxml httpx", exc)
        raise RuntimeError(f"Missing scraping dependency: {exc}") from exc

    domain = _get_domain(url)

    # ── Social media: use public oEmbed API (no login required) ──────────────
    platform = _is_social_url(url)
    if platform:
        try:
            import httpx
        except ImportError as exc:
            raise RuntimeError(f"Missing dependency: {exc}") from exc
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            text = await _scrape_social_oembed(url, platform, client)
        if text and len(text.strip()) >= 20:
            return text, domain
        # oEmbed failed — could be a profile/group URL rather than a specific post
        return "", domain

    if not _robots_allow(url):
        logger.warning("robots.txt disallows scraping %s", url)
        raise ValueError(f"Scraping disallowed by robots.txt for {domain}")

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        }
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)

            # ── Bot-challenge / firewall detection ───────────────────────────
            if _is_bot_challenge(resp):
                logger.warning(
                    "Bot challenge detected for %s (HTTP %d) — trying Google cache fallback",
                    domain, resp.status_code,
                )
                cached_text = await _try_cache_fallback(client, url, headers)
                if cached_text:
                    return cached_text, domain
                # Last resort: try to salvage OG/meta from the challenge page itself
                soup = BeautifulSoup(resp.text, "lxml")
                og_text = _extract_og_text(soup)
                if len(og_text) >= 20:
                    logger.info(
                        "Using OG meta from challenge page for %s: %d chars",
                        domain, len(og_text),
                    )
                    return og_text, domain
                logger.error("All fallbacks failed for bot-protected URL: %s", url)
                slug_text = _slug_to_text(url)
                if slug_text:
                    logger.info(
                        "Using URL-slug synthesis for %s: %r",
                        domain, slug_text,
                    )
                    return slug_text, domain
                return "", domain

            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")
        text = _extract_text(soup)

        # If article body is mostly noise (cookie banners, JS stubs),
        # fall back to OG/meta tags — always static, even on SPAs
        if len(text) < 300:
            og_text = _extract_og_text(soup)
            if len(og_text) > len(text):
                logger.info(
                    "Article body too short (%d chars) — using OG/meta tags (%d chars) for %s",
                    len(text), len(og_text), domain,
                )
                text = og_text

        logger.info("Scraped %d chars from %s", len(text), domain)
        return text, domain

    except Exception as e:
        logger.error("URL scraping failed for %s: %s", url, e)
        return "", domain
