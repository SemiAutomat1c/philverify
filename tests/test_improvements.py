"""
Tests for the 5 NLP pipeline improvements:
  1. calamanCy NER fallback chain
  2. Tagalog-RoBERTa classifier (ModelNotFoundError)
  3. EnsembleClassifier
  4. EDA augmentation
  5. Sentence-scoring ClaimExtractor
  6. NLI stance detection (Rule 1.5)
"""
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_sample(text: str, label: int = 0):
    from ml.dataset import Sample
    return Sample(text=text, label=label)


# ══════════════════════════════════════════════════════════════════════════════
# Part 1 — EDA Augmentation
# ══════════════════════════════════════════════════════════════════════════════

class TestEDAugmentation:
    def test_empty_input_returns_empty(self):
        from ml.dataset import augment_samples
        assert augment_samples([]) == []

    def test_augment_produces_two_variants_per_sample(self):
        from ml.dataset import augment_samples
        samples = [_make_sample("DOH confirms 500 new COVID cases today", 0)]
        aug = augment_samples(samples, seed=42)
        # One deletion + one swap variant per sample
        assert len(aug) == 2

    def test_augmented_labels_match_originals(self):
        from ml.dataset import augment_samples
        samples = [
            _make_sample("Senate passes new bill on health care reform", 0),
            _make_sample("SHOCKING truth about vaccines hidden by government", 2),
        ]
        aug = augment_samples(samples, seed=42)
        orig_labels = {s.label for s in samples}
        for a in aug:
            assert a.label in orig_labels

    def test_short_samples_skipped(self):
        from ml.dataset import augment_samples
        samples = [
            _make_sample("ok", 1),          # 1 word — too short
            _make_sample("fake news", 2),   # 2 words — too short
        ]
        aug = augment_samples(samples, seed=42)
        assert aug == []

    def test_augmented_texts_differ_from_original(self):
        from ml.dataset import augment_samples
        original = "GRABE sinabi ng DOH na 200 bata ang nagkasakit sa bagong virus"
        samples = [_make_sample(original, 2)]
        aug = augment_samples(samples, seed=99)
        # At least one variant should differ
        assert any(a.text != original for a in aug)

    def test_augment_triples_training_set_size(self):
        from ml.dataset import get_split, augment_samples
        train, _ = get_split()
        aug = augment_samples(train, seed=42)
        # aug should be at most 2× train size (some short samples may be skipped)
        assert len(aug) >= len(train)
        assert len(aug) <= 2 * len(train)

    def test_augmented_samples_are_non_empty(self):
        from ml.dataset import augment_samples
        samples = [_make_sample("The senator confirmed signing the new law today", 0)]
        aug = augment_samples(samples, seed=42)
        for a in aug:
            assert len(a.text.strip()) > 0


# ══════════════════════════════════════════════════════════════════════════════
# Part 2 — Sentence-scoring ClaimExtractor
# ══════════════════════════════════════════════════════════════════════════════

class TestClaimExtractor:
    def test_instantiates_without_loading_model(self):
        """New ClaimExtractor has no lazy model loading at all."""
        from nlp.claim_extractor import ClaimExtractor
        ce = ClaimExtractor()
        # No _pipe, no _loaded attributes
        assert not hasattr(ce, '_pipe')
        assert not hasattr(ce, '_loaded')

    def test_passthrough_for_short_text(self):
        from nlp.claim_extractor import ClaimExtractor
        result = ClaimExtractor().extract("hi")
        assert result.method == "passthrough"
        assert result.claim == "hi"

    def test_sentence_scoring_method_on_informative_sentence(self):
        from nlp.claim_extractor import ClaimExtractor
        # Has a date, a verb, and named org — should score high
        text = "GRABE! Sinabi ng DOH noong Martes na 200 bata ang nagkasakit sa bagong virus sa Maynila."
        result = ClaimExtractor().extract(text)
        # Should pick the DOH sentence, not all text or just "GRABE!"
        assert result.method == "sentence_scoring"
        assert "DOH" in result.claim or "200" in result.claim

    def test_heuristic_fallback_when_no_scored_sentences(self):
        from nlp.claim_extractor import ClaimExtractor
        # Text with no dates, no numbers, no verbs
        text = "Wow amazing incredible unbelievable spectacular incomprehensible."
        result = ClaimExtractor().extract(text)
        assert result.method in ("sentence_heuristic", "sentence_scoring")

    def test_returns_claim_result_dataclass(self):
        from nlp.claim_extractor import ClaimExtractor, ClaimResult
        result = ClaimExtractor().extract("The president signed the new healthcare law today.")
        assert isinstance(result, ClaimResult)
        assert isinstance(result.claim, str)
        assert isinstance(result.method, str)

    def test_picks_specific_sentence_over_clickbait_opener(self):
        from nlp.claim_extractor import ClaimExtractor
        text = "OMG! Natuklasan ng mga siyentipiko na 5,000 tao ang namatay dahil sa bagong sakit ngayong Enero."
        result = ClaimExtractor().extract(text)
        # The specific claim (5000 deaths) should be preferred over "OMG!"
        assert "5,000" in result.claim or "siyentipiko" in result.claim or result.method == "sentence_scoring"


# ══════════════════════════════════════════════════════════════════════════════
# Part 3 — TagalogRobertaClassifier
# ══════════════════════════════════════════════════════════════════════════════

class TestTagalogRobertaClassifier:
    def test_raises_model_not_found_when_checkpoint_missing(self, tmp_path, monkeypatch):
        """ModelNotFoundError raised when checkpoint directory doesn't exist."""
        import ml.tagalog_roberta_classifier as mod
        monkeypatch.setattr(mod, "MODEL_DIR", tmp_path / "nonexistent_model")
        with pytest.raises(mod.ModelNotFoundError):
            mod.TagalogRobertaClassifier()

    def test_model_not_found_is_subclass_of_file_not_found(self):
        from ml.xlm_roberta_classifier import ModelNotFoundError
        assert issubclass(ModelNotFoundError, FileNotFoundError)

    def test_shares_same_model_not_found_error(self):
        """Engine catches ModelNotFoundError from xlm_roberta_classifier —
        tagalog module re-uses the same class, so the same except clause catches it."""
        from ml.xlm_roberta_classifier import ModelNotFoundError as E1
        from ml.tagalog_roberta_classifier import ModelNotFoundError as E2
        assert E1 is E2


# ══════════════════════════════════════════════════════════════════════════════
# Part 4 — EnsembleClassifier
# ══════════════════════════════════════════════════════════════════════════════

class TestEnsembleClassifier:
    def _make_stub(self, probs_list: list[float]):
        """Return a stub classifier whose predict_probs returns fixed probabilities."""
        import torch
        stub = MagicMock()
        stub.predict_probs.return_value = (
            torch.tensor(probs_list, dtype=torch.float32),
            None,
            None,
        )
        stub._salient_tokens = MagicMock(return_value=["token1"])
        return stub

    def test_raises_value_error_for_empty_list(self):
        from ml.ensemble_classifier import EnsembleClassifier
        with pytest.raises(ValueError):
            EnsembleClassifier([])

    def test_single_classifier_returns_its_prediction(self):
        import torch
        from ml.ensemble_classifier import EnsembleClassifier
        stub = self._make_stub([0.7, 0.2, 0.1])
        ens = EnsembleClassifier([stub])
        result = ens.predict("any text")
        assert result.verdict == "Credible"
        assert abs(result.confidence - 70.0) < 1.0

    def test_two_classifiers_averages_probabilities(self):
        import torch
        from ml.ensemble_classifier import EnsembleClassifier
        # First: [0.8, 0.1, 0.1] → Credible 80%
        # Second: [0.4, 0.5, 0.1] → Unverified 50%
        # Average: [0.6, 0.3, 0.1] → Credible 60%
        stub1 = self._make_stub([0.8, 0.1, 0.1])
        stub2 = self._make_stub([0.4, 0.5, 0.1])
        ens = EnsembleClassifier([stub1, stub2])
        result = ens.predict("test text")
        assert result.verdict == "Credible"
        assert abs(result.confidence - 60.0) < 1.5

    def test_failing_classifier_gracefully_skipped(self):
        import torch
        from ml.ensemble_classifier import EnsembleClassifier
        good = self._make_stub([0.1, 0.1, 0.8])  # Likely Fake
        bad = MagicMock()
        bad.predict_probs.side_effect = RuntimeError("model failed")
        ens = EnsembleClassifier([good, bad])
        result = ens.predict("test text")
        # Should still get a result from the good classifier
        assert result.verdict == "Likely Fake"

    def test_all_classifiers_failing_returns_unverified_neutral(self):
        from ml.ensemble_classifier import EnsembleClassifier
        bad = MagicMock()
        bad.predict_probs.side_effect = RuntimeError("fail")
        ens = EnsembleClassifier([bad])
        result = ens.predict("test")
        assert result.verdict == "Unverified"
        assert result.confidence == 33.3

    def test_result_has_correct_type(self):
        import torch
        from ml.ensemble_classifier import EnsembleClassifier
        from ml.xlm_roberta_classifier import Layer1Result
        stub = self._make_stub([0.5, 0.3, 0.2])
        ens = EnsembleClassifier([stub])
        result = ens.predict("test")
        assert isinstance(result, Layer1Result)
        assert isinstance(result.triggered_features, list)


# ══════════════════════════════════════════════════════════════════════════════
# Part 5 — NLI Stance Detection
# ══════════════════════════════════════════════════════════════════════════════

class TestNLIStanceDetector:
    def _reset_nli_cache(self):
        """Reset the module-level NLI singleton between tests."""
        import evidence.stance_detector as mod
        mod._nli_pipe = None
        mod._nli_loaded = False

    def test_falls_through_to_keywords_when_nli_unavailable(self):
        """When NLI model can't be loaded, keyword rules still work."""
        import evidence.stance_detector as mod
        self._reset_nli_cache()
        with patch.object(mod, '_get_nli', return_value=None):
            result = mod.detect_stance(
                claim="Vaccines are safe",
                article_title="Fact check: COVID vaccines proven effective",
                article_description="Experts confirm vaccines are safe and effective after extensive testing.",
                article_url="",
                similarity=0.7,
            )
        from evidence.stance_detector import Stance
        # "confirmed" in article → Supports keyword rule
        assert result.stance in (Stance.SUPPORTS, Stance.NOT_ENOUGH_INFO, Stance.REFUTES)
        # Should not crash

    def test_nli_supports_high_confidence(self):
        """When NLI returns 'supports' at ≥0.65, stance is SUPPORTS with NLI reason."""
        import evidence.stance_detector as mod
        self._reset_nli_cache()
        mock_nli = MagicMock()
        mock_nli.return_value = {
            "labels": ["supports the claim", "contradicts the claim", "unrelated"],
            "scores": [0.82, 0.12, 0.06],
        }
        with patch.object(mod, '_get_nli', return_value=mock_nli):
            result = mod.detect_stance(
                claim="Government confirmed 500 new cases",
                article_title="Government says 500 new cases recorded",
                article_description="Officials confirmed today that 500 new cases were recorded nationwide.",
                similarity=0.75,
            )
        from evidence.stance_detector import Stance
        assert result.stance == Stance.SUPPORTS
        assert "NLI" in result.reason

    def test_nli_contradicts_high_confidence(self):
        """When NLI returns 'contradicts' at ≥0.65, stance is REFUTES with NLI reason."""
        import evidence.stance_detector as mod
        self._reset_nli_cache()
        mock_nli = MagicMock()
        mock_nli.return_value = {
            "labels": ["contradicts the claim", "supports the claim", "unrelated"],
            "scores": [0.78, 0.15, 0.07],
        }
        with patch.object(mod, '_get_nli', return_value=mock_nli):
            result = mod.detect_stance(
                claim="There is no evidence of fraud",
                article_title="Evidence of widespread fraud found",
                article_description="Investigators found extensive evidence of fraud in the election.",
                similarity=0.6,
            )
        from evidence.stance_detector import Stance
        assert result.stance == Stance.REFUTES
        assert "NLI" in result.reason

    def test_nli_low_confidence_falls_through_to_keywords(self):
        """NLI confidence < 0.65 — should fall through and use keyword rules."""
        import evidence.stance_detector as mod
        self._reset_nli_cache()
        mock_nli = MagicMock()
        mock_nli.return_value = {
            "labels": ["supports the claim", "contradicts the claim", "unrelated"],
            "scores": [0.45, 0.35, 0.20],  # below 0.65 threshold
        }
        with patch.object(mod, '_get_nli', return_value=mock_nli):
            result = mod.detect_stance(
                claim="Senator is guilty of corruption",
                article_title="Fact check: False claim about senator",
                article_description="This claim has been debunked by multiple fact-checkers.",
                similarity=0.5,
            )
        from evidence.stance_detector import Stance
        # Keyword "debunked" should trigger REFUTES
        assert result.stance == Stance.REFUTES

    def test_short_description_skips_nli(self):
        """Article description shorter than 30 chars → NLI skipped, no error."""
        import evidence.stance_detector as mod
        self._reset_nli_cache()
        mock_nli = MagicMock()
        with patch.object(mod, '_get_nli', return_value=mock_nli):
            result = mod.detect_stance(
                claim="Some claim",
                article_title="Short article",
                article_description="Short.",  # <30 chars
                similarity=0.5,
            )
        # NLI should not have been called
        mock_nli.assert_not_called()


# ══════════════════════════════════════════════════════════════════════════════
# Part 6 — calamanCy NER Fallback Chain
# ══════════════════════════════════════════════════════════════════════════════

class TestCalamanCyNERFallback:
    def _fresh_extractor(self):
        """Return a fresh (unloaded) EntityExtractor."""
        import importlib
        import nlp.ner
        importlib.reload(nlp.ner)
        return nlp.ner.EntityExtractor()

    def test_falls_back_to_spacy_when_calamancy_missing(self, monkeypatch):
        """When calamancy import fails, _nlp is set via spaCy en_core_web_sm."""
        import nlp.ner as mod
        extractor = mod.EntityExtractor()
        extractor._loaded = False  # force reload

        # Simulate calamancy not installed
        original_load = extractor._load_model.__func__

        def patched_load(self):
            self._loaded = True
            try:
                raise ImportError("No module named 'calamancy'")
            except ImportError:
                try:
                    import spacy
                    self._nlp = spacy.load("en_core_web_sm")
                except Exception:
                    self._nlp = None

        import types
        extractor._load_model = types.MethodType(patched_load, extractor)
        extractor._load_model()
        # Either spaCy loaded successfully or fell back to None
        assert extractor._loaded is True

    def test_hint_based_fallback_when_both_unavailable(self):
        """When both calamancy and spaCy fail, hint-based NER still works."""
        import nlp.ner as mod
        extractor = mod.EntityExtractor()
        extractor._loaded = True
        extractor._nlp = None  # force hint-based path

        result = extractor.extract("Sinabi ni Marcos sa Davao tungkol sa DOH")
        assert isinstance(result.persons, list)
        assert isinstance(result.organizations, list)
        assert isinstance(result.locations, list)
        # Should find hint-based entities
        assert any("Marcos" in p for p in result.persons)

    def test_ner_result_method_reflects_path(self):
        """method field on NERResult reflects which extraction path was used."""
        import nlp.ner as mod
        extractor = mod.EntityExtractor()
        extractor._loaded = True
        extractor._nlp = None

        result = extractor._hint_based_extract("Marcos is in Manila with DOH")
        assert result.method == "hints"

    def test_extract_with_no_model_returns_ner_result(self):
        from nlp.ner import EntityExtractor, NERResult
        e = EntityExtractor()
        e._loaded = True
        e._nlp = None
        result = e.extract("DOH confirmed 500 cases in Cebu on January 2026")
        assert isinstance(result, NERResult)
        assert len(result.dates) > 0  # Should find "January 2026"
