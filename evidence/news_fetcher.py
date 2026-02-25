"""
PhilVerify — Evidence Retrieval Module
Fetches related articles from two sources and merges the results:
  1. Google News RSS (gl=PH) — free, no API key, PH-indexed, primary source
  2. NewsAPI /everything  — broader English coverage, requires API key

Google News RSS is always attempted first since it covers local PH outlets
(GMA, Inquirer, Rappler, CNN Philippines, PhilStar, etc.) far better than
NewsAPI's free tier index.
"""
import asyncio
import logging
import hashlib
import xml.etree.ElementTree as ET
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# ── Cache ─────────────────────────────────────────────────────────────────────
# Shared cache for both sources. NewsAPI free tier = 100 req/day.
# Google News RSS has no hard limit but we cache anyway to stay polite.
_CACHE_DIR = Path(__file__).parent.parent / ".cache" / "newsapi"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Philippine news domains (used to boost Google News RSS results) ───────────
_PH_DOMAINS = {
    "rappler.com", "inquirer.net", "gmanetwork.com", "philstar.com",
    "manilatimes.net", "mb.com.ph", "abs-cbn.com", "cnnphilippines.com",
    "pna.gov.ph", "sunstar.com.ph", "businessmirror.com.ph",
    "businessworld.com.ph", "malaya.com.ph", "marikina.gov.ph",
    "verafiles.org", "pcij.org", "interaksyon.philstar.com",
}

# NewsAPI domains filter — restricts results to PH outlets when API key is set
_NEWSAPI_PH_DOMAINS = ",".join([
    "rappler.com", "inquirer.net", "gmanetwork.com", "philstar.com",
    "manilatimes.net", "mb.com.ph", "abs-cbn.com", "cnnphilippines.com",
    "pna.gov.ph", "sunstar.com.ph", "businessmirror.com.ph",
])


@dataclass
class ArticleResult:
    title: str
    url: str
    description: str
    source_name: str
    published_at: str
    similarity: float = 0.0
    stance: str = "Not Enough Info"
    domain_tier: int = 3


@dataclass
class EvidenceResult:
    verdict: str           # "Supported" | "Contradicted" | "Insufficient"
    evidence_score: float  # 0–100
    sources: list[ArticleResult] = field(default_factory=list)
    claim_used: str = ""


def _cache_key(prefix: str, claim: str) -> str:
    return f"{prefix}_{hashlib.md5(claim.lower().strip().encode()).hexdigest()}"


def _load_cache(key: str) -> list[dict] | None:
    path = _CACHE_DIR / f"{key}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def _save_cache(key: str, data: list[dict]) -> None:
    path = _CACHE_DIR / f"{key}.json"
    try:
        path.write_text(json.dumps(data))
    except Exception:
        pass


def _extract_domain(url: str) -> str:
    """Return bare domain from a URL string."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).hostname or ""
        return host.removeprefix("www.")
    except Exception:
        return ""


def _is_ph_article(article: dict) -> bool:
    """
    Return True if the article appears to be from a Philippine outlet.
    Checks the source name since Google News RSS links are redirect URLs.
    """
    src = (article.get("source", {}) or {}).get("name", "").lower()
    url = article.get("url", "").lower()
    # Direct domain match on URL (works for NewsAPI results)
    if _extract_domain(url) in _PH_DOMAINS:
        return True
    # Source-name match (works for Google News RSS redirect URLs)
    _PH_SOURCE_KEYWORDS = {
        "rappler", "inquirer", "gma", "abs-cbn", "cnn philippines",
        "philstar", "manila times", "manila bulletin", "sunstar",
        "businessworld", "business mirror", "malaya", "philippine news agency",
        "pna", "vera files", "pcij", "interaksyon",
    }
    return any(kw in src for kw in _PH_SOURCE_KEYWORDS)


def _build_query(claim: str, entities: list[str] | None) -> str:
    """Build a concise search query from entities or the first words of the claim."""
    if entities:
        return " ".join(entities[:3])
    words = claim.split()
    return " ".join(words[:6])


# ── Google News RSS ───────────────────────────────────────────────────────────

def _fetch_gnews_rss(query: str, max_results: int = 5) -> list[dict]:
    """
    Fetch articles from Google News RSS scoped to the Philippines.
    Returns a list of dicts in the same shape as NewsAPI articles so the
    rest of the pipeline can treat both sources uniformly.
    No API key required.
    """
    encoded = urllib.parse.quote(query)
    url = (
        f"https://news.google.com/rss/search"
        f"?q={encoded}&gl=PH&hl=en-PH&ceid=PH:en"
    )
    try:
        import requests as req_lib
        resp = req_lib.get(url, headers={"User-Agent": "PhilVerify/1.0"}, timeout=10)
        resp.raise_for_status()
        raw = resp.content
        root = ET.fromstring(raw)
        channel = root.find("channel")
        if channel is None:
            return []

        articles: list[dict] = []
        for item in channel.findall("item")[:max_results]:
            title_el = item.find("title")
            link_el  = item.find("link")
            desc_el  = item.find("description")
            pub_el   = item.find("pubDate")
            src_el   = item.find("source")

            title       = title_el.text if title_el is not None else ""
            link        = link_el.text  if link_el  is not None else ""
            description = desc_el.text  if desc_el  is not None else ""
            pub_date    = pub_el.text   if pub_el   is not None else ""
            src_name    = src_el.text   if src_el   is not None else _extract_domain(link)

            # Google News titles often include "- Source" suffix — strip it
            if src_name and title.endswith(f" - {src_name}"):
                title = title[: -(len(src_name) + 3)].strip()

            articles.append({
                "title":       title,
                "url":         link,
                "description": description or title,
                "publishedAt": pub_date,
                "source":      {"name": src_name},
                "_gnews":      True,   # Tag so we can log the origin
            })

        logger.info(
            "Google News RSS (PH) returned %d articles for query '%s...'",
            len(articles), query[:40],
        )
        return articles

    except Exception as exc:
        logger.warning("Google News RSS fetch failed: %s", exc)
        return []


# ── NewsAPI ───────────────────────────────────────────────────────────────────

def _fetch_newsapi(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    """
    Fetch from NewsAPI /everything, restricted to PH domains.
    Falls back to global search if the PH-domains query returns < 2 results.
    """
    try:
        from newsapi import NewsApiClient
        client = NewsApiClient(api_key=api_key)

        # Try Philippine outlets first
        resp = client.get_everything(
            q=query,
            domains=_NEWSAPI_PH_DOMAINS,
            language="en",
            sort_by="relevancy",
            page_size=max_results,
        )
        articles = resp.get("articles", [])

        # If PH domains yield nothing useful, fall back to global
        if len(articles) < 2:
            logger.debug("NewsAPI PH-domains sparse (%d) — retrying global", len(articles))
            resp = client.get_everything(
                q=query,
                language="en",
                sort_by="relevancy",
                page_size=max_results,
            )
            articles = resp.get("articles", [])

        logger.info(
            "NewsAPI returned %d articles for query '%s...'",
            len(articles), query[:40],
        )
        return articles
    except Exception as exc:
        logger.warning("NewsAPI fetch error: %s", exc)
        return []


# ── Public API ────────────────────────────────────────────────────────────────

async def fetch_evidence(
    claim: str,
    api_key: str,
    entities: list[str] = None,
    max_results: int = 5,
) -> list[dict]:
    """
    Fetch the most relevant articles for a claim by merging:
      1. Google News RSS (PH-scoped) — always attempted, no key needed
      2. NewsAPI                      — only when NEWS_API_KEY is configured

    Results are deduplicated by domain and capped at max_results.
    PH-domain articles are surfaced first so scoring reflects local coverage.
    """
    query = _build_query(claim, entities)

    # ── Google News RSS (check cache) ─────────────────────────────────────────
    gnews_key = _cache_key("gnews", query)
    gnews_articles = _load_cache(gnews_key)
    if gnews_articles is None:
        # Run blocking RSS fetch in a thread so we don't block the event loop
        gnews_articles = await asyncio.get_event_loop().run_in_executor(
            None, _fetch_gnews_rss, query, max_results
        )
        _save_cache(gnews_key, gnews_articles)
    else:
        logger.info("Google News RSS cache hit for query hash %s", gnews_key[-8:])

    # ── NewsAPI (check cache) ─────────────────────────────────────────────────
    newsapi_articles: list[dict] = []
    if api_key:
        newsapi_key = _cache_key("newsapi", query)
        newsapi_articles = _load_cache(newsapi_key)
        if newsapi_articles is None:
            newsapi_articles = await asyncio.get_event_loop().run_in_executor(
                None, _fetch_newsapi, query, api_key, max_results
            )
            _save_cache(newsapi_key, newsapi_articles)
        else:
            logger.info("NewsAPI cache hit for query hash %s", newsapi_key[-8:])

    # ── Merge: PH articles first, then global, deduplicated by domain ─────────
    seen_domains: set[str] = set()
    merged: list[dict] = []

    def _add(articles: list[dict]) -> None:
        for art in articles:
            url = art.get("url", "")
            domain = _extract_domain(url)
            # For Google News redirect URLs, deduplicate by source name instead
            dedup_key = domain if domain and "google.com" not in domain \
                        else (art.get("source", {}) or {}).get("name", url)
            if dedup_key and dedup_key in seen_domains:
                continue
            if dedup_key:
                seen_domains.add(dedup_key)
            merged.append(art)

    # PH-source Google News articles go first
    ph_gnews    = [a for a in gnews_articles if _is_ph_article(a)]
    other_gnews = [a for a in gnews_articles if not _is_ph_article(a)]

    _add(ph_gnews)
    _add(newsapi_articles)
    _add(other_gnews)  # non-PH Google News last

    result = merged[:max_results]
    logger.info(
        "Evidence merged: %d PH-gnews + %d newsapi + %d other → %d final",
        len(ph_gnews), len(newsapi_articles), len(other_gnews), len(result),
    )
    return result


def compute_similarity(claim: str, article_text: str) -> float:
    """
    Compute cosine similarity between claim and article using sentence-transformers.
    Falls back to simple word-overlap Jaccard similarity.
    """
    try:
        from sentence_transformers import SentenceTransformer, util
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb_claim = model.encode(claim, convert_to_tensor=True)
        emb_article = model.encode(article_text[:512], convert_to_tensor=True)
        score = float(util.cos_sim(emb_claim, emb_article)[0][0])
        return round(max(0.0, min(1.0, score)), 3)
    except Exception:
        # Jaccard fallback
        a = set(claim.lower().split())
        b = set(article_text.lower().split())
        if not a or not b:
            return 0.0
        return round(len(a & b) / len(a | b), 3)
