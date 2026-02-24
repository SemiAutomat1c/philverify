/**
 * Utility functions extracted per architect-reviewer:
 * no business logic in UI components.
 */

/**
 * Format ISO timestamp using Intl.DateTimeFormat (web-design-guidelines: no hardcoded formats)
 */
export function timeAgo(iso) {
    const diff = Date.now() - new Date(iso).getTime()
    const mins = Math.floor(diff / 60_000)
    if (mins < 1) return 'just now'
    if (mins < 60) return `${mins}m ago`
    const hrs = Math.floor(mins / 60)
    if (hrs < 24) return `${hrs}h ago`
    return new Intl.DateTimeFormat(undefined, { month: 'short', day: 'numeric' }).format(new Date(iso))
}

/**
 * Map a 0-100 credibility score to CSS color token
 */
export function scoreColor(score) {
    if (score >= 70) return 'var(--credible)'
    if (score >= 40) return 'var(--unverified)'
    return 'var(--fake)'
}

/**
 * Map verdict string to badge class
 */
export const VERDICT_MAP = {
    'Credible': { cls: 'badge-credible', label: 'VERIFIED', symbol: '✓' },
    'Unverified': { cls: 'badge-unverified', label: 'UNVERIFIED', symbol: '?' },
    'Likely Fake': { cls: 'badge-fake', label: 'FALSE', symbol: '✗' },
}
