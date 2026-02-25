"""
PhilVerify — Similarity Module (Phase 5)
Computes semantic similarity between a claim and evidence article text.
Primary:  sentence-transformers/all-MiniLM-L6-v2 (cosine similarity)
Fallback: Jaccard word-overlap similarity
"""
import logging
import functools

logger = logging.getLogger(__name__)

# Lazy-load the model at first use — avoids blocking app startup
@functools.lru_cache(maxsize=1)
def _get_model():
    """Load sentence-transformer model once and cache it."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        logger.info("sentence-transformers model loaded: all-MiniLM-L6-v2")
        return model
    except Exception as e:
        logger.warning("sentence-transformers unavailable (%s) — Jaccard fallback active", e)
        return None


def compute_similarity(claim: str, article_text: str) -> float:
    """
    Compute semantic similarity between a fact-check claim and an article.

    Args:
        claim:        The extracted falsifiable claim sentence.
        article_text: Title + description of a retrieved news article.

    Returns:
        Float in [0.0, 1.0] — higher means more semantically related.
    """
    if not claim or not article_text:
        return 0.0

    model = _get_model()
    if model is not None:
        try:
            from sentence_transformers import util
            emb_claim = model.encode(claim, convert_to_tensor=True)
            emb_article = model.encode(article_text[:512], convert_to_tensor=True)
            score = float(util.cos_sim(emb_claim, emb_article)[0][0])
            return round(max(0.0, min(1.0, score)), 4)
        except Exception as e:
            logger.warning("Embedding similarity failed (%s) — falling back to Jaccard", e)

    # Jaccard token-overlap fallback
    return _jaccard_similarity(claim, article_text)


def _jaccard_similarity(a: str, b: str) -> float:
    """Simple set-based Jaccard similarity on word tokens."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return round(len(intersection) / len(union), 4)


def rank_articles_by_similarity(claim: str, articles: list[dict]) -> list[dict]:
    """
    Annotate and sort a list of NewsAPI article dicts by similarity to the claim.

    Each article dict gets a `similarity` key added.
    Returns articles sorted descending by similarity.
    """
    scored = []
    for article in articles:
        article_text = f"{article.get('title', '')} {article.get('description', '')}"
        sim = compute_similarity(claim, article_text)
        scored.append({**article, "similarity": sim})

    scored.sort(key=lambda x: x["similarity"], reverse=True)
    return scored
