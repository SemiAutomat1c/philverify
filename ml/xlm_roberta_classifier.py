"""
PhilVerify — XLM-RoBERTa Sequence Classifier (Layer 1, Phase 10)

Fine-tuned on Philippine misinformation data (English / Filipino / Taglish).
Drop-in replacement for TFIDFClassifier — same predict() interface.

Uses `ml/models/xlmr_model/` if it exists (populated by train_xlmr.py).
Raises ModelNotFoundError if the model has not been trained yet; the
scoring engine falls back to TFIDFClassifier in that case.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# Where train_xlmr.py saves the fine-tuned checkpoint
MODEL_DIR = Path(__file__).parent / "models" / "xlmr_model"

# Labels must match the id2label mapping saved during training
LABEL_NAMES = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}
NUM_LABELS  = 3
MAX_LENGTH  = 256   # tokens; 256 covers 95%+ of PH news headlines/paragraphs


class ModelNotFoundError(FileNotFoundError):
    """Raised when the fine-tuned checkpoint directory is missing."""


@dataclass
class Layer1Result:
    verdict: str                                          # "Credible" | "Unverified" | "Likely Fake"
    confidence: float                                     # 0.0 – 100.0
    triggered_features: list[str] = field(default_factory=list)  # salient tokens


class XLMRobertaClassifier:
    """
    XLM-RoBERTa-based misinformation classifier.

    Loading is lazy: the model is not loaded until the first call to predict().
    This keeps FastAPI startup fast when the model is available.

    Raises ModelNotFoundError on instantiation if MODEL_DIR does not exist,
    so the scoring engine can detect the missing checkpoint immediately.
    """

    def __init__(self) -> None:
        if not MODEL_DIR.exists():
            raise ModelNotFoundError(
                f"XLM-RoBERTa checkpoint not found at {MODEL_DIR}. "
                "Run `python ml/train_xlmr.py` to fine-tune the model first."
            )
        self._tokenizer = None
        self._model     = None

    # ── Lazy load ─────────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import torch
            self._torch = torch
            logger.info("Loading XLM-RoBERTa from %s …", MODEL_DIR)
            self._tokenizer = AutoTokenizer.from_pretrained(str(MODEL_DIR))
            self._model = AutoModelForSequenceClassification.from_pretrained(
                str(MODEL_DIR),
                num_labels=NUM_LABELS,
            )
            self._model.eval()
            logger.info("XLM-RoBERTa loaded — device: %s", self._device)
        except Exception as exc:
            logger.exception("Failed to load XLM-RoBERTa model: %s", exc)
            raise

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

    def _salient_tokens(
        self,
        input_ids,       # (1, seq_len) torch.Tensor
        attentions,      # tuple of (1, heads, seq_len, seq_len) per layer
        n: int = 5,
    ) -> list[str]:
        """
        Average last-layer attention from CLS → all tokens.
        Returns top-N decoded sub-word tokens as human-readable strings.
        Strips the sentencepiece ▁ prefix and SFX tokens.
        """
        import torch
        last_layer_attn = attentions[-1]               # (1, heads, seq, seq)
        cls_attn = last_layer_attn[0, :, 0, :].mean(0)  # (seq,) — avg over heads
        seq_len  = cls_attn.shape[-1]
        tokens   = self._tokenizer.convert_ids_to_tokens(
            input_ids[0].tolist()[:seq_len]
        )

        # Score each token; skip special tokens
        scored = []
        for i, (tok, score) in enumerate(zip(tokens, cls_attn.tolist())):
            if tok in ("<s>", "</s>", "<pad>", "<unk>"):
                continue
            clean = tok.lstrip("▁").strip()
            if len(clean) >= 3 and clean.isalpha():
                scored.append((clean, score))

        # Sort descending, dedup, return top N
        seen: set[str] = set()
        result = []
        for word, _ in sorted(scored, key=lambda x: x[1], reverse=True):
            if word.lower() not in seen:
                seen.add(word.lower())
                result.append(word)
            if len(result) >= n:
                break
        return result

    # ── Public API (same interface as TFIDFClassifier) ────────────────────────

    def predict(self, text: str) -> Layer1Result:
        self._ensure_loaded()
        import torch

        encoding = self._tokenizer(
            text,
            truncation=True,
            max_length=MAX_LENGTH,
            return_tensors="pt",
        )
        input_ids      = encoding["input_ids"]
        attention_mask = encoding["attention_mask"]

        with torch.no_grad():
            outputs = self._model(
                input_ids=input_ids,
                attention_mask=attention_mask,
                output_attentions=True,
            )

        logits     = outputs.logits[0]                        # (num_labels,)
        probs      = torch.softmax(logits, dim=-1)
        pred_label = int(probs.argmax().item())
        confidence = round(float(probs[pred_label].item()) * 100, 1)
        verdict    = LABEL_NAMES[pred_label]

        triggered  = self._salient_tokens(input_ids, outputs.attentions)

        return Layer1Result(
            verdict=verdict,
            confidence=confidence,
            triggered_features=triggered,
        )
