import { useEffect, useState } from 'react'
import { subscribeToHistory } from '../firebase.js'
import { timeAgo } from '../utils/format.js'
import VerdictBadge from '../components/VerdictBadge.jsx'
import { Clock, RefreshCw } from 'lucide-react'

export default function HistoryPage() {
    const [entries, setEntries] = useState([])
    const [loading, setLoading] = useState(true)

    useEffect(() => {
        /** Real-time Firestore subscription */
        const unsub = subscribeToHistory((docs) => {
            setEntries(docs)
            setLoading(false)
        })
        return unsub
    }, [])

    return (
        <main className="max-w-3xl mx-auto px-4 py-8 space-y-6">
            <header className="ruled fade-up-1 flex items-end justify-between">
                <div>
                    <h1 style={{ fontSize: 32, fontFamily: 'var(--font-display)' }}>History</h1>
                    <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                        Real-time from Firestore
                        {/* web-design-guidelines: tabular-nums for counts */}
                        {' — '}<span className="tabular">{entries.length}</span> records
                    </p>
                </div>
                {/* aria-label on icon wrapper */}
                <div className="flex items-center gap-1.5 text-xs"
                    style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', letterSpacing: '0.1em' }}
                    aria-label="Data is refreshing live">
                    <RefreshCw size={11} aria-hidden="true" />
                    LIVE
                </div>
            </header>

            {loading && (
                <p className="text-center py-16 text-sm" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}
                    aria-live="polite">
                    Loading history…
                </p>
            )}

            {!loading && entries.length === 0 && (
                <div className="card p-12 text-center fade-up">
                    <Clock size={28} aria-hidden="true"
                        style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
                    <p style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
                        No verifications yet
                    </p>
                    <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                        Run your first fact-check on the Verify tab.
                    </p>
                </div>
            )}

            {/* web-design-guidelines: <ul> list for screen readers */}
            {entries.length > 0 && (
                <ul className="space-y-2" role="list" aria-label="Verification history" aria-live="polite">
                    {entries.map((e, i) => (
                        <li key={e.id} className="card p-4 fade-up"
                            style={{ animationDelay: `${Math.min(i * 30, 300)}ms` }}>
                            <div className="flex items-start justify-between gap-3">
                                <div className="flex-1 min-w-0">
                                    {/* web-design-guidelines: flex children need min-w-0 for truncation */}
                                    <p className="text-sm truncate" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
                                        {e.text_preview || 'No text preview'}
                                    </p>
                                    <div className="flex items-center gap-2 mt-1.5">
                                        <span className="text-xs px-1.5 py-0.5"
                                            style={{
                                                background: 'var(--bg-elevated)',
                                                color: 'var(--text-muted)',
                                                fontFamily: 'var(--font-display)',
                                                letterSpacing: '0.08em',
                                                fontSize: 10,
                                                borderRadius: 2,
                                            }}>
                                            {e.input_type?.toUpperCase() ?? 'TEXT'}
                                        </span>
                                        {/* web-design-guidelines: Intl.DateTimeFormat via timeAgo util */}
                                        <time className="text-xs tabular" style={{ color: 'var(--text-muted)' }}
                                            dateTime={e.timestamp}>
                                            {timeAgo(e.timestamp)}
                                        </time>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3 shrink-0">
                                    <span className="tabular text-sm font-bold" style={{ color: 'var(--text-muted)' }}>
                                        {Math.round(e.final_score)}
                                    </span>
                                    <VerdictBadge verdict={e.verdict} size="sm" />
                                </div>
                            </div>
                        </li>
                    ))}
                </ul>
            )}
        </main>
    )
}
