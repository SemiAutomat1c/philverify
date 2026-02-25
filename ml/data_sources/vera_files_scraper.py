"""
vera_files_scraper.py
---------------------
Scrapes fact-check articles from Vera Files (https://verafiles.org/fact-check).
Vera Files is an IFCN-certified Philippine fact-checking organization.

Respects robots.txt, caches results for 7 days, and never raises on failure.
"""
from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import re

import requests
from bs4 import BeautifulSoup

from .base import DataSource, NormalizedSample, clean_text, detect_language

logger = logging.getLogger(__name__)

_UA = "PhilVerify-Research/1.0 (academic research; contact: research@philverify.ph)"
_HEADERS = {"User-Agent": _UA}

# ---------------------------------------------------------------------------
# Verdict → label mapping
# ---------------------------------------------------------------------------
_VERDICT_MAP: dict[str, int] = {
    # Likely Fake  (label 2)
    "FALSE": 2,
    "FAKE": 2,
    "MISLEADING": 2,
    "NO BASIS": 2,
    "SATIRE": 2,
    # Unverified  (label 1)
    "NEEDS CONTEXT": 1,
    "MISSING CONTEXT": 1,
    "UNVERIFIED": 1,
    "PARTLY TRUE": 1,
    "HALF TRUE": 1,
    "MIXTURE": 1,
    # Credible  (label 0)
    "TRUE": 0,
    "ACCURATE": 0,
    "CORRECT": 0,
}

_CACHE_TTL_DAYS = 7
_REQUEST_DELAY = 1.5  # seconds between requests


def _resolve_verdict(raw: str) -> Optional[int]:
    """Normalise a raw verdict string to a label int, or None if unknown."""
    normalised = raw.strip().upper()
    # Exact match first
    if normalised in _VERDICT_MAP:
        return _VERDICT_MAP[normalised]
    # Prefix / substring match
    for key, label in _VERDICT_MAP.items():
        if key in normalised:
            return label
    return None


def _robots_allows(base_url: str, path: str) -> bool:
    """Return True if robots.txt permits PhilVerify to fetch *path*."""
    robots_url = urljoin(base_url, "/robots.txt")
    rp = RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:
        logger.warning("Could not read robots.txt (%s): %s — proceeding with caution", robots_url, exc)
        return True  # benefit of the doubt; we are polite anyway
    allowed = rp.can_fetch(_UA, urljoin(base_url, path))
    if not allowed:
        logger.warning("robots.txt disallows scraping %s%s", base_url, path)
    return allowed


def _get(url: str, timeout: int = 15) -> Optional[requests.Response]:
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


class VeraFilesScraper(DataSource):
    """Scrape fact-check articles from Vera Files and return NormalizedSample list.

    Parameters
    ----------
    max_pages:
        Maximum number of archive pages to iterate. Defaults to 10.
    """

    BASE_URL = "https://verafiles.org"
    ARCHIVE_PATH = "/fact-check"

    def __init__(self, max_pages: int = 10) -> None:
        self.max_pages = max_pages
        self.cache_file: Path = (
            Path(__file__).parent.parent / "data" / "raw" / "vera_files_cache.json"
        )
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        return "vera_files"

    def fetch(self) -> list[NormalizedSample]:
        """Fetch and return normalised samples from Vera Files.

        Loads from local cache when available and fresh; otherwise scrapes
        the live site and persists results to cache.
        """
        # 1. Try cache first
        if _cache_fresh(self.cache_file):
            logger.info("Loading Vera Files data from cache: %s", self.cache_file)
            return self._load_cache()

        # 2. Respect robots.txt
        if not _robots_allows(self.BASE_URL, self.ARCHIVE_PATH):
            logger.error("robots.txt forbids scraping %s%s — returning []", self.BASE_URL, self.ARCHIVE_PATH)
            return []

        logger.info("Scraping Vera Files fact-check archive (max %d pages)…", self.max_pages)
        article_urls: list[str] = []

        # 3. Collect article URLs from archive pages
        for page_num in range(1, self.max_pages + 1):
            urls = self._get_article_urls_from_page(page_num)
            if not urls:
                logger.info("No articles found on page %d — stopping pagination", page_num)
                break
            logger.info("Page %d: found %d article links", page_num, len(urls))
            article_urls.extend(urls)
            time.sleep(_REQUEST_DELAY)

        if not article_urls:
            logger.warning("No article URLs collected from Vera Files — returning []")
            return []

        # 4. Scrape individual articles
        samples: list[NormalizedSample] = []
        seen: set[str] = set()
        for idx, url in enumerate(article_urls, start=1):
            if url in seen:
                continue
            seen.add(url)
            logger.debug("[%d/%d] Scraping %s", idx, len(article_urls), url)
            sample = self._scrape_article(url)
            if sample is not None:
                samples.append(sample)
            time.sleep(_REQUEST_DELAY)

        logger.info("Vera Files: collected %d labelled samples", len(samples))

        # 5. Persist to cache
        if samples:
            self._save_cache(samples)

        return samples

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _page_url(self, page_num: int) -> list[str]:
        """Return candidate page URLs to try for a given page number."""
        base = f"{self.BASE_URL}{self.ARCHIVE_PATH}"
        return [
            f"{base}?page={page_num}",           # query-param style
            f"{base}/page/{page_num}/",           # WordPress style
            f"{base}/page/{page_num}",
        ]

    def _get_article_urls_from_page(self, page_num: int) -> list[str]:
        """Fetch one archive page and return all article URLs found on it."""
        candidates = self._page_url(page_num)
        resp = None
        for url in candidates:
            resp = _get(url)
            if resp is not None:
                break
            time.sleep(0.5)

        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        links: list[str] = []

        # Vera Files uses a Tailwind-based theme — article URLs follow the
        # pattern https://verafiles.org/articles/fact-check-*
        # Directly select all <a> tags whose href contains /articles/fact-check
        for node in soup.select('a[href*="/articles/fact-check"]'):
            href = node.get("href", "")
            if href and self.BASE_URL in href:
                links.append(href)
            elif href and href.startswith("/"):
                links.append(urljoin(self.BASE_URL, href))

        # De-duplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for link in links:
            if link not in seen:
                seen.add(link)
                unique.append(link)
        return unique

    def _scrape_article(self, url: str) -> Optional[NormalizedSample]:
        """Fetch a single Vera Files article and return a NormalizedSample or None."""
        resp = _get(url)
        if resp is None:
            return None

        soup = BeautifulSoup(resp.text, "lxml")

        # --- Headline ---
        headline = ""
        h1 = soup.find("h1")
        if h1:
            headline = h1.get_text(separator=" ", strip=True)

        # --- Verdict ---
        raw_verdict = self._extract_verdict(soup)
        if raw_verdict is None:
            logger.debug("No recognisable verdict in %s — skipping", url)
            return None

        label = _resolve_verdict(raw_verdict)
        if label is None:
            logger.debug("Unknown verdict %r at %s — skipping", raw_verdict, url)
            return None

        # --- Claim / body text ---
        claim_text = self._extract_claim(soup) or headline
        if not claim_text:
            return None

        text = clean_text(claim_text)
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
        """Try several heuristics to pull the verdict string from a parsed page."""
        # 1. Dedicated verdict / rating block (common CMS class patterns)
        verdict_selectors = [
            ".verdict",
            ".rating",
            ".fact-check-rating",
            ".fc-verdict",
            ".label-verdict",
            "[class*='verdict']",
            "[class*='rating']",
            ".wp-block-group",  # Gutenberg block
        ]
        for sel in verdict_selectors:
            nodes = soup.select(sel)
            for node in nodes:
                text = node.get_text(separator=" ", strip=True).upper()
                verdict = _resolve_verdict(text)
                if verdict is not None:
                    return node.get_text(separator=" ", strip=True).strip()

        # 2. Vera Files Tailwind site: "OUR VERDICT <rating>" appears in the
        #    article body text (e.g. "OUR VERDICT False: Remulla merely…")
        #    Try <article> tag first, then any large text block.
        article_tag = soup.find("article")
        if article_tag:
            body_text = article_tag.get_text(separator=" ", strip=True)
            upper_body = body_text.upper()
            match = re.search(
                r"OUR\s+VERDICT[\s:]+([A-Z][A-Z ]{1,30}?)(?:[:\s.\n]|$)",
                upper_body,
            )
            if match:
                candidate = match.group(1).strip()
                if _resolve_verdict(candidate) is not None:
                    return candidate
            # Also scan bold/strong tags inside article
            for strong in article_tag.find_all(["strong", "b", "em"]):
                t = strong.get_text(strip=True).upper()
                if t in _VERDICT_MAP or any(k in t for k in _VERDICT_MAP):
                    return strong.get_text(strip=True)

        # 3. Open Graph / meta description (often contains verdict)
        for meta in soup.find_all("meta"):
            content = meta.get("content", "")
            if content:
                upper = content.upper()
                for key in _VERDICT_MAP:
                    if key in upper:
                        return key

        # 4. Scan bold/strong tags in entry-content div (WordPress fallback)
        article_body = soup.find("div", class_=lambda c: c and "entry-content" in c)
        if article_body:
            for strong in article_body.find_all(["strong", "b", "em"]):
                t = strong.get_text(strip=True).upper()
                if t in _VERDICT_MAP or any(k in t for k in _VERDICT_MAP):
                    return strong.get_text(strip=True)

        # 5. Headline itself (e.g. "VERA FILES FACT CHECK: Claim is FALSE")
        h1 = soup.find("h1")
        if h1:
            h1_text = h1.get_text(strip=True).upper()
            for key in _VERDICT_MAP:
                if key in h1_text:
                    return key

        return None

    def _extract_claim(self, soup: BeautifulSoup) -> str:
        """Extract the claim being fact-checked as the best representative text."""
        # Priority 1: a dedicated claim/summary block
        claim_selectors = [
            ".claim",
            ".claim-text",
            ".fact-check-claim",
            "blockquote",
            ".entry-summary",
        ]
        for sel in claim_selectors:
            node = soup.select_one(sel)
            if node:
                text = node.get_text(separator=" ", strip=True)
                if len(text) > 20:
                    return text

        # Priority 2: first non-empty paragraph in article body.
        # Try <article> tag (Vera Files Tailwind site) then .entry-content div (WordPress).
        body = soup.find("article") or soup.find("div", class_=lambda c: c and "entry-content" in c)
        if body:
            for p in body.find_all("p"):
                text = p.get_text(separator=" ", strip=True)
                if len(text) > 40:
                    return text

        # Priority 3: OG description meta
        og_desc = soup.find("meta", property="og:description")
        if og_desc:
            return og_desc.get("content", "")

        # Priority 4: plain meta description
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
            self.cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info("Vera Files cache saved: %s (%d samples)", self.cache_file, len(samples))
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
            logger.info("Loaded %d samples from Vera Files cache", len(samples))
            return samples
        except (OSError, json.JSONDecodeError, KeyError) as exc:
            logger.error("Cache load failed (%s): %s — will re-scrape", self.cache_file, exc)
            return []


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    scraper = VeraFilesScraper(max_pages=2)
    results = scraper.fetch()
    print(f"\nTotal samples: {len(results)}")
    for sample in results[:5]:
        print(f"  [{sample.label}] ({sample.original_label}) {sample.text[:120]!r}")
