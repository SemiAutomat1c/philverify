/**
 * PhilVerify API client — proxied through Vite to http://localhost:8000
 * Typed via src/types.ts which mirrors api/schemas.py
 */
import type {
  VerificationResponse,
  HistoryParams,
  HistoryResponse,
  TrendsResponse,
  HealthResponse,
  ApiError as ApiErrorType,
} from './types'
import { ApiError } from './types'

const BASE = '/api'

// ── Internal fetch helpers ─────────────────────────────────────────────────────

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new ApiError(err.detail ?? `HTTP ${res.status}`, true)
  }
  return res.json() as Promise<T>
}

async function postForm<T>(path: string, formData: FormData): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: 'POST', body: formData })
  if (!res.ok) {
    const err = await res.json().catch(() => ({})) as { detail?: string }
    throw new ApiError(err.detail ?? `HTTP ${res.status}`, true)
  }
  return res.json() as Promise<T>
}

async function get<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const defined = Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined),
  ) as Record<string, string>
  const qs = new URLSearchParams(defined).toString()
  const res = await fetch(`${BASE}${path}${qs ? '?' + qs : ''}`)
  if (!res.ok) throw new ApiError(`HTTP ${res.status}`)
  return res.json() as Promise<T>
}

// ── Public API surface ─────────────────────────────────────────────────────────

export const api = {
  verifyText: (text: string): Promise<VerificationResponse> =>
    post('/verify/text', { text }),

  verifyUrl: (url: string): Promise<VerificationResponse> =>
    post('/verify/url', { url }),

  verifyImage: (file: File): Promise<VerificationResponse> => {
    const f = new FormData()
    f.append('file', file)
    return postForm('/verify/image', f)
  },

  verifyVideo: (file: File): Promise<VerificationResponse> => {
    const f = new FormData()
    f.append('file', file)
    return postForm('/verify/video', f)
  },

  history: (params?: HistoryParams): Promise<HistoryResponse> =>
    get('/history', params as Record<string, string | number | undefined>),

  trends: (): Promise<TrendsResponse> =>
    get('/trends'),

  health: (): Promise<HealthResponse> =>
    get('/health'),
} as const

// Re-export error class for consumers
export { ApiError } from './types'
export type { ApiErrorType }
