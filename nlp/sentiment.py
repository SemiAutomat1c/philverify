"""
PhilVerify — Sentiment & Emotion Analyzer
Uses HuggingFace transformers with graceful fallback to lexicon-based scoring.
"""
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ── Simple lexicons for fallback ──────────────────────────────────────────────
_NEGATIVE_WORDS = {
    "fake", "false", "lie", "liar", "hoax", "scam", "fraud", "corrupt",
    "criminal", "illegal", "murder", "die", "death", "dead", "kill",
    "patay", "namatay", "peke", "sinungaling", "corrupt", "magnanakaw",
    "kasamaan", "krimen", "karahasan", "pandemic", "sakit", "epidemya",
    "grabe", "nakakatakot", "nakakainis", "nakakagalit", "kahiya",
}
_POSITIVE_WORDS = {
    "good", "great", "excellent", "amazing", "wonderful", "positive",
    "success", "win", "victory", "help", "support", "safe", "free",
    "maganda", "magaling", "mahusay", "maayos", "tagumpay", "ligtas",
    "masaya", "mabuti", "mahalaga", "mahal", "salamat", "pagbabago",
}
_FEAR_WORDS = {
    "takot", "fear", "scared", "afraid", "terror", "danger", "dangerous",
    "banta", "panganib", "nakakatakot", "kalamidad", "lindol",
}
_ANGER_WORDS = {
    "galit", "angry", "anger", "furious", "rage", "outrage", "poot",
    "nakakagalit", "nakakaasar", "sumpain", "putang", "gago",
}


@dataclass
class SentimentResult:
    sentiment: str          # positive | negative | neutral | high positive | high negative
    sentiment_score: float  # -1.0 to 1.0
    emotion: str            # anger | fear | joy | sadness | neutral
    emotion_score: float    # 0.0 to 1.0
    method: str             # "transformer" | "lexicon"


class SentimentAnalyzer:
    """
    Two-strategy sentiment analysis:
    Primary  — cardiffnlp/twitter-roberta-base-sentiment-latest (social media optimized)
    Fallback — lexicon-based word counting
    """

    def __init__(self):
        self._sentiment_pipe = None
        self._emotion_pipe = None
        self._loaded = False

    def _load_models(self):
        if self._loaded:
            return
        try:
            from transformers import pipeline
            self._sentiment_pipe = pipeline(
                "text-classification",
                model="cardiffnlp/twitter-roberta-base-sentiment-latest",
                top_k=1,
            )
            self._emotion_pipe = pipeline(
                "text-classification",
                model="j-hartmann/emotion-english-distilroberta-base",
                top_k=1,
            )
            logger.info("Sentiment / emotion models loaded")
        except Exception as e:
            logger.warning("Transformer models not available (%s) — using lexicon fallback", e)
        self._loaded = True

    def _lexicon_analyze(self, text: str) -> SentimentResult:
        words = set(text.lower().split())
        neg = len(words & _NEGATIVE_WORDS)
        pos = len(words & _POSITIVE_WORDS)
        fear = len(words & _FEAR_WORDS)
        anger = len(words & _ANGER_WORDS)

        total = neg + pos
        if total == 0:
            score = 0.0
        else:
            score = (pos - neg) / total

        if score > 0.3:
            sentiment = "high positive" if score > 0.6 else "positive"
        elif score < -0.3:
            sentiment = "high negative" if score < -0.6 else "negative"
        else:
            sentiment = "neutral"

        emotion_score = 0.0
        if fear > anger:
            emotion = "fear"
            emotion_score = min(fear / max(len(words), 1) * 5, 1.0)
        elif anger > 0:
            emotion = "anger"
            emotion_score = min(anger / max(len(words), 1) * 5, 1.0)
        elif pos > neg:
            emotion = "joy"
            emotion_score = min(pos / max(len(words), 1) * 5, 1.0)
        elif neg > 0:
            emotion = "sadness"
            emotion_score = min(neg / max(len(words), 1) * 5, 1.0)
        else:
            emotion = "neutral"
            emotion_score = 0.0

        return SentimentResult(sentiment, round(score, 3), emotion, round(emotion_score, 3), "lexicon")

    def analyze(self, text: str) -> SentimentResult:
        self._load_models()
        snippet = text[:512]  # Transformer token limit

        if self._sentiment_pipe and self._emotion_pipe:
            try:
                s_out = self._sentiment_pipe(snippet)[0]
                e_out = self._emotion_pipe(snippet)[0]

                raw_label = s_out["label"].lower()
                score = s_out["score"]
                if "positive" in raw_label:
                    sentiment = "high positive" if score > 0.85 else "positive"
                    s_score = score
                elif "negative" in raw_label:
                    sentiment = "high negative" if score > 0.85 else "negative"
                    s_score = -score
                else:
                    sentiment = "neutral"
                    s_score = 0.0

                emotion = e_out["label"].lower()
                emotion_score = e_out["score"]
                return SentimentResult(sentiment, round(s_score, 3), emotion, round(emotion_score, 3), "transformer")
            except Exception as e:
                logger.warning("Transformer inference error: %s — falling back to lexicon", e)

        return self._lexicon_analyze(text)
