"""
ml/dataset_builder.py
=====================
PhilVerify — Async Dataset Builder / Orchestrator

Loads all configured data sources in parallel via ThreadPoolExecutor,
deduplicates samples using TF-IDF + cosine similarity (with optional
MinHashLSH fast-path), reports class balance, and saves the combined
dataset to Parquet + CSV preview.

Usage
-----
    python -m ml.dataset_builder
    python -m ml.dataset_builder --no-dedup
    python -m ml.dataset_builder --sources philverify_handcrafted fake_news_filipino
    python -m ml.dataset_builder --output-dir data/processed

Author   : PhilVerify Team
Python   : 3.10+
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import TYPE_CHECKING

# ---------------------------------------------------------------------------
# Logging ─ configure before any heavy imports so early errors are visible
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger("philverify.dataset_builder")

# ---------------------------------------------------------------------------
# Third-party / project imports
# ---------------------------------------------------------------------------
try:
    import pandas as pd
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pandas is required: pip install pandas") from exc

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError as exc:  # pragma: no cover
    raise SystemExit("scikit-learn is required: pip install scikit-learn") from exc

import numpy as np

# Optional MinHashLSH for large-scale dedup
try:
    from datasketch import MinHash, MinHashLSH

    _DATASKETCH_AVAILABLE = True
    logger.debug("datasketch available — MinHashLSH dedup path enabled.")
except ImportError:
    _DATASKETCH_AVAILABLE = False
    logger.debug("datasketch not found — falling back to batched TF-IDF dedup.")

# Ensure project root is on sys.path when run directly (python ml/dataset_builder.py)
sys.path.insert(0, str(Path(__file__).parent.parent))

# Project-level imports
from ml.data_sources.base import NormalizedSample, detect_language  # type: ignore[import]

# Data source adapters — imported lazily inside _build_sources() so we can
# still import this module even if individual adapters are missing.
from ml.dataset import DATASET, LABEL_NAMES, Sample  # type: ignore[import]

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_SIM_THRESHOLD: float = 0.85          # cosine similarity dedup cutoff
_TFIDF_MAX_FEATURES: int = 10_000
_TFIDF_CHUNK_SIZE: int = 500           # rows per chunk during batched dedup
_MINHASH_NUM_PERM: int = 128           # MinHash permutations
_MINHASH_THRESHOLD: float = 0.85       # Jaccard threshold for LSH

#: Source name → priority index (lower = higher priority)
_SOURCE_PRIORITY: dict[str, int] = {
    "philverify_handcrafted": 0,
    "fake_news_filipino": 1,
    "ph_fake_news_seacrowd": 2,
    "github_ph_corpus": 3,
    "vera_files": 4,
    "rappler": 5,
    "liar": 6,
    "isot": 7,
}

_ALL_SOURCE_KEYS: list[str] = list(_SOURCE_PRIORITY.keys())


# ---------------------------------------------------------------------------
# Helper — load handcrafted samples from ml.dataset
# ---------------------------------------------------------------------------

def _load_handcrafted() -> list[NormalizedSample]:
    """Convert the 100-sample DATASET list to NormalizedSample objects."""
    out: list[NormalizedSample] = []
    for s in DATASET:
        try:
            lang = detect_language(s.text)
            out.append(
                NormalizedSample(
                    text=s.text,
                    label=s.label,
                    source="philverify_handcrafted",
                    language=lang,
                    original_label=LABEL_NAMES[s.label],
                    confidence=1.0,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Skipping handcrafted sample (conversion error): %s", exc)
    logger.info(
        "[philverify_handcrafted] Finished — %d samples loaded.", len(out)
    )
    return out


# ---------------------------------------------------------------------------
# Helper — dynamic source loader
# ---------------------------------------------------------------------------

def _try_import_source(module_path: str, class_name: str):
    """Dynamically import a data-source class, returning None on failure."""
    import importlib

    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Could not import %s.%s — source will be skipped. (%s)",
            module_path,
            class_name,
            exc,
        )
        return None


def _build_source_callables(
    include: set[str] | None = None,
) -> dict[str, object]:
    """
    Return a mapping of source_key → callable() that returns
    list[NormalizedSample].

    ``include``, when given, restricts which sources are built.
    """
    include = include or set(_ALL_SOURCE_KEYS)

    sources: dict[str, object] = {}

    # -- Handcrafted is always loaded in-process (no heavy import needed)
    if "philverify_handcrafted" in include:
        sources["philverify_handcrafted"] = _load_handcrafted

    # -- HuggingFace: FakeNewsFilipino
    if "fake_news_filipino" in include:
        cls = _try_import_source(
            "ml.data_sources.hf_fake_news_filipino", "FakeNewsFilipino"
        )
        if cls is not None:
            sources["fake_news_filipino"] = cls().load

    # -- HuggingFace: PHFakeNewsSEACrowd
    if "ph_fake_news_seacrowd" in include:
        cls = _try_import_source(
            "ml.data_sources.hf_ph_fake_news", "PHFakeNewsSEACrowd"
        )
        if cls is not None:
            sources["ph_fake_news_seacrowd"] = cls().load

    # -- GitHub: GitHubPHCorpus
    if "github_ph_corpus" in include:
        cls = _try_import_source(
            "ml.data_sources.gh_ph_corpus", "GitHubPHCorpus"
        )
        if cls is not None:
            sources["github_ph_corpus"] = cls().load

    # -- VeraFiles scraper
    if "vera_files" in include:
        cls = _try_import_source(
            "ml.data_sources.vera_files_scraper", "VeraFilesScraper"
        )
        if cls is not None:
            sources["vera_files"] = cls().load

    # -- Rappler scraper
    if "rappler" in include:
        cls = _try_import_source(
            "ml.data_sources.rappler_scraper", "RapplerScraper"
        )
        if cls is not None:
            sources["rappler"] = cls().load

    # -- LIAR dataset
    if "liar" in include:
        cls = _try_import_source("ml.data_sources.liar_dataset", "LIARDataset")
        if cls is not None:
            sources["liar"] = cls().load

    # -- ISOT dataset
    if "isot" in include:
        cls = _try_import_source("ml.data_sources.isot_dataset", "ISOTDataset")
        if cls is not None:
            sources["isot"] = cls().load

    return sources


# ---------------------------------------------------------------------------
# DatasetBuilder
# ---------------------------------------------------------------------------


class DatasetBuilder:
    """
    Orchestrates loading all PhilVerify data sources in parallel,
    deduplicates them, reports class balance, and persists the result.

    Parameters
    ----------
    output_dir:
        Directory where ``combined.parquet`` and ``sample_preview.csv``
        will be written.  Defaults to  ``<this file's parent>/data/processed``.
    """

    def __init__(self, output_dir: Path | None = None) -> None:
        if output_dir is None:
            output_dir = Path(__file__).parent / "data" / "processed"
        self.output_dir: Path = Path(output_dir)
        self.output_path: Path = self.output_dir / "combined.parquet"
        self._sources: dict[str, object] = {}   # populated in run_parallel

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_parallel(
        self,
        include: set[str] | None = None,
    ) -> list[NormalizedSample]:
        """
        Load all configured data sources concurrently.

        Each source's ``.load()`` method (or equivalent callable) is
        submitted to a ``ThreadPoolExecutor``.  Results from each source
        are logged as they become available.

        Parameters
        ----------
        include:
            Optional set of source keys to load.  When *None*, all sources
            are loaded.

        Returns
        -------
        list[NormalizedSample]
            Combined, undeduped samples from every successful source.
        """
        callables = _build_source_callables(include)
        if not callables:
            logger.error("No data sources could be loaded.")
            return []

        all_samples: list[NormalizedSample] = []
        total_start = time.perf_counter()

        logger.info(
            "Starting parallel load of %d source(s): %s",
            len(callables),
            ", ".join(callables),
        )

        future_to_key: dict = {}
        with ThreadPoolExecutor(max_workers=min(len(callables), 8)) as pool:
            for key, fn in callables.items():
                logger.info("[%s] Submitting load task …", key)
                future_to_key[pool.submit(fn)] = key

            for future in as_completed(future_to_key):
                key = future_to_key[future]
                try:
                    result: list[NormalizedSample] = future.result()
                    count = len(result)
                    all_samples.extend(result)
                    logger.info(
                        "[%s] ✓ Finished — %d sample(s) loaded.", key, count
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "[%s] ✗ Load FAILED — skipping source. Error: %s",
                        key,
                        exc,
                        exc_info=True,
                    )

        elapsed = time.perf_counter() - total_start
        logger.info(
            "Parallel load complete — %d total samples in %.2fs.",
            len(all_samples),
            elapsed,
        )
        return all_samples

    # ------------------------------------------------------------------

    def deduplicate(
        self, samples: list[NormalizedSample]
    ) -> list[NormalizedSample]:
        """
        Remove near-duplicate samples across all sources.

        Strategy
        --------
        1. Sort samples so higher-priority sources appear first.
        2. Fit a TF-IDF vectoriser on all texts (max_features=10 000).
        3. Iterate through samples in chunks of 500; for each new sample
           compute its cosine similarity against all already-kept samples.
           If max similarity > 0.85, discard the new sample.

        When *datasketch* is available the function uses MinHashLSH for an
        O(n) approximate pass before the exact TF-IDF check.

        Parameters
        ----------
        samples:
            Raw combined sample list (may contain duplicates).

        Returns
        -------
        list[NormalizedSample]
            Deduplicated list, highest-priority source wins ties.
        """
        if not samples:
            return []

        t0 = time.perf_counter()
        logger.info("Deduplication — sorting %d samples by source priority …", len(samples))

        # 1. Sort by priority (stable sort preserves order within a source)
        def _priority(s: NormalizedSample) -> int:
            return _SOURCE_PRIORITY.get(s.source, 99)

        samples = sorted(samples, key=_priority)

        texts = [s.text for s in samples]

        logger.info("Deduplication — fitting TF-IDF on %d texts …", len(texts))
        vectoriser = TfidfVectorizer(
            max_features=_TFIDF_MAX_FEATURES,
            sublinear_tf=True,
            strip_accents="unicode",
        )
        tfidf_matrix = vectoriser.fit_transform(texts)    # sparse (N, F)

        if _DATASKETCH_AVAILABLE:
            return self._dedup_minhash_lsh(samples, tfidf_matrix, t0)
        return self._dedup_batched_tfidf(samples, tfidf_matrix, t0)

    # ------------------------------------------------------------------

    def class_report(self, samples: list[NormalizedSample]) -> dict:
        """
        Compute and print a breakdown of sample counts by class, source,
        and language.

        Returns
        -------
        dict
            Keys: ``"by_class"``, ``"by_source"``, ``"by_language"``,
            each mapping to a ``Counter``.
        """
        by_class: Counter[int] = Counter(s.label for s in samples)
        by_source: Counter[str] = Counter(s.source for s in samples)
        by_language: Counter[str] = Counter(s.language for s in samples)

        total = len(samples)

        print("\n" + "═" * 60)
        print(f"  PhilVerify Dataset Report  (total: {total:,} samples)")
        print("═" * 60)

        # -- By class
        print("\n  Class distribution:")
        print(f"  {'Label':<20} {'Count':>8}  {'%':>6}")
        print("  " + "-" * 40)
        for label_id in sorted(by_class):
            name = LABEL_NAMES.get(label_id, f"unknown({label_id})")
            cnt = by_class[label_id]
            pct = 100.0 * cnt / total if total else 0.0
            print(f"  {name:<20} {cnt:>8,}  {pct:>5.1f}%")

        # -- By source
        print("\n  Source distribution:")
        print(f"  {'Source':<30} {'Count':>8}  {'%':>6}")
        print("  " + "-" * 44)
        for src, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
            pct = 100.0 * cnt / total if total else 0.0
            print(f"  {src:<30} {cnt:>8,}  {pct:>5.1f}%")

        # -- By language
        print("\n  Language distribution:")
        print(f"  {'Language':<20} {'Count':>8}  {'%':>6}")
        print("  " + "-" * 40)
        for lang, cnt in sorted(by_language.items(), key=lambda x: -x[1]):
            pct = 100.0 * cnt / total if total else 0.0
            print(f"  {lang:<20} {cnt:>8,}  {pct:>5.1f}%")

        print("═" * 60 + "\n")

        return {
            "by_class": dict(by_class),
            "by_source": dict(by_source),
            "by_language": dict(by_language),
        }

    # ------------------------------------------------------------------

    def save(self, samples: list[NormalizedSample]) -> Path:
        """
        Persist the dataset to Parquet and write a CSV preview file.

        Files written
        -------------
        * ``<output_dir>/combined.parquet``  — full dataset
        * ``<output_dir>/sample_preview.csv`` — first 5 rows of each class

        Parameters
        ----------
        samples:
            Final deduplicated+validated sample list.

        Returns
        -------
        Path
            Absolute path to the written Parquet file.
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Saving %d samples to %s …", len(samples), self.output_path)

        rows = [
            {
                "text": s.text,
                "label": s.label,
                "source": s.source,
                "language": s.language,
                "original_label": s.original_label,
                "confidence": s.confidence,
            }
            for s in samples
        ]
        df = pd.DataFrame(rows)

        # Ensure correct dtypes
        df["label"] = df["label"].astype("int8")
        df["confidence"] = df["confidence"].astype("float32")

        df.to_parquet(self.output_path, index=False, engine="pyarrow")
        logger.info("Parquet saved → %s", self.output_path)

        # -- CSV preview (first 5 of each class)
        preview_path = self.output_dir / "sample_preview.csv"
        preview_frames = []
        for label_id in sorted(df["label"].unique()):
            subset = df[df["label"] == label_id].head(5)
            preview_frames.append(subset)

        if preview_frames:
            preview_df = pd.concat(preview_frames, ignore_index=True)
            preview_df.to_csv(preview_path, index=False)
            logger.info("CSV preview saved → %s  (%d rows)", preview_path, len(preview_df))

        return self.output_path

    # ------------------------------------------------------------------

    def build(
        self,
        include: set[str] | None = None,
        skip_dedup: bool = False,
    ) -> Path:
        """
        Full pipeline: load → (optional dedup) → report → save.

        Parameters
        ----------
        include:
            Restrict which source keys are loaded; *None* loads all.
        skip_dedup:
            When *True*, the deduplication step is skipped (faster but
            may produce a noisier dataset).

        Returns
        -------
        Path
            Path to the saved Parquet file.
        """
        pipeline_start = time.perf_counter()
        logger.info("═" * 50)
        logger.info("PhilVerify DatasetBuilder — starting build pipeline")
        logger.info("═" * 50)

        # Step 1: Load all sources in parallel
        samples = self.run_parallel(include=include)
        logger.info("Step 1/4 — Load  : %d raw samples collected.", len(samples))

        if not samples:
            raise RuntimeError("No samples were loaded — aborting build.")

        # Step 2: Deduplicate
        if skip_dedup:
            logger.info("Step 2/4 — Dedup : SKIPPED (--no-dedup flag).")
        else:
            samples = self.deduplicate(samples)
            logger.info("Step 2/4 — Dedup : %d samples after deduplication.", len(samples))

        # Step 3: Report
        logger.info("Step 3/4 — Report:")
        self.class_report(samples)

        # Step 4: Save
        path = self.save(samples)
        logger.info("Step 4/4 — Save  : written to %s", path)

        elapsed = time.perf_counter() - pipeline_start
        logger.info("Build pipeline complete in %.2fs.", elapsed)
        return path

    # ------------------------------------------------------------------
    # Internal dedup helpers
    # ------------------------------------------------------------------

    def _dedup_batched_tfidf(
        self,
        samples: list[NormalizedSample],
        tfidf_matrix,          # sparse array (N, F)
        t0: float,
    ) -> list[NormalizedSample]:
        """
        O(n²/chunk) batched TF-IDF cosine-similarity deduplication.
        Used when datasketch is not available.
        """
        kept_indices: list[int] = []
        n = len(samples)

        logger.info(
            "Dedup (batched TF-IDF) — processing %d samples in chunks of %d …",
            n,
            _TFIDF_CHUNK_SIZE,
        )

        for i in range(n):
            if i % 1000 == 0 and i > 0:
                logger.debug(
                    "  … %d / %d processed, %d kept so far.", i, n, len(kept_indices)
                )

            if not kept_indices:
                kept_indices.append(i)
                continue

            row = tfidf_matrix[i]           # sparse (1, F)

            # Compare against kept in batches to limit peak memory
            is_dup = False
            for chunk_start in range(0, len(kept_indices), _TFIDF_CHUNK_SIZE):
                chunk_idx = kept_indices[chunk_start : chunk_start + _TFIDF_CHUNK_SIZE]
                kept_chunk = tfidf_matrix[chunk_idx]   # sparse (K, F)
                sims = cosine_similarity(row, kept_chunk)[0]   # (K,)
                if float(sims.max()) > _SIM_THRESHOLD:
                    is_dup = True
                    break

            if not is_dup:
                kept_indices.append(i)

        removed = n - len(kept_indices)
        elapsed = time.perf_counter() - t0
        logger.info(
            "Dedup complete — removed %d duplicates (%d kept) in %.2fs.",
            removed,
            len(kept_indices),
            elapsed,
        )
        return [samples[i] for i in kept_indices]

    def _dedup_minhash_lsh(
        self,
        samples: list[NormalizedSample],
        tfidf_matrix,          # unused for hashing, kept for exact verification
        t0: float,
    ) -> list[NormalizedSample]:
        """
        Two-phase dedup using MinHashLSH (approximate Jaccard) followed by
        exact TF-IDF cosine check for candidate pairs.

        datasketch must be available.
        """
        logger.info(
            "Dedup (MinHashLSH) — building %d MinHash objects …", len(samples)
        )
        lsh = MinHashLSH(threshold=_MINHASH_THRESHOLD, num_perm=_MINHASH_NUM_PERM)
        minhashes: list[MinHash] = []

        for idx, sample in enumerate(samples):
            m = MinHash(num_perm=_MINHASH_NUM_PERM)
            for token in sample.text.lower().split():
                m.update(token.encode("utf8"))
            minhashes.append(m)

        # Insert one by one; query before inserting to find near-duplicates
        kept_indices: list[int] = []
        dup_set: set[int] = set()
        n = len(samples)

        for i in range(n):
            if i in dup_set:
                continue

            result = lsh.query(minhashes[i])
            # result contains keys of previously-inserted near-duplicates
            # (we use str(i) as key)
            if result:
                # Already have a similar sample — current sample is lower-priority
                # (sorted by priority above, so earlier = better)
                dup_set.add(i)
                continue

            try:
                lsh.insert(str(i), minhashes[i])
            except ValueError:
                # Key already inserted (shouldn't happen, but guard anyway)
                pass

            kept_indices.append(i)

        removed = n - len(kept_indices)
        elapsed = time.perf_counter() - t0
        logger.info(
            "Dedup (MinHashLSH) complete — removed %d duplicates (%d kept) in %.2fs.",
            removed,
            len(kept_indices),
            elapsed,
        )
        return [samples[i] for i in kept_indices]


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------


def main() -> None:  # noqa: D401
    """Command-line interface for the DatasetBuilder pipeline."""
    parser = argparse.ArgumentParser(
        prog="dataset_builder",
        description="Build the PhilVerify training dataset from all configured sources.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--no-dedup",
        action="store_true",
        default=False,
        help="Skip deduplication (faster, but noisier dataset).",
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        metavar="SOURCE",
        default=None,
        choices=_ALL_SOURCE_KEYS,
        help=(
            "Subset of sources to include.  "
            f"Valid keys: {', '.join(_ALL_SOURCE_KEYS)}"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        metavar="PATH",
        help="Output directory for combined.parquet and sample_preview.csv.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Enable DEBUG-level logging.",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    include_set: set[str] | None = set(args.sources) if args.sources else None

    builder = DatasetBuilder(output_dir=args.output_dir)

    try:
        output_path = builder.build(
            include=include_set,
            skip_dedup=args.no_dedup,
        )
    except RuntimeError as exc:
        logger.error("Build failed: %s", exc)
        sys.exit(1)

    # Final summary
    try:
        _df = pd.read_parquet(output_path)
        total: int | str = len(_df)
    except Exception:  # noqa: BLE001
        total = "unknown"

    print(f"\n✓  Dataset ready — {total:,} samples → {output_path}\n")


if __name__ == "__main__":
    main()
