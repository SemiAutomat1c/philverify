/**
 * SkeletonCard — Phase 8: Loading state skeleton screens
 * Used while the verification API call is in-flight.
 * web-design-guidelines: content-jumping — reserve space for async content.
 * web-design-guidelines: prefers-reduced-motion — skip animation if user prefers.
 */
export default function SkeletonCard({ lines = 3, height = null, className = '' }) {
    return (
        <div className={`card p-5 ${className}`} aria-hidden="true">
            {height ? (
                <SkeletonBar style={{ height, borderRadius: 4 }} />
            ) : (
                <div className="space-y-3">
                    {Array.from({ length: lines }).map((_, i) => (
                        <SkeletonBar key={i}
                            style={{
                                height: i === 0 ? 12 : 10,
                                width: i === lines - 1 ? '60%' : '100%',
                            }}
                        />
                    ))}
                </div>
            )}
        </div>
    )
}

function SkeletonBar({ style = {} }) {
    return (
        <div
            style={{
                background: 'var(--bg-elevated)',
                borderRadius: 3,
                overflow: 'hidden',
                ...style,
            }}
        >
            <div style={{
                width: '100%',
                height: '100%',
                background: 'linear-gradient(90deg, transparent 0%, rgba(245,240,232,0.05) 50%, transparent 100%)',
                animation: 'shimmer 1.5s infinite',
            }} />
        </div>
    )
}
