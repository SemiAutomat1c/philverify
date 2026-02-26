/**
 * PhilVerify — Content Script (Twitter/X + Facebook feed scanner)
 *
 * Click-triggered verification model:
 *   1. Watches for posts via MutationObserver (infinite scroll support)
 *   2. Injects a floating "Verify this post" button on each post that has content
 *   3. On click: extracts caption + image, sends to background.js → PhilVerify API
 *   4. Displays a full inline verification report (verdict, confidence, evidence, etc.)
 *
 * Skips posts with no text AND no image. Never injects on comments.
 * Uses `data-philverify-btn` attribute to prevent duplicate buttons.
 */

; (function philverifyContentScript() {
  'use strict'

  // ── Config ────────────────────────────────────────────────────────────────

  /** Minimum text length to send for verification (avoids verifying 1-word posts) */
  const MIN_TEXT_LENGTH = 40

  /** Minimum image dimension (px) to consider a real content image (filters avatars/icons) */
  const MIN_IMAGE_SIZE = 100

  /** Enable debug logging to console */
  const DEBUG = true
  function log(...args) { if (DEBUG) console.log('[PhilVerify]', ...args) }
  function warn(...args) { if (DEBUG) console.warn('[PhilVerify]', ...args) }

  // ── Platform detection ────────────────────────────────────────────────────

  const PLATFORM = (() => {
    const h = window.location.hostname
    if (h.includes('facebook.com')) return 'facebook'
    if (h.includes('x.com') || h.includes('twitter.com')) return 'twitter'
    return 'news'
  })()

  const IS_SOCIAL = PLATFORM === 'facebook' || PLATFORM === 'twitter'

  // ── Platform-specific selectors ───────────────────────────────────────────
  // Stored in a single config object for easy maintenance when platforms
  // update their DOM. Prefer data-testid / role attributes over class names.

  const PLATFORM_CFG = {
    facebook: {
      // Facebook's DOM is intentionally unstable. The most reliable anchor is
      // [role="feed"] — the WAI-ARIA feed landmark required for accessibility.
      // Direct children of the feed container are always posts (wrapped in divs),
      // while comments are nested deeper inside each post's [role="article"].
      //
      // We do NOT rely on data-pagelet attributes — Facebook removed/renamed them.
      // [role="article"] is used as a last-resort fallback with extra filtering.
      post: [
        '[role="article"]',   // Filtered by findPosts() — only feed-level articles
      ],
      // Text selectors ordered by specificity
      text: [
        '[data-ad-comet-preview="message"]',
        '[data-testid="post_message"]',
      ],
      // Exclude avatars explicitly: fbcdn images that are NOT inside avatar
      // containers, and are large enough to be actual post content.
      image: 'img[src*="fbcdn"]',
      // Selectors for containers known to hold avatar images — used to filter them out
      avatarContainers: [
        '[data-testid="profile_photo_image"]',
        'a[aria-label*="profile picture"]',
        'svg image',                // avatar circles rendered in SVG
        '[role="img"][aria-label]',  // decorative profile icons
      ],
      link: ['a[href*="l.facebook.com/l.php"]', 'a[role="link"][href*="http"]'],
      unwrapUrl(el) {
        try { return new URL(el.href).searchParams.get('u') || el.href } catch { return el.href }
      },
    },
    twitter: {
      post: ['article[data-testid="tweet"]'],
      text: ['[data-testid="tweetText"]'],
      // pbs.twimg.com/media is specifically for tweet media, NOT profile avatars
      // (avatars use pbs.twimg.com/profile_images)
      image: 'img[src*="pbs.twimg.com/media"]',
      avatarContainers: [
        '[data-testid="Tweet-User-Avatar"]',
      ],
      link: ['a[href*="t.co/"]', 'a[data-testid="card.layoutSmall.media"]'],
      unwrapUrl(el) { return el.href },
    },
    news: {
      post: ['[role="article"]', 'article', 'main'],
      text: ['h1', '.article-body', '.entry-content', 'article'],
      image: null,
      avatarContainers: [],
      link: [],
      unwrapUrl(el) { return el.href },
    },
  }

  const CFG = PLATFORM_CFG[PLATFORM] ?? PLATFORM_CFG.facebook
  const POST_SELECTORS = CFG.post

  // ── Verdict colors & labels ───────────────────────────────────────────────

  const VERDICT_COLORS = {
    'Credible': '#16a34a',
    'Unverified': '#d97706',
    'Likely Fake': '#dc2626',
  }
  const VERDICT_LABELS = {
    'Credible': '✓ Credible',
    'Unverified': '? Unverified',
    'Likely Fake': '✗ Likely Fake',
  }
  const VERDICT_BG = {
    'Credible': 'rgba(22, 163, 74, 0.12)',
    'Unverified': 'rgba(217, 119, 6, 0.12)',
    'Likely Fake': 'rgba(220, 38, 38, 0.12)',
  }

  // ── Utilities ─────────────────────────────────────────────────────────────

  /** Escape HTML special chars to prevent XSS */
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

  // ── Content extraction ────────────────────────────────────────────────────

  /**
   * Try to expand Facebook's "See more" truncation before extracting text.
   * Clicks the "See more" link if found. Only targets known truncation patterns.
   */
  function expandSeeMore(post) {
    if (PLATFORM === 'facebook') {
      // Facebook uses div[role="button"] or <span> with "See more" / "See More"
      const buttons = post.querySelectorAll('[role="button"]')
      for (const btn of buttons) {
        const txt = btn.textContent?.trim()
        if (txt && /^see\s*more$/i.test(txt) && btn.offsetHeight < 30) {
          try {
            btn.click()
            log('Expanded "See more" on Facebook post')
          } catch (e) {
            warn('Failed to expand "See more":', e)
          }
          return
        }
      }
    }
    if (PLATFORM === 'twitter') {
      // Twitter uses a "Show more" link inside truncated tweets
      const showMore = post.querySelector('[data-testid="tweet-text-show-more-link"]')
      if (showMore) {
        try {
          showMore.click()
          log('Expanded "Show more" on Twitter post')
        } catch (e) {
          warn('Failed to expand Twitter "Show more":', e)
        }
      }
    }
  }

  function extractPostText(post) {
    expandSeeMore(post)

    // Primary selectors — platform-specific, high confidence
    for (const sel of CFG.text) {
      const el = post.querySelector(sel)
      if (el?.innerText?.trim().length >= MIN_TEXT_LENGTH) {
        log('Text extracted via primary selector:', sel)
        return el.innerText.trim().slice(0, 2000)
      }
    }

    // Facebook fallback: look for [dir="auto"] ONLY inside known message containers
    if (PLATFORM === 'facebook') {
      const messageContainers = post.querySelectorAll(
        '[data-ad-comet-preview="message"] [dir="auto"], [data-testid="post_message"] [dir="auto"]'
      )
      for (const el of messageContainers) {
        const t = el.innerText?.trim()
        if (t && t.length >= MIN_TEXT_LENGTH) {
          log('Text extracted via scoped [dir="auto"] fallback')
          return t.slice(0, 2000)
        }
      }
      // Last resort: standalone [dir="auto"] with substantial text,
      // excluding comments, headers, and nav elements
      for (const el of post.querySelectorAll('[dir="auto"]')) {
        if (el.closest('[role="navigation"]') || el.closest('header') || el.closest('[data-testid="UFI2Comment"]')) continue
        // Also skip if inside a nested comment article
        const parentArticle = el.closest('[role="article"]')
        if (parentArticle && parentArticle !== post) continue
        const t = el.innerText?.trim()
        if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http')) {
          log('Text extracted via broad [dir="auto"] fallback (filtered)')
          return t.slice(0, 2000)
        }
      }
    }

    // General fallback: any span with substantial text
    for (const span of post.querySelectorAll('span')) {
      const t = span.innerText?.trim()
      if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http')) {
        // Skip if inside a nested comment article
        const parentArticle = span.closest('[role="article"]')
        if (parentArticle && parentArticle !== post) continue
        log('Text extracted via span fallback')
        return t.slice(0, 2000)
      }
    }

    log('No text found in post')
    return null
  }

  function extractPostUrl(post) {
    for (const sel of (CFG.link ?? [])) {
      const el = post.querySelector(sel)
      if (el?.href) return CFG.unwrapUrl(el)
    }
    return null
  }

  /**
   * Returns the src of the most prominent content image in a post, or null.
   * Filters out avatars, icons, emoji, and tracking pixels by:
   *   1. Excluding images inside known avatar containers
   *   2. Requiring a minimum rendered dimension (MIN_IMAGE_SIZE)
   *   3. Preferring the largest image by naturalWidth
   */
  function extractPostImage(post) {
    if (!CFG.image) return null

    const allImgs = Array.from(post.querySelectorAll(CFG.image))
    if (!allImgs.length) { log('No candidate images found'); return null }

    // Build a set of avatar container elements to check ancestry against
    const avatarContainers = (CFG.avatarContainers ?? []).flatMap(sel =>
      Array.from(post.querySelectorAll(sel))
    )

    const contentImgs = allImgs.filter(img => {
      // Exclude images nested inside avatar containers
      const isAvatar = avatarContainers.some(container => container.contains(img))
      if (isAvatar) return false

      // Exclude tiny images (avatars are typically 36-48px; icons < 24px)
      const w = img.naturalWidth || img.width || 0
      const h = img.naturalHeight || img.height || 0
      if (w < MIN_IMAGE_SIZE && h < MIN_IMAGE_SIZE) return false

      // Exclude common avatar URL patterns
      const src = img.src || ''
      if (PLATFORM === 'facebook' && /\/p\d+x\d+\//.test(src)) return false
      if (PLATFORM === 'twitter' && src.includes('profile_images')) return false

      return true
    })

    if (!contentImgs.length) { log('All images filtered out (avatars/icons)'); return null }

    // Pick the largest content image (best representative for carousel posts)
    const best = contentImgs.reduce((a, b) =>
      (b.naturalWidth || b.width || 0) > (a.naturalWidth || a.width || 0) ? b : a
    )
    const src = best.src || best.dataset?.src
    if (!src || !src.startsWith('http')) return null
    log('Image extracted:', src.slice(0, 80) + '…')
    return src
  }

  // ── Post discovery (feed-based strategy) ───────────────────────────────────

  /**
   * Checks if a [role="article"] element is a top-level post (not a comment).
   *
   * PRIMARY STRATEGY: Use [role="feed"] as the anchor.
   * - [role="feed"] is a WAI-ARIA landmark that Facebook keeps for accessibility.
   * - Direct children of the feed are always posts (wrapped in <div> containers).
   * - Comments are always deeper nested inside another [role="article"].
   *
   * This function checks:
   *   1. Is this article a direct descendant of [role="feed"]? → It's a post.
   *   2. Is this article nested inside another article? → It's a comment.
   *   3. Neither? Use URL-based heuristic for detail pages.
   */
  function isTopLevelPost(el) {
    if (PLATFORM !== 'facebook') return true
    if (el.getAttribute('role') !== 'article') return true

    // ── Check 1: Is this article nested inside another article?
    // If yes, it's definitely a comment (true for both feed and detail pages).
    const parentArticle = el.parentElement?.closest('[role="article"]')
    if (parentArticle) {
      log('Skipping comment (nested inside parent article)')
      return false
    }

    // ── Check 2: Is this article a child of [role="feed"]?
    // Direct children of the feed are always posts.
    const feedAncestor = el.closest('[role="feed"]')
    if (feedAncestor) {
      // This article is inside the feed and NOT nested in another article → post
      return true
    }

    // ── Check 3: Not in a feed — could be a detail page.
    // On detail pages (e.g. /posts/123, /permalink/, /photo/),
    // the FIRST [role="article"] on the page is the main post.
    // All subsequent ones are comments.
    const path = window.location.pathname + window.location.search
    const isDetailPage = /\/(posts|photos|permalink|story\.php|watch|reel|videos)/.test(path)
    if (isDetailPage) {
      const allArticles = document.querySelectorAll('[role="article"]')
      if (allArticles.length > 0 && allArticles[0] === el) {
        // First article on a detail page → the main post
        return true
      }
      // Not the first article on a detail page → comment
      log('Skipping comment (detail page, not the first article)')
      return false
    }

    // ── Fallback: Allow it (could be a page layout we haven't seen)
    // Better to show a button on something unexpected than miss a real post.
    return true
  }

  /**
   * Find posts in the given DOM subtree.
   *
   * Two-pass strategy for Facebook:
   *   Pass 1: Find [role="feed"] container → get [role="article"] elements
   *           that are direct children of the feed (not nested in other articles)
   *   Pass 2: If no feed found (detail pages, etc.), fall back to all
   *           [role="article"] elements filtered by isTopLevelPost()
   *
   * For Twitter and other platforms, uses POST_SELECTORS directly.
   */
  function findPosts(root) {
    if (PLATFORM === 'facebook') {
      // ── Pass 1: Feed-based detection (most reliable)
      const feeds = root.querySelectorAll('[role="feed"]')
      if (feeds.length === 0 && root.getAttribute?.('role') === 'feed') {
        // root itself might be the feed
        const articles = Array.from(root.querySelectorAll('[role="article"]'))
          .filter(el => !el.parentElement?.closest('[role="article"]'))
        if (articles.length) {
          log(`Found ${articles.length} posts via feed (root is feed)`)
          return articles
        }
      }
      for (const feed of feeds) {
        // Get all articles inside this feed that are NOT nested in another article
        const articles = Array.from(feed.querySelectorAll('[role="article"]'))
          .filter(el => !el.parentElement?.closest('[role="article"]'))
        if (articles.length) {
          log(`Found ${articles.length} posts via [role="feed"] container`)
          return articles
        }
      }

      // ── Pass 2: No feed container found — detail page or unusual layout
      const allArticles = Array.from(root.querySelectorAll('[role="article"]'))
      const topLevel = allArticles.filter(el => isTopLevelPost(el))
      if (topLevel.length) {
        log(`Found ${topLevel.length} posts via fallback (no feed container)`)
        return topLevel
      }
      return []
    }

    // Non-Facebook platforms: simple selector matching
    for (const sel of POST_SELECTORS) {
      const found = Array.from(root.querySelectorAll(sel))
      if (found.length) return found
    }
    return []
  }

  // ── "Verify this post" button injection ───────────────────────────────────

  /**
   * Creates and injects a floating "Verify this post" button on a post.
   * The button is absolutely positioned at the bottom-right of the post,
   * above the action bar (like/comment/share).
   */
  function injectVerifyButton(post) {
    // Prevent duplicate injection
    if (post.dataset.philverifyBtn) return
    post.dataset.philverifyBtn = 'true'

    // Note: We do NOT gate on content availability here.
    // Facebook lazy-loads post content via React hydration, so text/images
    // may not be in the DOM yet when this runs. Content is checked at click
    // time (in handleVerifyClick) when everything is fully rendered.

    // Create wrapper (flex container for right-alignment)
    const wrapper = document.createElement('div')
    wrapper.className = 'pv-verify-btn-wrapper'

    // Create the button
    const btn = document.createElement('button')
    btn.className = 'pv-verify-btn'
    btn.setAttribute('type', 'button')
    btn.setAttribute('aria-label', 'Verify this post with PhilVerify')

    // Button content using createElement (no innerHTML for XSS safety)
    const icon = document.createElement('span')
    icon.className = 'pv-verify-btn-icon'
    icon.textContent = '🛡️'
    icon.setAttribute('aria-hidden', 'true')

    const label = document.createElement('span')
    label.className = 'pv-verify-btn-label'
    label.textContent = 'Verify this post'

    btn.appendChild(icon)
    btn.appendChild(label)

    // Click handler → extract content, call API, show report
    btn.addEventListener('click', (e) => {
      e.stopPropagation()
      e.preventDefault()
      handleVerifyClick(post, btn)
    })

    wrapper.appendChild(btn)

    // Insert the wrapper inline in the post.
    // Strategy: Find a good insertion point near the bottom of the
    // visible post content, but BEFORE the comments section.
    // On Facebook, we look for the action bar area or similar landmarks.
    let inserted = false
    if (PLATFORM === 'facebook') {
      // Try to insert after the action bar (Like/Comment/Share row)
      const actionBar = post.querySelector('[role="toolbar"]') ||
        post.querySelector('[aria-label*="Like"]')?.closest('div:not([role="article"])')
      if (actionBar?.parentElement) {
        actionBar.parentElement.insertBefore(wrapper, actionBar.nextSibling)
        inserted = true
      }
    }

    // Fallback: just append to the post (works for Twitter and other platforms)
    if (!inserted) {
      post.appendChild(wrapper)
    }

    log('Verify button injected on post')
  }

  // ── Verify click handler ──────────────────────────────────────────────────

  async function handleVerifyClick(post, btn) {
    // Disable button and show loading state
    btn.disabled = true
    btn.classList.add('pv-verify-btn--loading')
    const origIcon = btn.querySelector('.pv-verify-btn-icon')
    const origLabel = btn.querySelector('.pv-verify-btn-label')
    if (origIcon) origIcon.textContent = ''
    if (origLabel) origLabel.textContent = 'Analyzing…'

    // Add spinner
    const spinner = document.createElement('span')
    spinner.className = 'pv-spinner'
    spinner.setAttribute('aria-hidden', 'true')
    btn.insertBefore(spinner, btn.firstChild)

    // Extract content
    const text = extractPostText(post)
    const url = extractPostUrl(post)
    const image = extractPostImage(post)

    log(`Verify clicked: text=${!!text} (${text?.length ?? 0} chars), url=${!!url}, image=${!!image}`)

    // Determine what to send
    let inputSummary = ''
    if (!text && !url && !image) {
      showErrorReport(post, btn, 'Could not read post content — no text or image found.')
      return
    }

    try {
      let msgPayload

      if (url) {
        msgPayload = { type: 'VERIFY_URL', url }
        inputSummary = 'Shared link analyzed'
      } else if (text && image) {
        msgPayload = { type: 'VERIFY_TEXT', text, imageUrl: image }
        inputSummary = 'Caption + image analyzed'
      } else if (text) {
        msgPayload = { type: 'VERIFY_TEXT', text }
        inputSummary = 'Caption text only'
      } else {
        msgPayload = { type: 'VERIFY_IMAGE_URL', imageUrl: image }
        inputSummary = 'Image only (OCR)'
      }

      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage(msgPayload, (resp) => {
          if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message))
          else if (!resp?.ok) reject(new Error(resp?.error ?? 'Unknown error'))
          else resolve(resp.result)
        })
      })

      log(`Verification result: verdict=${response.verdict}, score=${response.final_score}`)
      showVerificationReport(post, btn, response, inputSummary)
    } catch (err) {
      warn('Verification failed:', err.message)
      showErrorReport(post, btn, err.message)
    }
  }

  // ── Verification report rendering ─────────────────────────────────────────

  function showVerificationReport(post, btn, result, inputSummary) {
    // Remove the button
    btn.remove()

    // Remove any existing report on this post
    const existing = post.querySelector('.pv-report')
    if (existing) existing.remove()

    const verdict = result.verdict ?? 'Unknown'
    const color = VERDICT_COLORS[verdict] ?? '#5c554e'
    const bg = VERDICT_BG[verdict] ?? 'rgba(92, 85, 78, 0.12)'
    const label = VERDICT_LABELS[verdict] ?? verdict
    const score = Math.round(result.final_score ?? 0)
    const confidence = result.confidence?.toFixed(1) ?? '—'
    const language = result.language ?? '—'
    const sources = result.layer2?.sources ?? []
    const features = result.layer1?.triggered_features ?? []
    const cached = result._fromCache ? ' · cached' : ''

    // Build report using createElement (no innerHTML for XSS safety)
    const report = document.createElement('div')
    report.className = 'pv-report'
    report.setAttribute('role', 'region')
    report.setAttribute('aria-label', 'PhilVerify fact-check report')

    // — Header row
    const header = document.createElement('div')
    header.className = 'pv-report-header'

    const logo = document.createElement('span')
    logo.className = 'pv-report-logo'
    logo.innerHTML = 'PHIL<span style="color:#dc2626">VERIFY</span>'

    const closeBtn = document.createElement('button')
    closeBtn.className = 'pv-report-close'
    closeBtn.textContent = '✕'
    closeBtn.setAttribute('aria-label', 'Close fact-check report')
    closeBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      report.remove()
      // Re-inject the verify button so user can re-verify
      delete post.dataset.philverifyBtn
      injectVerifyButton(post)
    })

    header.appendChild(logo)
    header.appendChild(closeBtn)
    report.appendChild(header)

    // — Verdict row (large, prominent)
    const verdictRow = document.createElement('div')
    verdictRow.className = 'pv-report-verdict-row'
    verdictRow.style.borderLeftColor = color

    const verdictLabel = document.createElement('div')
    verdictLabel.className = 'pv-report-verdict'
    verdictLabel.style.color = color
    verdictLabel.textContent = label

    const scoreText = document.createElement('div')
    scoreText.className = 'pv-report-score-text'
    scoreText.textContent = `${score}% credibility${cached}`

    verdictRow.appendChild(verdictLabel)
    verdictRow.appendChild(scoreText)
    report.appendChild(verdictRow)

    // — Confidence bar
    const barWrap = document.createElement('div')
    barWrap.className = 'pv-confidence-bar-wrap'

    const barLabel = document.createElement('span')
    barLabel.className = 'pv-report-label'
    barLabel.textContent = 'CONFIDENCE'

    const barTrack = document.createElement('div')
    barTrack.className = 'pv-confidence-bar-track'

    const barFill = document.createElement('div')
    barFill.className = 'pv-confidence-bar-fill'
    barFill.style.width = `${Math.min(score, 100)}%`
    barFill.style.background = color

    const barValue = document.createElement('span')
    barValue.className = 'pv-confidence-bar-value'
    barValue.textContent = `${confidence}%`

    barTrack.appendChild(barFill)
    barWrap.appendChild(barLabel)
    barWrap.appendChild(barTrack)
    barWrap.appendChild(barValue)
    report.appendChild(barWrap)

    // — Info rows (Language, Input)
    const addInfoRow = (labelText, valueText) => {
      const row = document.createElement('div')
      row.className = 'pv-report-row'
      const lbl = document.createElement('span')
      lbl.className = 'pv-report-label'
      lbl.textContent = labelText
      const val = document.createElement('span')
      val.className = 'pv-report-value'
      val.textContent = valueText
      row.appendChild(lbl)
      row.appendChild(val)
      report.appendChild(row)
    }

    addInfoRow('LANGUAGE', safeText(language))
    addInfoRow('INPUT', safeText(inputSummary))

    // — Triggered signals/features
    if (features.length > 0) {
      const signalsSection = document.createElement('div')
      signalsSection.className = 'pv-report-signals'

      const signalsLabel = document.createElement('span')
      signalsLabel.className = 'pv-report-label'
      signalsLabel.textContent = 'SUSPICIOUS SIGNALS'
      signalsSection.appendChild(signalsLabel)

      const tagsWrap = document.createElement('div')
      tagsWrap.className = 'pv-report-tags'
      for (const f of features.slice(0, 5)) {
        const tag = document.createElement('span')
        tag.className = 'pv-report-tag'
        tag.textContent = f
        tagsWrap.appendChild(tag)
      }
      signalsSection.appendChild(tagsWrap)
      report.appendChild(signalsSection)
    }

    // — Evidence sources
    if (sources.length > 0) {
      const sourcesSection = document.createElement('div')
      sourcesSection.className = 'pv-report-sources'

      const sourcesLabel = document.createElement('span')
      sourcesLabel.className = 'pv-report-label'
      sourcesLabel.textContent = 'EVIDENCE SOURCES'
      sourcesSection.appendChild(sourcesLabel)

      const sourcesList = document.createElement('ul')
      sourcesList.className = 'pv-report-sources-list'

      for (const src of sources.slice(0, 5)) {
        const li = document.createElement('li')
        li.className = 'pv-report-source-item'

        const link = document.createElement('a')
        link.href = safeUrl(src.url)
        link.target = '_blank'
        link.rel = 'noreferrer'
        link.className = 'pv-report-source-link'
        link.textContent = src.title?.slice(0, 60) ?? src.source_name ?? 'View source'

        const stance = document.createElement('span')
        stance.className = 'pv-report-source-stance'
        stance.textContent = src.stance ?? ''
        if (src.stance === 'Refutes') stance.style.color = '#dc2626'
        if (src.stance === 'Supports') stance.style.color = '#16a34a'

        li.appendChild(link)
        li.appendChild(stance)
        sourcesList.appendChild(li)
      }
      sourcesSection.appendChild(sourcesList)
      report.appendChild(sourcesSection)
    }

    // — Explanation (claim used)
    if (result.layer2?.claim_used) {
      const explanation = document.createElement('div')
      explanation.className = 'pv-report-explanation'
      const explLabel = document.createElement('span')
      explLabel.className = 'pv-report-label'
      explLabel.textContent = 'CLAIM ANALYZED'
      const explText = document.createElement('p')
      explText.className = 'pv-report-explanation-text'
      explText.textContent = result.layer2.claim_used
      explanation.appendChild(explLabel)
      explanation.appendChild(explText)
      report.appendChild(explanation)
    }

    // — Full analysis link
    const fullLink = document.createElement('a')
    fullLink.className = 'pv-report-full-link'
    fullLink.href = 'https://philverify.web.app'
    fullLink.target = '_blank'
    fullLink.rel = 'noreferrer'
    fullLink.textContent = 'Open Full Dashboard ↗'
    report.appendChild(fullLink)

    // Insert report into post
    post.appendChild(report)
  }

  function showErrorReport(post, btn, errorMessage) {
    // Remove spinner, restore button as error state
    btn.classList.remove('pv-verify-btn--loading')
    btn.classList.add('pv-verify-btn--error')
    btn.disabled = false

    const spinner = btn.querySelector('.pv-spinner')
    if (spinner) spinner.remove()

    const icon = btn.querySelector('.pv-verify-btn-icon')
    const label = btn.querySelector('.pv-verify-btn-label')
    if (icon) icon.textContent = '⚠️'
    if (label) label.textContent = 'Verification failed — tap to retry'

    // On next click, retry
    const retryHandler = (e) => {
      e.stopPropagation()
      e.preventDefault()
      btn.removeEventListener('click', retryHandler)
      btn.classList.remove('pv-verify-btn--error')
      handleVerifyClick(post, btn)
    }

    // Remove old click listeners by replacing element
    const newBtn = btn.cloneNode(true)
    btn.replaceWith(newBtn)
    newBtn.addEventListener('click', (e) => {
      e.stopPropagation()
      e.preventDefault()
      newBtn.classList.remove('pv-verify-btn--error')
      handleVerifyClick(post, newBtn)
    })
  }

  // ── MutationObserver ──────────────────────────────────────────────────────

  const pendingPosts = new Set()
  let rafScheduled = false

  function flushPosts() {
    rafScheduled = false
    for (const post of pendingPosts) injectVerifyButton(post)
    pendingPosts.clear()
  }

  function scheduleProcess(post) {
    pendingPosts.add(post)
    if (!rafScheduled) {
      rafScheduled = true
      requestAnimationFrame(flushPosts)
    }
  }

  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (node.nodeType !== 1) continue   // element nodes only

        if (PLATFORM === 'facebook') {
          // Facebook strategy: only process nodes that are inside [role="feed"]
          // or that contain a feed. This prevents processing individual comment
          // nodes that are added dynamically.
          const inFeed = node.closest?.('[role="feed"]') ||
            node.querySelector?.('[role="feed"]') ||
            node.getAttribute?.('role') === 'feed'
          if (!inFeed && node.getAttribute?.('role') === 'article') {
            // An article added outside of a feed — could be a detail page.
            // Only process if isTopLevelPost says it's a post.
            if (isTopLevelPost(node)) {
              scheduleProcess(node)
            }
            continue
          }
        }

        // Check descendants for posts (findPosts handles feed-based filtering)
        const posts = findPosts(node)
        for (const post of posts) scheduleProcess(post)
      }
    }
  })

  // ── Initialization ────────────────────────────────────────────────────────

  async function init() {
    log(`Initializing on ${PLATFORM} (${window.location.hostname})`)

    // Check autoScan setting — controls whether buttons are shown at all
    let response
    try {
      response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'GET_SETTINGS' }, (r) => {
          if (chrome.runtime.lastError) {
            warn('Settings fetch error:', chrome.runtime.lastError.message)
            resolve({ autoScan: true })
          } else {
            resolve(r ?? { autoScan: true })
          }
        })
      })
    } catch {
      response = { autoScan: true }
    }

    log('Settings:', response)
    if (response?.autoScan === false) {
      log('Auto-scan disabled by settings — no verify buttons will be shown')
      return
    }

    // Process any posts already in the DOM
    const existing = findPosts(document.body)
    log(`Found ${existing.length} existing posts`)
    for (const post of existing) scheduleProcess(post)

    // Watch for new posts (both platforms are SPAs with infinite scroll)
    observer.observe(document.body, { childList: true, subtree: true })
    log('MutationObserver started — watching for new posts')
  }

  init()

  // ── Auto-verify news article pages (non-social) ────────────────────────────
  // When the content script runs on a PH news site (not the homepage),
  // it auto-verifies the current URL and injects a floating verdict banner.

  async function autoVerifyPage() {
    const url = window.location.href
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

    // Build banner content with createElement for XSS safety
    const leftSection = document.createElement('div')
    leftSection.style.cssText = 'display:flex;align-items:center;gap:8px;min-width:0;overflow:hidden;'

    const logoSpan = document.createElement('span')
    logoSpan.style.cssText = 'font-weight:800;letter-spacing:0.1em;color:#f5f0e8;flex-shrink:0;'
    logoSpan.innerHTML = 'PHIL<span style="color:#dc2626">VERIFY</span>'

    const statusEl = document.createElement('span')
    statusEl.id = 'pv-auto-status'
    statusEl.style.cssText = 'display:flex;align-items:center;gap:6px;overflow:hidden;'

    const statusSpinner = document.createElement('span')
    statusSpinner.className = 'pv-spinner'
    statusSpinner.setAttribute('aria-hidden', 'true')

    const statusText = document.createElement('span')
    statusText.style.cssText = 'white-space:nowrap;'
    statusText.textContent = 'Verifying article…'

    statusEl.appendChild(statusSpinner)
    statusEl.appendChild(statusText)
    leftSection.appendChild(logoSpan)
    leftSection.appendChild(statusEl)

    const rightSection = document.createElement('div')
    rightSection.style.cssText = 'display:flex;align-items:center;gap:8px;flex-shrink:0;'

    const fullLink = document.createElement('a')
    fullLink.id = 'pv-open-full'
    fullLink.href = 'https://philverify.web.app'
    fullLink.target = '_blank'
    fullLink.rel = 'noreferrer'
    fullLink.style.cssText = 'color:#dc2626;font-size:9px;font-weight:700;letter-spacing:0.1em;text-decoration:none;border:1px solid rgba(220,38,38,0.35);padding:3px 8px;border-radius:2px;white-space:nowrap;'
    fullLink.setAttribute('aria-label', 'Open PhilVerify dashboard')
    fullLink.textContent = 'FULL ANALYSIS ↗'

    const closeButton = document.createElement('button')
    closeButton.id = 'pv-close-banner'
    closeButton.style.cssText = 'background:none;border:none;color:#5c554e;cursor:pointer;font-size:13px;padding:2px 4px;line-height:1;flex-shrink:0;'
    closeButton.setAttribute('aria-label', 'Dismiss PhilVerify banner')
    closeButton.textContent = '✕'

    rightSection.appendChild(fullLink)
    rightSection.appendChild(closeButton)
    banner.appendChild(leftSection)
    banner.appendChild(rightSection)

    document.body.insertAdjacentElement('afterbegin', banner)
    document.documentElement.style.marginTop = '36px'

    closeButton.addEventListener('click', () => {
      banner.remove()
      document.documentElement.style.marginTop = ''
    })

    try {
      const response = await new Promise((resolve, reject) => {
        chrome.runtime.sendMessage({ type: 'VERIFY_URL', url }, (resp) => {
          if (chrome.runtime.lastError) reject(new Error(chrome.runtime.lastError.message))
          else if (!resp?.ok) reject(new Error(resp?.error ?? 'Unknown error'))
          else resolve(resp.result)
        })
      })

      const color = VERDICT_COLORS[response.verdict] ?? '#5c554e'
      // Update status with result
      statusEl.textContent = ''

      const dotEl = document.createElement('span')
      dotEl.style.cssText = `width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;`
      dotEl.setAttribute('aria-hidden', 'true')

      const verdictEl = document.createElement('span')
      verdictEl.style.cssText = `color:${color};font-weight:700;`
      verdictEl.textContent = response.verdict

      const scoreEl = document.createElement('span')
      scoreEl.style.cssText = 'color:#5c554e;margin-left:2px;'
      scoreEl.textContent = `${Math.round(response.final_score)}% credibility`

      statusEl.appendChild(dotEl)
      statusEl.appendChild(verdictEl)
      statusEl.appendChild(scoreEl)

      if (response.layer1?.triggered_features?.length) {
        const featureEl = document.createElement('span')
        featureEl.style.cssText = 'color:#5c554e;margin-left:4px;font-size:9px;'
        featureEl.textContent = `· ${response.layer1.triggered_features[0]}`
        statusEl.appendChild(featureEl)
      }

      banner.style.borderBottomColor = color + '88'

      // Auto-dismiss if credible
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

  // Listen for settings changes to enable/disable button injection
  chrome.storage.onChanged.addListener((changes, area) => {
    if (area !== 'local' || !changes.settings) return
    const autoScan = changes.settings.newValue?.autoScan
    if (autoScan === false) {
      observer.disconnect()
      // Remove all existing verify buttons
      document.querySelectorAll('.pv-verify-btn').forEach(btn => btn.remove())
      document.querySelectorAll('[data-philverify-btn]').forEach(el => {
        delete el.dataset.philverifyBtn
      })
    } else if (autoScan === true) {
      observer.observe(document.body, { childList: true, subtree: true })
      const existing = findPosts(document.body)
      for (const post of existing) scheduleProcess(post)
    }
  })

})()
