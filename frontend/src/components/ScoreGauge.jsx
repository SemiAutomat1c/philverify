import { scoreColor } from '../utils/format.js'

/**
 * SVG radial gauge — credibility score 0-100.
 * Uses JetBrains Mono for score display (tabular, terminal aesthetic).
 * web-design-guidelines: SVG transform on wrapper with transform-box fill-box.
 * web-design-guidelines: prefers-reduced-motion handled in CSS.
 */
export default function ScoreGauge({ score = 0, size = 140 }) {
    const R = 50
    const circumference = 2 * Math.PI * R
    const arcLen = (circumference * 240) / 360   // 240° sweep
    const filled = (Math.min(score, 100) / 100) * arcLen
    const color = scoreColor(score)

    return (
        <figure aria-label={`Credibility score: ${Math.round(score)} out of 100`}
            style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <svg width={size} height={size} viewBox="0 0 120 120" role="img"
                aria-hidden="true">
                {/* Background arc track */}
                <circle
                    cx="60" cy="60" r={R}
                    fill="none"
                    stroke="rgba(245,240,232,0.05)"
                    strokeWidth="10"
                    strokeDasharray={`${arcLen} ${circumference}`}
                    strokeLinecap="round"
                    transform="rotate(150 60 60)"
                />
                {/* Filled arc */}
                <circle
                    className="gauge-arc"
                    cx="60" cy="60" r={R}
                    fill="none"
                    stroke={color}
                    strokeWidth="10"
                    strokeDasharray={`${filled} ${circumference}`}
                    strokeLinecap="round"
                    transform="rotate(150 60 60)"
                />
                {/* Score numeral — JetBrains Mono for terminal precision */}
                <text x="60" y="62" textAnchor="middle"
                    style={{
                        fill: color,
                        fontSize: 26,
                        fontFamily: 'var(--font-mono)',
                        fontWeight: 700,
                        letterSpacing: '-0.02em',
                    }}>
                    {Math.round(score)}
                </text>
                <text x="60" y="76" textAnchor="middle"
                    style={{
                        fill: 'var(--text-muted)',
                        fontSize: 7.5,
                        fontFamily: 'var(--font-display)',
                        fontWeight: 600,
                        letterSpacing: '0.2em',
                    }}>
                    CREDIBILITY
                </text>
            </svg>
        </figure>
    )
}
