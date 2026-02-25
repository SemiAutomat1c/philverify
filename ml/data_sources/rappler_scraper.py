"""
rappler_scraper.py
------------------
Scrapes fact-check articles from Rappler's Facts First / Fact-Check sections.
(https://www.rappler.com/facts-first/ and https://www.rappler.com/newsbreak/fact-check/)

Respects robots.txt, caches results for 7 days, and never raises on failure.
"""
from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from .base import DataSource, NormalizedSample, clean_text, detect_language

logger = logging.getLogger(__name__)

_UA = "PhilVerify-Research/1.0 (academic research; contact: research@philverify.ph)"
_HEADERS = {
    "User-Agent": _UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

# ---------------------------------------------------------------------------
# Verdict → label mapping
# ---------------------------------------------------------------------------
_VERDICT_MAP: dict[str, int] = {
    # Likely Fake  (label 2)
    "FALSE": 2,
    "FAKE": 2,
    "MISLEADING": 2,
    "DISINFORMATION": 2,
    "FABRICATED": 2,
    # Unverified  (label 1)
    "UNVERIFIED": 1,
    "NEEDS MORE CONTEXT": 1,
    "MISSING CONTEXT": 1,
    "NEEDS CONTEXT": 1,
    "PARTLY TRUE": 1,
    "PARTLY FALSE": 1,
    "HALF TRUE": 1,
    "MIXTURE": 1,
    "UNPROVEN": 1,
    # Credible  (label 0)
    "TRUE": 0,
    "ACCURATE": 0,
    "CORRECT": 0,
    "VERIFIED": 0,
}

_CACHE_TTL_DAYS = 7
_REQUEST_DELAY = 1.5  # seconds between requests


def _resolve_verdict(raw: str) -> Optional[int]:
    """Normalise a raw verdict string to a label int, or None if unrecognised."""
    normalised = raw.strip().upper()
    if normalised in _VERDICT_MAP:
        return _VERDICT_MAP[normalised]
    for key, label in _VERDICT_MAP.items():
        if key in normalised:
            return label
    return None


def _robots_allows(base_url: str, path: str) -> bool:
    """Return True when robots.txt permits PhilVerify to access *path*."""
    robots_url = urljoin(base_url, "/robots.txt")
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        logger.warning("Could not read robots.txt (%s): %s — proceeding with caution", robots_url, exc)
        return True
    target = urljoin(base_url, path)
    allowed = rp.can_fetch(_UA, target)
    if not allowed:
        logger.warning("robots.txt disallows scraping %s", target)
    return allowed


def _get(url: str, timeout: int = 20) -> Optional[requests.Response]:
    """GET *url* with the project User-Agent; return None on any error."""
    try:
        resp = requests.get(url, headers=_HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except requests.RequestException as exc:
        logger.warning("GET %s failed: %s", url, exc)
        return None


def _cache_fresh(cache_path: Path) -> bool:
    """True if *cache_path* exists and was written within the TTL window."""
    if not cache_path.exists():
        return False
    mtime = datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc)
    age_days = (datetime.now(tz=timezone.utc) - mtime).days
    return age_days < _CACHE_TTL_DAYS


class RapplerScraper(DataSource):
    """Scrape fact-check articles from Rappler and return NormalizedSample list.

    Tries both:
    - https://www.rappler.com/facts-first/
    - https://www.rappler.com/newsbreak/fact-check/

    Parameters
    ----------
    max_pages:
        Maximum number of listing pages to iterate per section. Defaults to 10.
    """

    BASE_URL = "https://www.rappler.com"

    # Ordered list of archive sections to attempt; first one that yields articles wins.
    ARCHIVE_PATHS = [
        "/facts-first/",
        "/newsbreak/fact-check/",
    ]

    def __init__(self, max_pages: int = 10) -> None:
        self.max_pages = max_pages
        self.cache_file: Path = (
            Path(__file__).parent.parent / "data" / "raw" / "rappler_cache.json"
        )
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        return "rappler_factcheck"

    def fetch(self) -> list[NormalizedSample]:
        """Fetch and return normalised samples from Rappler.

        Loads from local cache when available and fresh; otherwise scrapes
        the live site and persists results to cache.
        """
        # 1. Try cache first
        if _cache_fresh(self.cache_file):
            logger.info("Loading Rappler data from cache: %s", self.cache_file)
            return self._load_cache()

        # 2. Respect robots.txt (check each section path)
        allowed_paths = [
            path for path in self.ARCHIVE_PATHS
            if _robots_allows(self.BASE_URL, path)
        ]
        if not allowed_paths:
            logger.error("robots.txt forbids all Rappler fact-check paths — returning []")
            return []

        logger.info("Scraping Rappler (paths: %s, max %d pages each)…", allowed_paths, self.max_pages)

        article_urls: list[str] = []

        # 3. Collect article URLs across all allowed archive sections
        for archive_path in allowed_paths:
            section_urls = self._collect_article_urls(archive_path)
            logger.info("Section %s: found %d article links", archive_path, len(section_urls))
            article_urls.extend(section_urls)
            time.sleep(_REQUEST_DELAY)

        # De-duplicate
        seen_set: set[str] = set()
        unique_urls: list[str] = []
        for u in article_urls:
            if u not in seen_set:
                seen_set.add(u)
                unique_urls.append(u)

        if not unique_urls:
            logger.warning("No article URLs collected from Rappler — returning []")
            return []

        # 4. Scrape individual articles
        samples: list[NormalizedSample] = []
        for idx, url in enumerate(unique_urls, start=1):
            logger.debug("[%d/%d] Scraping %s", idx, len(unique_urls), url)
            sample = self._scrape_article(url)
            if sample is not None:
                samples.append(sample)
            time.sleep(_REQUEST_DELAY)

        logger.info("Rappler: collected %d labelled samples", len(samples))

        # 5. Persist to cache
        if samples:
            self._save_cache(samples)

        return samples

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _collect_article_urls(self, archive_path: str) -> list[str]:
        """Return all article URLs found across paginated listing pages for *archive_path*."""
        urls: list[str] = []
        for page_num in range(1, self.max_pages + 1):
            page_urls = self._get_article_urls_from_page(archive_path, page_num)
            if not page_urls:
                logger.info(
                    "No articles on page %d of %s — stopping pagination",
                    page_num,
                    archive_path,
                )
                break
            logger.info("  %s page %d: %d links", archive_path, page_num, len(page_urls))
            urls.extend(page_urls)
            time.sleep(_REQUEST_DELAY)
        return urls

    def _listing_page_candidates(self, archive_path: str, page_num: int) -> list[str]:
        """Return concrete URLs to try for a given archive path + page number."""
        base = f"{self.BASE_URL}{archive_path}"
        base = base.rstrip("/")
        candidates = [
            f"{base}/",                       # page 1 root
            f"{base}/page/{page_num}/",       # WordPress-style
            f"{base}?page={page_num}",        # query-param style
            f"{base}?paged={page_num}",
        ]
        if page_num == 1:
            # For page 1 try root first; duplicates are fine — we break early
            candidates.insert(0, f"{base}/")
        return candidates

    def _get_article_urls_from_page(self, archive_path: str, page_num: int) -> list[str]:
        """Fetch one listing page and return article URLs found on it."""
        for url in self._listing_page_candidates(archive_path, page_num):
            resp = _get(url)
            if resp is None:
                time.sleep(0.5)
                continue

            soup = BeautifulSoup(resp.text, "lxml")
            links = self._parse_article_links(soup)
            if links:
                return links
            # If the page loaded but had no links, try next candidate
            time.sleep(0.3)

        return []

    def _parse_article_links(self, soup: BeautifulSoup) -> list[str]:
        """Extract article hrefs from a listing-page soup object."""
        links: list[str] = []

        selectors = [
            "article h2 a",
            "article h3 a",
            ".entry-title a",
            "h2.entry-title a",
            ".story-card__title a",
            ".article-title a",
            ".post-title a",
            "h2 a[href*='fact-check']",
            "h3 a[href*='fact-check']",
            "h2 a[href*='facts-first']",
            "h3 a[href*='facts-first']",
            "h2 a",
        ]
        for selector in selectors:
            nodes = soup.select(selector)
            if not nodes:
                continue
            for node in nodes:
                href = node.get("href", "")
                if not href:
                    continue
                if href.startswith("http"):
                    full = href
                elif href.startswith("/"):
                    full = urljoin(self.BASE_URL, href)
                else:
                    continue
                # Only keep URLs that look like Rappler articles
                if "rappler.com" in full:
                    links.append(full)
            if links:
                break

        # De-duplicate preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique.append(link)
        return unique

    def _scrape_article(self, url: str) -> Optional[NormalizedSample]:
        """Fetch a single Rappler article page and return a NormalizedSample or None."""
        resp = _get(url)
        if resp is None:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # --- Verdict ---
        raw_verdict = self._extract_verdict(soup)
        if raw_verdict is None:
            logger.debug("No recognisable verdict in %s — skipping", url)
            return None

        label = _resolve_verdict(raw_verdict)
        if label is None:
            logger.debug("Unknown verdict %r at %s — skipping", raw_verdict, url)
            return None

        # --- Headline ---
        headline = ""
        h1 = soup.find("h1")
        if h1:
            headline = h1.get_text(separator=" ", strip=True)

        # --- Body / summary text ---
        body_text = self._extract_body_text(soup) or headline
        if not body_text:
            return None

        text = clean_text(body_text)
        if not text:
            return None

        lang = detect_language(text)

        return NormalizedSample(
            text=text,
            label=label,
            source=self.source_name,
            language=lang,
            original_label=raw_verdict,
            confidence=1.0,
        )

    def _extract_verdict(self, soup: BeautifulSoup) -> Optional[str]:
        """Try several heuristics to extract the verdict string from a Rappler article."""

        # 1. Dedicated verdict / rating blocks — Rappler uses coloured label boxes
        verdict_selectors = [
            ".verdict",
            ".rating",
            ".label",
            ".fact-check-label",
            ".fc-label",
            "[class*='verdict']",
            "[class*='rating']",
            "[class*='label-']",
            ".wp-block-group",
            ".rappler-verdict",
        ]
        for sel in verdict_selectors:
            for node in soup.select(sel):
                raw = node.get_text(separator=" ", strip=True)
                if _resolve_verdict(raw) is not None:
                    return raw.strip()

        # 2. Open Graph / Twitter card meta (Rappler often embeds verdict in og:description)
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            if not content:
                continue
            upper = content.upper()
            for key in _VERDICT_MAP:
                # Look for the verdict keyword appearing near the start or as a standalone token
                pattern = r"\b" + re.escape(key) + r"\b"
                if re.search(pattern, upper):
                    return key

        # 3. Structured data / JSON-LD (some CMS setups put verdict in schema.org ClaimReview)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "{}")
                # ClaimReview schema
                if isinstance(data, dict):
                    items = data if not isinstance(data.get("@graph"), list) else {}
                    review = items if items.get("@type") == "ClaimReview" else {}
                    rating = review.get("reviewRating", {})
                    alt_name = rating.get("alternateName", "")
                    if alt_name and _resolve_verdict(alt_name) is not None:
                        return alt_name
            except (json.JSONDecodeError, AttributeError):
                pass

        # 4. Bold/strong within article body
        article_body = (
            soup.find("div", class_=lambda c: c and "article-body" in c)
            or soup.find("div", class_=lambda c: c and "entry-content" in c)
            or soup.find("div", class_=lambda c: c and "content" in c)
        )
        if article_body:
            for tag in article_body.find_all(["strong", "b", "em", "span"]):
                raw = tag.get_text(strip=True)
                if _resolve_verdict(raw) is not None:
                    return raw

        # 5. Headline heuristic (e.g. "FACT CHECK: … is FALSE")
        h1 = soup.find("h1")
        if h1:
            h1_text = h1.get_text(strip=True).upper()
            for key in _VERDICT_MAP:
                if re.search(r"\b" + re.escape(key) + r"\b", h1_text):
                    return key

        # 6. Page title tag
        title_tag = soup.find("title")
        if title_tag:
            title_text = title_tag.get_text(strip=True).upper()
            for key in _VERDICT_MAP:
                if re.search(r"\b" + re.escape(key) + r"\b", title_text):
                    return key

        return None

    def _extract_body_text(self, soup: BeautifulSoup) -> str:
        """Extract the best representative text (claim + summary) from the article."""
        # Priority 1: claim box or summary paragraph
        claim_selectors = [
            ".claim",
            ".claim-text",
            ".fact-check-claim",
            ".article-summary",
            ".entry-summary",
            "blockquote",
        ]
        for sel in claim_selectors:
            node = soup.select_one(sel)
            if node:
                text = node.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    return text

        # Priority 2: first substantive paragraph in article body
        body = (
            soup.find("div", class_=lambda c: c and "article-body" in c)
            or soup.find("div", class_=lambda c: c and "entry-content" in c)
            or soup.find("div", class_=lambda c: c and "content" in c)
        )
        if body:
            for p in body.find_all("p"):
                text = p.get_text(separator=" ", strip=True)
                if len(text) > 40:
                    return text

        # Priority 3: OG description
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            content = og_desc.get("content", "")
            if len(content) > 20:
                return content

        # Priority 4: meta description
        meta_desc = soup.find("meta", attrs={"name": "description"})
        if meta_desc:
            return meta_desc.get("content", "")

        return ""

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    def _save_cache(self, samples: list[NormalizedSample]) -> None:
        payload = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "source": self.source_name,
            "samples": [
                {
                    "text": s.text,
                    "label": s.label,
                    "source": s.source,
                    "language": s.language,
                    "original_label": s.original_label,
                    "confidence": s.confidence,
                }
                for s in samples
            ],
        }
        try:
            self.cache_file.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("Rappler cache saved: %s (%d samples)", self.cache_file, len(samples))
        except OSError as exc:
            logger.error("Failed to write cache file %s: %s", self.cache_file, exc)

    def _load_cache(self) -> list[NormalizedSample]:
        try:
            payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
            samples = [
                NormalizedSample(
                    text=item["text"],
                    label=item["label"],
                    source=item["source"],
                    language=item["language"],
                    original_label=item["original_label"],
                    confidence=item.get("confidence", 1.0),
                )
                for item in payload.get("samples", [])
            ]
            logger.info("Loaded %d samples from Rappler cache", len(samples))
            return samples
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.error("Cache load failed (%s): %s — will re-scrape", self.cache_file, exc)
            return []


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    scraper = RapplerScraper(max_pages=2)
    results = scraper.fetch()
    print(f"\nTotal samples: {len(results)}")
    for sample in results[:5]:
        print(f"  [{sample.label}] ({sample.original_label}) {sample.text[:120]!r}")
