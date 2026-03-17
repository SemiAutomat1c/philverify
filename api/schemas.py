"""
PhilVerify — Pydantic Request / Response Schemas
Matches the structured JSON output format from the system spec.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, HttpUrl, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class Verdict(str, Enum):
    CREDIBLE = "Credible"
    UNVERIFIED = "Unverified"
    LIKELY_FAKE = "Likely Fake"


class Stance(str, Enum):
    SUPPORTS = "Supports"
    REFUTES = "Refutes"
    NOT_ENOUGH_INFO = "Not Enough Info"


class Language(str, Enum):
    TAGALOG = "Tagalog"
    ENGLISH = "English"
    TAGLISH = "Taglish"
    UNKNOWN = "Unknown"


class Sentiment(str, Enum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    HIGH_POSITIVE = "high positive"
    HIGH_NEGATIVE = "high negative"


class DomainTier(int, Enum):
    CREDIBLE = 1
    SATIRE_OPINION = 2
    SUSPICIOUS = 3
    KNOWN_FAKE = 4


# ── Request Models ─────────────────────────────────────────────────────────────

class TextVerifyRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=10_000, description="Raw text to verify")
    image_url: Optional[str] = Field(None, description="Optional image URL to run OCR on alongside the text")


class URLVerifyRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the news article or social media post")


# ── Nested Response Models ────────────────────────────────────────────────────

class EntitiesResult(BaseModel):
    persons: list[str] = []
    organizations: list[str] = []
    locations: list[str] = []
    dates: list[str] = []


class Layer1Result(BaseModel):
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=100.0, description="Confidence % from ML classifier")
    triggered_features: list[str] = Field(
        default_factory=list,
        description="Human-readable list of suspicious features detected",
    )
    model_tier: Optional[str] = Field(None, description="Classifier used: ensemble | xlmr | tfidf")


class EvidenceSource(BaseModel):
    title: str
    url: str
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity to input claim")
    stance: Stance
    stance_reason: Optional[str] = Field(None, description="NLI entailment or keyword reason for stance")
    domain_tier: DomainTier
    published_at: Optional[str] = None
    source_name: Optional[str] = None


class Layer2Result(BaseModel):
    verdict: Verdict
    evidence_score: float = Field(..., ge=0.0, le=100.0)
    sources: list[EvidenceSource] = []
    claim_used: Optional[str] = Field(None, description="Extracted claim sent to evidence search")
    claim_method: Optional[str] = Field(None, description="How the claim was extracted: sentence_scoring | sentence_heuristic | passthrough")


# ── Classifier Comparison ─────────────────────────────────────────────────────

class ClassifierComparisonEntry(BaseModel):
    name: str                           # "BoW", "TF-IDF", "Naive Bayes", "LDA"
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=100.0)
    top_features: list[str] = []        # up to 3 top features / lda_topic_N label


# ── LDA Topic Result ──────────────────────────────────────────────────────────

class LDATopicResult(BaseModel):
    label: str                                          # Human-assigned topic name
    top_words: list[str]                                # Top 6 words defining this topic
    confidence: float = Field(..., ge=0.0, le=100.0)   # Dominant topic probability (%)


# ── Main Response ─────────────────────────────────────────────────────────────

class VerificationResponse(BaseModel):
    verdict: Verdict
    confidence: float = Field(..., ge=0.0, le=100.0)
    final_score: float = Field(..., ge=0.0, le=100.0)
    layer1: Layer1Result
    layer2: Layer2Result
    entities: EntitiesResult
    sentiment: str
    emotion: str
    language: Language
    domain_credibility: Optional[DomainTier] = None
    input_type: str = "text"
    processing_time_ms: Optional[float] = None
    extracted_text: Optional[str] = Field(None, description="Raw text extracted from the URL / image / video for transparency")
    ocr_text: Optional[str] = Field(None, description="Text extracted from an image via OCR (when image_url was provided alongside text)")
    classifier_comparison: list[ClassifierComparisonEntry] = Field(
        default_factory=list,
        description="Per-classifier results from all classical ML models (BoW, TF-IDF, NB, LDA)",
    )
    lda_topic: Optional[LDATopicResult] = Field(
        None,
        description="Dominant LDA topic inferred for this text",
    )


# ── History / Trends ──────────────────────────────────────────────────────────

class HistoryEntry(BaseModel):
    id: str
    timestamp: str
    input_type: str
    text_preview: str
    verdict: Verdict
    confidence: float
    final_score: float


class HistoryResponse(BaseModel):
    total: int
    entries: list[HistoryEntry]


class TrendingEntity(BaseModel):
    entity: str
    entity_type: str  # person | org | location
    count: int
    fake_count: int
    fake_ratio: float


class TrendingTopic(BaseModel):
    topic: str
    count: int
    dominant_verdict: Verdict


class VerdictDayPoint(BaseModel):
    date: str          # YYYY-MM-DD
    credible: int = 0
    unverified: int = 0
    fake: int = 0


class TrendsResponse(BaseModel):
    top_entities: list[TrendingEntity]
    top_topics: list[TrendingTopic]
    verdict_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Counts per verdict: Credible, Unverified, Likely Fake",
    )
    verdict_by_day: list[VerdictDayPoint] = Field(
        default_factory=list,
        description="Day-by-day verdict counts for the area chart (last N days)",
    )


# ── Error ─────────────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
