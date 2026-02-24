"""
PhilVerify — Claim Extractor
Extracts the key falsifiable claim from noisy social media text.
Primary: HuggingFace summarization (t5-small)
Fallback: First 2 sentence heuristic
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


@dataclass
class ClaimResult:
    claim: str
    method: str   # "summarization" | "sentence_heuristic"


class ClaimExtractor:
    """
    Extracts the single most falsifiable claim from input text.
    This claim is then sent to the NewsAPI evidence retrieval step.

    Prompt engineering guide:
      The summarization model is given a task-specific prefix to bias it
      toward extracting assertions rather than summaries.
    """

    _TASK_PREFIX = "Extract the main factual claim: "

    def __init__(self):
        self._pipe = None
        self._loaded = False

    def _load_model(self):
        if self._loaded:
            return
        try:
            from transformers import pipeline
            self._pipe = pipeline(
                "summarization",
                model="sshleifer/distilbart-cnn-6-6",
                max_length=80,
                min_length=10,
                do_sample=False,
            )
            logger.info("Claim extractor model loaded (distilbart-cnn-6-6)")
        except Exception as e:
            logger.warning("Summarization model not available (%s) — using sentence heuristic", e)
        self._loaded = True

    def _sentence_heuristic(self, text: str) -> str:
        """Return the first 1-2 sentences as the claim (fast fallback)."""
        sentences = _SENTENCE_SPLIT.split(text.strip())
        candidates = [s.strip() for s in sentences if len(s.strip()) > 20]
        if not candidates:
            return text[:200].strip()
        return " ".join(candidates[:2])

    def extract(self, text: str) -> ClaimResult:
        self._load_model()

        if not text or len(text.strip()) < 20:
            return ClaimResult(claim=text.strip(), method="passthrough")

        if self._pipe:
            try:
                input_text = self._TASK_PREFIX + text[:1024]
                out = self._pipe(input_text, truncation=True)
                claim = out[0]["summary_text"].strip()
                # Strip the task prefix echo if model includes it
                claim = re.sub(r"^extract the main factual claim:?\s*", "", claim, flags=re.I)
                if len(claim) > 15:
                    return ClaimResult(claim=claim, method="summarization")
            except Exception as e:
                logger.warning("Summarization inference error: %s", e)

        return ClaimResult(
            claim=self._sentence_heuristic(text),
            method="sentence_heuristic",
        )
