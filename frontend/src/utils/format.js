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
    'Credible': { cls: 'badge-credible', label: 'VERIFIED', symbol: '✓', explanation: 'This claim appears credible. Multiple signals and/or supporting evidence suggest this information is likely true.' },
    'Unverified': { cls: 'badge-unverified', label: 'UNVERIFIED', symbol: '?', explanation: 'We couldn\'t confirm or deny this claim. There isn\'t enough evidence either way — treat this information with caution and verify from other sources.' },
    'Likely Fake': { cls: 'badge-fake', label: 'FALSE', symbol: '✗', explanation: 'This claim shows strong signs of being false or misleading. Our analysis detected multiple red flags — do not share this without verifying from trusted news sources.' },
}

/**
 * Human-readable interpretation of a 0-100 score
 */
export function scoreInterpretation(score) {
    if (score >= 85) return 'Very high credibility — strong evidence supports this claim.'
    if (score >= 70) return 'Likely credible — most signals point to this being true.'
    if (score >= 55) return 'Uncertain — some supporting evidence, but not enough to confirm.'
    if (score >= 40) return 'Questionable — limited evidence and some suspicious signals detected.'
    if (score >= 20) return 'Likely false — multiple red flags and contradicting evidence found.'
    return 'Very likely false — strong indicators of misinformation detected.'
}

/**
 * Human-readable explanation for Layer 1 ML confidence
 */
export function mlConfidenceExplanation(confidence, verdict) {
    const isFake = verdict === 'Likely Fake'
    if (confidence >= 85) return isFake
        ? 'The AI model is very confident this contains fake news patterns (clickbait, emotional manipulation, misleading language).'
        : 'The AI model is very confident this reads like legitimate, credible reporting.'
    if (confidence >= 60) return isFake
        ? 'The AI model detected several patterns commonly found in fake news.'
        : 'The AI model found this mostly consistent with credible content.'
    return 'The AI model has low confidence — the text doesn\'t clearly match fake or credible patterns.'
}

/**
 * Human-readable explanation for Layer 2 evidence score
 */
export function evidenceExplanation(score, sources) {
    const count = sources?.length || 0
    if (count === 0) return 'No matching news articles were found to cross-reference this claim. The score reflects a neutral default.'
    if (score >= 70) return `Found ${count} related article${count > 1 ? 's' : ''} from news sources that support this claim.`
    if (score >= 40) return `Found ${count} related article${count > 1 ? 's' : ''}, but evidence is mixed or inconclusive.`
    return `Found ${count} related article${count > 1 ? 's' : ''} — some contradict or debunk this claim.`
}
