/**
 * PhilVerify — Background Service Worker (Manifest V3)
 *
 * Responsibilities:
 *  - Proxy API calls to the PhilVerify FastAPI backend
 *  - File-based cache via chrome.storage.local (24-hour TTL, max 50 entries)
 *  - Maintain personal verification history
 *  - Respond to messages from content.js and popup.js
 *
 * Message types handled:
 *  VERIFY_TEXT  { text }        → VerificationResponse
 *  VERIFY_URL   { url }         → VerificationResponse
 *  GET_HISTORY  {}              → { history: HistoryEntry[] }
 *  GET_SETTINGS {}              → { apiBase, autoScan }
 *  SAVE_SETTINGS { apiBase, autoScan } → {}
 */

const CACHE_TTL_MS = 24 * 60 * 60 * 1000   // 24 hours
const MAX_HISTORY  = 50

// ── Default settings ──────────────────────────────────────────────────────────
const DEFAULT_SETTINGS = {
  apiBase:  'http://localhost:8000',
  autoScan: true,    // Automatically scan Facebook feed posts
}

// ── Utilities ─────────────────────────────────────────────────────────────────
/** Validate that a string is a safe http/https URL */
function isHttpUrl(str) {
  if (!str || typeof str !== 'string') return false
  try {
    const u = new URL(str)
    return u.protocol === 'http:' || u.protocol === 'https:'
  } catch { return false }
}
async function sha256prefix(text, len = 16) {
  const buf = await crypto.subtle.digest(
    'SHA-256',
    new TextEncoder().encode(text.trim().toLowerCase()),
  )
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
    .slice(0, len)
}

async function getSettings() {
  const stored = await chrome.storage.local.get('settings')
  return { ...DEFAULT_SETTINGS, ...(stored.settings ?? {}) }
}

// ── Cache helpers ─────────────────────────────────────────────────────────────

async function getCached(key) {
  const stored = await chrome.storage.local.get(key)
  const entry = stored[key]
  if (!entry) return null
  if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
    await chrome.storage.local.remove(key)
    return null
  }
  return entry.result
}

async function setCached(key, result, preview) {
  await chrome.storage.local.set({
    [key]: { result, timestamp: Date.now() },
  })

  // Prepend to history list
  const { history = [] } = await chrome.storage.local.get('history')
  const entry = {
    id:           key,
    timestamp:    new Date().toISOString(),
    text_preview: preview.slice(0, 80),
    verdict:      result.verdict,
    final_score:  result.final_score,
  }
  const updated = [entry, ...history.filter(h => h.id !== key)].slice(0, MAX_HISTORY)
  await chrome.storage.local.set({ history: updated })
}

// ── API calls ─────────────────────────────────────────────────────────────────

async function verifyText(text) {
  const key  = 'txt_' + await sha256prefix(text)
  const hit  = await getCached(key)
  if (hit) return { ...hit, _fromCache: true }

  const { apiBase } = await getSettings()
  const res = await fetch(`${apiBase}/verify/text`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ text }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `API error ${res.status}`)
  }
  const result = await res.json()
  await setCached(key, result, text)
  return result
}

async function verifyUrl(url) {
  const key = 'url_' + await sha256prefix(url)
  const hit = await getCached(key)
  if (hit) return { ...hit, _fromCache: true }

  const { apiBase } = await getSettings()
  const res = await fetch(`${apiBase}/verify/url`, {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ url }),
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail ?? `API error ${res.status}`)
  }
  const result = await res.json()
  await setCached(key, result, url)
  return result
}

// ── Message handler ───────────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  switch (msg.type) {

    case 'VERIFY_TEXT':
      verifyText(msg.text)
        .then(r  => sendResponse({ ok: true,  result: r }))
        .catch(e => sendResponse({ ok: false, error: e.message }))
      return true   // keep message channel open for async response

    case 'VERIFY_URL':
      if (!isHttpUrl(msg.url)) {
        sendResponse({ ok: false, error: 'Invalid URL: only http/https allowed' })
        return false
      }
      verifyUrl(msg.url)
        .then(r  => sendResponse({ ok: true,  result: r }))
        .catch(e => sendResponse({ ok: false, error: e.message }))
      return true

    case 'GET_HISTORY':
      chrome.storage.local.get('history')
        .then(({ history = [] }) => sendResponse({ history }))
      return true

    case 'GET_SETTINGS':
      getSettings().then(s => sendResponse(s))
      return true

    case 'SAVE_SETTINGS': {
      const incoming = msg.settings ?? {}
      // Validate apiBase is a safe URL before persisting
      if (incoming.apiBase && !isHttpUrl(incoming.apiBase)) {
        sendResponse({ ok: false, error: 'Invalid API URL: only http/https allowed' })
        return false
      }
      chrome.storage.local
        .set({ settings: incoming })
        .then(() => sendResponse({ ok: true }))
      return true
    }

    default:
      break
  }
})
