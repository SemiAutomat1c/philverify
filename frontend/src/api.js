/** PhilVerify API client — proxied through Vite to http://localhost:8000 */
const BASE = '/api'

async function post(path, body) {
    const res = await fetch(`${BASE}${path}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
    })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
    }
    return res.json()
}

async function postForm(path, formData) {
    const res = await fetch(`${BASE}${path}`, { method: 'POST', body: formData })
    if (!res.ok) {
        const err = await res.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${res.status}`)
    }
    return res.json()
}

async function get(path, params = {}) {
    const qs = new URLSearchParams(params).toString()
    const res = await fetch(`${BASE}${path}${qs ? '?' + qs : ''}`)
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
}

export const api = {
    verifyText: (text) => post('/verify/text', { text }),
    verifyUrl: (url) => post('/verify/url', { url }),
    verifyImage: (file) => { const f = new FormData(); f.append('file', file); return postForm('/verify/image', f) },
    verifyVideo: (file) => { const f = new FormData(); f.append('file', file); return postForm('/verify/video', f) },
    history: (params) => get('/history', params),
    trends: () => get('/trends'),
    health: () => get('/health'),
}
