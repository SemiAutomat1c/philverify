"""
ml/data_sources/hf_ph_fake_news.py
PhilVerify – HuggingFace data source adapter for SEACrowd/ph_fake_news_corpus.

Dataset:  https://huggingface.co/datasets/SEACrowd/ph_fake_news_corpus
Config:   ph_fake_news_corpus_source  (SEACrowd schema source view)
Splits:   train / test / validation   (availability may vary)
Columns:  schema is resolved at runtime; common candidates tried in order.

3-class mapping (delegated to binary_to_three_class):
  "real" / 0  → PhilVerify 0 (Credible)
  "fake" / 1  → PhilVerify 2 (Likely Fake)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tqdm import tqdm

from .base import DataSource, NormalizedSample, binary_to_three_class, clean_text, detect_language

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATASET_ID: str = "SEACrowd/ph_fake_news_corpus"
_CONFIG_NAME: str = "ph_fake_news_corpus_source"
_SPLITS: tuple[str, ...] = ("train", "test", "validation")
_RAW_DIR: Path = Path(__file__).parent.parent / "data" / "raw"
_CREDIBILITY_PATH: Path = Path(__file__).parent.parent.parent / "domain_credibility.json"

# Candidate column names tried in priority order
_TEXT_COLUMNS: list[str] = ["text", "title", "article", "content"]
_LABEL_COLUMNS: list[str] = ["label", "Label", "class"]

_MAX_RETRIES: int = 3
_BACKOFF_BASE: float = 2.0  # seconds

# Strings that map to "real/credible"
_REAL_VALUES: frozenset[str] = frozenset({"0", "real", "credible", "true", "legit"})
# Strings that map to "fake"
_FAKE_VALUES: frozenset[str] = frozenset({"1", "fake", "false", "misinformation", "hoax"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_with_retry(
    dataset_id: str,
    config_name: str | None = None,
) -> "datasets.DatasetDict":  # noqa: F821
    """Load a HuggingFace dataset, falling back to direct parquet download.

    Strategy:
    1. Try ``load_dataset(dataset_id)`` (no trust_remote_code).
    2. On loading-script error, fall back to direct parquet via huggingface_hub.

    Args:
        dataset_id:  HuggingFace dataset identifier string.
        config_name: Optional configuration/subset name (tried then ignored
                     on failure so the adapter is resilient to schema changes).

    Returns:
        A ``datasets.DatasetDict`` containing at least one split.

    Raises:
        RuntimeError: If all strategies fail.
    """
    import datasets  # local import – optional dependency

    configs_to_try: list[str | None] = [config_name, None] if config_name else [None]
    last_exc: Exception | None = None

    # ── Attempt 1: standard load ───────────────────────────────────────────
    for cfg in configs_to_try:
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                kwargs: dict[str, Any] = {}
                if cfg is not None:
                    kwargs["name"] = cfg
                cfg_label = cfg if cfg else "<default>"
                logger.info("Loading '%s' config=%s (attempt %d/%d)…",
                            dataset_id, cfg_label, attempt, _MAX_RETRIES)
                ds = datasets.load_dataset(dataset_id, **kwargs)
                logger.info("Dataset '%s' config=%s loaded successfully.", dataset_id, cfg_label)
                return ds
            except datasets.exceptions.DatasetNotFoundError:
                logger.error("Dataset '%s' not found on the HuggingFace Hub.", dataset_id)
                raise
            except ValueError as exc:
                logger.warning("Config '%s' rejected for '%s': %s.", cfg, dataset_id, exc)
                last_exc = exc
                break
            except Exception as exc:
                if "scripts are no longer supported" in str(exc) or "loading script" in str(exc).lower():
                    logger.warning("'%s' uses a loading script (unsupported). Using parquet fallback.",
                                   dataset_id)
                    last_exc = exc
                    break
                last_exc = exc
                wait = _BACKOFF_BASE ** attempt
                logger.warning("Attempt %d/%d failed (config=%s): %s. Retrying in %.1fs…",
                               attempt, _MAX_RETRIES, cfg, exc, wait)
                if attempt < _MAX_RETRIES:
                    time.sleep(wait)
                else:
                    break
        # If we broke for loading-script reason, don't try other configs.
        if last_exc and ("scripts are no longer supported" in str(last_exc)
                         or "loading script" in str(last_exc).lower()):
            break

    # ── Attempt 2: direct parquet download via huggingface_hub ────────────
    logger.info("Trying direct parquet download for '%s' …", dataset_id)
    try:
        import pandas as pd
        from huggingface_hub import HfFileSystem
        fs = HfFileSystem()
        # Recursively search for parquet files anywhere in the dataset repo
        parquet_files = fs.glob(f"datasets/{dataset_id}/**/*.parquet")
        if not parquet_files:
            raise RuntimeError(f"No parquet files found in '{dataset_id}'.")
        logger.info("Found %d parquet file(s) in '%s'.", len(parquet_files), dataset_id)
        splits: dict[str, "datasets.Dataset"] = {}
        for pf in parquet_files:
            stem = str(pf).split("/")[-1].replace(".parquet", "")
            split_name = "train"
            for s in ("train", "test", "validation"):
                if s in stem:
                    split_name = s
                    break
            df = pd.read_parquet(fs.open(pf))
            ds_split = datasets.Dataset.from_pandas(df)
            splits[split_name] = (
                datasets.concatenate_datasets([splits[split_name], ds_split])
                if split_name in splits else ds_split
            )
        return datasets.DatasetDict(splits)
    except Exception as exc:
        raise RuntimeError(
            f"All load strategies failed for '{dataset_id}': {exc}"
        ) from exc


def _resolve_text_column(columns: list[str]) -> str | None:
    """Return the first candidate text column present in *columns*, or ``None``."""
    for candidate in _TEXT_COLUMNS:
        if candidate in columns:
            logger.info("Using text column: '%s'", candidate)
            return candidate
    return None


def _resolve_label_column(columns: list[str]) -> str | None:
    """Return the first candidate label column present in *columns*, or ``None``."""
    for candidate in _LABEL_COLUMNS:
        if candidate in columns:
            logger.info("Using label column: '%s'", candidate)
            return candidate
    return None


def _normalise_label(raw: Any) -> int | None:
    """Convert a raw label value (int or str) to a PhilVerify 3-class integer.

    Returns:
        0  (Credible),  2 (Likely Fake), or ``None`` if the value is unknown.
    """
    key = str(raw).strip().lower()
    if key in _REAL_VALUES:
        return binary_to_three_class("real", None, str(_CREDIBILITY_PATH))
    if key in _FAKE_VALUES:
        return binary_to_three_class("fake", None, str(_CREDIBILITY_PATH))
    return None


# ---------------------------------------------------------------------------
# DataSource implementation
# ---------------------------------------------------------------------------

class PHFakeNewsSEACrowd(DataSource):
    """HuggingFace data-source adapter for ``SEACrowd/ph_fake_news_corpus``.

    This adapter is intentionally defensive about schema uncertainty:

    * It tries multiple column names for both text and label fields.
    * It logs the exact columns it finds so deviations from expectation are
      immediately visible in the application log.
    * Unknown label values are skipped with a debug-level log entry rather
      than raising an exception, keeping the pipeline non-fatal.
    """

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        """Canonical HuggingFace dataset identifier."""
        return _DATASET_ID

    def fetch(self) -> list[NormalizedSample]:
        """Fetch and normalise all available splits of the SEACrowd PH corpus.

        Returns:
            A list of :class:`~ml.data_sources.base.NormalizedSample` objects
            representing every retained article across all discovered splits.
        """
        _RAW_DIR.mkdir(parents=True, exist_ok=True)

        try:
            dataset_dict = _load_with_retry(_DATASET_ID, _CONFIG_NAME)
        except Exception as exc:
            logger.error("Could not load dataset '%s': %s", _DATASET_ID, exc)
            return []

        samples: list[NormalizedSample] = []

        for split in _SPLITS:
            if split not in dataset_dict:
                logger.debug("Split '%s' not present in '%s' – skipping.", split, _DATASET_ID)
                continue

            split_data = dataset_dict[split]
            columns: list[str] = split_data.column_names

            logger.info(
                "Split '%s' columns found: %s", split, columns
            )

            text_col = _resolve_text_column(columns)
            label_col = _resolve_label_column(columns)

            if text_col is None:
                logger.error(
                    "No recognised text column in split '%s' (columns=%s). "
                    "Tried: %s. Skipping split.",
                    split, columns, _TEXT_COLUMNS,
                )
                continue

            if label_col is None:
                logger.error(
                    "No recognised label column in split '%s' (columns=%s). "
                    "Tried: %s. Skipping split.",
                    split, columns, _LABEL_COLUMNS,
                )
                continue

            split_samples: list[NormalizedSample] = []
            skipped_label = 0
            skipped_empty = 0

            logger.info("Processing split '%s' (%d rows)…", split, len(split_data))

            for row in tqdm(split_data, desc=f"{_DATASET_ID}/{split}", unit="row", leave=False):
                raw_text: str = row.get(text_col, "") or ""
                text = clean_text(raw_text)
                if not text:
                    skipped_empty += 1
                    continue

                raw_label: Any = row.get(label_col)
                normalized_label = _normalise_label(raw_label)

                if normalized_label is None:
                    logger.debug(
                        "Skipping row with unrecognised label %r (col=%r).", raw_label, label_col
                    )
                    skipped_label += 1
                    continue

                original_label = str(raw_label).strip().lower()
                language = detect_language(text)

                split_samples.append(
                    NormalizedSample(
                        text=text,
                        label=normalized_label,
                        source=self.source_name,
                        language=language,
                        original_label=original_label,
                        confidence=1.0,
                    )
                )

            logger.info(
                "Split '%s': %d/%d rows retained  (skipped empty=%d, bad_label=%d).",
                split,
                len(split_samples),
                len(split_data),
                skipped_empty,
                skipped_label,
            )
            samples.extend(split_samples)

        logger.info(
            "PHFakeNewsSEACrowd.fetch() complete – %d total samples from '%s'.",
            len(samples),
            _DATASET_ID,
        )
        return samples


# ---------------------------------------------------------------------------
# Stand-alone smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    source = PHFakeNewsSEACrowd()
    results = source.fetch()

    print(f"\nTotal samples loaded: {len(results)}")
    print("First 3 samples:")
    for i, s in enumerate(results[:3], 1):
        preview = s.text[:120].replace("\n", " ")
        print(
            f"  [{i}] label={s.label} ({s.original_label!r}) "
            f"lang={s.language!r} | {preview!r}"
        )
