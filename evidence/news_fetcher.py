"""
PhilVerify — Evidence Retrieval Module
Fetches related articles from NewsAPI, computes cosine similarity,
and produces an evidence score for Layer 2 of the scoring engine.
"""
import logging
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
import json

logger = logging.getLogger(__name__)

# Simple file-based cache to respect NewsAPI 100 req/day free tier limit
_CACHE_DIR = Path(__file__).parent.parent / ".cache" / "newsapi"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


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


def _cache_key(claim: str) -> str:
    return hashlib.md5(claim.lower().strip().encode()).hexdigest()


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
    path.write_text(json.dumps(data))


async def fetch_evidence(claim: str, api_key: str, max_results: int = 5) -> list[dict]:
    """Fetch top articles from NewsAPI for the given claim. Cached."""
    key = _cache_key(claim)
    cached = _load_cache(key)
    if cached is not None:
        logger.info("NewsAPI cache hit for claim hash %s", key[:8])
        return cached

    if not api_key:
        logger.warning("NEWS_API_KEY not set — returning empty evidence")
        return []

    try:
        from newsapi import NewsApiClient
        client = NewsApiClient(api_key=api_key)
        # Use first 100 chars of claim as query
        query = claim[:100]
        resp = client.get_everything(
            q=query,
            language="en",
            sort_by="relevancy",
            page_size=max_results,
        )
        articles = resp.get("articles", [])
        _save_cache(key, articles)
        logger.info("NewsAPI returned %d articles for query '%s...'", len(articles), query[:30])
        return articles
    except Exception as e:
        logger.warning("NewsAPI fetch error: %s", e)
        return []


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
