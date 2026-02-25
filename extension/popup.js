/**
 * PhilVerify — Popup Script
 * Controls the extension popup: verify tab, history tab, settings tab.
 */
'use strict'

// ── Constants ─────────────────────────────────────────────────────────────────

const VERDICT_COLORS = {
  'Credible':    '#16a34a',
  'Unverified':  '#d97706',
  'Likely Fake': '#dc2626',
}

// ── Helpers ───────────────────────────────────────────────────────────────────
/** Escape HTML special chars to prevent XSS in innerHTML templates */
function safeText(str) {
  if (str == null) return ''
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
}

/** Allow only http/https URLs; return '#' for anything else */
function safeUrl(url) {
  if (!url) return '#'
  try {
    const u = new URL(url)
    return (u.protocol === 'http:' || u.protocol === 'https:') ? u.href : '#'
  } catch { return '#' }
}
function msg(obj) {
  return new Promise(resolve => {
    chrome.runtime.sendMessage(obj, resolve)
  })
}

function timeAgo(iso) {
  const diff = Date.now() - new Date(iso).getTime()
  if (diff < 60_000)   return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}

function isUrl(s) {
  try { new URL(s); return s.startsWith('http'); } catch { return false }
}

// ── Render helpers ────────────────────────────────────────────────────────────

function renderResult(result, container) {
  const color = VERDICT_COLORS[result.verdict] ?? '#5c554e'
  const topSource = result.layer2?.sources?.[0]

  container.innerHTML = `
    <div class="result" role="status" aria-live="polite">
      <div class="result-verdict" style="color:${color}">${safeText(result.verdict)}</div>
      <div class="result-score">${Math.round(result.final_score)}% credibility${result._fromCache ? ' (cached)' : ''}</div>
      <div class="result-row">
        <span class="result-label">Language</span>
        <span class="result-val">${safeText(result.language ?? '—')}</span>
      </div>
      <div class="result-row">
        <span class="result-label">Confidence</span>
        <span class="result-val" style="color:${color}">${result.confidence?.toFixed(1)}%</span>
      </div>
      ${result.layer1?.triggered_features?.length ? `
      <div class="result-row">
        <span class="result-label">Signals</span>
        <span class="result-val">${result.layer1.triggered_features.slice(0, 3).map(safeText).join(', ')}</span>
      </div>` : ''}
      ${topSource ? `
      <div class="result-source">
        <div class="result-label" style="margin-bottom:4px;">Top Source</div>
        <a href="${safeUrl(topSource.url)}" target="_blank" rel="noreferrer">${safeText(topSource.title?.slice(0, 55) ?? topSource.source_name ?? 'View')} ↗</a>
      </div>` : ''}
      <a class="open-full" href="https://philverify.web.app" target="_blank" rel="noreferrer">
        Open Full Dashboard ↗
      </a>
    </div>
  `
}

function renderHistory(entries, container) {
  if (!entries.length) {
    container.innerHTML = '<div class="state-empty">No verifications yet.</div>'
    return
  }
  container.innerHTML = `
    <ul class="history-list" role="list" aria-label="Verification history">
      ${entries.map(e => {
        const color = VERDICT_COLORS[e.verdict] ?? '#5c554e'
        return `
          <li class="history-item" role="listitem">
            <div class="history-item-top">
              <span class="history-verdict" style="background:${color}22;color:${color};border:1px solid ${color}4d;">${safeText(e.verdict)}</span>
              <span class="history-score">${Math.round(e.final_score)}%</span>
            </div>
            <div class="history-preview">${safeText(e.text_preview || '—')}</div>
            <div class="history-time">${timeAgo(e.timestamp)}</div>
          </li>`
      }).join('')}
    </ul>
  `
}

// ── Tab switching ─────────────────────────────────────────────────────────────

document.querySelectorAll('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    document.querySelectorAll('.tab').forEach(t => {
      t.classList.remove('active')
      t.setAttribute('aria-selected', 'false')
    })
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'))
    tab.classList.add('active')
    tab.setAttribute('aria-selected', 'true')
    document.getElementById(`panel-${tab.dataset.tab}`)?.classList.add('active')
    if (tab.dataset.tab === 'history') loadHistory()
    if (tab.dataset.tab === 'settings') loadSettings()
  })
})

// ── Verify tab ────────────────────────────────────────────────────────────────

const verifyInput  = document.getElementById('verify-input')
const btnVerify    = document.getElementById('btn-verify')
const verifyResult = document.getElementById('verify-result')
const currentUrlEl = document.getElementById('current-url')

// Auto-populate input with current tab URL if it's a news article
chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
  const url = tab?.url ?? ''
  if (url && !url.startsWith('chrome') && !url.includes('facebook.com')) {
    currentUrlEl.textContent = url
    currentUrlEl.title = url
    verifyInput.value = url
  } else {
    currentUrlEl.textContent = 'facebook.com — use text input below'
  }
})

btnVerify.addEventListener('click', async () => {
  const raw = verifyInput.value.trim()
  if (!raw) return

  btnVerify.disabled = true
  btnVerify.setAttribute('aria-busy', 'true')
  btnVerify.textContent = 'Verifying…'
  verifyResult.innerHTML = `
    <div class="state-loading" aria-live="polite">
      <div class="spinner" aria-hidden="true"></div><br>Analyzing claim…
    </div>`

  const type = isUrl(raw) ? 'VERIFY_URL' : 'VERIFY_TEXT'
  const payload = type === 'VERIFY_URL' ? { type, url: raw } : { type, text: raw }
  const resp = await msg(payload)

  btnVerify.disabled = false
  btnVerify.setAttribute('aria-busy', 'false')
  btnVerify.textContent = 'Verify Claim'

  if (resp?.ok) {
    renderResult(resp.result, verifyResult)
  } else {
    verifyResult.innerHTML = `
      <div class="state-error" role="alert">
        ${resp?.error ?? 'Could not reach PhilVerify backend.'}<br>
        <span style="font-size:10px;color:var(--text-muted)">Is the backend running at your configured API URL?</span>
      </div>`
  }
})

// Allow Enter (single line) to trigger verify when text area is focused on Ctrl+Enter
verifyInput.addEventListener('keydown', e => {
  if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
    e.preventDefault()
    btnVerify.click()
  }
})

// ── History tab ───────────────────────────────────────────────────────────────

async function loadHistory() {
  const container = document.getElementById('history-container')
  container.innerHTML = '<div class="state-loading"><div class="spinner"></div><br>Loading…</div>'
  const resp = await msg({ type: 'GET_HISTORY' })
  renderHistory(resp?.history ?? [], container)
}

// ── Settings tab ──────────────────────────────────────────────────────────────

async function loadSettings() {
  const resp = await msg({ type: 'GET_SETTINGS' })
  if (!resp) return
  document.getElementById('api-base').value    = resp.apiBase  ?? 'http://localhost:8000'
  document.getElementById('auto-scan').checked = resp.autoScan ?? true
}

document.getElementById('btn-save').addEventListener('click', async () => {
  const settings = {
    apiBase:  document.getElementById('api-base').value.trim() || 'http://localhost:8000',
    autoScan: document.getElementById('auto-scan').checked,
  }
  await msg({ type: 'SAVE_SETTINGS', settings })

  const flash = document.getElementById('saved-flash')
  flash.textContent = 'Saved ✓'
  setTimeout(() => { flash.textContent = '' }, 2000)
})

// ── API status check ──────────────────────────────────────────────────────────

async function checkApiStatus() {
  const dot   = document.getElementById('api-status-dot')
  const label = document.getElementById('api-status-label')
  try {
    const { apiBase } = await msg({ type: 'GET_SETTINGS' })
    const res = await fetch(`${apiBase ?? 'http://localhost:8000'}/health`, { signal: AbortSignal.timeout(3000) })
    if (res.ok) {
      dot.style.background   = 'var(--credible)'
      label.style.color      = 'var(--credible)'
      label.textContent      = 'ONLINE'
    } else {
      throw new Error(`${res.status}`)
    }
  } catch {
    dot.style.background  = 'var(--fake)'
    label.style.color     = 'var(--fake)'
    label.textContent     = 'OFFLINE'
  }
}

checkApiStatus()
