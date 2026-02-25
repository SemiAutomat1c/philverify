"""
ml/data_sources/hf_fake_news_filipino.py
PhilVerify – HuggingFace data source adapter for jcblaise/fake_news_filipino.

Dataset:  https://huggingface.co/datasets/jcblaise/fake_news_filipino
Splits:   train / test / validation
Columns:  article (str), label (int: 0=real, 1=fake)
3-class mapping:
  dataset 0 (real)  → PhilVerify 0 (Credible)
  dataset 1 (fake)  → PhilVerify 2 (Likely Fake)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from tqdm import tqdm

from .base import DataSource, NormalizedSample, binary_to_three_class, clean_text, detect_language

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DATASET_ID: str = "jcblaise/fake_news_filipino"
_SPLITS: tuple[str, ...] = ("train", "test", "validation")
_RAW_DIR: Path = Path(__file__).parent.parent / "data" / "raw"
_CREDIBILITY_PATH: Path = Path(__file__).parent.parent.parent / "domain_credibility.json"

# Direct download URL – bypasses the unsupported loading-script mechanism
_DIRECT_ZIP_URL: str = (
    "https://huggingface.co/datasets/jcblaise/fake_news_filipino"
    "/resolve/main/fakenews.zip"
)
_ZIP_INNER_PATH: str = "fakenews/full.csv"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _load_raw() -> "datasets.DatasetDict":  # noqa: F821
    """Download ``fakenews.zip`` directly and return a ``DatasetDict``.

    The zip contains ``fakenews/full.csv`` with columns ``label`` (0=real,
    1=fake) and ``article`` (text).  The CSV is cached locally in
    ``ml/data/raw/fake_news_filipino/full.csv`` to avoid repeated downloads.

    Returns:
        ``datasets.DatasetDict`` with a single ``'train'`` split.

    Raises:
        RuntimeError: If download or parsing fails.
    """
    import io
    import zipfile

    import datasets
    import pandas as pd
    import requests

    cache_dir = _RAW_DIR / "fake_news_filipino"
    cache_csv = cache_dir / "full.csv"

    if not cache_csv.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info("Downloading fakenews.zip from HuggingFace …")
        try:
            resp = requests.get(_DIRECT_ZIP_URL, timeout=120)
            resp.raise_for_status()
            raw_bytes = resp.content
        except Exception as exc:
            raise RuntimeError(f"Failed to download fakenews.zip: {exc}") from exc
        with zipfile.ZipFile(io.BytesIO(raw_bytes)) as zf:
            with zf.open(_ZIP_INNER_PATH) as f:
                csv_bytes = f.read()
        cache_csv.write_bytes(csv_bytes)
        logger.info("Cached CSV → %s", cache_csv)
    else:
        logger.info("Using cached CSV from %s", cache_csv)

    df = pd.read_csv(
        cache_csv,
        quotechar='"',
        quoting=0,
        skipinitialspace=True,
    )
    if "article" not in df.columns or "label" not in df.columns:
        raise RuntimeError(
            f"Unexpected columns in fakenews CSV: {list(df.columns)}.  "
            "Expected 'label' and 'article'."
        )
    df["label"] = df["label"].astype(int)
    ds = datasets.Dataset.from_pandas(df.reset_index(drop=True))
    return datasets.DatasetDict({"train": ds})


# ---------------------------------------------------------------------------
# DataSource implementation
# ---------------------------------------------------------------------------

class FakeNewsFilipino(DataSource):
    """HuggingFace data-source adapter for ``jcblaise/fake_news_filipino``.

    The dataset contains Philippine news articles labelled as real (0) or
    fake (1). This adapter normalises them into the PhilVerify 3-class schema:

    * 0 → Credible
    * 2 → Likely Fake
    (Class 1 / Unverified is not produced by this source.)
    """

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        """Canonical HuggingFace dataset identifier."""
        return _DATASET_ID

    def fetch(self) -> list[NormalizedSample]:
        """Fetch and normalise all splits of ``jcblaise/fake_news_filipino``.

        Returns:
            A list of :class:`~ml.data_sources.base.NormalizedSample` objects
            representing every non-empty article across all splits.
        """
        _RAW_DIR.mkdir(parents=True, exist_ok=True)

        try:
            dataset_dict = _load_raw()
        except Exception as exc:
            logger.error("Could not load dataset '%s': %s", _DATASET_ID, exc)
            return []

        samples: list[NormalizedSample] = []

        for split in _SPLITS:
            if split not in dataset_dict:
                logger.warning("Split '%s' not found in '%s' – skipping.", split, _DATASET_ID)
                continue

            split_data = dataset_dict[split]
            split_samples: list[NormalizedSample] = []

            logger.info("Processing split '%s' (%d rows)…", split, len(split_data))

            for row in tqdm(split_data, desc=f"{_DATASET_ID}/{split}", unit="row", leave=False):
                raw_text: str = row.get("article", "") or ""
                text = clean_text(raw_text)
                if not text:
                    continue

                raw_label: int = int(row.get("label", -1))

                if raw_label == 0:
                    # real → Credible
                    normalized_label: int = binary_to_three_class(
                        "real", None, str(_CREDIBILITY_PATH)
                    )
                    original_label = "real"
                    confidence: float = 1.0
                elif raw_label == 1:
                    # fake → Likely Fake
                    normalized_label = binary_to_three_class(
                        "fake", None, str(_CREDIBILITY_PATH)
                    )
                    original_label = "fake"
                    confidence = 1.0
                else:
                    logger.debug("Skipping row with unknown label %r.", raw_label)
                    continue

                language = detect_language(text)

                split_samples.append(
                    NormalizedSample(
                        text=text,
                        label=normalized_label,
                        source=self.source_name,
                        language=language,
                        original_label=original_label,
                        confidence=confidence,
                    )
                )

            logger.info(
                "Split '%s': %d/%d rows retained after cleaning.",
                split,
                len(split_samples),
                len(split_data),
            )
            samples.extend(split_samples)

        logger.info(
            "FakeNewsFilipino.fetch() complete – %d total samples from '%s'.",
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

    source = FakeNewsFilipino()
    results = source.fetch()

    print(f"\nTotal samples loaded: {len(results)}")
    print("First 3 samples:")
    for i, s in enumerate(results[:3], 1):
        preview = s.text[:120].replace("\n", " ")
        print(
            f"  [{i}] label={s.label} ({s.original_label!r}) "
            f"lang={s.language!r} | {preview!r}"
        )
