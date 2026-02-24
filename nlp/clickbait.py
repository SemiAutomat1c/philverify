"""
PhilVerify — Clickbait Detector
Detects clickbait patterns common in Philippine fake news / viral content.
Uses regex patterns + feature flags (no model needed).
"""
import re
from dataclasses import dataclass, field

# ── Pattern library ───────────────────────────────────────────────────────────
_CLICKBAIT_PHRASES_EN = [
    r"\byou won'?t believe\b", r"\bshocking\b", r"\bviral\b", r"\bbreaking\b",
    r"\bexclusive\b", r"\bmust[\s-]?see\b", r"\bsecret\b", r"\bconfirmed\b",
    r"\bexposed\b", r"\bscandal\b", r"\bunbelievable\b", r"\bmiraculous?\b",
    r"\bhoax\b", r"\bfact[\s-]?check\b", r"\bthis is why\b", r"\bwatch this\b",
]
_CLICKBAIT_PHRASES_TL = [
    r"\bgrabe\b", r"\bwow\b", r"\bsurprise\b", r"\bshocking\b", r"\btrending\b",
    r"\bselo\b", r"\bbalita\b", r"\bnatuklasan\b", r"\bnahuli\b", r"\bsikat\b",
    r"\bpakinggan\b", r"\bpanoorin\b", r"\bkumpirmado\b", r"\bkatotohanan\b",
]

_CAPS_WORD = re.compile(r"\b[A-Z]{2,}\b")
_EXCESSIVE_PUNCT = re.compile(r"[!?]{2,}")
_NUMBER_BAIT = re.compile(r"\b\d+\s+(?:reasons?|things?|ways?|tips?|signs?|bagay)\b", re.I)
_QUESTION_BAIT = re.compile(r"\b(?:ano|bakit|paano|kailan|sino|saan)\b.*\?", re.I)
_ALL_PHRASES = [re.compile(p, re.IGNORECASE) for p in _CLICKBAIT_PHRASES_EN + _CLICKBAIT_PHRASES_TL]


@dataclass
class ClickbaitResult:
    is_clickbait: bool
    score: float                          # 0.0 – 1.0
    triggered_patterns: list[str] = field(default_factory=list)


class ClickbaitDetector:
    """
    Feature-flag based clickbait detector optimized for PH social media.
    Returns a continuous score based on how many patterns are triggered.
    """

    def detect(self, text: str) -> ClickbaitResult:
        triggered: list[str] = []

        # ALL CAPS words (2+ in a short span)
        caps_words = _CAPS_WORD.findall(text)
        if len(caps_words) >= 2:
            triggered.append(f"all_caps_words: {caps_words[:3]}")

        # Excessive punctuation !! ???
        if _EXCESSIVE_PUNCT.search(text):
            triggered.append("excessive_punctuation")

        # Number-based bait: "5 reasons why..."
        if _NUMBER_BAIT.search(text):
            triggered.append("number_bait")

        # Rhetorical question bait (Tagalog)
        if _QUESTION_BAIT.search(text):
            triggered.append("question_bait")

        # Title length signal (extremely short or extremely long)
        word_count = len(text.split())
        if word_count < 5:
            triggered.append("title_too_short")
        elif word_count > 30:
            triggered.append("title_very_long")

        # Phrase patterns
        for pattern in _ALL_PHRASES:
            m = pattern.search(text)
            if m:
                triggered.append(f"clickbait_phrase: '{m.group(0)}'")

        # Score: each feature contributes a weight
        weights = {
            "excessive_punctuation": 0.20,
            "all_caps_words": 0.20,
            "number_bait": 0.15,
            "question_bait": 0.10,
            "title_too_short": 0.05,
            "title_very_long": 0.05,
        }
        score = 0.0
        for feat in triggered:
            for key, w in weights.items():
                if feat.startswith(key):
                    score += w
                    break
            else:
                # clickbait_phrase triggers
                if feat.startswith("clickbait_phrase"):
                    score += 0.25

        score = min(score, 1.0)
        return ClickbaitResult(
            is_clickbait=score >= 0.4,
            score=round(score, 3),
            triggered_patterns=triggered,
        )
