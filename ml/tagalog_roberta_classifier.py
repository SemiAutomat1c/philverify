"""
PhilVerify — Tagalog-RoBERTa Sequence Classifier (Layer 1)

Fine-tuned on Philippine misinformation data using jcblaise/roberta-tagalog-base
as the backbone. This model was pre-trained on TLUnified — a large, topically-
varied Filipino corpus — and shows +4.47% average accuracy gain over prior
Filipino models on classification tasks.

Drop-in replacement for XLMRobertaClassifier — same predict() interface.
Checkpoint: ml/models/tagalog_roberta_model/ (populated by train_tagalog_roberta.py).
Raises ModelNotFoundError if checkpoint missing so the engine falls back gracefully.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from ml.xlm_roberta_classifier import Layer1Result, ModelNotFoundError

logger = logging.getLogger(__name__)

MODEL_DIR  = Path(__file__).parent / "models" / "tagalog_roberta_model"
LABEL_NAMES = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}
NUM_LABELS  = 3
MAX_LENGTH  = 256


class TagalogRobertaClassifier:
    """
    jcblaise/roberta-tagalog-base fine-tuned for misinformation classification.

    Loading is lazy: the model is not loaded until the first call to predict().
    Raises ModelNotFoundError on instantiation if the checkpoint is missing.
    """

    def __init__(self) -> None:
        if not MODEL_DIR.exists():
            raise ModelNotFoundError(
                f"Tagalog-RoBERTa checkpoint not found at {MODEL_DIR}. "
                "Run `python ml/train_tagalog_roberta.py` to fine-tune the model first."
            )
        self._tokenizer = None
        self._model     = None

    # ── Lazy load ─────────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        self._torch = torch
        logger.info("Loading Tagalog-RoBERTa from %s …", MODEL_DIR)
        self._tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
        self._model = AutoModelForSequenceClassification.from_pretrained(
            str(MODEL_DIR),
            num_labels=NUM_LABELS,
        )
        self._model.eval()
        logger.info("Tagalog-RoBERTa loaded — device: %s", self._device)

    @property
    def _device(self) -> str:
        try:
            import torch
            if torch.backends.mps.is_available():
                return "mps"
        except Exception:
            pass
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    # ── Saliency: attention-based token importance ────────────────────────────

    def _salient_tokens(self, input_ids, attentions, n: int = 5) -> list[str]:
        import torch
        last_layer_attn = attentions[-1]
        cls_attn = last_layer_attn[0, :, 0, :].mean(0)
        seq_len  = cls_attn.shape[-1]
        tokens   = self._tokenizer.convert_ids_to_tokens(
            input_ids[0].tolist()[:seq_len]
        )
        scored = []
        for tok, score in zip(tokens, cls_attn.tolist()):
            if tok in ("<s>", "</s>", "<pad>", "<unk>"):
                continue
            clean = tok.lstrip("▁").strip()
            if len(clean) >= 3 and clean.isalpha():
                scored.append((clean, score))

        seen: set[str] = set()
        result = []
        for word, _ in sorted(scored, key=lambda x: x[1], reverse=True):
            if word.lower() not in seen:
                seen.add(word.lower())
                result.append(word)
            if len(result) >= n:
                break
        return result

    # ── Public API ────────────────────────────────────────────────────────────

    def predict(self, text: str) -> Layer1Result:
        self._ensure_loaded()
        import torch

        encoding = self._tokenizer(
            text,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = self._model(
                input_ids=encoding["input_ids"],
                attention_mask=encoding["attention_mask"],
                output_attentions=True,
            )

        logits     = outputs.logits[0]
        probs      = torch.softmax(logits, dim=-1)
        pred_label = int(probs.argmax().item())
        confidence = round(float(probs[pred_label].item()) * 100, 1)

        # SDPA attention doesn't return attentions; fallback to empty
        triggered = self._salient_tokens(encoding["input_ids"], outputs.attentions) if outputs.attentions else []

        return Layer1Result(
            verdict=LABEL_NAMES[pred_label],
            confidence=confidence,
            triggered_features=triggered,
        )

    def predict_probs(self, text: str):
        """Return raw softmax probability tensor for ensemble averaging."""
        self._ensure_loaded()
        import torch

        encoding = self._tokenizer(
            text,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        with torch.no_grad():
            outputs = self._model(
                input_ids=encoding["input_ids"],
                attention_mask=encoding["attention_mask"],
                output_attentions=True,
            )
        return torch.softmax(outputs.logits[0], dim=-1), outputs.attentions, encoding["input_ids"]
