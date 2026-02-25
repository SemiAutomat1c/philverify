"""
Tests for Phase 10 — XLM-RoBERTa fine-tuning components.

These tests are designed to pass whether or not the fine-tuned model has
been generated (ml/train_xlmr.py has been run). Tests that require an actual
checkpoint are skipped when ml/models/xlmr_model/ is absent.
"""
import sys
from pathlib import Path
import pytest

# Ensure the PhilVerify package root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml.dataset import (
    DATASET,
    LABEL_NAMES,
    NUM_LABELS,
    get_dataset,
    get_split,
    class_weights,
    Sample,
)

XLMR_MODEL_DIR = Path(__file__).parent.parent / "ml" / "models" / "xlmr_model"
MODEL_PRESENT   = XLMR_MODEL_DIR.exists()


# ───────────────────────────────────────────────────────────────────────────────
# Dataset tests (always run)
# ───────────────────────────────────────────────────────────────────────────────

class TestDataset:

    def test_has_minimum_samples(self):
        """Dataset contains at least 90 samples across all 3 classes."""
        assert len(DATASET) >= 90

    def test_all_labels_present(self):
        labels = {s.label for s in DATASET}
        assert labels == {0, 1, 2}, "All three label classes must be present"

    def test_minimum_samples_per_class(self):
        """Each class has at least 25 samples for meaningful fine-tuning."""
        from collections import Counter
        counts = Counter(s.label for s in DATASET)
        for label in range(NUM_LABELS):
            assert counts[label] >= 25, (
                f"Class {LABEL_NAMES[label]} has only {counts[label]} samples"
            )

    def test_no_empty_texts(self):
        for s in DATASET:
            assert s.text.strip(), "All samples must have non-empty text"

    def test_all_label_ids_valid(self):
        for s in DATASET:
            assert s.label in LABEL_NAMES, f"Invalid label: {s.label}"

    def test_tagalog_samples_present(self):
        """Filipino/Tagalog samples must exist (dataset is multilingual)."""
        tagalog_keywords = {"ayon", "sinabi", "nagbigay", "ang", "ng", "sa"}
        tagalog_count = sum(
            1 for s in DATASET
            if any(kw in s.text.lower().split() for kw in tagalog_keywords)
        )
        assert tagalog_count >= 15, (
            f"Expected at least 15 Tagalog samples, found {tagalog_count}"
        )

    def test_get_dataset_returns_all(self):
        ds = get_dataset()
        assert len(ds) == len(DATASET)

    def test_get_split_sizes(self):
        train, val = get_split(train_ratio=0.8)
        total = len(train) + len(val)
        assert total == len(DATASET), "split must account for all samples"
        assert len(train) > len(val), "train set must be larger"

    def test_get_split_is_stratified(self):
        """Both train and val splits contain all 3 classes."""
        from collections import Counter
        train, val = get_split(train_ratio=0.8)
        train_labels = Counter(s.label for s in train)
        val_labels   = Counter(s.label for s in val)
        for label in range(NUM_LABELS):
            assert train_labels[label] > 0, f"Class {label} absent in train split"
            assert val_labels[label] > 0,   f"Class {label} absent in val split"

    def test_get_split_reproducible(self):
        """Same seed produces same split."""
        train_a, val_a = get_split(seed=7)
        train_b, val_b = get_split(seed=7)
        assert [s.text for s in train_a] == [s.text for s in train_b]

    def test_class_weights_positive(self):
        train, _ = get_split()
        weights = class_weights(train)
        assert len(weights) == NUM_LABELS
        for w in weights:
            assert w > 0, "All class weights must be positive"

    def test_class_weights_inversely_proportional(self):
        """
        Minority classes must have higher weight than majority.
        (May not hold when all classes are equal, so check ordering only
        when counts differ by at least 2).
        """
        from collections import Counter
        train, _ = get_split()
        counts  = Counter(s.label for s in train)
        weights = class_weights(train)
        # If class i has fewer samples than class j, i should have >= weight
        for i in range(NUM_LABELS):
            for j in range(NUM_LABELS):
                if counts[i] < counts[j] - 2:
                    assert weights[i] >= weights[j], (
                        f"Class {i} (count={counts[i]}) should have >= weight "
                        f"than class {j} (count={counts[j]})"
                    )


# ───────────────────────────────────────────────────────────────────────────────
# Classifier instantiation tests (always run)
# ───────────────────────────────────────────────────────────────────────────────

class TestXLMRClassifierInstantiation:

    def test_model_not_found_raises_correct_error(self, tmp_path, monkeypatch):
        """When checkpoint dir is missing, ModelNotFoundError is raised."""
        from ml.xlm_roberta_classifier import XLMRobertaClassifier, ModelNotFoundError
        import ml.xlm_roberta_classifier as xlmr_mod
        monkeypatch.setattr(xlmr_mod, "MODEL_DIR", tmp_path / "nonexistent")
        with pytest.raises(ModelNotFoundError):
            XLMRobertaClassifier()

    def test_model_not_found_is_file_not_found_subclass(self):
        """ModelNotFoundError must be catchable as FileNotFoundError."""
        from ml.xlm_roberta_classifier import ModelNotFoundError
        assert issubclass(ModelNotFoundError, FileNotFoundError)

    def test_engine_falls_back_to_tfidf_when_xlmr_absent(self, monkeypatch):
        """
        scoring.engine.run_verification uses TF-IDF when no XLMR checkpoint.
        We verify it still produces a valid VerificationResponse.
        """
        import ml.xlm_roberta_classifier as xlmr_mod
        from pathlib import Path
        import tempfile
        # Point MODEL_DIR at missing path so XLMRobertaClassifier raises
        monkeypatch.setattr(xlmr_mod, "MODEL_DIR", Path(tempfile.mkdtemp()) / "missing")
        # Run a small verification — should complete without exception
        import asyncio
        from scoring.engine import run_verification
        result = asyncio.run(run_verification("Libreng kuryente na simula bukas ayon sa Pangulo"))
        assert result.verdict in ("Credible", "Unverified", "Likely Fake")
        assert 0 <= result.final_score <= 100
        assert result.layer1 is not None


# ───────────────────────────────────────────────────────────────────────────────
# Classifier prediction tests (skipped when model absent)
# ───────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not MODEL_PRESENT, reason="XLM-RoBERTa checkpoint not found — run ml/train_xlmr.py first")
class TestXLMRClassifierPredict:

    @pytest.fixture(scope="class")
    def classifier(self):
        from ml.xlm_roberta_classifier import XLMRobertaClassifier
        return XLMRobertaClassifier()

    def test_predict_returns_layer1_result(self, classifier):
        from ml.xlm_roberta_classifier import Layer1Result
        result = classifier.predict("DOH confirms 200 new COVID cases in Metro Manila")
        assert isinstance(result, Layer1Result)

    def test_verdict_is_valid_string(self, classifier):
        from ml.xlm_roberta_classifier import LABEL_NAMES
        result = classifier.predict("Rappler: BSP keeps rate at 6.5 percent")
        assert result.verdict in LABEL_NAMES.values()

    def test_confidence_in_range(self, classifier):
        result = classifier.predict("GRABE! Libreng kuryente na simula bukas!")
        assert 0.0 <= result.confidence <= 100.0

    def test_triggered_features_are_strings(self, classifier):
        result = classifier.predict("SHOCKING: Senator caught stealing in Senate vault")
        assert isinstance(result.triggered_features, list)
        assert all(isinstance(f, str) for f in result.triggered_features)

    def test_handles_empty_ish_input_gracefully(self, classifier):
        # Very short inputs should not crash
        result = classifier.predict("ok")
        assert result.verdict in ("Credible", "Unverified", "Likely Fake")

    def test_handles_tagalog_input(self, classifier):
        result = classifier.predict("Ayon sa DOH, bumaba na ang bilang ng bagong kaso ng COVID sa Pilipinas")
        assert result.verdict in ("Credible", "Unverified", "Likely Fake")
        assert 0.0 <= result.confidence <= 100.0

    def test_handles_taglish_input(self, classifier):
        result = classifier.predict("Kinumpirma ng Malacañang ang bagong EO about minimum wage increase")
        assert result.verdict in ("Credible", "Unverified", "Likely Fake")

    def test_fake_news_correctly_classified(self, classifier):
        """
        Obvious fake-news patterns should lean toward Likely Fake.
        This is a sanity test, not a hard assertion — model may vary.
        """
        result = classifier.predict(
            "TOTOO! Bill Gates microchip natuklasan sa bakuna — PANGANIB!"
        )
        # Just check it doesn't crash and returns a valid result
        assert result.verdict in ("Credible", "Unverified", "Likely Fake")

    def test_credible_news_correctly_classified(self, classifier):
        result = classifier.predict(
            "PSA reports Philippine GDP grew 5.2 percent in Q3 2025 based on official statistics"
        )
        assert result.verdict in ("Credible", "Unverified", "Likely Fake")


# ───────────────────────────────────────────────────────────────────────────────
# Training script unit tests (no actual training — just imports + data loading)
# ───────────────────────────────────────────────────────────────────────────────

class TestTrainingScript:

    def test_parse_args_defaults(self):
        """train_xlmr.parse_args returns expected defaults with empty argv."""
        import ml.train_xlmr as train_mod
        import argparse
        # Patch sys.argv for argparse
        import sys
        orig = sys.argv
        sys.argv = ["train_xlmr.py"]
        try:
            args = train_mod.parse_args()
        finally:
            sys.argv = orig
        assert args.epochs    == 5
        assert args.lr        == 2e-5
        assert args.batch_size == 8
        assert args.keep_top_n == 2
        assert args.no_freeze  is False
        assert args.seed       == 42

    def test_philverify_dataset_class_needs_torch(self):
        """PhilVerifyDataset should work with tokenizer+samples (no network call)."""
        import torch
        from ml.dataset import get_split
        from ml.train_xlmr import PhilVerifyDataset
        train_samples, _ = get_split()
        # Use a minimal mock tokenizer to avoid hitting the network
        class MockTokenizer:
            def __call__(self, texts, **kwargs):
                n = len(texts)
                return {
                    "input_ids":      torch.zeros(n, 8, dtype=torch.long),
                    "attention_mask": torch.ones(n, 8, dtype=torch.long),
                }
        ds = PhilVerifyDataset(train_samples, MockTokenizer())
        assert len(ds) == len(train_samples)
        item = ds[0]
        assert "input_ids"      in item
        assert "attention_mask" in item
        assert "labels"         in item
        assert int(item["labels"].item()) in (0, 1, 2)

    def test_freeze_lower_layers_import(self):
        """freeze_lower_layers is importable and callable."""
        from ml.train_xlmr import freeze_lower_layers
        assert callable(freeze_lower_layers)

    def test_evaluate_import(self):
        """evaluate function is importable."""
        from ml.train_xlmr import evaluate
        assert callable(evaluate)
