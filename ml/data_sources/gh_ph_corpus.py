"""
ml/data_sources/gh_ph_corpus.py

DataSource adapter for the Philippine Fake News Corpus:
  https://github.com/aaroncarlfernandez/Philippine-Fake-News-Corpus

Strategy
--------
1. Query the GitHub Trees API to discover every .csv in the repository.
2. Download each CSV via a raw.githubusercontent.com URL.
3. Cache raw CSVs under  ml/data/raw/gh_ph_corpus/  so repeated runs do
   not hit the network.
4. Auto-detect the label column and text column from well-known aliases.
5. Normalise binary labels ("fake" / "real") to the project's three-class
   scheme (0 = Credible, 1 = Unverified, 2 = Likely Fake) via
   binary_to_three_class().

Label mapping
-------------
  row label contains "fake"                       → raw_label = "fake"
  row label contains "real", "true", "credible"   → raw_label = "real"
  anything else                                   → row skipped with a warning
"""

from __future__ import annotations

import csv
import io
import logging
import os
import time
import zipfile
from pathlib import Path
from typing import Optional

import requests

from .base import (
    DataSource,
    NormalizedSample,
    binary_to_three_class,
    clean_text,
    detect_language,
)

# ---------------------------------------------------------------------------
# Module-level logger
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_REPO_OWNER = "aaroncarlfernandez"
_REPO_NAME  = "Philippine-Fake-News-Corpus"

# This repo uses 'master' (7-year-old repo, predates the GitHub default change)
_BRANCHES: list[str] = ["master", "main"]

# Populated at runtime once we find the live branch
_BRANCH: str = _BRANCHES[0]

# The corpus is shipped as a single zip archive (no raw CSVs in the tree)
_CORPUS_ZIP_NAME = "Philippine Fake News Corpus.zip"
_CORPUS_ZIP_URL = (
    f"https://github.com/{_REPO_OWNER}/{_REPO_NAME}"
    f"/raw/master/Philippine%20Fake%20News%20Corpus.zip"
)

# Fallback direct CSV paths (kept for future-proofing; all currently 404)
_FALLBACK_CSV_PATHS: list[str] = []

# Column name candidates (case-insensitive match attempted first)
_LABEL_COLUMN_CANDIDATES: list[str] = [
    "label", "Label", "class", "Class", "verdict", "type", "category",
]
_TEXT_COLUMN_CANDIDATES: list[str] = [
    "text", "article", "title", "content", "headline", "body", "news",
]

# Cache directory relative to the project root (resolved at runtime)
_CACHE_SUBDIR = Path("ml") / "data" / "raw" / "gh_ph_corpus"

# Minimum text length in characters; shorter rows are skipped
_MIN_TEXT_LEN = 15

# Shared HTTP headers
_HEADERS: dict[str, str] = {
    "User-Agent": f"PhilVerify-DataLoader/1.0 ({_REPO_OWNER}/{_REPO_NAME})",
    "Accept": "application/vnd.github.v3+json",
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _project_root() -> Path:
    """
    Return the absolute path to the PhilVerify project root.

    Assumes this file lives at  <root>/ml/data_sources/gh_ph_corpus.py.
    """
    return Path(__file__).resolve().parents[2]


def _cache_dir() -> Path:
    """Return (and create if necessary) the raw-CSV cache directory."""
    cache = _project_root() / _CACHE_SUBDIR
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _safe_get(url: str, timeout: int = 30) -> Optional[requests.Response]:
    """
    Perform a GET request and return the Response, or None on failure.

    Handles:
    - Network errors (ConnectionError, Timeout, etc.)
    - HTTP 403 / 429  (GitHub rate-limit) — logs a warning and returns None
    - Any other non-2xx status  — logs a warning and returns None
    """
    try:
        response = requests.get(url, headers=_HEADERS, timeout=timeout)
    except requests.RequestException as exc:
        logger.warning("Network error fetching %s: %s", url, exc)
        return None

    if response.status_code in (403, 429):
        reset_ts = response.headers.get("X-RateLimit-Reset")
        if reset_ts:
            wait = max(0, int(reset_ts) - int(time.time()))
            logger.warning(
                "GitHub rate-limit hit fetching %s. "
                "Retry-After: %d s (X-RateLimit-Reset: %s)",
                url, wait, reset_ts,
            )
        else:
            logger.warning(
                "HTTP %d from %s — possible rate-limit or auth issue.",
                response.status_code, url,
            )
        return None

    if not response.ok:
        logger.warning("HTTP %d fetching %s", response.status_code, url)
        return None

    return response


def _find_column(header: list[str], candidates: list[str]) -> Optional[str]:
    """
    Return the first header name that matches, case-insensitively, one of
    *candidates*.  Returns None if none match.
    """
    lower_header = {col.lower(): col for col in header}
    for candidate in candidates:
        if candidate.lower() in lower_header:
            return lower_header[candidate.lower()]
    return None


def _normalise_raw_label(cell_value: str) -> Optional[str]:
    """
    Map a raw CSV cell value to "fake" or "real".

    Returns None if the value cannot be mapped.
    """
    val = cell_value.strip().lower()
    # Check negative / fake forms FIRST to avoid substring false-positives
    # e.g. "not credible" must not match the later "credible" → real branch
    if "not credible" in val or "non-credible" in val or "noncredible" in val:
        return "fake"
    if "fake" in val or "not real" in val:
        return "fake"
    if "real" in val or "true" in val or "credible" in val or "legitimate" in val:
        return "real"
    return None


# ---------------------------------------------------------------------------
# Main DataSource class
# ---------------------------------------------------------------------------

class GitHubPHCorpus(DataSource):
    """
    DataSource adapter for aaroncarlfernandez/Philippine-Fake-News-Corpus.

    Attributes
    ----------
    project_root : Path
        Absolute path to the PhilVerify project root; used to resolve the
        cache directory and the domain-credibility JSON.

    Examples
    --------
    >>> corpus = GitHubPHCorpus()
    >>> samples = corpus.load()
    >>> print(len(samples), "samples loaded")
    """

    def __init__(self) -> None:
        self._project_root: Path = _project_root()
        self._cache_dir: Path = _cache_dir()
        self._credibility_path: Path = (
            self._project_root / "domain_credibility.json"
        )

    # ------------------------------------------------------------------
    # DataSource interface
    # ------------------------------------------------------------------

    @property
    def source_name(self) -> str:
        """Canonical identifier for this data source."""
        return f"{_REPO_OWNER}/{_REPO_NAME}"

    def fetch(self) -> list[NormalizedSample]:
        """
        Download (or load from cache) all CSV files in the corpus and return
        a list of NormalizedSample objects.

        The repository packages data as a single ZIP archive rather than
        individual CSV files, so the primary strategy is zip-based.  The
        GitHub Trees API / fallback URL paths are kept as a secondary
        strategy in case the repo layout changes.

        Returns an empty list (without raising) if all download attempts fail.
        """
        # Primary: download-and-extract the corpus ZIP archive
        zip_samples = self._fetch_and_parse_zip()
        if zip_samples:
            return zip_samples

        # Secondary: individual CSV via GitHub Trees API / fallback paths
        csv_paths = self._resolve_csv_paths()
        if not csv_paths:
            logger.error(
                "GitHubPHCorpus: no CSV files found via zip, API, or fallback URLs. "
                "Returning empty dataset."
            )
            return []

        samples: list[NormalizedSample] = []
        for path in csv_paths:
            raw_bytes = self._fetch_csv(path)
            if raw_bytes is None:
                logger.warning("Skipping inaccessible CSV: %s", path)
                continue
            new_samples = self._parse_csv(raw_bytes, remote_path=path)
            logger.info(
                "  %-50s → %d samples", path, len(new_samples)
            )
            samples.extend(new_samples)

        logger.info(
            "GitHubPHCorpus: total samples loaded = %d", len(samples)
        )
        return samples

    def _fetch_and_parse_zip(self) -> list[NormalizedSample]:
        """
        Download the corpus ZIP archive, extract every .csv inside it to the
        local cache directory, then parse them all.

        Returns an empty list (without raising) on any failure.
        """
        zip_cache = self._cache_dir / "corpus.zip"

        # Download zip only if not already cached
        if not zip_cache.exists():
            logger.info(
                "GitHubPHCorpus: downloading corpus ZIP from %s", _CORPUS_ZIP_URL
            )
            response = _safe_get(_CORPUS_ZIP_URL, timeout=180)
            if response is None:
                logger.error("GitHubPHCorpus: failed to download corpus ZIP.")
                return []
            try:
                zip_cache.write_bytes(response.content)
                logger.info(
                    "GitHubPHCorpus: saved corpus ZIP (%d bytes)",
                    len(response.content),
                )
            except OSError as exc:
                logger.error("GitHubPHCorpus: could not write ZIP cache: %s", exc)
                return []
        else:
            logger.info(
                "GitHubPHCorpus: using cached corpus ZIP at %s", zip_cache
            )

        # Extract CSV files to cache dir
        csv_local_paths: list[Path] = []
        try:
            with zipfile.ZipFile(zip_cache) as zf:
                for name in zf.namelist():
                    if not name.lower().endswith(".csv"):
                        continue
                    # Flatten nested paths: keep only the filename
                    safe_name = Path(name).name
                    out_path = self._cache_dir / safe_name
                    if not out_path.exists():
                        out_path.write_bytes(zf.read(name))
                        logger.debug(
                            "GitHubPHCorpus: extracted %s → %s", name, out_path
                        )
                    csv_local_paths.append(out_path)
        except zipfile.BadZipFile as exc:
            logger.error(
                "GitHubPHCorpus: bad ZIP file at %s: %s — deleting cache.",
                zip_cache, exc,
            )
            zip_cache.unlink(missing_ok=True)
            return []

        if not csv_local_paths:
            logger.warning(
                "GitHubPHCorpus: corpus ZIP contained no CSV files."
            )
            return []

        logger.info(
            "GitHubPHCorpus: found %d CSV(s) in ZIP.", len(csv_local_paths)
        )

        samples: list[NormalizedSample] = []
        for local_path in csv_local_paths:
            raw_bytes = local_path.read_bytes()
            new_samples = self._parse_csv(
                raw_bytes, remote_path=local_path.name
            )
            logger.info(
                "  %-50s → %d samples", local_path.name, len(new_samples)
            )
            samples.extend(new_samples)

        logger.info(
            "GitHubPHCorpus: total samples from ZIP = %d", len(samples)
        )
        return samples

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_csv_paths(self) -> list[str]:
        """
        Return a list of in-repo relative paths to .csv files.

        First attempts the GitHub Trees API; falls back to a hard-coded list
        of known paths if the API is unavailable or returns no results.
        """
        api_paths = self._fetch_csv_paths_from_api()
        if api_paths:
            logger.info(
                "GitHubPHCorpus: discovered %d CSV(s) via GitHub API.",
                len(api_paths),
            )
            return api_paths

        logger.warning(
            "GitHubPHCorpus: GitHub API unavailable or returned no CSVs. "
            "Trying %d known fallback path(s).",
            len(_FALLBACK_CSV_PATHS),
        )
        return _FALLBACK_CSV_PATHS

    def _fetch_csv_paths_from_api(self) -> list[str]:
        """
        Query the GitHub Trees API and return all .csv paths in the tree.
        Tries 'main' first, then 'master'. Updates the module-level _BRANCH.

        Returns an empty list on any failure or rate-limit.
        """
        global _BRANCH
        for branch in _BRANCHES:
            api_url = (
                f"https://api.github.com/repos/{_REPO_OWNER}/{_REPO_NAME}"
                f"/git/trees/{branch}?recursive=1"
            )
            response = _safe_get(api_url)
            if response is None:
                continue
            try:
                data = response.json()
            except ValueError as exc:
                logger.warning("GitHubPHCorpus: failed to parse API JSON: %s", exc)
                continue
            tree: list[dict] = data.get("tree", [])
            csv_paths = [
                item["path"]
                for item in tree
                if item.get("type") == "blob"
                and item.get("path", "").lower().endswith(".csv")
            ]
            if csv_paths:
                _BRANCH = branch
                logger.info("GitHubPHCorpus: using branch '%s'.", branch)
                return csv_paths
        return []

    def _fetch_csv(self, repo_path: str) -> Optional[bytes]:
        """
        Return raw bytes for a CSV file, loading from the local cache when
        available and downloading + caching otherwise.

        Parameters
        ----------
        repo_path:
            In-repo relative path (e.g. ``"data/fake_news.csv"``).

        Returns
        -------
        bytes or None
            Raw UTF-8 / latin-1 bytes of the CSV, or None if unavailable.
        """
        cache_file = self._cache_dir / repo_path.replace("/", "_")

        # ── Cache hit ────────────────────────────────────────────────────
        if cache_file.exists():
            logger.debug("Loading from cache: %s", cache_file)
            return cache_file.read_bytes()

        # ── Download — try all known branches ──────────────────────────
        raw: Optional[bytes] = None
        for branch in _BRANCHES:
            url = (
                f"https://raw.githubusercontent.com/{_REPO_OWNER}/{_REPO_NAME}"
                f"/{branch}/{repo_path}"
            )
            response = _safe_get(url)
            if response is not None:
                raw = response.content
                break

        if raw is None:
            return None

        try:
            cache_file.write_bytes(raw)
            logger.debug("Cached %s → %s", repo_path, cache_file)
        except OSError as exc:
            logger.warning("Could not write cache file %s: %s", cache_file, exc)

        return raw

    def _parse_csv(
        self,
        raw_bytes: bytes,
        *,
        remote_path: str = "<unknown>",
    ) -> list[NormalizedSample]:
        """
        Parse raw CSV bytes into NormalizedSample objects.

        Parameters
        ----------
        raw_bytes:
            Raw bytes of the CSV file (UTF-8 preferred; latin-1 fallback).
        remote_path:
            Original repo path used only for log messages.

        Returns
        -------
        list[NormalizedSample]
        """
        # ── Decode ───────────────────────────────────────────────────────
        try:
            text_content = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_content = raw_bytes.decode("latin-1", errors="replace")

        reader = csv.DictReader(io.StringIO(text_content))
        if reader.fieldnames is None:
            logger.warning("CSV %s has no header row; skipping.", remote_path)
            return []

        header: list[str] = list(reader.fieldnames)

        # ── Column detection ─────────────────────────────────────────────
        label_col = _find_column(header, _LABEL_COLUMN_CANDIDATES)
        text_col  = _find_column(header, _TEXT_COLUMN_CANDIDATES)

        if label_col is None:
            logger.warning(
                "CSV %s: cannot detect label column in %s; skipping.",
                remote_path, header,
            )
            return []

        if text_col is None:
            logger.warning(
                "CSV %s: cannot detect text column in %s; skipping.",
                remote_path, header,
            )
            return []

        logger.info(
            "CSV %s: using label_col=%r  text_col=%r",
            remote_path, label_col, text_col,
        )

        # ── Infer a static raw_label for files whose *name* encodes the
        #    class (e.g. fake_news.csv / real_news.csv / not_credible.csv)
        #    so we can handle label-less files gracefully.
        filename_hint: Optional[str] = None
        lower_path = remote_path.lower()
        # Check negative forms first ("not credible" etc.) before positive
        if "not credible" in lower_path or "not_credible" in lower_path or "noncredible" in lower_path:
            filename_hint = "fake"
        elif "fake" in lower_path or "not real" in lower_path:
            filename_hint = "fake"
        elif "real" in lower_path or "true" in lower_path or "credible" in lower_path or "legitimate" in lower_path:
            filename_hint = "real"

        # ── Row iteration ────────────────────────────────────────────────
        samples: list[NormalizedSample] = []
        skipped_short   = 0
        skipped_label   = 0
        skipped_notext  = 0

        for row in reader:
            # ── Text ─────────────────────────────────────────────────────
            raw_text = (row.get(text_col) or "").strip()
            if not raw_text:
                skipped_notext += 1
                continue

            cleaned = clean_text(raw_text)
            if len(cleaned) < _MIN_TEXT_LEN:
                skipped_short += 1
                continue

            # ── Label ────────────────────────────────────────────────────
            cell_label = (row.get(label_col) or "").strip()
            raw_label  = _normalise_raw_label(cell_label)

            if raw_label is None:
                # Fall back to filename hint (e.g. for label-less files)
                if filename_hint:
                    raw_label = filename_hint
                else:
                    logger.debug(
                        "CSV %s: unrecognised label %r; skipping row.",
                        remote_path, cell_label,
                    )
                    skipped_label += 1
                    continue

            # ── Three-class mapping ───────────────────────────────────────
            label_int = binary_to_three_class(
                raw_label,
                None,  # domain — not available from corpus
                str(self._credibility_path),
            )

            # ── Language detection ────────────────────────────────────────
            language = detect_language(cleaned)

            samples.append(
                NormalizedSample(
                    text=cleaned,
                    label=label_int,
                    source=self.source_name,
                    language=language,
                    original_label=cell_label if cell_label else raw_label,
                    confidence=1.0,
                )
            )

        if skipped_short or skipped_label or skipped_notext:
            logger.debug(
                "CSV %s: skipped %d short-text, %d unrecognised-label, "
                "%d empty-text rows.",
                remote_path, skipped_short, skipped_label, skipped_notext,
            )

        return samples


# ---------------------------------------------------------------------------
# Standalone testing entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )

    corpus = GitHubPHCorpus()
    samples = corpus.load()

    print(f"\n{'='*60}")
    print(f"Source      : {corpus.source_name}")
    print(f"Total rows  : {len(samples)}")

    if samples:
        from collections import Counter
        label_counts = Counter(s.label for s in samples)
        lang_counts  = Counter(s.language for s in samples)
        label_names  = {0: "Credible", 1: "Unverified", 2: "Likely Fake"}

        print("\nLabel distribution:")
        for lbl in sorted(label_counts):
            print(f"  {lbl} ({label_names.get(lbl, '?'):12s}): "
                  f"{label_counts[lbl]:>6d}")

        print("\nLanguage distribution:")
        for lang, count in lang_counts.most_common():
            print(f"  {lang:<10s}: {count:>6d}")

        print(f"\nSample (first 3):")
        for s in samples[:3]:
            snippet = s.text[:80].replace("\n", " ")
            print(f"  [{label_names.get(s.label, '?')}] [{s.language}] {snippet!r}")

    print(f"{'='*60}\n")
