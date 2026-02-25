"""
ml/data_sources/isot_dataset.py
================================
PhilVerify adapter for the ISOT Fake News Dataset.

The ISOT dataset consists of two CSV files (``True.csv`` and ``Fake.csv``)
that must be placed locally by the user.  ``True.csv`` contains Reuters
articles labelled as real; ``Fake.csv`` contains articles flagged as
fabricated.  This adapter maps those two classes to PhilVerify's three-class
schema (class 1 / Unverified is intentionally absent from this binary source).

Label mapping
-------------
  True.csv  → 0  Credible     (confidence 1.00)
  Fake.csv  → 2  Likely Fake  (confidence 1.00)

Usage
-----
    from ml.data_sources.isot_dataset import ISOTDataset
    from pathlib import Path

    ds = ISOTDataset()                     # default data_dir
    # ds = ISOTDataset(data_dir=Path("/custom/path"))
    samples = ds.fetch()

Download
--------
    https://www.kaggle.com/datasets/clmentbisaillon/fake-and-real-news-dataset

    Place True.csv and Fake.csv in:
        ml/data/raw/isot/

References
----------
    Ahmed H., Traore I., Saad S. (2018).
    Detecting opinion spam and fake news using text n-gram features.
    Digital Investigation, 27, 244–258.
"""

from __future__ import annotations

import logging
import random
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from .base import DataSource, NormalizedSample, clean_text

try:
    import pandas as pd  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    pd = None  # type: ignore[assignment]  # lazy; guarded in _load_csv

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Expected CSV filenames inside data_dir.
_TRUE_CSV = "True.csv"
_FAKE_CSV = "Fake.csv"

#: Kaggle download URL shown in the warning when files are absent.
_KAGGLE_URL = (
    "https://www.kaggle.com/datasets/clmentbisaillon/fake-and-real-news-dataset"
)

#: Minimum cleaned-text length (chars) below which a sample is discarded.
_MIN_TEXT_LEN = 10


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class ISOTDataset(DataSource):
    """PhilVerify adapter for the local ISOT Fake News Dataset.

    Parameters
    ----------
    max_samples:
        Total number of samples to return.  The cap is split evenly between
        ``True.csv`` (class 0) and ``Fake.csv`` (class 2): each contributes
        at most ``max_samples // 2`` rows.  Defaults to ``2000``.
    data_dir:
        Directory that contains ``True.csv`` and ``Fake.csv``.  Defaults to
        ``<project_root>/ml/data/raw/isot/``.

    Examples
    --------
    >>> ds = ISOTDataset(max_samples=200)
    >>> samples = ds.fetch()          # returns [] if CSVs not found
    """

    def __init__(
        self,
        max_samples: int = 2000,
        data_dir: Optional[Path] = None,
    ) -> None:
        self.max_samples = max_samples
        self.data_dir: Path = (
            data_dir
            if data_dir is not None
            else Path(__file__).parent.parent / "data" / "raw" / "isot"
        )

    # -- DataSource interface ------------------------------------------------

    @property
    def source_name(self) -> str:
        """Dataset identifier."""
        return "isot"

    def fetch(self) -> list[NormalizedSample]:
        """Load ISOT CSVs, normalise text, and return capped samples.

        When the CSV files cannot be found this method logs an informative
        warning with download instructions and returns an empty list rather
        than raising an exception — consistent with the PhilVerify multi-source
        pipeline convention.

        Returns
        -------
        list[NormalizedSample]
            Normalised English samples labelled 0 (Credible) or 2 (Likely Fake).
        """
        true_path = self.data_dir / _TRUE_CSV
        fake_path = self.data_dir / _FAKE_CSV

        # ---- Existence check — try kagglehub auto-download if needed --------
        missing = [p for p in (true_path, fake_path) if not p.is_file()]
        if missing:
            logger.info("[isot] CSV files not found locally — attempting kagglehub auto-download …")
            self._auto_download(self.data_dir)
            missing = [p for p in (true_path, fake_path) if not p.is_file()]
            if missing:
                self._warn_missing(missing)
                return []

        # ---- Load, clean, cap ----------------------------------------------
        per_class_cap = max(1, self.max_samples // 2)

        logger.info("[isot] Loading %s …", true_path)
        print(f"[isot] Loading {true_path} …")
        true_samples = self._load_csv(
            path=true_path,
            label=0,
            original_label="real",
            confidence=1.00,
            cap=per_class_cap,
        )

        logger.info("[isot] Loading %s …", fake_path)
        print(f"[isot] Loading {fake_path} …")
        fake_samples = self._load_csv(
            path=fake_path,
            label=2,
            original_label="fake",
            confidence=1.00,
            cap=per_class_cap,
        )

        print(f"[isot]   True.csv → {len(true_samples)} samples (class 0 Credible)")
        print(f"[isot]   Fake.csv → {len(fake_samples)} samples (class 2 Likely Fake)")
        logger.info(
            "[isot] Loaded %d credible + %d fake = %d total.",
            len(true_samples),
            len(fake_samples),
            len(true_samples) + len(fake_samples),
        )

        samples = true_samples + fake_samples

        # Final shuffle for good measure (deterministic)
        rng = random.Random(42)
        rng.shuffle(samples)

        self.log_class_distribution(samples)
        return samples

    # -- Private helpers -----------------------------------------------------

    def _load_csv(
        self,
        path: Path,
        label: int,
        original_label: str,
        confidence: float,
        cap: int,
    ) -> list[NormalizedSample]:
        """Read one ISOT CSV and return up to *cap* NormalizedSamples.

        The text fed to the model is the concatenation of the ``title`` and
        ``text`` columns (``"<title> <text>"``).  Leading/trailing whitespace
        from each column is stripped before joining, and the combined string is
        then passed through :func:`clean_text`.

        Parameters
        ----------
        path:
            Absolute path to the CSV file.
        label:
            Integer PhilVerify class for all rows in this file.
        original_label:
            Raw label string preserved in :class:`NormalizedSample`.
        confidence:
            Annotation confidence (1.0 for both ISOT splits).
        cap:
            Maximum number of samples to return from this file.

        Returns
        -------
        list[NormalizedSample]
        """
        try:
            import pandas as _pd  # noqa: PLC0415
            df = _pd.read_csv(path, dtype=str)
        except ImportError as exc:
            raise ImportError(
                "The 'pandas' package is required to load ISOT. "
                "Install it with: pip install pandas"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.error("[isot] Failed to read %s: %s", path, exc)
            print(f"[isot] ERROR: could not read {path}: {exc}")
            return []

        # ---- Validate expected columns -------------------------------------
        for col in ("title", "text"):
            if col not in df.columns:
                logger.warning(
                    "[isot] Expected column '%s' not found in %s. "
                    "Available columns: %s",
                    col,
                    path.name,
                    list(df.columns),
                )
                # Fall back to whatever text-like columns are available
                df[col] = ""

        # ---- Shuffle within class before capping ---------------------------
        rng = random.Random(42)
        indices = list(range(len(df)))
        rng.shuffle(indices)
        df = df.iloc[indices].reset_index(drop=True)

        # ---- Build samples -------------------------------------------------
        samples: list[NormalizedSample] = []

        for _, row in tqdm(
            df.head(cap * 3).iterrows(),  # oversample then trim after filtering
            total=min(cap * 3, len(df)),
            desc=f"[isot] {path.name}",
            leave=False,
        ):
            sample = self._process_row(
                row=row,
                label=label,
                original_label=original_label,
                confidence=confidence,
            )
            if sample is not None:
                samples.append(sample)
                if len(samples) >= cap:
                    break

        return samples

    @staticmethod
    def _process_row(
        row: "pd.Series",
        label: int,
        original_label: str,
        confidence: float,
    ) -> Optional[NormalizedSample]:
        """Convert a single DataFrame row to a :class:`NormalizedSample`.

        Combines the ``title`` and ``text`` columns, cleans the result,
        and returns ``None`` if the cleaned text is empty (i.e. too short).

        Parameters
        ----------
        row:
            A pandas Series representing one CSV row.
        label:
            Integer PhilVerify class.
        original_label:
            Raw label string (``"real"`` or ``"fake"``).
        confidence:
            Annotation confidence.

        Returns
        -------
        NormalizedSample | None
        """
        title: str = str(row.get("title") or "").strip()
        body: str = str(row.get("text") or "").strip()

        # Combine title + body; a space separation is sufficient
        raw_text = f"{title} {body}" if title and body else (title or body)
        text = clean_text(raw_text)

        if not text or len(text) < _MIN_TEXT_LEN:
            return None

        return NormalizedSample(
            text=text,
            label=label,
            source="isot",
            language="en",
            original_label=original_label,
            confidence=confidence,
        )

    @staticmethod
    def _auto_download(data_dir: Path) -> None:
        """Attempt to download ISOT CSVs via ``kagglehub``.

        Calls ``kagglehub.dataset_download("csmalarkodi/isot-fake-news-dataset")``
        and copies ``True.csv`` / ``Fake.csv`` into *data_dir*.
        Silently skips on any error so the caller can fall back to the manual
        download message.

        Parameters
        ----------
        data_dir:
            Destination directory where the CSVs should end up.
        """
        import shutil
        try:
            import kagglehub  # type: ignore[import-untyped]
        except ImportError:
            logger.warning(
                "[isot] 'kagglehub' not installed — run: pip install kagglehub. "
                "Falling back to manual download."
            )
            return

        try:
            logger.info("[isot] kagglehub: downloading csmalarkodi/isot-fake-news-dataset …")
            dl_path = Path(kagglehub.dataset_download("csmalarkodi/isot-fake-news-dataset"))
            logger.info("[isot] kagglehub download path: %s", dl_path)
        except Exception as exc:
            logger.warning("[isot] kagglehub download failed: %s", exc)
            return

        data_dir.mkdir(parents=True, exist_ok=True)
        for target_name in ("True.csv", "Fake.csv"):
            # Search recursively — kagglehub may nest files in a subdirectory
            found = list(dl_path.rglob(target_name))
            if not found:
                logger.warning("[isot] '%s' not found in kagglehub download.", target_name)
                continue
            src = found[0]
            dst = data_dir / target_name
            if not dst.exists():
                shutil.copy2(src, dst)
                logger.info("[isot] Copied %s → %s", src, dst)
            else:
                logger.info("[isot] '%s' already exists — skipping copy.", target_name)

    def _warn_missing(self, missing: list[Path]) -> None:
        """Emit a clear, actionable warning when CSV files are absent."""
        missing_names = ", ".join(p.name for p in missing)
        msg = (
            f"\n{'=' * 60}\n"
            f"[isot] WARNING: ISOT dataset file(s) not found: {missing_names}\n"
            f"\n"
            f"Download the dataset from Kaggle:\n"
            f"  {_KAGGLE_URL}\n"
            f"\n"
            f"Then place True.csv and Fake.csv in:\n"
            f"  {self.data_dir}\n"
            f"\n"
            f"The ISOT source will be skipped for this run.\n"
            f"{'=' * 60}\n"
        )
        print(msg)
        logger.warning(msg)

    # Delegate log_class_distribution to a local print-based implementation
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
    print("ISOTDataset — smoke test")
    print("=" * 60)

    ds = ISOTDataset(max_samples=200)
    samples = ds.fetch()

    if samples:
        print(f"\nReturned {len(samples)} samples.")
        print("\nFirst 5 samples:")
        for i, s in enumerate(samples[:5]):
            print(
                f"  [{i}] label={s.label} conf={s.confidence:.2f} "
                f"orig={s.original_label!r:>6}  text={s.text[:80]!r}"
            )
    else:
        print(
            "\nNo samples returned.  "
            "Place True.csv and Fake.csv under ml/data/raw/isot/ and re-run."
        )
