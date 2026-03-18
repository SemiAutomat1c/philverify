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

  /** Detect Facebook's character-obfuscation spans: "s o o p S d e t r n …" */
  function isObfuscatedText(text) {
    const tokens = text.split(/\s+/).filter(w => w.length > 0)
    if (tokens.length < 8) return false
    const singleCharCount = tokens.filter(w => w.length === 1).length
    return singleCharCount / tokens.length > 0.5
  }

  function extractPostText(post) {
    expandSeeMore(post)

    // ── Reshare detection ─────────────────────────────────────────────────────
    // Re-shared Facebook posts have a nested [role="article"] inside the outer
    // post. The sharer's caption lives in the outer [data-ad-comet-preview="message"],
    // while the ORIGINAL post content is inside the nested article.
    // We want to fact-check the original content, not the sharer's commentary.
    if (PLATFORM === 'facebook') {
      const innerArticle = Array.from(post.querySelectorAll('[role="article"]'))
        .find(el => el !== post)

      if (innerArticle) {
        for (const sel of CFG.text) {
          const el = innerArticle.querySelector(sel)
          const t = el?.innerText?.trim()
          if (t && t.length >= MIN_TEXT_LENGTH) {
            log('Reshared post: extracted original content from nested article via', sel)
            return t.slice(0, 2000)
          }
        }
        for (const el of innerArticle.querySelectorAll('[dir="auto"]')) {
          const t = el.innerText?.trim()
          if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http')) {
            log('Reshared post: extracted original content via dir=auto in nested article')
            return t.slice(0, 2000)
          }
        }
      }
    }

    // Primary selectors — platform-specific, high confidence
    // Also search in the nearest article ancestor in case postElement is a sub-section
    const primarySearchRoots = [post]
    if (PLATFORM === 'facebook') {
      const articleAncestor = post.closest?.('[role="article"]')
      if (articleAncestor && articleAncestor !== post) primarySearchRoots.push(articleAncestor)
    }
    for (const root of primarySearchRoots) {
      for (const sel of CFG.text) {
        const el = root.querySelector(sel)
        if (el?.innerText?.trim().length >= MIN_TEXT_LENGTH) {
          log('Text extracted via primary selector:', sel)
          return el.innerText.trim().slice(0, 2000)
        }
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

      // Broader [dir="auto"] scan — exclude comments, navs, headers
      for (const el of post.querySelectorAll('[dir="auto"]')) {
        if (el.closest('[role="navigation"]') || el.closest('header') || el.closest('[data-testid="UFI2Comment"]')) continue
        const parentArticle = el.closest('[role="article"]')
        // Skip only if parentArticle is a completely separate subtree from post
        // (i.e., it doesn't contain post). If post is inside parentArticle, that's fine.
        if (parentArticle && parentArticle !== post && !parentArticle.contains(post)) continue
        const t = el.innerText?.trim()
        if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http') && !isObfuscatedText(t)) {
          log('Text extracted via broad [dir="auto"] fallback (filtered)')
          return t.slice(0, 2000)
        }
      }

      // Last resort for Facebook: walk UP the DOM from post to find the article,
      // then collect all [dir="auto"] text from that full article.
      // This handles cases where postElement is only a sub-section of the full post.
      const fullArticle = post.closest?.('[role="article"]') ?? post
      if (fullArticle !== post) {
        for (const el of fullArticle.querySelectorAll('[dir="auto"]')) {
          if (el.closest('[role="navigation"]') || el.closest('header')) continue
          const t = el.innerText?.trim()
          if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http')) {
            log('Text extracted via full-article [dir="auto"] walk-up')
            return t.slice(0, 2000)
          }
        }
        // Combine all short [dir="auto"] fragments from the full article
        const combined = Array.from(fullArticle.querySelectorAll('[dir="auto"]'))
          .map(el => el.innerText?.trim())
          .filter(t => t && t.length > 5 && !t.startsWith('http'))
          .join(' ')
        if (combined.length >= MIN_TEXT_LENGTH) {
          log('Text extracted by combining dir=auto fragments in full article')
          return combined.slice(0, 2000)
        }
      }

      // Combine all short [dir="auto"] fragments in the current post element
      const allDirAuto = Array.from(post.querySelectorAll('[dir="auto"]'))
        .map(el => el.innerText?.trim())
        .filter(t => t && t.length > 5 && !t.startsWith('http'))
        .join(' ')
      if (allDirAuto.length >= MIN_TEXT_LENGTH) {
        log('Text extracted by combining dir=auto fragments')
        return allDirAuto.slice(0, 2000)
      }
    }

    // General fallback: any span with substantial text (skip obfuscated char-spans)
    for (const span of post.querySelectorAll('span')) {
      const t = span.innerText?.trim()
      if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http') && !isObfuscatedText(t)) {
        // Skip if inside a nested comment article
        const parentArticle = span.closest('[role="article"]')
        if (parentArticle && parentArticle !== post && !parentArticle.contains(post)) continue
        log('Text extracted via span fallback')
        return t.slice(0, 2000)
      }
    }

    // Walk UP the DOM and try the full article — covers cases where postElement
    // is a small sub-section that doesn't contain the text itself
    const ancestor = post.closest?.('[role="article"]')
    if (ancestor && ancestor !== post) {
      for (const span of ancestor.querySelectorAll('span')) {
        const t = span.innerText?.trim()
        if (t && t.length >= MIN_TEXT_LENGTH && !t.startsWith('http') && !isObfuscatedText(t)) {
          log('Text extracted via ancestor span walk-up')
          return t.slice(0, 2000)
        }
      }
    }

    log('No text found in post')
    return null
  }

  function extractPostUrl(post) {
    for (const sel of (CFG.link ?? [])) {
      const el = post.querySelector(sel)
      if (el?.href) {
        const url = CFG.unwrapUrl(el)
        // Skip common internal Facebook/Twitter links that aren't actually shared external content
        if (PLATFORM === 'facebook') {
          const u = url.toLowerCase()
          if (u.includes('facebook.com') && !u.includes('l.php')) {
            // Probably a profile link or internal post link, ignore as "URL input"
            continue
          }
        }
        return url
      }
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

    // Search in post, then fall back to the nearest article ancestor if nothing found.
    // postElement from the walk-up may only wrap the message text, not the image.
    let allImgs = Array.from(post.querySelectorAll(CFG.image))
    if (!allImgs.length && PLATFORM === 'facebook') {
      const articleAncestor = post.closest?.('[role="article"]')
      if (articleAncestor) allImgs = Array.from(articleAncestor.querySelectorAll(CFG.image))
    }
    if (!allImgs.length) { log('No candidate images found'); return null }

    // Build a set of avatar container elements to check ancestry against
    const imgSearchRoot = post.closest?.('[role="article"]') ?? post
    const avatarContainers = (CFG.avatarContainers ?? []).flatMap(sel =>
      Array.from(imgSearchRoot.querySelectorAll(sel))
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

  // ── Post discovery ────────────────────────────────────────────────────────

  /**
   * Facebook: Scan the entire document for [aria-label="Hide post"] buttons.
   * This is the same proven anchor used by the classmate's working extension.
   * Walk up from the button to find the enclosing post container, then inject.
   *
   * Why this works better than [role="feed"] / [role="article"] detection:
   *   - Facebook's WAI-ARIA feed/article structure changes frequently
   *   - The "Hide post" ✕ button is rendered on EVERY post and is very stable
   *   - Walking up to find the enclosing article-level div is reliable
   */
  function addButtonsToFacebookPosts() {
    // Anchor buttons that appear in EVERY post header (both home feed and profile pages).
    // "Actions for this post" is the ⋯ button — always visible, never on comments.
    const hideButtons = document.querySelectorAll(
      '[aria-label="Actions for this post"], [aria-label="Hide post"], [aria-label="hide post"], [aria-label="Hide or report this"], [aria-label="Edit post"], [aria-label="Edit memory"]'
    )

    let added = 0
    hideButtons.forEach((hideBtn) => {
      const btnContainer = hideBtn.parentElement
      const btnGrandparent = btnContainer?.parentElement
      if (!btnContainer || !btnGrandparent) return

      // Skip if we already injected on this container
      if (btnGrandparent.querySelector('.pv-verify-btn')) return

      // Walk up from btnGrandparent to find the post container.
      // Priority: container with a message attribute > non-empty article > first innerText>100.
      // We don't stop on innerText>100 alone because the header grandparent often has
      // that much text but doesn't contain the post body — keep walking for a better anchor.
      let postElement = null
      let innerTextFallback = null
      let el = btnGrandparent
      while (el && el !== document.body) {
        // Best match: element that directly wraps the post message
        if (el.querySelector('[data-ad-rendering-role="story_message"], [data-ad-comet-preview="message"]')) {
          postElement = el; break
        }
        // Second best: an article/ARTICLE with actual content (non-skeleton)
        if ((el.getAttribute('role') === 'article' || el.tagName === 'ARTICLE') &&
            (el.innerText?.length ?? 0) > 100) {
          postElement = el; break
        }
        // Track first innerText>100 as fallback (but keep walking for better match)
        if (!innerTextFallback && (el.innerText?.length ?? 0) > 100) {
          innerTextFallback = el
        }
        el = el.parentElement
      }
      if (!postElement) postElement = innerTextFallback ?? btnGrandparent

      // Skip if postElement is nested inside another article (comment / reshared post)
      if (postElement.parentElement?.closest('[role="article"]')) return

      // Skip if already injected on this post
      if (postElement.dataset.philverifyBtn) return

      // "Actions for this post" (⋯ button) and "Hide or report this" only appear in
      // post headers, never on comments. Profile page posts don't have
      // [data-ad-comet-preview] so skip the content check and place the button
      // directly next to the anchor (for ⋯) or via injectVerifyButton (for the other).
      const hideBtnLabel = hideBtn.getAttribute('aria-label')
      // "Actions for this post" (⋯) and "Hide or report this" are in post headers only.
      // Delegate placement to injectVerifyButton so the button lands in the action bar.
      if (hideBtnLabel === 'Actions for this post' || hideBtnLabel === 'Hide or report this') {
        injectVerifyButton(postElement)
        added++
        return
      }

      // For all other anchor labels (Hide post, Edit post, Edit memory): require a
      // post message container. These labels only exist on home feed posts which
      // always have [data-ad-comet-preview="message"].
      if (!postElement.querySelector(
        '[data-ad-comet-preview="message"], [data-ad-rendering-role="story_message"]'
      )) return

      // Delegate to injectVerifyButton so placement uses the action bar (Like/Comment/Share)
      // on all page types — avoids the button being hidden in the post header area.
      injectVerifyButton(postElement)
      added++
    })

    if (added > 0) log(`Added ${added} verify button(s) via hide-post anchor`)

    // ── Supplementary scan: article-based (profile pages, group pages, etc.) ──
    // Both profile posts AND comments are [role="article"] on Facebook.
    // Posts are top-level (no parent article); comments are nested inside posts.
    // The nesting check below correctly distinguishes them.
    // Note: the previous comment injection bug was caused by [aria-label="Remove"]
    // in the button-anchor pass (now removed), not by this scan.
    let supplementaryAdded = 0
    document.querySelectorAll('[role="article"]').forEach(article => {
      if (article.dataset.philverifyBtn) return
      if (article.parentElement?.closest('[role="article"]')) return
      // Profile page [role="article"] elements are permanent loading skeletons with no
      // real content. Only inject on articles that actually have post message content.
      if (PLATFORM === 'facebook' && !article.querySelector(
        '[data-ad-comet-preview="message"], [data-ad-rendering-role="story_message"]'
      )) return
      injectVerifyButton(article)
      supplementaryAdded++
    })
    if (supplementaryAdded > 0) log(`Added ${supplementaryAdded} verify button(s) via article scan`)
  }

  /**
   * For Twitter and news sites: use the original selector-based approach.
   */
  function findPosts(root) {
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

    // Create the button
    const btn = document.createElement('button')
    btn.className = 'pv-verify-btn'
    btn.setAttribute('type', 'button')
    btn.setAttribute('aria-label', 'Verify this post with PhilVerify')

    const icon = document.createElement('span')
    icon.className = 'pv-verify-btn-icon'
    icon.setAttribute('aria-hidden', 'true')
    // Shield SVG — trust indicator, replaces emoji for a polished look
    icon.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/></svg>'

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

    // ── Insertion strategy ───────────────────────────────────────────────────
    // Strategy 1 (most reliable — same anchor as classmate's working extension):
    // The "hide post" ✕ button is stable across Facebook layout changes.
    // Insert the verify button next to it in the post header.
    let inserted = false

    if (PLATFORM === 'facebook') {
      // Strategy 1 (primary): Insert BEFORE the message text block — places button at top of post.
      // [data-ad-comet-preview="message"] is stable and already used for text extraction.
      if (!inserted) {
        const searchRoot = post.closest('[role="article"]') ?? post
        const msgBlock =
          searchRoot.querySelector('[data-ad-comet-preview="message"]') ??
          searchRoot.querySelector('[data-testid="post_message"]') ??
          post.querySelector('[data-ad-comet-preview="message"]') ??
          post.querySelector('[data-testid="post_message"]')
        if (msgBlock?.parentElement) {
          const wrapper = document.createElement('div')
          wrapper.className = 'pv-verify-btn-wrapper'
          wrapper.style.marginBottom = '8px'
          wrapper.appendChild(btn)
          msgBlock.parentElement.insertBefore(wrapper, msgBlock)
          inserted = true
          log('Verify button injected before message block (top of post)')
        }
      }

      // Strategy 2 (fallback): Insert after the action row (Like / Comment / Share)
      if (!inserted) {
        const searchRoot = post.closest('[role="article"]') ?? post
        const likeBtn =
          searchRoot.querySelector('[aria-label="Like"], [aria-label^="Like:"]') ??
          post.querySelector('[aria-label="Like"], [aria-label^="Like:"]')
        const actionBar =
          likeBtn?.closest('[role="toolbar"]') ??
          likeBtn?.closest('[role="group"]') ??
          searchRoot.querySelector('[role="toolbar"]') ??
          searchRoot.querySelector('[aria-label*="Comment"]')?.closest('div:not([role="article"])')
        if (actionBar?.parentElement) {
          const wrapper = document.createElement('div')
          wrapper.className = 'pv-verify-btn-wrapper'
          wrapper.appendChild(btn)
          actionBar.parentElement.insertBefore(wrapper, actionBar.nextSibling)
          inserted = true
          log('Verify button injected after action bar (fallback)')
        }
      }
    }

    // Twitter: insert after tweet text block
    if (!inserted && PLATFORM === 'twitter') {
      const tweetText = post.querySelector('[data-testid="tweetText"]')
      if (tweetText?.parentElement) {
        const wrapper = document.createElement('div')
        wrapper.className = 'pv-verify-btn-wrapper'
        wrapper.appendChild(btn)
        tweetText.parentElement.insertBefore(wrapper, tweetText.nextSibling)
        inserted = true
      }
    }

    // News sites: inject after the h1 headline so the button is visible without scrolling
    if (!inserted && PLATFORM === 'news') {
      const h1 = post.querySelector('h1')
      if (h1?.parentElement) {
        const wrapper = document.createElement('div')
        wrapper.className = 'pv-verify-btn-wrapper'
        wrapper.appendChild(btn)
        h1.parentElement.insertBefore(wrapper, h1.nextSibling)
        inserted = true
        log('Verify button injected after h1 headline')
      }
    }

    // Final fallback: append a wrapped button directly to the post
    if (!inserted) {
      const wrapper = document.createElement('div')
      wrapper.className = 'pv-verify-btn-wrapper'
      wrapper.appendChild(btn)
      post.appendChild(wrapper)
      log('Verify button injected via fallback (appended to post)')
    }
  }

  // ── Verify click handler ──────────────────────────────────────────────────

  async function handleVerifyClick(post, btn) {
    // Disable button and show loading state
    btn.disabled = true
    btn.classList.add('pv-verify-btn--loading')
    const origIcon = btn.querySelector('.pv-verify-btn-icon')
    const origLabel = btn.querySelector('.pv-verify-btn-label')

    // Replace icon with scanning SVG
    if (origIcon) origIcon.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>'

    // 3-dot bounce loader
    const dots = document.createElement('span')
    dots.className = 'pv-dots'
    dots.setAttribute('aria-hidden', 'true')
    dots.innerHTML = '<span class="pv-dot"></span><span class="pv-dot"></span><span class="pv-dot"></span>'
    btn.insertBefore(dots, origLabel)

    // Cycle through status messages while waiting for the API
    const SCAN_STEPS = ['Scanning text…', 'Cross-referencing…', 'Analyzing evidence…', 'Almost done…']
    let stepIdx = 0
    if (origLabel) origLabel.textContent = SCAN_STEPS[0]
    btn._pvStepTimer = setInterval(() => {
      stepIdx = (stepIdx + 1) % SCAN_STEPS.length
      if (origLabel) origLabel.textContent = SCAN_STEPS[stepIdx]
    }, 1800)

    // Extract content
    const text = extractPostText(post)
    const url = extractPostUrl(post)
    const image = extractPostImage(post)

    console.log('[PhilVerify] Extracted:', { text, url, image })

    log(`Verify clicked: text=${!!text} (${text?.length ?? 0} chars), url=${!!url}, image=${!!image}`)

    // Determine what to send
    let inputSummary = ''
    if (!text && !url && !image) {
      console.warn('[PhilVerify] Extraction failed: No content found.')
      showErrorReport(post, btn, 'Could not read post content — no text or image found.')
      return
    }

    try {
      let msgPayload
      let usedType = ''

      // Start by attempting URL verification if present
      if (url) {
        msgPayload = { type: 'VERIFY_URL', url }
        usedType = 'URL'
        inputSummary = 'Shared link analyzed'
      } else if (text && image) {
        msgPayload = { type: 'VERIFY_TEXT', text, imageUrl: image }
        usedType = 'TEXT'
        inputSummary = 'Caption + image analyzed'
      } else if (text) {
        msgPayload = { type: 'VERIFY_TEXT', text }
        usedType = 'TEXT'
        inputSummary = 'Caption text only'
      } else {
        msgPayload = { type: 'VERIFY_IMAGE_URL', imageUrl: image }
        usedType = 'IMAGE'
        inputSummary = 'Image only (OCR)'
      }

      console.log(`[PhilVerify] Attempting ${usedType} verification:`, msgPayload)

      let response
      try {
        response = await new Promise((resolve, reject) => {
          chrome.runtime.sendMessage(msgPayload, (resp) => {
            if (chrome.runtime.lastError) {
              const msg = chrome.runtime.lastError.message ?? ''
              reject(new Error(
                msg.includes('Extension context invalidated')
                  ? 'Extension was reloaded — please refresh the page to re-activate PhilVerify.'
                  : msg
              ))
            }
            else if (!resp?.ok) reject(new Error(resp?.error ?? 'Unknown error'))
            else resolve(resp.result)
          })
        })
      } catch (err) {
        // FALLBACK LOGIC: If URL verification failed but we have text, try verifying the text instead
        if (usedType === 'URL' && text && text.length >= MIN_TEXT_LENGTH) {
          warn('URL verification failed, falling back to text verification:', err.message)
          
          if (image) {
            msgPayload = { type: 'VERIFY_TEXT', text, imageUrl: image }
            inputSummary = 'Caption + image analyzed (fallback)'
          } else {
            msgPayload = { type: 'VERIFY_TEXT', text }
            inputSummary = 'Caption text only (fallback)'
          }
          
          console.log('[PhilVerify] Fallback attempt (TEXT):', msgPayload)
          response = await new Promise((resolve, reject) => {
            chrome.runtime.sendMessage(msgPayload, (resp) => {
              if (chrome.runtime.lastError) {
              const msg = chrome.runtime.lastError.message ?? ''
              reject(new Error(
                msg.includes('Extension context invalidated')
                  ? 'Extension was reloaded — please refresh the page to re-activate PhilVerify.'
                  : msg
              ))
            }
              else if (!resp?.ok) reject(new Error(resp?.error ?? 'Unknown error'))
              else resolve(resp.result)
            })
          })
        } else {
          // Re-throw if no fallback possible
          throw err
        }
      }

      log(`Verification result: verdict=${response.verdict}, score=${response.final_score}`)
      if (btn._pvStepTimer) { clearInterval(btn._pvStepTimer); btn._pvStepTimer = null }
      const dots = btn.querySelector('.pv-dots')
      if (dots) dots.remove()
      const extractedText = usedType === 'URL' ? url : (usedType === 'TEXT' ? text : null)
      showVerificationReport(post, btn, response, inputSummary, extractedText, image)
    } catch (err) {
      warn('Verification failed:', err.message)
      showErrorReport(post, btn, err.message)
    }
  }

  // ── Verification report rendering ─────────────────────────────────────────

  function showVerificationReport(post, btn, result, inputSummary, extractedText, extractedImage) {
    // Remove the button
    btn.remove()

    // Remove any existing modal
    document.getElementById('pv-modal-overlay')?.remove()

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

    // ── Backdrop overlay
    const overlay = document.createElement('div')
    overlay.id = 'pv-modal-overlay'
    overlay.className = 'pv-modal-overlay'
    overlay.setAttribute('role', 'dialog')
    overlay.setAttribute('aria-modal', 'true')
    overlay.setAttribute('aria-label', 'PhilVerify fact-check report')

    function closeModal() {
      overlay.classList.remove('pv-modal--open')
      overlay.addEventListener('transitionend', () => {
        overlay.remove()
        delete post.dataset.philverifyBtn
        addButtonsToFacebookPosts()
      }, { once: true })
    }

    // Click outside card = close
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) closeModal()
    })
    // Escape key = close
    const onKey = (e) => { if (e.key === 'Escape') { closeModal(); document.removeEventListener('keydown', onKey) } }
    document.addEventListener('keydown', onKey)

    // ── Modal card
    const card = document.createElement('div')
    card.className = 'pv-modal-card'

    // — Header
    const header = document.createElement('div')
    header.className = 'pv-report-header'

    const logo = document.createElement('span')
    logo.className = 'pv-report-logo'
    logo.innerHTML = 'PHIL<span style="color:#dc2626">VERIFY</span>'

    const closeBtn = document.createElement('button')
    closeBtn.className = 'pv-report-close'
    closeBtn.textContent = '✕'
    closeBtn.setAttribute('aria-label', 'Close fact-check report')
    closeBtn.addEventListener('click', (e) => { e.stopPropagation(); closeModal() })

    header.appendChild(logo)
    header.appendChild(closeBtn)
    card.appendChild(header)

    // — Verdict row
    const verdictRow = document.createElement('div')
    verdictRow.className = 'pv-report-verdict-row'
    verdictRow.style.borderLeftColor = color
    verdictRow.style.background = bg

    const verdictLabel = document.createElement('div')
    verdictLabel.className = 'pv-report-verdict'
    verdictLabel.style.color = color
    verdictLabel.textContent = label

    const scoreText = document.createElement('div')
    scoreText.className = 'pv-report-score-text'
    scoreText.textContent = `${score}% credibility${cached}`

    verdictRow.appendChild(verdictLabel)
    verdictRow.appendChild(scoreText)
    card.appendChild(verdictRow)

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
    barFill.style.width = '0'
    barFill.style.background = color

    const barValue = document.createElement('span')
    barValue.className = 'pv-confidence-bar-value'
    barValue.textContent = `${confidence}%`

    barTrack.appendChild(barFill)
    barWrap.appendChild(barLabel)
    barWrap.appendChild(barTrack)
    barWrap.appendChild(barValue)
    card.appendChild(barWrap)

    // — Info rows
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
      card.appendChild(row)
    }

    addInfoRow('LANGUAGE', safeText(language))
    addInfoRow('INPUT', safeText(inputSummary))

    // — Image analyzed (thumbnail + OCR text)
    if (extractedImage) {
      const imgSection = document.createElement('div')
      imgSection.className = 'pv-report-explanation'
      const imgLabel = document.createElement('span')
      imgLabel.className = 'pv-report-label'
      imgLabel.textContent = 'IMAGE ANALYZED'
      const img = document.createElement('img')
      img.src = extractedImage
      img.alt = 'Extracted post image'
      img.style.cssText = 'width:100%;border-radius:6px;margin-top:6px;display:block;'
      imgSection.appendChild(imgLabel)
      imgSection.appendChild(img)

      // OCR text extracted from the image
      if (result.ocr_text) {
        const ocrLabel = document.createElement('span')
        ocrLabel.className = 'pv-report-label'
        ocrLabel.style.marginTop = '8px'
        ocrLabel.textContent = 'IMAGE TEXT (OCR)'
        const ocrPara = document.createElement('p')
        ocrPara.className = 'pv-report-explanation-text'
        ocrPara.textContent = safeText(result.ocr_text)
        imgSection.appendChild(ocrLabel)
        imgSection.appendChild(ocrPara)
      }

      card.appendChild(imgSection)
    }

    // — Caption / text analyzed (full text, no truncation)
    if (extractedText) {
      const textSection = document.createElement('div')
      textSection.className = 'pv-report-explanation'
      const textLabel = document.createElement('span')
      textLabel.className = 'pv-report-label'
      textLabel.textContent = 'CAPTION TEXT'
      const textPara = document.createElement('p')
      textPara.className = 'pv-report-explanation-text'
      textPara.textContent = safeText(extractedText)
      textSection.appendChild(textLabel)
      textSection.appendChild(textPara)
      card.appendChild(textSection)
    }

    // — Signals
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
      card.appendChild(signalsSection)
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
        if (src.stance_reason) {
          stance.title = src.stance_reason
          stance.style.cursor = 'help'
        }
        li.appendChild(link)
        li.appendChild(stance)
        sourcesList.appendChild(li)
      }
      sourcesSection.appendChild(sourcesList)
      card.appendChild(sourcesSection)
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
      card.appendChild(explanation)
    }

    // — Metadata footer (model tier + claim method)
    const modelTier   = result.layer1?.model_tier
    const claimMethod = result.layer2?.claim_method
    if (modelTier || claimMethod) {
      const metaFooter = document.createElement('div')
      metaFooter.className = 'pv-report-meta-footer'
      if (modelTier) {
        const lbl = document.createElement('span')
        lbl.className = 'pv-report-meta-label'
        lbl.textContent = 'MODEL'
        const val = document.createElement('span')
        val.className = 'pv-report-meta-val'
        val.textContent = modelTier
        metaFooter.appendChild(lbl)
        metaFooter.appendChild(val)
      }
      if (modelTier && claimMethod) {
        const sep = document.createElement('span')
        sep.className = 'pv-report-meta-sep'
        sep.textContent = '·'
        metaFooter.appendChild(sep)
      }
      if (claimMethod) {
        const lbl = document.createElement('span')
        lbl.className = 'pv-report-meta-label'
        lbl.textContent = 'VIA'
        const val = document.createElement('span')
        val.className = 'pv-report-meta-val'
        val.textContent = claimMethod
        metaFooter.appendChild(lbl)
        metaFooter.appendChild(val)
      }
      card.appendChild(metaFooter)
    }

    // — Full analysis link
    const fullLink = document.createElement('a')
    fullLink.className = 'pv-report-full-link'
    fullLink.href = 'https://philverify.web.app'
    fullLink.target = '_blank'
    fullLink.rel = 'noreferrer'
    fullLink.textContent = 'Open Full Dashboard ↗'
    card.appendChild(fullLink)

    // Assemble and show
    overlay.appendChild(card)
    document.body.appendChild(overlay)

    // Trigger animation
    requestAnimationFrame(() => overlay.classList.add('pv-modal--open'))
    
    // Animate the confidence bar fill
    setTimeout(() => {
      barFill.style.width = `${confidence}%`
    }, 300)
  }

  function showErrorReport(post, btn, errorMessage) {
    // Clear cycling status timer
    if (btn._pvStepTimer) { clearInterval(btn._pvStepTimer); btn._pvStepTimer = null }

    btn.classList.remove('pv-verify-btn--loading')
    btn.classList.add('pv-verify-btn--error')
    btn.disabled = false

    const dots = btn.querySelector('.pv-dots')
    if (dots) dots.remove()

    const icon = btn.querySelector('.pv-verify-btn-icon')
    const label = btn.querySelector('.pv-verify-btn-label')

    // Extension was reloaded — retrying is useless, user must refresh the tab
    const needsRefresh = errorMessage.includes('Extension was reloaded') ||
      errorMessage.includes('Extension context invalidated')

    if (needsRefresh) {
      if (icon) icon.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/></svg>'
      if (label) label.textContent = 'Extension updated — refresh page'
      btn.disabled = true
      return
    }

    if (icon) icon.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
    if (label) label.textContent = 'Verification failed — tap to retry'

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

  // For Facebook: debounced full rescan (new posts appear via infinite scroll)
  let fbDebounceTimer = null
  function scheduleFacebookScan() {
    if (fbDebounceTimer) clearTimeout(fbDebounceTimer)
    fbDebounceTimer = setTimeout(() => {
      fbDebounceTimer = null
      addButtonsToFacebookPosts()
    }, 150)
  }

  // For Twitter/news: RAF-batched per-post injection
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

  const observer = new MutationObserver(() => {
    if (PLATFORM === 'facebook') {
      // Just re-scan the whole document for new hide-post buttons
      scheduleFacebookScan()
      return
    }
    // Twitter / news: find posts inside mutated subtrees
    const posts = findPosts(document.body)
    for (const post of posts) scheduleProcess(post)
  })

  // ── Initialization ────────────────────────────────────────────────────────

  async function init() {
    log(`Initializing on ${PLATFORM} (${window.location.hostname})`)

    // Check autoScan setting — controls whether buttons are shown at all
    // Use a short timeout so we don't block if background worker is asleep
    let response = { autoScan: true }
    try {
      response = await Promise.race([
        new Promise((resolve) => {
          chrome.runtime.sendMessage({ type: 'GET_SETTINGS' }, (r) => {
            if (chrome.runtime.lastError) resolve({ autoScan: true })
            else resolve(r ?? { autoScan: true })
          })
        }),
        new Promise((resolve) => setTimeout(() => resolve({ autoScan: true }), 1500)),
      ])
    } catch {
      response = { autoScan: true }
    }

    log('Settings:', response)
    if (response?.autoScan === false) {
      log('Auto-scan disabled — no verify buttons will be shown')
      return
    }

    if (PLATFORM === 'facebook') {
      // Initial scan + watch for new posts via infinite scroll
      addButtonsToFacebookPosts()
      observer.observe(document.body, { childList: true, subtree: true })
      log('Facebook mode: watching for new posts via hide-post button anchor')
    } else {
      // Twitter / news sites: selector-based
      const existing = findPosts(document.body)
      log(`Found ${existing.length} existing posts`)
      for (const post of existing) scheduleProcess(post)
      observer.observe(document.body, { childList: true, subtree: true })
      log('MutationObserver started')
      // News article pages: also show auto-verify banner at top of page
      if (PLATFORM === 'news') autoVerifyPage()
    }
  }

  init()

  // ── SPA navigation listener ───────────────────────────────────────────────
  // Facebook is a single-page app. background.js fires RE_SCAN_POSTS whenever
  // it detects a pushState navigation on facebook.com via webNavigation API.
  // This ensures profile pages, group pages, etc. get scanned after navigation.
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === 'RE_SCAN_POSTS') {
      log('SPA navigation detected, re-scanning for posts...')
      // Small delay to let Facebook finish rendering the new page content
      setTimeout(addButtonsToFacebookPosts, 500)
    }
  })

  // ── Auto-verify news article pages (non-social) ────────────────────────────
  // When the content script runs on a PH news site (not the homepage),
  // it auto-verifies the current URL and injects a floating verdict banner.

  async function autoVerifyPage() {
    const url = window.location.href
    const path = new URL(url).pathname
    // Skip homepages and section indexes (very short paths like / or /news)
    if (!path || path.length < 5 || path.split('/').filter(Boolean).length < 1) return

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
          if (chrome.runtime.lastError) {
              const msg = chrome.runtime.lastError.message ?? ''
              reject(new Error(
                msg.includes('Extension context invalidated')
                  ? 'Extension was reloaded — please refresh the page to re-activate PhilVerify.'
                  : msg
              ))
            }
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
