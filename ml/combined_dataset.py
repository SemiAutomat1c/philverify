"""
PhilVerify — Combined Dataset Loader (ml/combined_dataset.py)

Drop-in replacement for ml/dataset.py that loads from the preprocessed
combined.parquet file when available, with automatic fallback to the
hand-crafted samples from ml/dataset.py.

Parquet schema expected:
    text            (str)   — article/headline text
    label           (int)   — 0=Credible, 1=Unverified, 2=Likely Fake
    source          (str)   — dataset origin identifier
    language        (str)   — detected language code
    original_label  (str)   — label string before remapping
    confidence      (float) — remapping confidence score (drop < 0.5)

Usage in train_xlmr.py — change ONE import line:
    # Before:  from ml.dataset import get_split, class_weights, LABEL_NAMES, NUM_LABELS
    # After:   from ml.combined_dataset import get_split, class_weights, LABEL_NAMES, NUM_LABELS
"""

from __future__ import annotations

import logging
import random
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Ensure project root is on sys.path when run directly (python ml/combined_dataset.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

# ── Module logger ─────────────────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Label constants ───────────────────────────────────────────────────────────
LABEL_NAMES: dict[int, str] = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}
LABEL_IDS: dict[str, int] = {v: k for k, v in LABEL_NAMES.items()}
NUM_LABELS: int = 3

# ── Path resolution ───────────────────────────────────────────────────────────
_THIS_FILE = Path(__file__).resolve()
_ML_DIR = _THIS_FILE.parent                                    # ml/
_PARQUET_PATH: Path = _ML_DIR / "data" / "processed" / "combined.parquet"

# ── Module-level cache ────────────────────────────────────────────────────────
_DATASET_CACHE: Optional[list[Sample]] = None
_FALLBACK_MODE: bool = False  # set to True when parquet is unavailable


@dataclass
class Sample:
    """Single labelled text sample.

    Attributes:
        text:  Raw article or headline text.
        label: Integer class label — 0=Credible, 1=Unverified, 2=Likely Fake.
    """

    text: str
    label: int  # 0 | 1 | 2


# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_from_parquet(path: Path) -> list[Sample]:
    """Load, filter, deduplicate, and shuffle samples from *path*.

    Filtering rules applied in order:
    1. Drop rows with empty / null text.
    2. Drop rows whose label is not in {0, 1, 2}.
    3. Drop rows with confidence < 0.5.
    4. Drop exact-match duplicates (case-insensitive).
    5. Shuffle with random.seed(42) before returning.

    Args:
        path: Absolute path to the combined.parquet file.

    Returns:
        Cleaned, shuffled list of :class:`Sample` objects.
    """
    try:
        import pandas as pd
    except ImportError as exc:
        raise ImportError(
            "pandas is required to load the combined dataset. "
            "Install it with: pip install pandas pyarrow"
        ) from exc

    df = pd.read_parquet(path)
    original_len = len(df)

    # ── 1. Non-empty text ─────────────────────────────────────────────────────
    df = df[df["text"].notna() & (df["text"].str.strip() != "")]

    # ── 2. Valid labels ───────────────────────────────────────────────────────
    df = df[df["label"].isin({0, 1, 2})]

    # ── 3. Confidence threshold ───────────────────────────────────────────────
    if "confidence" in df.columns:
        df = df[df["confidence"] >= 0.5]

    # ── 4. Deduplicate (case-insensitive) ─────────────────────────────────────
    df = df.drop_duplicates(subset=["text"])
    lower_text = df["text"].str.lower()
    df = df[~lower_text.duplicated(keep="first")]

    kept = len(df)
    logger.info(
        "Loaded combined dataset: %d rows kept out of %d (dropped %d).",
        kept, original_len, original_len - kept,
    )

    # ── Class distribution log ────────────────────────────────────────────────
    counts = Counter(int(v) for v in df["label"])
    for label_id, name in LABEL_NAMES.items():
        logger.info("  %s (%d): %d samples", name, label_id, counts.get(label_id, 0))

    # ── 5. Shuffle ────────────────────────────────────────────────────────────
    samples = [Sample(text=str(row["text"]), label=int(row["label"])) for row in df.to_dict("records")]
    random.seed(42)
    random.shuffle(samples)
    return samples


def _load_fallback() -> list[Sample]:
    """Return the hand-crafted samples from ml/dataset.py as fallback.

    Logs a WARNING so the caller is clearly notified of degraded data quality.
    """
    global _FALLBACK_MODE
    _FALLBACK_MODE = True
    logger.warning(
        "Combined dataset not found at %s. "
        "Falling back to hand-crafted samples. "
        "Run: python ml/dataset_builder.py",
        _PARQUET_PATH,
    )
    # Support both `python -m ml.combined_dataset` (package context) and
    # `python ml/combined_dataset.py` (script context) by adjusting sys.path
    # when the ml package cannot be resolved directly.
    try:
        from ml.dataset import DATASET  # package import (normal usage)
    except ModuleNotFoundError:
        import sys
        _project_root = str(_ML_DIR.parent)
        if _project_root not in sys.path:
            sys.path.insert(0, _project_root)
        from ml.dataset import DATASET  # retry after path fix
    return list(DATASET)


# ── Public API ─────────────────────────────────────────────────────────────────

def get_dataset() -> list[Sample]:
    """Return the full combined dataset (cached after first call).

    Loads from *ml/data/processed/combined.parquet* when available; otherwise
    falls back to the hand-crafted samples from :mod:`ml.dataset`.

    Returns:
        List of :class:`Sample` objects, shuffled with seed 42.
    """
    global _DATASET_CACHE, _FALLBACK_MODE

    if _DATASET_CACHE is not None:
        return _DATASET_CACHE

    if _PARQUET_PATH.is_file():
        _FALLBACK_MODE = False
        _DATASET_CACHE = _load_from_parquet(_PARQUET_PATH)
    else:
        _FALLBACK_MODE = True
        _DATASET_CACHE = _load_fallback()

    return _DATASET_CACHE


def get_split(
    train_ratio: float = 0.8,
    seed: int = 42,
) -> tuple[list[Sample], list[Sample]]:
    """Split the dataset into stratified train / validation sets.

    Stratification is performed per label to preserve class balance even with
    skewed distributions.  Both partitions are shuffled independently.

    Args:
        train_ratio: Fraction of each class to place in the training set.
                     Must be in (0, 1).  Defaults to 0.8.
        seed:        Random seed for reproducibility.  Defaults to 42.

    Returns:
        A ``(train, val)`` tuple of :class:`Sample` lists.
    """
    dataset = get_dataset()
    rng = random.Random(seed)

    by_label: dict[int, list[Sample]] = {0: [], 1: [], 2: []}
    for s in dataset:
        by_label[s.label].append(s)

    train: list[Sample] = []
    val: list[Sample] = []
    for label_samples in by_label.values():
        shuffled = label_samples[:]
        rng.shuffle(shuffled)
        split_idx = max(1, int(len(shuffled) * train_ratio))
        train.extend(shuffled[:split_idx])
        val.extend(shuffled[split_idx:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def class_weights(samples: list[Sample]) -> list[float]:
    """Compute inverse-frequency class weights for imbalanced training.

    Uses the standard formula:
        weight_i = total / (NUM_LABELS * count_i)

    A floor of 1 is applied to each per-class count to avoid division by zero
    if a class happens to be absent from *samples*.

    Args:
        samples: List of :class:`Sample` objects (typically the training split).

    Returns:
        List of ``NUM_LABELS`` floats, one per class in ascending label order.
    """
    counts = Counter(s.label for s in samples)
    total = len(samples)
    return [total / (NUM_LABELS * max(counts[i], 1)) for i in range(NUM_LABELS)]


def dataset_info() -> dict:
    """Return a summary dictionary describing the currently loaded dataset.

    Forces a load if the cache is empty.  Fields:

    * ``total``         — total sample count
    * ``per_class``     — mapping of label name → count
    * ``per_source``    — mapping of source → count (only when parquet loaded)
    * ``fallback_mode`` — True when using hand-crafted samples
    * ``parquet_path``  — resolved path string of the expected parquet file

    Returns:
        Dict with the keys listed above.
    """
    samples = get_dataset()
    counts = Counter(s.label for s in samples)

    per_class = {LABEL_NAMES[i]: counts.get(i, 0) for i in range(NUM_LABELS)}

    per_source: dict[str, int] = {}
    if not _FALLBACK_MODE and _PARQUET_PATH.is_file():
        try:
            import pandas as pd
            df = pd.read_parquet(_PARQUET_PATH, columns=["source"])
            per_source = dict(Counter(str(v) for v in df["source"]))
        except Exception:
            per_source = {}

    return {
        "total": len(samples),
        "per_class": per_class,
        "per_source": per_source,
        "fallback_mode": _FALLBACK_MODE,
        "parquet_path": str(_PARQUET_PATH),
    }


# ── CLI entry-point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    info = dataset_info()

    print("\n" + "=" * 56)
    print("  PhilVerify — Combined Dataset Info")
    print("=" * 56)
    print(f"  Parquet path : {info['parquet_path']}")
    print(f"  Fallback mode: {info['fallback_mode']}")
    print(f"  Total samples: {info['total']}")
    print()
    print("  Class distribution:")
    for name, count in info["per_class"].items():
        pct = count / info["total"] * 100 if info["total"] else 0.0
        print(f"    {name:<14} {count:>5}  ({pct:5.1f}%)")

    if info["per_source"]:
        print()
        print("  Source distribution:")
        for src, cnt in sorted(info["per_source"].items(), key=lambda x: -x[1]):
            print(f"    {src:<30} {cnt:>5}")

    print("=" * 56)
    print()

    # Also print train/val split sizes
    train, val = get_split()
    tw = class_weights(train)
    print(f"  Train samples : {len(train)}")
    print(f"  Val   samples : {len(val)}")
    print(f"  Class weights : {[round(w, 4) for w in tw]}")
    print()
