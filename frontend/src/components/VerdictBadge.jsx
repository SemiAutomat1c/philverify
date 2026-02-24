import { VERDICT_MAP } from '../utils/format.js'

/**
 * VerdictBadge — broadcast-style breaking news label.
 * architect-review: uses shared VERDICT_MAP from utils, not inline logic.
 */
export default function VerdictBadge({ verdict, size = 'sm' }) {
    const { cls, label, symbol } = VERDICT_MAP[verdict] ?? VERDICT_MAP['Unverified']

    return size === 'banner' ? (
        /* Large banner variant for results page */
        <div className={`verdict-banner verdict-banner-${cls.replace('badge-', '')}`}
            role="status" aria-label={`Verdict: ${label}`}>
            {symbol} {label}
        </div>
    ) : (
        <span
            className={`${cls} rounded-sm font-semibold inline-flex items-center gap-1`}
            style={{
                fontFamily: 'var(--font-display)',
                letterSpacing: '0.06em',
                fontSize: size === 'sm' ? 10 : 12,
                padding: size === 'sm' ? '2px 8px' : '4px 12px',
            }}
            role="status"
            aria-label={`Verdict: ${label}`}
        >
            <span aria-hidden="true">{symbol}</span>
            {label}
        </span>
    )
}
