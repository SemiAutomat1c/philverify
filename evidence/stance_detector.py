"""
PhilVerify — Stance Detection Module (Phase 5)
Classifies the relationship between a claim and a retrieved evidence article.

Stance labels:
  Supports        — article content supports the claim
  Refutes         — article content contradicts / debunks the claim
  Not Enough Info — article is related but not conclusive either way

Strategy (rule-based hybrid — no heavy model dependency):
  1. Keyword scan of title + description for refutation/support signals
  2. Similarity threshold guard — low similarity → NEI
  3. Factuality keywords override similarity-based detection
"""
import logging
import re
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class Stance(str, Enum):
    SUPPORTS = "Supports"
    REFUTES = "Refutes"
    NOT_ENOUGH_INFO = "Not Enough Info"


# ── Keyword Lists ─────────────────────────────────────────────────────────────
# Ordered: check REFUTATION first (stronger signal), then SUPPORT
_REFUTATION_KEYWORDS = [
    # Fact-check verdicts
    r"\bfact.?check\b", r"\bfalse\b", r"\bfake\b", r"\bhoax\b",
    r"\bdebunked\b", r"\bmisinformation\b", r"\bdisinformation\b",
    r"\bnot true\b", r"\bno evidence\b", r"\bunverified\b",
    r"\bcorrection\b", r"\bretract\b", r"\bwrong\b", r"\bdenied\b",
    r"\bscam\b", r"\bsatire\b",
    # Filipino equivalents
    r"\bkasinungalingan\b", r"\bhindi totoo\b", r"\bpeke\b",
]

_SUPPORT_KEYWORDS = [
    r"\bconfirmed\b", r"\bverified\b", r"\bofficial\b", r"\bproven\b",
    r"\btrue\b", r"\blegitimate\b", r"\baccurate\b", r"\bauthorized\b",
    r"\breal\b", r"\bgenuine\b",
    # Filipino equivalents
    r"\btotoo\b", r"\bkumpirmado\b", r"\bopisyal\b",
]

# Articles from these PH fact-check domains always → Refutes regardless of content
_FACTCHECK_DOMAINS = {
    "vera-files.org", "verafiles.org", "factcheck.afp.com",
    "rappler.com/newsbreak/fact-check", "cnn.ph/fact-check",
}

# Similarity threshold: below this → NEI even with support keywords
_SIMILARITY_NEI_THRESHOLD = 0.15
# Similarity above this + support keywords → Supports
_SIMILARITY_SUPPORT_THRESHOLD = 0.35


@dataclass
class StanceResult:
    stance: Stance
    confidence: float         # 0.0–1.0 — how confident we are in this label
    matched_keywords: list[str]
    reason: str


def detect_stance(
    claim: str,
    article_title: str,
    article_description: str,
    article_url: str = "",
    similarity: float = 0.0,
) -> StanceResult:
    """
    Detect the stance of an article relative to the claim.

    Args:
        claim:               The extracted falsifiable claim.
        article_title:       NewsAPI article title.
        article_description: NewsAPI article description.
        article_url:         Article URL (used for fact-check domain detection).
        similarity:          Pre-computed cosine similarity score (0–1).

    Returns:
        StanceResult with stance label, confidence, and reason.
    """
    # Combine article text for keyword search
    article_text = f"{article_title} {article_description}".lower()

    # ── Rule 0: Known fact-check domain → always Refutes ──────────────────────
    if article_url:
        for fc_domain in _FACTCHECK_DOMAINS:
            if fc_domain in article_url.lower():
                return StanceResult(
                    stance=Stance.REFUTES,
                    confidence=0.90,
                    matched_keywords=[fc_domain],
                    reason="Known Philippine fact-check domain",
                )

    # ── Rule 1: Similarity floor — too low to make any claim ──────────────────
    if similarity < _SIMILARITY_NEI_THRESHOLD:
        return StanceResult(
            stance=Stance.NOT_ENOUGH_INFO,
            confidence=0.80,
            matched_keywords=[],
            reason=f"Low similarity ({similarity:.2f}) — article not related to claim",
        )

    # ── Rule 2: Scan for refutation keywords ──────────────────────────────────
    refutation_hits = _scan_keywords(article_text, _REFUTATION_KEYWORDS)
    if refutation_hits:
        confidence = min(0.95, 0.65 + len(refutation_hits) * 0.10)
        return StanceResult(
            stance=Stance.REFUTES,
            confidence=round(confidence, 2),
            matched_keywords=refutation_hits,
            reason=f"Refutation signal detected: {', '.join(refutation_hits[:3])}",
        )

    # ── Rule 3: Scan for support keywords + similarity threshold ──────────────
    support_hits = _scan_keywords(article_text, _SUPPORT_KEYWORDS)
    if support_hits and similarity >= _SIMILARITY_SUPPORT_THRESHOLD:
        confidence = min(0.90, 0.50 + len(support_hits) * 0.10 + similarity * 0.20)
        return StanceResult(
            stance=Stance.SUPPORTS,
            confidence=round(confidence, 2),
            matched_keywords=support_hits,
            reason=f"Support signal + similarity {similarity:.2f}: {', '.join(support_hits[:3])}",
        )

    # ── Default: Not Enough Info ───────────────────────────────────────────────
    return StanceResult(
        stance=Stance.NOT_ENOUGH_INFO,
        confidence=0.70,
        matched_keywords=[],
        reason="No conclusive support or refutation signals found",
    )


def _scan_keywords(text: str, patterns: list[str]) -> list[str]:
    """Return list of matched keyword patterns found in text."""
    hits = []
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            hits.append(match.group(0))
    return hits


def compute_evidence_score(
    stances: list[StanceResult],
    similarities: list[float],
) -> tuple[float, str]:
    """
    Aggregate multiple article stances into a single evidence score (0–100)
    and an overall Layer 2 verdict.

    Scoring:
      - Start at neutral 50
      - Each Supports article: +10 × similarity bonus
      - Each Refutes article: -15 penalty (stronger signal)
      - NEI articles: no effect

    Returns:
        (evidence_score, verdict_label)
    """
    if not stances:
        return 50.0, "Unverified"

    score = 50.0
    supporting = [s for s in stances if s.stance == Stance.SUPPORTS]
    refuting = [s for s in stances if s.stance == Stance.REFUTES]

    for i, stance in enumerate(stances):
        sim = similarities[i] if i < len(similarities) else 0.5
        if stance.stance == Stance.SUPPORTS:
            score += 10.0 * (0.5 + sim)
        elif stance.stance == Stance.REFUTES:
            score -= 15.0 * stance.confidence

    score = round(max(0.0, min(100.0, score)), 1)

    if len(refuting) > len(supporting):
        verdict = "Likely Fake"
    elif len(supporting) >= 2 and score >= 60:
        verdict = "Credible"
    else:
        verdict = "Unverified"

    return score, verdict
