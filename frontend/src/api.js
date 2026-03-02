/** PhilVerify API client
 * Dev:        Vite proxies /api → http://localhost:8000
 * Production: Set VITE_API_BASE_URL to your backend URL (e.g. HF Space)
 */
const BASE = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/$/, '') || '/api'

function _detailToString(detail, status) {
    if (!detail) return `HTTP ${status}`
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) {
        // FastAPI validation errors: [{loc, msg, type}, ...]
        return detail.map(d => d.msg || JSON.stringify(d)).join('; ')
    }
    return JSON.stringify(detail)
}

async function post(path, body) {
    const res = await fetch(`${BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        const e = new Error(_detailToString(err.detail, res.status))
        e.isBackendError = true   // backend responded — not a connection failure
        throw e
    }
    return res.json()
}

async function postForm(path, formData) {
    const res = await fetch(`${BASE}${path}`, { method: 'POST', body: formData })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(_detailToString(err.detail, res.status))
    }
    return res.json()
}

async function get(path, params = {}) {
    const qs = new URLSearchParams(params).toString()
    const res = await fetch(`${BASE}${path}${qs ? '?' + qs : ''}`)
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(_detailToString(err.detail, res.status))
    }
    return res.json().catch(() => {
        throw new Error('API returned an unexpected response — the server may be starting up. Please try again.')
    })
}

export const api = {
    verifyText: (text) => post('/verify/text', { text }),
    verifyUrl: (url) => post('/verify/url', { url }),
    verifyImage: (file) => { const f = new FormData(); f.append('file', file); return postForm('/verify/image', f) },
    verifyVideo: (file) => { const f = new FormData(); f.append('file', file); return postForm('/verify/video', f) },
    history: (params) => get('/history', params),
    historyDetail: (id) => get(`/history/${id}`),
    trends: () => get('/trends'),
    health: () => get('/health'),
    preview: (url) => get('/preview', { url }),
}
