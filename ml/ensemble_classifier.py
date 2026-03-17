"""
PhilVerify — Ensemble Classifier (Layer 1)

Averages softmax probabilities from XLMRobertaClassifier and
TagalogRobertaClassifier, then returns a single Layer1Result.

When only one classifier is passed the ensemble degrades gracefully
to that single model (no averaging needed, no performance penalty).
"""
from __future__ import annotations

import logging

from ml.xlm_roberta_classifier import Layer1Result

logger = logging.getLogger(__name__)

LABEL_NAMES = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}


class EnsembleClassifier:
    """
    Soft-voting ensemble over one or more classifiers that implement
    predict_probs(text) → (probs_tensor, attentions, input_ids).

    Triggered features are taken from the classifier with the highest
    individual confidence (the most "sure" model), then deduplicated.
    """

    def __init__(self, classifiers: list) -> None:
        if not classifiers:
            raise ValueError("EnsembleClassifier requires at least one classifier")
        self._classifiers = classifiers

    def predict(self, text: str) -> Layer1Result:
        import torch

        all_probs     = []
        all_attentions = []
        all_input_ids  = []

        for clf in self._classifiers:
            try:
                probs, attentions, input_ids = clf.predict_probs(text)
                all_probs.append(probs)
                all_attentions.append((attentions, input_ids, clf))
            except Exception as exc:
                logger.warning("Classifier %s failed during ensemble: %s", clf, exc)

        if not all_probs:
            # All classifiers failed — return a neutral Unverified result
            return Layer1Result(verdict="Unverified", confidence=33.3, triggered_features=[])

        # Average probabilities across all classifiers that succeeded
        avg_probs  = torch.stack(all_probs).mean(dim=0)   # (num_labels,)
        pred_label = int(avg_probs.argmax().item())
        confidence = round(float(avg_probs[pred_label].item()) * 100, 1)
        verdict    = LABEL_NAMES[pred_label]

        # Triggered features: from the classifier with highest individual confidence
        triggered: list[str] = []
        best_conf = -1.0
        for probs, (attentions, input_ids, clf) in zip(all_probs, all_attentions):
            clf_conf = float(probs.max().item())
            if clf_conf > best_conf and hasattr(clf, "_salient_tokens") and attentions:
                best_conf = clf_conf
                triggered = clf._salient_tokens(input_ids, attentions)

        logger.debug(
            "Ensemble (%d classifiers): %s %.1f%%", len(all_probs), verdict, confidence
        )
        return Layer1Result(
            verdict=verdict,
            confidence=confidence,
            triggered_features=triggered,
        )
