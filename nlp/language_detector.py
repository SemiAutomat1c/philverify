"""
PhilVerify — Language Detector
Detects Tagalog / English / Taglish using langdetect + Filipino stopword ratio heuristic.
No heavy model needed — runs instantly.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Filipino stopword set for heuristic ───────────────────────────────────────
_TL_MARKERS = {
    "ang", "ng", "na", "sa", "at", "ay", "mga", "ni", "nang", "si",
    "ko", "mo", "siya", "kami", "kayo", "sila", "ito", "raw", "daw",
    "ba", "po", "din", "rin", "naman", "lang", "kaya", "dahil", "kung",
    "pero", "kapag", "talaga", "pala", "sana", "grabe", "wala", "hindi",
    "may", "mayroon", "bakit", "paano", "kailan", "nasaan", "sino",
}

# English marker words (distinct from TL)
_EN_MARKERS = {
    "the", "and", "is", "are", "was", "were", "this", "that", "with",
    "from", "have", "has", "had", "will", "would", "could", "should",
    "not", "been", "being", "they", "their", "there",
}


@dataclass
class LanguageResult:
    language: str          # "Tagalog" | "English" | "Taglish" | "Unknown"
    confidence: float      # 0.0 – 1.0
    tl_ratio: float
    en_ratio: float
    method: str            # "heuristic" | "langdetect" | "combined"


class LanguageDetector:
    """
    Two-pass language detector:
    Pass 1 — Filipino stopword ratio (fast, handles code-switching)
    Pass 2 — langdetect (for confirmation when ratios are ambiguous)

    Decision rules:
        tl_ratio >= 0.25 and en_ratio < 0.15  → Tagalog
        en_ratio >= 0.25 and tl_ratio < 0.15  → English
        both >= 0.15                           → Taglish
        fallback                               → langdetect result
    """

    def _token_ratios(self, text: str) -> tuple[float, float]:
        tokens = re.findall(r"\b\w+\b", text.lower())
        if not tokens:
            return 0.0, 0.0
        tl_count = sum(1 for t in tokens if t in _TL_MARKERS)
        en_count = sum(1 for t in tokens if t in _EN_MARKERS)
        total = len(tokens)
        return tl_count / total, en_count / total

    def _langdetect(self, text: str) -> str:
        try:
            from langdetect import detect
            code = detect(text)
            # langdetect returns 'tl' for Tagalog
            if code == "tl":
                return "Tagalog"
            elif code == "en":
                return "English"
            else:
                return "Unknown"
        except Exception:
            return "Unknown"

    def detect(self, text: str) -> LanguageResult:
        if not text or len(text.strip()) < 5:
            return LanguageResult("Unknown", 0.0, 0.0, 0.0, "heuristic")

        tl_ratio, en_ratio = self._token_ratios(text)

        # Clear Tagalog
        if tl_ratio >= 0.25 and en_ratio < 0.15:
            return LanguageResult("Tagalog", tl_ratio, tl_ratio, en_ratio, "heuristic")

        # Clear English
        if en_ratio >= 0.25 and tl_ratio < 0.15:
            return LanguageResult("English", en_ratio, tl_ratio, en_ratio, "heuristic")

        # Taglish — both markers present
        if tl_ratio >= 0.10 and en_ratio >= 0.10:
            confidence = (tl_ratio + en_ratio) / 2
            return LanguageResult("Taglish", confidence, tl_ratio, en_ratio, "heuristic")

        # Ambiguous — fall back to langdetect
        ld_lang = self._langdetect(text)
        if ld_lang != "Unknown":
            confidence = max(tl_ratio, en_ratio, 0.5)
            return LanguageResult(ld_lang, confidence, tl_ratio, en_ratio, "langdetect")

        return LanguageResult("Taglish", 0.4, tl_ratio, en_ratio, "combined")
