"""
PhilVerify — Scoring Engine (Orchestrator)
Ties together all NLP modules, Layer 1, and Layer 2 into a final VerificationResponse.
Final Score = (ML Confidence × 0.40) + (Evidence Score × 0.60)
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path

from config import get_settings
from api.schemas import (
    VerificationResponse, Verdict, Language, DomainTier,
    Layer1Result, Layer2Result, EntitiesResult, EvidenceSource, Stance,
)

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Domain credibility lookup ─────────────────────────────────────────────────
_DOMAIN_DB_PATH = Path(__file__).parent.parent / "domain_credibility.json"
_DOMAIN_DB: dict = {}

def _load_domain_db() -> dict:
    global _DOMAIN_DB
    if not _DOMAIN_DB:
        try:
            _DOMAIN_DB = json.loads(_DOMAIN_DB_PATH.read_text())
        except Exception as e:
            logger.warning("Could not load domain_credibility.json: %s", e)
    return _DOMAIN_DB

def get_domain_tier(domain: str) -> DomainTier | None:
    if not domain:
        return None
    db = _load_domain_db()
    domain = domain.lower().replace("www.", "")
    for tier_key, tier_data in db.items():
        if domain in tier_data.get("domains", []):
            return DomainTier(int(tier_key[-1]))
    return DomainTier.SUSPICIOUS  # Unknown domains default to Tier 3


def _map_verdict(final_score: float) -> Verdict:
    if final_score >= settings.credible_threshold:
        return Verdict.CREDIBLE
    elif final_score >= settings.fake_threshold:
        return Verdict.UNVERIFIED
    else:
        return Verdict.LIKELY_FAKE


async def run_verification(
    text: str,
    input_type: str = "text",
    source_domain: str | None = None,
) -> VerificationResponse:
    """
    Full verification pipeline orchestrator.
    Runs NLP analysis and ML classifier synchronously, evidence retrieval async.
    """
    # ── Lazy imports so app starts without heavy deps ─────────────────────────
    from nlp.preprocessor import TextPreprocessor
    from nlp.language_detector import LanguageDetector
    from nlp.ner import EntityExtractor
    from nlp.sentiment import SentimentAnalyzer
    from nlp.clickbait import ClickbaitDetector
    from nlp.claim_extractor import ClaimExtractor
    from ml.tfidf_classifier import TFIDFClassifier
    from evidence.news_fetcher import fetch_evidence, compute_similarity

    # ── Step 1: Preprocess ────────────────────────────────────────────────────
    preprocessor = TextPreprocessor()
    proc = preprocessor.preprocess(text)

    # ── Step 2: Language detection ────────────────────────────────────────────
    lang_detector = LanguageDetector()
    lang_result = lang_detector.detect(text)
    language = Language(lang_result.language) if lang_result.language in Language._value2member_map_ else Language.TAGLISH

    # ── Steps 3–6: NLP analysis (run concurrently) ───────────────────────────
    ner_extractor = EntityExtractor()
    sentiment_analyzer = SentimentAnalyzer()
    clickbait_detector = ClickbaitDetector()
    claim_extractor = ClaimExtractor()

    ner_result = ner_extractor.extract(text)
    sentiment_result = sentiment_analyzer.analyze(proc.cleaned)
    clickbait_result = clickbait_detector.detect(text)
    claim_result = claim_extractor.extract(proc.cleaned)

    # ── Step 7: Layer 1 — ML Classifier ──────────────────────────────────────
    classifier = TFIDFClassifier()
    classifier.train()
    l1 = classifier.predict(proc.cleaned)

    # Enrich triggered features with NLP signals
    if clickbait_result.is_clickbait:
        l1.triggered_features.extend(clickbait_result.triggered_patterns[:3])
    if sentiment_result.sentiment in ("high negative",):
        l1.triggered_features.append("high emotional language")

    layer1 = Layer1Result(
        verdict=Verdict(l1.verdict),
        confidence=l1.confidence,
        triggered_features=l1.triggered_features,
    )

    # ── Step 8: Layer 2 — Evidence Retrieval ──────────────────────────────────
    evidence_score = 50.0  # Neutral default when API key absent
    evidence_sources: list[EvidenceSource] = []
    l2_verdict = Verdict.UNVERIFIED

    if settings.news_api_key:
        try:
            articles = await fetch_evidence(claim_result.claim, settings.news_api_key)
            for art in articles[:5]:
                article_text = f"{art.get('title', '')} {art.get('description', '')}"
                sim = compute_similarity(claim_result.claim, article_text)
                domain = (art.get("source", {}) or {}).get("name", "unknown").lower()
                tier = get_domain_tier(domain)

                # Simple stance heuristic — negative title keywords → Refutes
                title_lower = (art.get("title") or "").lower()
                stance = Stance.NOT_ENOUGH_INFO
                if any(w in title_lower for w in ["false", "fake", "hoax", "wrong", "debunked", "fact check"]):
                    stance = Stance.REFUTES
                elif sim > 0.6:
                    stance = Stance.SUPPORTS

                evidence_sources.append(EvidenceSource(
                    title=art.get("title", ""),
                    url=art.get("url", ""),
                    similarity=sim,
                    stance=stance,
                    domain_tier=tier or DomainTier.SUSPICIOUS,
                    published_at=art.get("publishedAt"),
                    source_name=art.get("source", {}).get("name"),
                ))

            # Evidence score: average similarity × 100, penalized for refuting sources
            if evidence_sources:
                supporting = [s for s in evidence_sources if s.stance == Stance.SUPPORTS]
                refuting = [s for s in evidence_sources if s.stance == Stance.REFUTES]
                avg_sim = sum(s.similarity for s in evidence_sources) / len(evidence_sources)
                refute_penalty = len(refuting) * 15
                evidence_score = max(0.0, min(100.0, avg_sim * 100 - refute_penalty))

                if len(refuting) > len(supporting):
                    l2_verdict = Verdict.LIKELY_FAKE
                elif len(supporting) >= 2:
                    l2_verdict = Verdict.CREDIBLE
        except Exception as e:
            logger.warning("Evidence retrieval failed: %s — using neutral score", e)

    layer2 = Layer2Result(
        verdict=l2_verdict,
        evidence_score=round(evidence_score, 1),
        sources=evidence_sources,
        claim_used=claim_result.claim,
    )

    # ── Step 9: Final Score ───────────────────────────────────────────────────
    # ML confidence is 0-100 where high = more credible for the predicted class.
    # Adjust: if ML says Fake, its confidence works against credibility.
    ml_credibility = l1.confidence if l1.verdict == "Credible" else (100 - l1.confidence)
    final_score = round(
        (ml_credibility * settings.ml_weight) + (evidence_score * settings.evidence_weight),
        1,
    )
    verdict = _map_verdict(final_score)

    # ── Step 10: Assemble response ────────────────────────────────────────────
    result = VerificationResponse(
        verdict=verdict,
        confidence=round(max(l1.confidence, evidence_score / 100 * 100), 1),
        final_score=final_score,
        layer1=layer1,
        layer2=layer2,
        entities=EntitiesResult(
            persons=ner_result.persons,
            organizations=ner_result.organizations,
            locations=ner_result.locations,
            dates=ner_result.dates,
        ),
        sentiment=sentiment_result.sentiment,
        emotion=sentiment_result.emotion,
        language=language,
        domain_credibility=get_domain_tier(source_domain) if source_domain else None,
        input_type=input_type,
    )

    # ── Record to history ─────────────────────────────────────────────────────
    try:
        from api.routes.history import record_verification
        record_verification({
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "input_type": input_type,
            "text_preview": text[:120],
            "verdict": verdict.value,
            "confidence": result.confidence,
            "final_score": final_score,
            "entities": ner_result.to_dict(),
            "claim_used": claim_result.claim,
        })
    except Exception as e:
        logger.warning("Failed to record history: %s", e)

    return result
