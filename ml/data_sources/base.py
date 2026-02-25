"""
ml/data_sources/base.py
Abstract base class and shared utilities for PhilVerify data source adapters.

Provides:
  - NormalizedSample  : canonical dataclass for all ingested samples
  - DataSource        : ABC that every source adapter must implement
  - clean_text        : HTML-strip + Unicode normalization + whitespace collapse
  - detect_language   : langdetect wrapper returning "tl" / "en" / "mixed"
  - domain_to_credibility_score : looks up domain tier from domain_credibility.json
  - binary_to_three_class       : maps raw dataset labels to {0, 1, 2}

Label schema
------------
  0 → Credible
  1 → Unverified
  2 → Likely Fake
"""

from __future__ import annotations

import json
import logging
import re
import unicodedata
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import ClassVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default path: ml/data_sources/ → ml/ → PhilVerify/ → domain_credibility.json
# ---------------------------------------------------------------------------
_DEFAULT_CREDIBILITY_JSON: Path = (
    Path(__file__).parent.parent.parent / "domain_credibility.json"
)

# Module-level cache so the JSON file is only read from disk once per process.
_credibility_cache: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclass
class NormalizedSample:
    """A single article or headline normalized to PhilVerify's label schema.

    Attributes
    ----------
    text:
        Cleaned article text or headline.
    label:
        Integer label in {0, 1, 2} (Credible / Unverified / Likely Fake).
    source:
        Dataset identifier, e.g. ``"jcblaise/fake_news_filipino"``.
    language:
        BCP-47-style language code: ``"tl"``, ``"en"``, or ``"mixed"``.
    original_label:
        The raw label string from the upstream dataset, e.g. ``"fake"``,
        ``"real"``, ``"pants-fire"``.  Preserved for debugging / auditing.
    confidence:
        A float in [0.0, 1.0] representing how confident the label mapping is.
        Defaults to ``1.0`` for unambiguous remappings; use lower values for
        heuristic or model-assisted mappings.
    """

    text: str
    label: int
    source: str
    language: str
    original_label: str
    confidence: float = field(default=1.0)

    def __post_init__(self) -> None:
        if self.label not in {0, 1, 2}:
            raise ValueError(
                f"label must be 0, 1, or 2; got {self.label!r}"
            )
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError(
                f"confidence must be in [0.0, 1.0]; got {self.confidence!r}"
            )


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------


class DataSource(ABC):
    """Abstract base class for PhilVerify data source adapters.

    Subclasses must implement :meth:`fetch` and the :attr:`source_name`
    property.  Callers should use :meth:`load`, which wraps :meth:`fetch`
    with logging and error handling.

    Class Attributes
    ----------------
    LABEL_NAMES:
        Human-readable names for each integer label.
    """

    LABEL_NAMES: ClassVar[dict[int, str]] = {
        0: "Credible",
        1: "Unverified",
        2: "Likely Fake",
    }

    # -- Abstract interface --------------------------------------------------

    @property
    @abstractmethod
    def source_name(self) -> str:
        """A stable, unique identifier for this data source.

        Recommended format: ``"<owner>/<dataset>"`` for HuggingFace datasets,
        or a descriptive slug for scraped / local sources.

        Example: ``"jcblaise/fake_news_filipino"``
        """

    @abstractmethod
    def fetch(self) -> list[NormalizedSample]:
        """Download or load raw data and return normalized samples.

        This method may perform network I/O and should not swallow exceptions;
        error handling is the responsibility of :meth:`load`.

        Returns
        -------
        list[NormalizedSample]
            Every sample extracted from this source after normalization.
        """

    # -- Concrete helpers ----------------------------------------------------

    def load(self) -> list[NormalizedSample]:
        """Call :meth:`fetch`, log progress, and handle errors gracefully.

        Returns an empty list (rather than raising) if fetching fails, so that
        a single broken source does not abort a multi-source pipeline.

        Returns
        -------
        list[NormalizedSample]
            Normalized samples, or ``[]`` on failure.
        """
        logger.info("Loading data source: %s", self.source_name)
        try:
            samples = self.fetch()
            logger.info(
                "Loaded %d samples from %s", len(samples), self.source_name
            )
            return samples
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to load data source '%s'. Returning empty list.",
                self.source_name,
                exc_info=True,
            )
            return []


# ---------------------------------------------------------------------------
# NLP utility functions
# ---------------------------------------------------------------------------


_HTML_TAG_RE = re.compile(r"<[^>]+>", re.UNICODE)
_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)
_MIN_TEXT_LENGTH = 10


def clean_text(text: str) -> str:
    """Clean article text for downstream tokenization.

    Steps applied in order:

    1. Strip HTML / XML tags with a regex (no third-party HTML parser needed).
    2. Normalize Unicode to NFC (handles combining characters, full-width
       glyphs, etc.).
    3. Collapse consecutive whitespace characters (spaces, tabs, newlines) to
       a single ASCII space.
    4. Strip leading and trailing whitespace.
    5. Return an empty string if the result is shorter than 10 characters
       (avoids feeding near-empty strings to the model).

    Parameters
    ----------
    text:
        Raw text, possibly containing HTML markup.

    Returns
    -------
    str
        Cleaned text, or ``""`` if the cleaned result is too short.
    """
    if not text:
        return ""

    # 1. Remove HTML tags
    cleaned = _HTML_TAG_RE.sub(" ", text)

    # 2. Unicode NFC normalization
    cleaned = unicodedata.normalize("NFC", cleaned)

    # 3. Collapse whitespace
    cleaned = _WHITESPACE_RE.sub(" ", cleaned)

    # 4. Strip edges
    cleaned = cleaned.strip()

    # 5. Minimum length guard
    if len(cleaned) < _MIN_TEXT_LENGTH:
        return ""

    return cleaned


def detect_language(text: str) -> str:
    """Detect the primary language of *text*.

    Uses ``langdetect`` (which must be installed in the environment).

    Returns
    -------
    str
        ``"tl"`` for Filipino/Tagalog, ``"en"`` for English,
        ``"mixed"`` for any other detected language or on detection failure.
    """
    try:
        from langdetect import detect  # type: ignore[import-untyped]
        from langdetect.lang_detect_exception import (  # type: ignore[import-untyped]
            LangDetectException,
        )

        try:
            lang = detect(text)
            if lang == "tl":
                return "tl"
            if lang == "en":
                return "en"
            return "mixed"
        except LangDetectException:
            return "mixed"

    except ImportError:
        logger.warning(
            "langdetect is not installed; defaulting language to 'mixed'."
        )
        return "mixed"


def domain_to_credibility_score(
    domain: str,
    credibility_json_path: Path = _DEFAULT_CREDIBILITY_JSON,
) -> int:
    """Look up a domain's credibility tier score.

    Reads ``domain_credibility.json`` (cached after the first call) and maps
    the domain to a numeric score:

    +---------+-------+---------------------------+
    | Tier    | Score | Meaning                   |
    +=========+=======+===========================+
    | tier1   |   100 | High-credibility outlet   |
    +---------+-------+---------------------------+
    | tier2   |    50 | Mainstream / mid-tier     |
    +---------+-------+---------------------------+
    | tier3   |    25 | Low-credibility           |
    +---------+-------+---------------------------+
    | tier4   |     0 | Known misinformation site |
    +---------+-------+---------------------------+
    | unknown |    50 | Domain not found (default)|
    +---------+-------+---------------------------+

    Parameters
    ----------
    domain:
        Bare domain name, e.g. ``"rappler.com"``.
    credibility_json_path:
        Path to ``domain_credibility.json``.  Defaults to the file at the
        PhilVerify project root.

    Returns
    -------
    int
        Credibility score for the domain.
    """
    cache_key = str(credibility_json_path)

    if cache_key not in _credibility_cache:
        try:
            with credibility_json_path.open(encoding="utf-8") as fh:
                _credibility_cache[cache_key] = json.load(fh)
        except (FileNotFoundError, json.JSONDecodeError):
            logger.warning(
                "Could not load domain_credibility.json from %s; "
                "all domains will receive a default score of 50.",
                credibility_json_path,
            )
            _credibility_cache[cache_key] = {}

    data: dict = _credibility_cache[cache_key]

    tier_scores: dict[str, int] = {
        "tier1": 100,
        "tier2": 50,
        "tier3": 25,
        "tier4": 0,
    }

    for tier, score in tier_scores.items():
        tier_domains: list[str] = data.get(tier, [])
        if domain in tier_domains:
            return score

    # Domain not found → treat as tier2 / unknown
    return 50


def binary_to_three_class(
    raw_label: str,
    domain: str | None,
    credibility_json_path: Path = _DEFAULT_CREDIBILITY_JSON,
) -> int:
    """Map a raw dataset label string to PhilVerify's three-class schema.

    Label mapping rules
    -------------------
    * ``"fake"`` / ``"0"`` / ``"FALSE"`` / ``"pants-fire"`` / ``"false"``
      → **2** (Likely Fake)

    * ``"real"`` / ``"1"`` / ``"TRUE"`` / ``"true"``
      → credibility-aware decision:

      - domain score ≥ 75 → **0** (Credible)
      - domain score ≥ 40 → **0** (Credible, mainstream source)
      - domain score <  40 → **1** (Unverified, low-credibility domain)

    * ``"mostly-true"``
      → **0** (Credible)

    * ``"half-true"`` / ``"barely-true"``
      → **1** (Unverified)

    * *anything else*
      → **1** (Unverified, safe default)

    Parameters
    ----------
    raw_label:
        The label string exactly as it appears in the upstream dataset.
    domain:
        The publisher domain used for credibility lookup when the raw label
        indicates truth.  Pass ``None`` to skip domain lookup (score → 50).
    credibility_json_path:
        Path to ``domain_credibility.json``.

    Returns
    -------
    int
        An integer in ``{0, 1, 2}``.
    """
    _FAKE_LABELS: frozenset[str] = frozenset(
        {"fake", "0", "FALSE", "pants-fire", "false"}
    )
    _TRUE_LABELS: frozenset[str] = frozenset({"real", "1", "TRUE", "true"})

    if raw_label in _FAKE_LABELS:
        return 2

    if raw_label in _TRUE_LABELS:
        if domain:
            score = domain_to_credibility_score(domain, credibility_json_path)
        else:
            score = 50  # neutral default when no domain is available

        if score >= 75:
            return 0  # Credible
        if score >= 40:
            return 0  # Credible — mainstream source
        return 1  # Unverified — low-credibility domain

    if raw_label == "mostly-true":
        return 0

    if raw_label in {"half-true", "barely-true"}:
        return 1

    # Default: treat as Unverified
    return 1
