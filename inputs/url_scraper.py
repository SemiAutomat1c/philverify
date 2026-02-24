"""
PhilVerify — URL Scraper (BeautifulSoup)
Extracts article text from news URLs. Respects robots.txt.
"""
import logging
import re
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

logger = logging.getLogger(__name__)

_UNWANTED_TAGS = {"script", "style", "nav", "footer", "header", "aside", "figure", "figcaption"}


def _get_domain(url: str) -> str:
    return urlparse(url).netloc.replace("www.", "")


def _robots_allow(url: str) -> bool:
    try:
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        return rp.can_fetch("*", url)
    except Exception:
        return True  # Allow by default if robots.txt fetch fails


async def scrape_url(url: str) -> tuple[str, str]:
    """
    Returns (article_text, domain).
    Raises ValueError if robots.txt disallows scraping.
    """
    domain = _get_domain(url)

    if not _robots_allow(url):
        logger.warning("robots.txt disallows scraping %s", url)
        raise ValueError(f"Scraping disallowed by robots.txt for {domain}")

    try:
        import httpx
        from bs4 import BeautifulSoup

        headers = {"User-Agent": "PhilVerifyBot/1.0 (fact-checking research)"}
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "lxml")

        # Remove unwanted tags
        for tag in soup(list(_UNWANTED_TAGS)):
            tag.decompose()

        # Try article tag first, fall back to body
        article = soup.find("article") or soup.find("main") or soup.body
        if article is None:
            return "", domain

        paragraphs = article.find_all("p")
        text = " ".join(p.get_text(separator=" ", strip=True) for p in paragraphs)
        text = re.sub(r"\s+", " ", text).strip()

        logger.info("Scraped %d chars from %s", len(text), domain)
        return text, domain

    except Exception as e:
        logger.error("URL scraping failed for %s: %s", url, e)
        return "", domain
