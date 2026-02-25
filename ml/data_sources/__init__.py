"""
ml/data_sources/__init__.py
Package init for PhilVerify data source adapters.

Exports the abstract base class, normalized sample dataclass,
and shared NLP utility functions used across all source adapters.
"""

from __future__ import annotations

from .base import (
    DataSource,
    NormalizedSample,
    clean_text,
    detect_language,
)

__all__ = [
    "DataSource",
    "NormalizedSample",
    "clean_text",
    "detect_language",
]
