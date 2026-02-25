/**
 * PhilVerify — Content Script (Facebook feed scanner)
 *
 * Watches the Facebook feed via MutationObserver.
 * For each new post that appears:
 *   1. Extracts the post text or shared URL
 *   2. Sends to background.js for verification (with cache)
 *   3. Injects a credibility badge overlay onto the post card
 *
 * Badge click → opens an inline detail panel with verdict, score, and top source.
 *
 * Uses `data-philverify` attribute to mark already-processed posts.
 */

;(function philverifyContentScript() {
  'use strict'

  // ── Config ────────────────────────────────────────────────────────────────

  /** Minimum text length to send for verification (avoids verifying 1-word posts) */
  const MIN_TEXT_LENGTH = 40

  /**
   * Facebook feed post selectors — ordered by reliability.
   * Facebook's class names are obfuscated; structural role/data attributes are
   * more stable across renames.
   */
  const POST_SELECTORS = [
    '[data-pagelet^="FeedUnit"]',
    '[data-pagelet^="GroupsFeedUnit"]',
    '[role="article"]',
    '[data-testid="post_message"]',
  ]

  const VERDICT_COLORS = {
    'Credible':    '#16a34a',
    'Unverified':  '#d97706',
    'Likely Fake': '#dc2626',
  }
  const VERDICT_LABELS = {
    'Credible':    '✓ Credible',
    'Unverified':  '? Unverified',
    'Likely Fake': '✗ Likely Fake',
  }

  // ── Utilities ─────────────────────────────────────────────────────────────

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

  function extractPostText(post) {
    for (const sel of CFG.text) {
      const el = post.querySelector(sel)
      if (el?.innerText?.trim().length >= MIN_TEXT_LENGTH)
        return el.innerText.trim().slice(0, 2000)
    }
    // Fallback: any span with substantial text
    for (const span of post.querySelectorAll('span')) {
      const t = span.innerText?.trim()
      if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http')) return t.slice(0, 2000)
    }
    return null
  }

  function extractPostUrl(post) {
    for (const sel of CFG.link) {
      const el = post.querySelector(sel)
      if (el?.href) return CFG.unwrapUrl(el)
    }
    return null
  }

  /** Returns the src of the most prominent image in a post, or null. */
  function extractPostImage(post) {
    if (!CFG.image) return null
    // Prefer largest image by rendered width
    const imgs = Array.from(post.querySelectorAll(CFG.image))
    if (!imgs.length) return null
    const best = imgs.reduce((a, b) =>
      (b.naturalWidth || b.width || 0) > (a.naturalWidth || a.width || 0) ? b : a
    )
    const src = best.src || best.dataset?.src
    if (!src || !src.startsWith('http')) return null
    return src
  }

  function genPostId(post) {
    // Use aria-label prefix + UUID for stable, unique ID
    // Avoids offsetTop which forces a synchronous layout read
    const label = (post.getAttribute('aria-label') ?? '').replace(/\W/g, '').slice(0, 20)
    return 'pv_' + label + crypto.randomUUID().replace(/-/g, '').slice(0, 12)
  }

  // ── Badge rendering ───────────────────────────────────────────────────────

  function createBadge(verdict, score, result) {
    const color = VERDICT_COLORS[verdict] ?? '#5c554e'
    const label = VERDICT_LABELS[verdict] ?? verdict

    const wrap = document.createElement('div')
    wrap.className = 'pv-badge'
    wrap.setAttribute('role', 'status')
    wrap.setAttribute('aria-label', `PhilVerify: ${label} — ${Math.round(score)}% credibility score`)
    wrap.style.cssText = `
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 4px 10px;
      border-radius: 3px;
      border: 1px solid ${color}4d;
      background: ${color}14;
      cursor: pointer;
      font-family: system-ui, sans-serif;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.04em;
      color: ${color};
      touch-action: manipulation;
      -webkit-tap-highlight-color: transparent;
      position: relative;
      z-index: 10;
    `

    const dot = document.createElement('span')
    dot.style.cssText = `
      width: 7px; height: 7px;
      border-radius: 50%;
      background: ${color};
      flex-shrink: 0;
    `

    const text = document.createElement('span')
    text.textContent = `${label}  ${Math.round(score)}%`

    const cacheTag = result._fromCache
      ? (() => { const t = document.createElement('span'); t.textContent = '·cached'; t.style.cssText = `opacity:0.5;font-size:9px;`; return t })()
      : null

    wrap.appendChild(dot)
    wrap.appendChild(text)
    if (cacheTag) wrap.appendChild(cacheTag)

    // Click → toggle detail panel
    wrap.addEventListener('click', (e) => {
      e.stopPropagation()
      toggleDetailPanel(wrap, result)
    })

    return wrap
  }

  function toggleDetailPanel(badge, result) {
    const existing = badge.parentElement?.querySelector('.pv-detail')
    if (existing) { existing.remove(); return }

    const panel = document.createElement('div')
    panel.className = 'pv-detail'
    panel.setAttribute('role', 'dialog')
    panel.setAttribute('aria-label', 'PhilVerify fact-check details')

    const color = VERDICT_COLORS[result.verdict] ?? '#5c554e'
    const topSource = result.layer2?.sources?.[0]

    panel.innerHTML = `
      <div class="pv-detail-header">
        <span class="pv-logo">PHIL<span style="color:${color}">VERIFY</span></span>
        <button class="pv-close" aria-label="Close fact-check panel">✕</button>
      </div>
      <div class="pv-row">
        <span class="pv-label">VERDICT</span>
        <span class="pv-val" style="color:${color};font-weight:700">${safeText(result.verdict)}</span>
      </div>
      <div class="pv-row">
        <span class="pv-label">SCORE</span>
        <span class="pv-val" style="color:${color}">${Math.round(result.final_score)}%</span>
      </div>
      <div class="pv-row">
        <span class="pv-label">LANGUAGE</span>
        <span class="pv-val">${safeText(result.language ?? '—')}</span>
      </div>
      ${result.layer1?.triggered_features?.length ? `
      <div class="pv-signals">
        <span class="pv-label">SIGNALS</span>
        <div class="pv-tags">
          ${result.layer1.triggered_features.slice(0, 3).map(f =>
            `<span class="pv-tag">${safeText(f)}</span>`
          ).join('')}
        </div>
      </div>` : ''}
      ${topSource ? `
      <div class="pv-source">
        <span class="pv-label">TOP SOURCE</span>
        <a href="${safeUrl(topSource.url)}" target="_blank" rel="noreferrer" class="pv-source-link">
          ${safeText(topSource.title?.slice(0, 60) ?? topSource.source_name ?? 'View source')} ↗
        </a>
      </div>` : ''}
      <a href="https://philverify.web.app" target="_blank" rel="noreferrer" class="pv-open-full">
        Open full analysis ↗
      </a>
    `

    panel.querySelector('.pv-close').addEventListener('click', (e) => {
      e.stopPropagation()
      panel.remove()
    })

    badge.insertAdjacentElement('afterend', panel)
  }

  function injectBadgeIntoPost(post, result) {
    // Find a stable injection point — platform-specific
    let anchor = null
    if (PLATFORM === 'facebook') {
      anchor = post.querySelector('[data-testid="UFI2ReactionsCount/root"]')
        ?? post.querySelector('[aria-label*="reaction"]')
        ?? post.querySelector('[role="toolbar"]')
    } else if (PLATFORM === 'twitter') {
      // Tweet action bar (reply / retweet / like row)
      anchor = post.querySelector('[role="group"][aria-label]')
        ?? post.querySelector('[data-testid="reply"]')?.closest('[role="group"]')
    }

    const container = document.createElement('div')
    container.className = 'pv-badge-wrap'
    const badge = createBadge(result.verdict, result.final_score, result)
    container.appendChild(badge)

    if (anchor && anchor !== post) {
      anchor.insertAdjacentElement('beforebegin', container)
    } else {
      post.appendChild(container)
    }
  }

  // ── Loading state ─────────────────────────────────────────────────────────

  function injectLoadingBadge(post) {
    const container = document.createElement('div')
    container.className = 'pv-badge-wrap pv-loading'
    container.setAttribute('aria-label', 'PhilVerify: verifying…')
    container.innerHTML = `
      <div class="pv-badge pv-badge--loading">
        <span class="pv-spinner" aria-hidden="true"></span>
        <span>Verifying…</span>
      </div>
    `
    post.appendChild(container)
    return container
  }

  // ── Post processing ───────────────────────────────────────────────────────

  async function processPost(post) {
    if (post.dataset.philverify) return    // already processed
    const id = genPostId(post)
    post.dataset.philverify = id

    const text  = extractPostText(post)
    const url   = extractPostUrl(post)
    const image = extractPostImage(post)

    // Need at least one signal to verify
    if (!text && !url && !image) return

    const loader = injectLoadingBadge(post)

    try {
      let msgPayload
      if (url) {
        // A shared article link is the most informative signal
        msgPayload = { type: 'VERIFY_URL', url }
      } else if (text) {
        // Caption / tweet text
        msgPayload = { type: 'VERIFY_TEXT', text }
      } else {
        // Image-only post — send to OCR endpoint
        msgPayload = { type: 'VERIFY_IMAGE_URL', imageUrl: image }
      }

      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(msgPayload, (resp) => {
          if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message))
          else if (!resp?.ok)           reject(new Error(resp?.error ?? 'Unknown error'))
          else                          resolve(resp.result)
        })
      })

      loader.remove()
      injectBadgeIntoPost(post, response)
    } catch (err) {
      loader.remove()
      const errBadge = document.createElement('div')
      errBadge.className = 'pv-badge-wrap'
      const errInner = document.createElement('div')
      errInner.className = 'pv-badge pv-badge--error'
      errInner.title = err.message
      errInner.textContent = '⚠ PhilVerify offline'
      errBadge.appendChild(errInner)
      post.appendChild(errBadge)
    }
  }

  // ── MutationObserver ──────────────────────────────────────────────────────

  const pendingPosts = new Set()
  let rafScheduled = false

  function flushPosts() {
    rafScheduled = false
    for (const post of pendingPosts) processPost(post)
    pendingPosts.clear()
  }

  function scheduleProcess(post) {
    pendingPosts.add(post)
    if (!rafScheduled) {
      rafScheduled = true
      requestAnimationFrame(flushPosts)
    }
  }

  function findPosts(root) {
    for (const sel of POST_SELECTORS) {
      const found = root.querySelectorAll(sel)
      if (found.length) return found
    }
    return []
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== 1) continue   // element nodes only
        // Check if the node itself matches
        for (const sel of POST_SELECTORS) {
          if (node.matches?.(sel)) { scheduleProcess(node); break }
        }
        // Check descendants
        const posts = findPosts(node)
        for (const post of posts) scheduleProcess(post)
      }
    }
  })

  // ── Initialization ────────────────────────────────────────────────────────

  async function init() {
    // Check autoScan setting before activating
    const response = await new Promise(resolve => {
      chrome.runtime.sendMessage({ type: 'GET_SETTINGS' }, resolve)
    }).catch(() => ({ autoScan: true }))

    if (!response?.autoScan) return

    // Process any posts already in the DOM
    const existing = findPosts(document.body)
    for (const post of existing) scheduleProcess(post)

    // Watch for new posts (Facebook is a SPA — feed dynamically loads more)
    observer.observe(document.body, { childList: true, subtree: true })
  }

  init()

  // ── Auto-verify news article pages (non-social) ────────────────────────────
  // When the content script runs on a PH news site (not the homepage),
  // it auto-verifies the current URL and injects a floating verdict banner.

  async function autoVerifyPage() {
    const url  = window.location.href
    const path = new URL(url).pathname
    // Skip homepages and section indexes (very short paths like / or /news)
    if (!path || path.length < 8 || path.split('/').filter(Boolean).length < 2) return

    const banner = document.createElement('div')
    banner.id = 'pv-auto-banner'
    banner.setAttribute('role', 'status')
    banner.setAttribute('aria-live', 'polite')
    banner.style.cssText = [
      'position:fixed;top:0;left:0;right:0;z-index:2147483647',
      'background:#141414;border-bottom:2px solid rgba(220,38,38,0.4)',
      'padding:7px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px',
      'font-family:system-ui,sans-serif;font-size:11px;color:#a89f94',
      'box-shadow:0 2px 16px rgba(0,0,0,0.6)',
    ].join(';')

    banner.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden;">
        <span style="font-weight:800;letter-spacing:0.1em;color:#f5f0e8;flex-shrink:0;">
          PHIL<span style="color:#dc2626">VERIFY</span>
        </span>
        <span id="pv-auto-status" style="display:flex;align-items:center;gap:6px;overflow:hidden;">
          <span class="pv-spinner" aria-hidden="true"></span>
          <span style="white-space:nowrap;">Verifying article…</span>
        </span>
      </div>
      <div style="display:flex;align-items:center;gap:8px;flex-shrink:0;">
        <a id="pv-open-full"
           href="https://philverify.web.app"
           target="_blank"
           rel="noreferrer"
           style="color:#dc2626;font-size:9px;font-weight:700;letter-spacing:0.1em;text-decoration:none;border:1px solid rgba(220,38,38,0.35);padding:3px 8px;border-radius:2px;white-space:nowrap;"
           aria-label="Open PhilVerify dashboard">
          FULL ANALYSIS ↗
        </a>
        <button id="pv-close-banner"
          style="background:none;border:none;color:#5c554e;cursor:pointer;font-size:13px;padding:2px 4px;line-height:1;flex-shrink:0;"
          aria-label="Dismiss PhilVerify banner">✕</button>
      </div>
    `

    document.body.insertAdjacentElement('afterbegin', banner)
    // Push page content down so banner doesn't overlap
    document.documentElement.style.marginTop = '36px'

    document.getElementById('pv-close-banner').addEventListener('click', () => {
      banner.remove()
      document.documentElement.style.marginTop = ''
    })

    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'VERIFY_URL', url }, (resp) => {
          if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message))
          else if (!resp?.ok)           reject(new Error(resp?.error ?? 'Unknown error'))
          else                          resolve(resp.result)
        })
      })

      const color   = VERDICT_COLORS[response.verdict] ?? '#5c554e'
      const statusEl = document.getElementById('pv-auto-status')
      if (statusEl) {
        statusEl.innerHTML = `
          <span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;" aria-hidden="true"></span>
          <span style="color:${color};font-weight:700;">${safeText(response.verdict)}</span>
          <span style="color:#5c554e;margin-left:2px;">${Math.round(response.final_score)}% credibility</span>
          ${response.layer1?.triggered_features?.length
            ? `<span style="color:#5c554e;margin-left:4px;font-size:9px;">· ${safeText(response.layer1.triggered_features[0])}</span>`
            : ''}
        `
      }
      banner.style.borderBottomColor = color + '88'
      // Update full-analysis link to deep-link with the URL pre-filled
      const fullLink = document.getElementById('pv-open-full')
      if (fullLink) fullLink.href = `https://philverify.web.app`

      // Auto-dismiss if credible and user hasn't interacted
      if (response.verdict === 'Credible') {
        setTimeout(() => {
          if (document.contains(banner)) {
            banner.remove()
            document.documentElement.style.marginTop = ''
          }
        }, 5000)
      }
    } catch (_) {
      banner.remove()
      document.documentElement.style.marginTop = ''
    }
  }

  if (!IS_SOCIAL) {
    autoVerifyPage()
  }
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local' || !changes.settings) return
    const autoScan = changes.settings.newValue?.autoScan
    if (autoScan === false) {
      observer.disconnect()
    } else if (autoScan === true) {
      observer.observe(document.body, { childList: true, subtree: true })
      // Process any posts that appeared while scanning was paused
      const existing = findPosts(document.body)
      for (const post of existing) scheduleProcess(post)
    }
  })

})()
