"""
PhilVerify — Claim Extractor
Extracts the key falsifiable claim from noisy social media text.

Strategy: sentence scoring based on presence of named entities,
verbs, dates, and numbers — no heavy model required.

Filipino fake news headlines almost always embed the checkworthy
assertion in a sentence that contains a specific number/date + person/org
name + an attribution verb (sinabi, ayon, announced, confirmed, etc.).
Scoring these signals finds the right sentence faster and more reliably
than a summarization model that was trained on English news compression.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")

# Numbers, percentages, or month names signal a specific, verifiable claim
_DATE_OR_NUM = re.compile(
    r"\b(\d[\d,.%]*"
    r"|(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)"
    r"|(?:Enero|Pebrero|Marso|Abril|Mayo|Hunyo|Hulyo|Agosto|"
    r"Setyembre|Oktubre|Nobyembre|Disyembre))\b",
    re.IGNORECASE,
)

# Attribution / assertion verbs in English and Filipino
_VERB_PATTERN = re.compile(
    r"\b(is|are|was|were|has|have|had|will|would"
    r"|said|says|announced|confirmed|reported|claims|showed"
    r"|found|revealed|arrested|killed|died|signed|approved|ordered"
    r"|sinabi|ipinahayag|inanunsyo|kinumpirma|ayon|nagpahayag"
    r"|inihayag|iniutos|nagsabi|ipinag-utos)\b",
    re.IGNORECASE,
)


@dataclass
class ClaimResult:
    claim: str
    method: str   # "sentence_scoring" | "sentence_heuristic"


def _score_sentence(sent: str) -> float:
    """Score a sentence by how likely it is to contain a falsifiable claim."""
    score = 0.0
    if _DATE_OR_NUM.search(sent):
        score += 2.0
    score += min(3.0, len(_VERB_PATTERN.findall(sent)) * 1.0)
    if len(sent) > 30:
        score += 1.0
    return score


class ClaimExtractor:
    """
    Extracts the single most falsifiable claim from input text using
    sentence scoring. No heavy model required — spaCy already loaded
    for NER; this module uses only stdlib regex.

    The highest-scoring sentence (by date/number + verb density) is
    returned as the claim for downstream NewsAPI evidence retrieval.
    """

    def extract(self, text: str) -> ClaimResult:
        if not text or len(text.strip()) < 20:
            return ClaimResult(claim=text.strip(), method="passthrough")

        sentences = [s.strip() for s in _SENTENCE_SPLIT.split(text.strip())]
        candidates = [s for s in sentences if len(s) > 15]

        if not candidates:
            return ClaimResult(claim=text[:200].strip(), method="sentence_heuristic")

        scored = [(s, _score_sentence(s)) for s in candidates]
        best_sent, best_score = max(scored, key=lambda x: x[1])

        if best_score > 0:
            return ClaimResult(claim=best_sent, method="sentence_scoring")

        # All scores zero — fall back to first two sentences
        return ClaimResult(
            claim=" ".join(candidates[:2]),
            method="sentence_heuristic",
        )
