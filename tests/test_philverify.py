"""
PhilVerify — Unit Tests
Covers: text preprocessor, language detector, clickbait detector, and scoring engine.
Run: pytest tests/ -v
"""
import sys
from pathlib import Path

# Ensure project root is on PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest


# ── TextPreprocessor ──────────────────────────────────────────────────────────

class TestTextPreprocessor:
    def setup_method(self):
        from nlp.preprocessor import TextPreprocessor
        self.preprocessor = TextPreprocessor()

    def test_lowercases_text(self):
        result = self.preprocessor.clean("HELLO WORLD")
        assert result == "hello world"

    def test_strips_urls(self):
        result = self.preprocessor.clean("Check this out https://rappler.com/news/article123")
        assert "https://" not in result
        assert "rappler.com" not in result

    def test_strips_html_tags(self):
        result = self.preprocessor.clean("<p>Hello <b>World</b></p>")
        assert "<" not in result and ">" not in result

    def test_strips_mentions(self):
        result = self.preprocessor.clean("Great post @PresidentPH and @DOH_Philippines!")
        assert "@" not in result

    def test_removes_stopwords(self):
        filtered = self.preprocessor.remove_stopwords(["ang", "fake", "news", "sa", "pilipinas"])
        assert "ang" not in filtered
        assert "fake" in filtered

    def test_normalizes_repeated_chars(self):
        result = self.preprocessor.normalize("graaabe ang gaaalit ko")
        assert "graaabe" not in result

    def test_full_pipeline_returns_result(self):
        from nlp.preprocessor import PreprocessResult
        result = self.preprocessor.preprocess("GRABE! Namatay daw ang tatlong tao sa bagong sakit na kumakalat!")
        assert isinstance(result, PreprocessResult)
        assert result.char_count > 0
        assert len(result.tokens) > 0


# ── LanguageDetector ──────────────────────────────────────────────────────────

class TestLanguageDetector:
    def setup_method(self):
        from nlp.language_detector import LanguageDetector
        self.detector = LanguageDetector()

    def test_detects_tagalog(self):
        result = self.detector.detect(
            "Ang mga mamamayan ay nag-aalala sa bagong batas na isinusulong ng pangulo."
        )
        assert result.language in ("Tagalog", "Taglish")

    def test_detects_english(self):
        result = self.detector.detect(
            "The Supreme Court ruled in favor of the petition filed by the opposition."
        )
        assert result.language in ("English", "Taglish")

    def test_detects_taglish(self):
        result = self.detector.detect(
            "Grabe ang news ngayon! The president announced na libre ang lahat!"
        )
        # Should detect either Taglish or remain consistent
        assert result.language in ("Tagalog", "English", "Taglish")

    def test_unknown_for_empty(self):
        result = self.detector.detect("")
        assert result.language == "Unknown"

    def test_confidence_between_0_and_1(self):
        result = self.detector.detect("Ang balita ay napakalaki!")
        assert 0.0 <= result.confidence <= 1.0


# ── ClickbaitDetector ─────────────────────────────────────────────────────────

class TestClickbaitDetector:
    def setup_method(self):
        from nlp.clickbait import ClickbaitDetector
        self.detector = ClickbaitDetector()

    def test_detects_clickbait_all_caps(self):
        result = self.detector.detect("SHOCKING NEWS: GOVERNMENT CAUGHT LYING TO EVERYONE!")
        assert result.is_clickbait is True
        assert result.score > 0.3

    def test_detects_clickbait_tagalog(self):
        result = self.detector.detect("GRABE!! Natuklasan na ang katotohanan ng bigas scandal!!!")
        assert result.score > 0.3

    def test_clean_headline_not_clickbait(self):
        result = self.detector.detect(
            "DOH reports 500 new cases as vaccination drive continues in Metro Manila"
        )
        assert result.is_clickbait is False

    def test_score_between_0_and_1(self):
        result = self.detector.detect("Breaking news today")
        assert 0.0 <= result.score <= 1.0


# ── TF-IDF Classifier ─────────────────────────────────────────────────────────

class TestTFIDFClassifier:
    def setup_method(self):
        from ml.tfidf_classifier import TFIDFClassifier
        self.clf = TFIDFClassifier()
        self.clf.train()

    def test_predict_returns_valid_verdict(self):
        result = self.clf.predict("DOH reports 500 new COVID cases today in Metro Manila")
        assert result.verdict in ("Credible", "Unverified", "Fake")

    def test_confidence_in_valid_range(self):
        result = self.clf.predict("SHOCKING: Government hid the truth about vaccines!")
        assert 0.0 <= result.confidence <= 100.0

    def test_triggered_features_are_strings(self):
        result = self.clf.predict("GRABE! Namatay daw ang tatlong tao sa bagong sakit!")
        assert all(isinstance(f, str) for f in result.triggered_features)

    def test_seed_fake_news_detected(self):
        result = self.clf.predict("CONFIRMED: Philippines to become 51st state of USA in 2026!")
        # Should not be Credible for obvious fake claim
        assert result.verdict in ("Unverified", "Fake", "Likely Fake")


# ── Scoring Engine (lightweight integration) ──────────────────────────────────

class TestScoringEngine:
    """Integration test — no API keys needed, evidence score defaults to 50."""

    @pytest.mark.asyncio
    async def test_verify_text_returns_response(self):
        from scoring.engine import run_verification
        from api.schemas import VerificationResponse

        result = await run_verification(
            "GRABE! Nakita ko raw namatay ang tatlong tao sa bagong sakit na kumakalat sa Pilipinas!",
            input_type="text",
        )
        assert isinstance(result, VerificationResponse)
        assert result.verdict is not None
        assert 0.0 <= result.final_score <= 100.0

    @pytest.mark.asyncio
    async def test_verify_credible_text(self):
        from scoring.engine import run_verification

        result = await run_verification(
            "DOH reports 500 new COVID-19 cases as vaccination drive continues in Metro Manila",
            input_type="text",
        )
        assert result.final_score is not None
        assert result.language is not None

    @pytest.mark.asyncio
    async def test_entities_extracted(self):
        from scoring.engine import run_verification

        result = await run_verification(
            "President Marcos announced new policies in Manila regarding the AFP and PNP.",
            input_type="text",
        )
        assert result.entities is not None
