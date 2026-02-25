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
    // Try common post message containers
    const msgSelectors = [
      '[data-ad-preview="message"]',
      '[data-testid="post_message"]',
      '[dir="auto"] > div > div > div > span',
      'div[style*="text-align"] span',
    ]
    for (const sel of msgSelectors) {
      const el = post.querySelector(sel)
      if (el?.innerText?.trim().length >= MIN_TEXT_LENGTH) {
        return el.innerText.trim().slice(0, 2000)
      }
    }
    // Fallback: gather all text spans ≥ MIN_TEXT_LENGTH chars
    const spans = Array.from(post.querySelectorAll('span'))
    for (const span of spans) {
      const t = span.innerText?.trim()
      if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http')) return t.slice(0, 2000)
    }
    return null
  }

  function extractPostUrl(post) {
    // Shared article links
    const linkSelectors = [
      'a[href*="l.facebook.com/l.php"]',       // Facebook link wrapper
      'a[target="_blank"][href^="https"]',       // Direct external links
      'a[aria-label][href*="facebook.com/watch"]', // Videos
    ]
    for (const sel of linkSelectors) {
      const el = post.querySelector(sel)
      if (el?.href) {
        try {
          const u = new URL(el.href)
          const dest = u.searchParams.get('u')  // Unwrap l.facebook.com redirect
          return dest || el.href
        } catch {
          return el.href
        }
      }
    }
    return null
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
      <a href="http://localhost:5173" target="_blank" rel="noreferrer" class="pv-open-full">
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
    // Find a stable injection point near the post actions bar
    const actionBar = post.querySelector('[data-testid="UFI2ReactionsCount/root"]')
      ?? post.querySelector('[aria-label*="reaction"]')
      ?? post.querySelector('[role="toolbar"]')
      ?? post

    const container = document.createElement('div')
    container.className = 'pv-badge-wrap'
    const badge = createBadge(result.verdict, result.final_score, result)
    container.appendChild(badge)

    // Insert before the action bar, or append inside the post
    if (actionBar && actionBar !== post) {
      actionBar.insertAdjacentElement('beforebegin', container)
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

    const text = extractPostText(post)
    const url  = extractPostUrl(post)

    if (!text && !url) return              // nothing to verify

    const loader = injectLoadingBadge(post)

    try {
      const response = await new Promise((resolve, reject) => {
        const msg = url
          ? { type: 'VERIFY_URL', url  }
          : { type: 'VERIFY_TEXT', text }
        chrome.runtime.sendMessage(msg, (resp) => {
          if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message))
          else if (!resp?.ok)           reject(new Error(resp?.error ?? 'Unknown error'))
          else                          resolve(resp.result)
        })
      })

      loader.remove()
      injectBadgeIntoPost(post, response)
    } catch (err) {
      loader.remove()
      // Show a muted error indicator — don't block reading
      const errBadge = document.createElement('div')
      errBadge.className = 'pv-badge-wrap'
      const errInner = document.createElement('div')
      errInner.className = 'pv-badge pv-badge--error'
      errInner.title = err.message   // .title setter is XSS-safe
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

  // React to autoScan toggle without requiring page reload
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
