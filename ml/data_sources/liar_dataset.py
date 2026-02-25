"""
ml/data_sources/liar_dataset.py
================================
PhilVerify adapter for the LIAR dataset (HuggingFace: "liar").

The LIAR dataset contains ~12,800 short political statements labelled with
one of six fine-grained veracity categories.  This adapter collapses those
six categories into PhilVerify's three-class schema and caps the output at
``max_samples`` English examples to serve as a balanced English supplement
to the Filipino training corpus.

Label mapping
-------------
  "true"        → 0  Credible     (confidence 1.00)
  "mostly-true" → 0  Credible     (confidence 0.90)
  "half-true"   → 1  Unverified   (confidence 0.70)
  "barely-true" → 1  Unverified   (confidence 0.60)
  "false"       → 2  Likely Fake  (confidence 0.95)
  "pants-fire"  → 2  Likely Fake  (confidence 1.00)

Usage
-----
    from ml.data_sources.liar_dataset import LIARDataset

    ds = LIARDataset(max_samples=3000)
    samples = ds.fetch()

References
----------
    Wang, W.Y. (2017). "Liar, Liar Pants on Fire":
    A New Benchmark Dataset for Fake News Detection.
    https://aclanthology.org/P17-2067/

    HuggingFace: https://huggingface.co/datasets/liar
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Optional

from .base import DataSource, NormalizedSample, clean_text

logger = logging.getLogger(__name__)

# Raw download URL – avoids the unsupported loading-script mechanism
_LIAR_ZIP_URL: str = "https://www.cs.ucsb.edu/~william/data/liar_dataset.zip"
_RAW_DIR: Path = Path(__file__).parent.parent / "data" / "raw"

# LIAR TSV column indices (no header row)
_COL_LABEL = 1      # e.g. "true", "false", "pants-fire", …
_COL_STATEMENT = 2  # the short political statement (main text)

# ---------------------------------------------------------------------------
# Label mapping tables
# ---------------------------------------------------------------------------

#: Maps each LIAR veracity label to a PhilVerify integer class.
_LABEL_TO_CLASS: dict[str, int] = {
    "true": 0,
    "mostly-true": 0,
    "half-true": 1,
    "barely-true": 1,
    "false": 2,
    "pants-fire": 2,
}

#: Annotation confidence assigned to each raw LIAR label.
_LABEL_CONFIDENCE: dict[str, float] = {
    "true": 1.00,
    "mostly-true": 0.90,
    "half-true": 0.70,
    "barely-true": 0.60,
    "false": 0.95,
    "pants-fire": 1.00,
}

# Maximum subject prefix length (chars) before we skip enrichment.
_MAX_SUBJECT_PREFIX_LEN = 60


# ---------------------------------------------------------------------------
# Raw-download helper
# ---------------------------------------------------------------------------

def _load_liar_from_zip() -> dict[str, list[dict]]:
    """Download ``liar_dataset.zip`` from UCSB and parse TSV splits.

    The zip contains ``train.tsv``, ``test.tsv``, and ``valid.tsv``.  Each TSV
    has no header row.  The columns we use are:

    * Index 1 → label (e.g. ``"true"``, ``"false"``, ``"pants-fire"``)
    * Index 2 → statement (the short political claim – the main text)

    Results are cached in ``ml/data/raw/liar/`` to avoid repeated downloads.

    Returns:
        ``dict`` mapping split names to lists of ``{"label": str, "statement": str}``.

    Raises:
        RuntimeError: If download or parsing fails.
    """
    import csv
    import io
    import zipfile

    import requests

    cache_dir = _RAW_DIR / "liar"
    cache_dir.mkdir(parents=True, exist_ok=True)

    split_files = {
        "train": "train.tsv",
        "test": "test.tsv",
        "validation": "valid.tsv",
    }

    # Download only if any split is missing
    missing = [s for s, fname in split_files.items() if not (cache_dir / fname).exists()]
    if missing:
        logger.info("[liar] Downloading liar_dataset.zip from UCSB …")
        try:
            resp = requests.get(_LIAR_ZIP_URL, timeout=120)
            resp.raise_for_status()
            raw_bytes = resp.content
        except Exception as exc:
            raise RuntimeError(f"[liar] Failed to download liar_dataset.zip: {exc}") from exc
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            for tsv_name in split_files.values():
                # The zip may contain the files in a subdirectory
                candidates = [tsv_name, f"liar_dataset/{tsv_name}"]
                for candidate in candidates:
                    if candidate in zf.namelist():
                        (cache_dir / tsv_name).write_bytes(zf.read(candidate))
                        break
                else:
                    logger.warning("[liar] '%s' not found in zip (names: %s)", tsv_name, zf.namelist()[:10])
        logger.info("[liar] Cached TSV files to %s", cache_dir)
    else:
        logger.info("[liar] Using cached TSV files from %s", cache_dir)

    result: dict[str, list[dict]] = {}
    for split_name, fname in split_files.items():
        path = cache_dir / fname
        if not path.exists():
            logger.warning("[liar] Split file missing: %s — skipping.", path)
            continue
        rows: list[dict] = []
        with open(path, encoding="utf-8") as f:
            reader = csv.reader(f, delimiter="\t", quoting=csv.QUOTE_NONE)
            for row in reader:
                if len(row) > max(_COL_LABEL, _COL_STATEMENT):
                    rows.append({
                        "label": row[_COL_LABEL].strip(),
                        "statement": row[_COL_STATEMENT].strip(),
                    })
        result[split_name] = rows
        logger.info("[liar] Parsed %d rows from %s", len(rows), fname)
    return result


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class LIARDataset(DataSource):
    """PhilVerify adapter for the HuggingFace ``liar`` dataset.

    Parameters
    ----------
    max_samples:
        Hard cap on the total number of samples returned.  When the raw
        dataset exceeds this limit the output is drawn by stratified random
        sampling (seed 42) so that class proportions are approximately
        preserved.  Defaults to ``3000``.

    Examples
    --------
    >>> ds = LIARDataset(max_samples=1000)
    >>> samples = ds.fetch()
    >>> len(samples) <= 1000
    True
    """

    def __init__(self, max_samples: int = 3000) -> None:
        self.max_samples = max_samples

    # -- DataSource interface ------------------------------------------------

    @property
    def source_name(self) -> str:
        """Dataset identifier."""
        return "liar"

    def fetch(self) -> list[NormalizedSample]:
        """Load all LIAR splits, normalise, map labels, and cap output.

        Returns
        -------
        list[NormalizedSample]
            Normalised English samples with three-class labels.
        """
        logger.info("[liar] Downloading / loading LIAR dataset …")

        try:
            split_data = _load_liar_from_zip()
        except Exception as exc:
            raise RuntimeError(f"[liar] Could not load LIAR dataset: {exc}") from exc

        if not split_data:
            raise RuntimeError(
                "Could not load the LIAR dataset from direct download. "
                "Ensure you have an active internet connection and"
                f" {_LIAR_ZIP_URL} is accessible."
            )

        # Collect samples from every available split
        raw: list[NormalizedSample] = []
        for split_name, rows in split_data.items():
            n_rows = len(rows)
            logger.info("[liar] Processing split '%s' (%d rows) …", split_name, n_rows)
            for row in rows:
                sample = self._process_row(row)
                if sample is not None:
                    raw.append(sample)

        # Cap with stratified random sampling
        samples = self._stratified_cap(raw, self.max_samples)

        self.log_class_distribution(samples)
        return samples

    # -- Private helpers -----------------------------------------------------

    def _process_row(self, row: dict) -> Optional[NormalizedSample]:
        """Convert a single LIAR row dict to a :class:`NormalizedSample`.

        Returns ``None`` when the row should be discarded (empty text,
        unknown label, etc.).
        """
        # ---- text ----------------------------------------------------------
        statement: str = row.get("statement") or ""
        text = clean_text(statement)

        # Skip too-short samples (clean_text already returns "" if < 10 chars)
        if not text:
            return None

        # Optional enrichment: prepend the subject for topical context.
        # We keep it brief to avoid drowning out the claim itself.
        subject: str = row.get("subject") or ""
        if subject and len(subject) <= _MAX_SUBJECT_PREFIX_LEN:
            subject_clean = clean_text(subject)
            if subject_clean:
                text = f"[{subject_clean}] {text}"

        # ---- label ---------------------------------------------------------
        raw_label: str = row.get("label") or ""

        # HuggingFace may store the label as an integer index
        if isinstance(raw_label, int):
            _IDX_TO_STR = [
                "false",
                "half-true",
                "mostly-true",
                "true",
                "barely-true",
                "pants-fire",
            ]
            raw_label = _IDX_TO_STR[raw_label] if 0 <= raw_label < len(_IDX_TO_STR) else ""

        if raw_label not in _LABEL_TO_CLASS:
            logger.debug("[liar] Unknown label %r — skipping row.", raw_label)
            return None

        mapped_label: int = _LABEL_TO_CLASS[raw_label]
        confidence: float = _LABEL_CONFIDENCE[raw_label]

        return NormalizedSample(
            text=text,
            label=mapped_label,
            source=self.source_name,
            language="en",
            original_label=raw_label,
            confidence=confidence,
        )

    @staticmethod
    def _stratified_cap(
        samples: list[NormalizedSample],
        max_total: int,
    ) -> list[NormalizedSample]:
        """Return at most *max_total* samples, preserving class proportions.

        If the dataset is already within the cap the full list is returned
        (shuffled deterministically).

        Parameters
        ----------
        samples:
            Full unnormalised sample list.
        max_total:
            Maximum number of samples to return.

        Returns
        -------
        list[NormalizedSample]
            A stratified random subsample.
        """
        if len(samples) <= max_total:
            rng = random.Random(42)
            rng.shuffle(samples)
            return samples

        # Group by label
        buckets: dict[int, list[NormalizedSample]] = {0: [], 1: [], 2: []}
        for s in samples:
            buckets[s.label].append(s)

        total = len(samples)
        result: list[NormalizedSample] = []
        rng = random.Random(42)

        for lbl, bucket in buckets.items():
            rng.shuffle(bucket)
            # Proportional quota — at least 1 if the bucket is non-empty
            quota = max(1, round(max_total * len(bucket) / total)) if bucket else 0
            result.extend(bucket[:quota])

        # Trim or top-up to hit max_total exactly via global shuffle
        rng.shuffle(result)
        # If proportional rounding pushed us slightly over, trim
        return result[:max_total]

    # Delegate log_class_distribution to base class helper
    def log_class_distribution(self, samples: list[NormalizedSample]) -> None:
        """Log class frequencies for the fetched sample list."""
        label_names = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}
        counts: dict[int, int] = {0: 0, 1: 0, 2: 0}
        for s in samples:
            counts[s.label] = counts.get(s.label, 0) + 1
        total = len(samples)
        print(f"[{self.source_name}] Class distribution ({total} total):")
        for lbl, name in label_names.items():
            n = counts.get(lbl, 0)
            pct = 100 * n / total if total else 0.0
            print(f"[{self.source_name}]   {lbl} {name:<15} {n:>5}  ({pct:.1f}%)")


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        stream=sys.stdout,
    )

    print("=" * 60)
    print("LIARDataset — smoke test")
    print("=" * 60)

    ds = LIARDataset(max_samples=300)
    samples = ds.fetch()

    print(f"\nReturned {len(samples)} samples.")
    print("\nFirst 5 samples:")
    for i, s in enumerate(samples[:5]):
        print(
            f"  [{i}] label={s.label} conf={s.confidence:.2f} "
            f"orig={s.original_label!r:>12}  text={s.text[:80]!r}"
        )
