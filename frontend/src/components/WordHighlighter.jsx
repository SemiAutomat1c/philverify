/**
 * WordHighlighter — Phase 8: Suspicious Word Highlighter
 * Highlights suspicious / clickbait trigger words in the claim text.
 * Uses triggered_features from Layer 1 as hint words.
 *
 * architect-review: pure presentational, no side-effects.
 * web-design-guidelines: uses <mark> with visible styles, screen-reader friendly.
 */

// Common suspicious/misinformation signal words to highlight
const SUSPICIOUS_PATTERNS = [
    // English signals
    /\b(shocking|exposed|revealed|secret|hoax|fake|false|confirmed|breaking|urgent|emergency|exclusive|banned|cover[\s-]?up|conspiracy|miracle|crisis|scandal|leaked|hidden|truth|they don't want you to know)\b/gi,
    // Filipino signals
    /\b(grabe|nakakagulat|totoo|peke|huwag maniwala|nagsisinungaling|lihim|inilabas|natuklasan|katotohanan|panlilinlang|kahirap-hirap|itinatago)\b/gi,
]

function getHighlightedSegments(text, triggerWords = []) {
    if (!text) return []

    // Build a combined pattern from both static patterns + dynamic trigger words
    const allPatterns = [...SUSPICIOUS_PATTERNS]

    if (triggerWords.length > 0) {
        const escaped = triggerWords.map(w => w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
        allPatterns.push(new RegExp(`\\b(${escaped.join('|')})\\b`, 'gi'))
    }

    // Find all match intervals
    const matches = []
    for (const pattern of allPatterns) {
        pattern.lastIndex = 0
        let m
        while ((m = pattern.exec(text)) !== null) {
            matches.push({ start: m.index, end: m.index + m[0].length, word: m[0] })
        }
    }

    if (matches.length === 0) return [{ text, highlighted: false }]

    // Sort + merge overlapping intervals
    matches.sort((a, b) => a.start - b.start)
    const merged = []
    for (const m of matches) {
        const last = merged[merged.length - 1]
        if (last && m.start <= last.end) {
            last.end = Math.max(last.end, m.end)
        } else {
            merged.push({ ...m })
        }
    }

    // Build segments
    const segments = []
    let cursor = 0
    for (const { start, end, word } of merged) {
        if (cursor < start) segments.push({ text: text.slice(cursor, start), highlighted: false })
        segments.push({ text: text.slice(start, end), highlighted: true, word })
        cursor = end
    }
    if (cursor < text.length) segments.push({ text: text.slice(cursor), highlighted: false })

    return segments
}

export default function WordHighlighter({ text = '', triggerWords = [], className = '' }) {
    const segments = getHighlightedSegments(text, triggerWords)
    const hitCount = segments.filter(s => s.highlighted).length

    if (segments.length === 1 && !segments[0].highlighted) {
        // No suspicious words found
        return (
            <p className={className}
                style={{ fontFamily: 'var(--font-body)', lineHeight: 1.7, color: 'var(--text-primary)' }}>
                {text}
            </p>
        )
    }

    return (
        <div>
            {hitCount > 0 && (
                <p className="text-xs mb-2"
                    style={{
                        color: 'var(--accent-gold)',
                        fontFamily: 'var(--font-display)',
                        letterSpacing: '0.08em',
                    }}
                    aria-live="polite">
                    ⚠ {hitCount} suspicious signal{hitCount !== 1 ? 's' : ''} detected
                </p>
            )}
            <p className={className} style={{ fontFamily: 'var(--font-body)', lineHeight: 1.7, color: 'var(--text-primary)' }}>
                {segments.map((seg, i) =>
                    seg.highlighted ? (
                        <mark key={i}
                            title={`Suspicious signal: "${seg.word}"`}
                            style={{
                                background: 'rgba(220, 38, 38, 0.18)',
                                color: '#f87171',
                                borderRadius: 2,
                                padding: '0 2px',
                                fontWeight: 600,
                                outline: '1px solid rgba(220,38,38,0.3)',
                            }}>
                            {seg.text}
                        </mark>
                    ) : (
                        <span key={i}>{seg.text}</span>
                    )
                )}
            </p>
        </div>
    )
}
