/**
 * PhilVerify Frontend Type Definitions
 * Mirrors the Pydantic models defined in api/schemas.py
 */

// ── Input types ────────────────────────────────────────────────────────────────

export interface VerifyTextRequest {
  text: string
}

export interface VerifyUrlRequest {
  url: string
}

// ── Layer 1 (TF-IDF classifier) ────────────────────────────────────────────────

export interface Layer1Result {
  verdict: Verdict
  score: number          // 0–100 credibility score
  confidence: number     // 0–100%
  triggered_features: string[]
  explanation: string
}

// ── Layer 2 (Evidence retrieval) ───────────────────────────────────────────────

export interface SourceArticle {
  title: string
  url: string
  source_name: string
  similarity: number
  published_at?: string
  credibility_score?: number
}

export interface Layer2Result {
  sources: SourceArticle[]
  stance: 'supporting' | 'contradicting' | 'neutral' | string
  evidence_score: number     // 0–100
}

// ── Verification response ──────────────────────────────────────────────────────

export type Verdict = 'Credible' | 'Unverified' | 'Likely Fake'
export type InputType = 'text' | 'url' | 'image' | 'video'

export interface VerificationResponse {
  text_preview: string
  language: string
  verdict: Verdict
  final_score: number        // 0–100 final credibility score
  confidence: number         // 0–100%
  layer1: Layer1Result
  layer2: Layer2Result
  timestamp: string          // ISO 8601
  input_type?: InputType
  /** Present only in extension cached results */
  _fromCache?: boolean
}

// ── History ────────────────────────────────────────────────────────────────────

export interface HistoryEntry {
  id: string
  text_preview: string
  verdict: Verdict
  final_score: number
  language?: string
  timestamp: string          // ISO 8601
  input_type?: InputType
}

export interface HistoryParams {
  limit?: number
  offset?: number
  verdict?: Verdict
}

export interface HistoryResponse {
  items: HistoryEntry[]
  total: number
  limit: number
  offset: number
}

// ── Trends ─────────────────────────────────────────────────────────────────────

export interface TrendingEntity {
  entity: string
  count: number
}

export interface TrendingTopic {
  topic: string
  count: number
}

export interface VerdictDayPoint {
  date: string               // YYYY-MM-DD
  credible: number
  unverified: number
  fake: number
}

export interface TrendsResponse {
  top_entities: TrendingEntity[]
  top_topics: TrendingTopic[]
  verdict_distribution: Record<Verdict, number>
  verdict_by_day: VerdictDayPoint[]
}

// ── Health ─────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: 'ok' | 'degraded' | 'error'
  version: string
  models_loaded: boolean
  firestore_connected: boolean
}

// ── API error ──────────────────────────────────────────────────────────────────

export class ApiError extends Error {
  /** True when the backend responded (HTTP error), false for network failures */
  readonly isBackendError: boolean

  constructor(message: string, isBackendError = false) {
    super(message)
    this.name = 'ApiError'
    this.isBackendError = isBackendError
  }
}
