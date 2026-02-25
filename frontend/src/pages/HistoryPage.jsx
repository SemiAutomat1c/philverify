import { useEffect, useState, useCallback, useMemo } from 'react'
import { subscribeToHistory } from '../firebase.js'
import { timeAgo, VERDICT_MAP, scoreColor } from '../utils/format.js'
import { PAGE_STYLE } from '../App.jsx'
import { api } from '../api'
import VerdictBadge from '../components/VerdictBadge.jsx'
import SkeletonCard from '../components/SkeletonCard.jsx'
import { Clock, RefreshCw, WifiOff, ChevronUp, ChevronDown, ChevronsUpDown, X, Loader2, FileText, Globe, ImageIcon, Video } from 'lucide-react'


/* ── Sort icon helper ─────────────────────────────────── */
function SortIcon({ field, current, dir }) {
    if (current !== field) return <ChevronsUpDown size={10} aria-hidden="true" style={{ opacity: 0.3 }} />
    return dir === 'asc'
        ? <ChevronUp size={10} aria-hidden="true" />
        : <ChevronDown size={10} aria-hidden="true" />
}

/* ── Column header button ─────────────────────────────── */
function ColHeader({ children, field, sort, dir, onSort }) {
    const active = sort === field
    return (
        <button
            onClick={() => onSort(field)}
            className="flex items-center gap-1 text-xs font-semibold uppercase"
            style={{
                fontFamily: 'var(--font-display)',
                letterSpacing: '0.1em',
                color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                padding: 0,
                minHeight: 44,
            }}
            aria-sort={active ? (dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
            {children}
            <SortIcon field={field} current={sort} dir={dir} />
        </button>
    )
}

/* ── Input-type icon ─────────────────────────────────── */
function InputTypeIcon({ type, size = 12 }) {
    const icons = { url: Globe, image: ImageIcon, video: Video, text: FileText }
    const Icon = icons[type] ?? FileText
    return <Icon size={size} aria-hidden="true" />
}

/* ── Detail Modal ────────────────────────────────────── */
function DetailModal({ id, onClose }) {
    const [data, setData] = useState(null)
    const [loadingDetail, setLoadingDetail] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        setLoadingDetail(true); setError(null)
        api.historyDetail(id)
            .then(setData)
            .catch(e => setError(e.message ?? 'Failed to load'))
            .finally(() => setLoadingDetail(false))
    }, [id])

    useEffect(() => {
        function onKey(e) { if (e.key === 'Escape') onClose() }
        window.addEventListener('keydown', onKey)
        return () => window.removeEventListener('keydown', onKey)
    }, [onClose])

    const s = scoreColor(data?.final_score)
    const layer1 = data?.layer1
    const layer2 = data?.layer2
    const entities = data?.entities?.entities ?? []

    return (
        <div
            role="dialog"
            aria-modal="true"
            aria-label="Verification detail"
            onClick={e => { if (e.target === e.currentTarget) onClose() }}
            style={{
                position: 'fixed', inset: 0, zIndex: 1000,
                background: 'rgba(0,0,0,0.6)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                padding: '16px',
                backdropFilter: 'blur(4px)',
            }}>
            <div className="card"
                style={{
                    width: '100%', maxWidth: 600,
                    maxHeight: '90vh', overflowY: 'auto',
                    padding: 0,
                    position: 'relative',
                    borderColor: 'var(--border-light)',
                    display: 'flex', flexDirection: 'column',
                }}>
                {/* Header */}
                <div className="flex items-center justify-between"
                    style={{
                        padding: '16px 20px',
                        borderBottom: '1px solid var(--border)',
                        background: 'var(--bg-elevated)',
                        position: 'sticky', top: 0, zIndex: 1,
                    }}>
                    <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold uppercase"
                            style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                            Verification Detail
                        </span>
                        {data && <span className="text-xs tabular"
                            style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', fontSize: 10 }}>
                            {id.slice(0, 8)}…
                        </span>}
                    </div>
                    <button onClick={onClose} aria-label="Close"
                        style={{
                            background: 'none', border: 'none', cursor: 'pointer',
                            color: 'var(--text-muted)', display: 'flex', alignItems: 'center',
                            padding: 4, borderRadius: 4,
                        }}>
                        <X size={16} />
                    </button>
                </div>

                {/* Body */}
                <div style={{ padding: '20px', display: 'flex', flexDirection: 'column', gap: 18 }}>

                    {loadingDetail && (
                        <div className="flex items-center justify-center" style={{ padding: 40, gap: 8, color: 'var(--text-muted)' }}>
                            <Loader2 size={18} className="animate-spin" />
                            <span className="text-sm" style={{ fontFamily: 'var(--font-body)' }}>Loading…</span>
                        </div>
                    )}

                    {error && (
                        <div className="text-sm text-center" style={{ color: 'var(--fake)', padding: 32, fontFamily: 'var(--font-body)' }}>
                            {error}
                        </div>
                    )}

                    {data && !loadingDetail && (<>
                        {/* Verdict + Score row */}
                        <div className="flex items-center gap-3 flex-wrap">
                            <VerdictBadge verdict={data.verdict} size="md" />
                            <span className="tabular font-bold"
                                style={{ fontSize: 28, fontFamily: 'var(--font-mono)', color: s, lineHeight: 1 }}>
                                {Math.round(data.final_score)}
                            </span>
                            <span className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                                score
                            </span>
                            <span className="tabular text-sm" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)', marginLeft: 'auto' }}>
                                {Math.round(data.confidence)}% confidence
                            </span>
                        </div>

                        {/* Meta row */}
                        <div className="flex items-center flex-wrap gap-2">
                            <span className="flex items-center gap-1 text-xs px-1.5 py-0.5"
                                style={{
                                    background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                                    borderRadius: 3, fontFamily: 'var(--font-display)', letterSpacing: '0.08em',
                                    color: 'var(--text-muted)',
                                }}>
                                <InputTypeIcon type={data.input_type} />
                                {data.input_type?.toUpperCase()}
                            </span>
                            {data.language && (
                                <span className="text-xs px-1.5 py-0.5"
                                    style={{
                                        background: 'var(--bg-elevated)', border: '1px solid var(--border)',
                                        borderRadius: 3, fontFamily: 'var(--font-display)', letterSpacing: '0.08em',
                                        color: 'var(--text-muted)', textTransform: 'uppercase',
                                    }}>
                                    {data.language}
                                </span>
                            )}
                            <time className="text-xs tabular ml-auto"
                                style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}
                                dateTime={data.timestamp}>
                                {new Date(data.timestamp).toLocaleString()}
                            </time>
                        </div>

                        {/* Claim / text */}
                        {(data.claim_used || data.text_preview) && (
                            <div style={{ borderLeft: '2px solid var(--border-light)', paddingLeft: 12 }}>
                                <p className="text-xs font-semibold uppercase mb-1"
                                    style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                                    Claim
                                </p>
                                <p className="text-sm" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)', lineHeight: 1.6 }}>
                                    {data.claim_used || data.text_preview}
                                </p>
                            </div>
                        )}

                        {/* Layer 1 */}
                        {layer1 && (
                            <div style={{ background: 'var(--bg-elevated)', borderRadius: 4, padding: '12px 14px', border: '1px solid var(--border)' }}>
                                <p className="text-xs font-semibold uppercase mb-2"
                                    style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                                    Layer 1 — NLP Analysis
                                </p>
                                <div className="flex items-center gap-3 mb-2">
                                    <VerdictBadge verdict={layer1.verdict} size="sm" />
                                    <span className="tabular text-sm" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                                        {Math.round(layer1.confidence)}% confidence
                                    </span>
                                </div>
                                {layer1.triggered_features?.length > 0 && (
                                    <div className="flex flex-wrap gap-1 mt-2">
                                        {layer1.triggered_features.map(f => (
                                            <span key={f} className="text-xs px-2 py-0.5"
                                                style={{
                                                    background: 'var(--bg-hover)', border: '1px solid var(--border)',
                                                    borderRadius: 3, fontFamily: 'var(--font-mono)',
                                                    color: 'var(--text-secondary)', fontSize: 10,
                                                }}>
                                                {f}
                                            </span>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Layer 2 */}
                        {layer2 && (
                            <div style={{ background: 'var(--bg-elevated)', borderRadius: 4, padding: '12px 14px', border: '1px solid var(--border)' }}>
                                <p className="text-xs font-semibold uppercase mb-2"
                                    style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                                    Layer 2 — Evidence Check
                                </p>
                                <div className="flex items-center gap-3 mb-2">
                                    <VerdictBadge verdict={layer2.verdict} size="sm" />
                                    <span className="tabular text-sm" style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
                                        Evidence: {Math.round((layer2.evidence_score ?? 0) * 100)}%
                                    </span>
                                </div>
                                {layer2.claim_used && (
                                    <p className="text-xs italic"
                                        style={{ fontFamily: 'var(--font-body)', color: 'var(--text-muted)', marginTop: 6 }}>
                                        &ldquo;{layer2.claim_used}&rdquo;
                                    </p>
                                )}
                            </div>
                        )}

                        {/* Sentiment */}
                        {(data.sentiment || data.emotion) && (
                            <div className="flex gap-3 flex-wrap">
                                {data.sentiment && (
                                    <div style={{ background: 'var(--bg-elevated)', borderRadius: 4, padding: '10px 14px', border: '1px solid var(--border)', flex: 1 }}>
                                        <p className="text-xs font-semibold uppercase mb-1"
                                            style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                                            Sentiment
                                        </p>
                                        <p className="text-sm capitalize" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
                                            {data.sentiment}
                                        </p>
                                    </div>
                                )}
                                {data.emotion && (
                                    <div style={{ background: 'var(--bg-elevated)', borderRadius: 4, padding: '10px 14px', border: '1px solid var(--border)', flex: 1 }}>
                                        <p className="text-xs font-semibold uppercase mb-1"
                                            style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                                            Emotion
                                        </p>
                                        <p className="text-sm capitalize" style={{ fontFamily: 'var(--font-body)', color: 'var(--text-primary)' }}>
                                            {data.emotion}
                                        </p>
                                    </div>
                                )}
                            </div>
                        )}

                        {/* Entities */}
                        {entities.length > 0 && (
                            <div>
                                <p className="text-xs font-semibold uppercase mb-2"
                                    style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                                    Entities Detected
                                </p>
                                <div className="flex flex-wrap gap-1.5">
                                    {entities.map((ent, i) => (
                                        <span key={i} className="flex items-center gap-1 text-xs px-2 py-0.5"
                                            style={{
                                                background: 'var(--bg-elevated)', border: '1px solid var(--border-light)',
                                                borderRadius: 3, fontFamily: 'var(--font-body)',
                                                color: 'var(--text-primary)',
                                            }}>
                                            {ent.text ?? ent.entity ?? ent}
                                            {(ent.label ?? ent.entity_type) && (
                                                <span style={{ color: 'var(--text-muted)', fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700 }}>
                                                    {(ent.label ?? ent.entity_type).toUpperCase()}
                                                </span>
                                            )}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}
                    </>)}
                </div>
            </div>
        </div>
    )
}

export default function HistoryPage() {
    const [entries, setEntries] = useState([])
    const [loading, setLoading] = useState(true)
    const [source, setSource] = useState('firestore')
    const [sort, setSort] = useState('timestamp')
    const [dir, setDir] = useState('desc')
    const [filter, setFilter] = useState('all') // 'all' | 'Credible' | 'Unverified' | 'Likely Fake'
    const [selectedId, setSelectedId] = useState(null)

    const fetchRest = useCallback(() => {
        api.history({ limit: 50 })
            .then(data => {
                const list = Array.isArray(data) ? data : (data.entries ?? [])
                setEntries(list)
            })
            .catch(() => setEntries([]))
            .finally(() => setLoading(false))
    }, [])

    useEffect(() => {
        let resolved = false
        let restInterval = null
        let unsubRef = null // declared before subscribeToHistory so goRest() can reach it

        function goRest() {
            if (resolved) return
            resolved = true
            // Immediately kill the Firestore listener so the SDK stops retrying
            // (prevents the ERR_BLOCKED_BY_CLIENT console flood from auto-retries)
            unsubRef?.()
            setSource('rest')
            fetchRest()
            restInterval = setInterval(fetchRest, 30_000)
        }

        // Fallback to REST after 1.5 s if Firestore hasn't connected
        const fallbackTimer = setTimeout(goRest, 1500)

        unsubRef = subscribeToHistory(
            (docs) => {
                if (!resolved) { resolved = true; clearTimeout(fallbackTimer) }
                setEntries(docs)
                setLoading(false)
            },
            // onError: Firestore blocked by ad-blocker → instant REST fallback
            () => {
                clearTimeout(fallbackTimer)
                goRest()
            }
        )

        return () => { unsubRef?.(); clearTimeout(fallbackTimer); if (restInterval) clearInterval(restInterval) }
    }, [fetchRest])

    function handleSort(field) {
        if (sort === field) setDir(d => d === 'asc' ? 'desc' : 'asc')
        else { setSort(field); setDir('desc') }
    }

    const filtered = useMemo(() => {
        let data = [...entries]
        if (filter !== 'all') data = data.filter(e => e.verdict === filter)
        data.sort((a, b) => {
            let av = a[sort], bv = b[sort]
            if (sort === 'timestamp') { av = new Date(av); bv = new Date(bv) }
            if (sort === 'final_score') { av = Number(av); bv = Number(bv) }
            if (av < bv) return dir === 'asc' ? -1 : 1
            if (av > bv) return dir === 'asc' ? 1 : -1
            return 0
        })
        return data
    }, [entries, sort, dir, filter])

    const verdictCounts = useMemo(() => {
        const counts = { all: entries.length, Credible: 0, Unverified: 0, 'Likely Fake': 0 }
        entries.forEach(e => { if (counts[e.verdict] !== undefined) counts[e.verdict]++ })
        return counts
    }, [entries])

    const FILTER_TABS = [
        { key: 'all', label: 'All', color: 'var(--text-secondary)' },
        { key: 'Credible', label: 'Verified', color: 'var(--credible)' },
        { key: 'Unverified', label: 'Unverified', color: 'var(--unverified)' },
        { key: 'Likely Fake', label: 'False', color: 'var(--fake)' },
    ]

    return (
        <main style={{ ...PAGE_STYLE, paddingTop: 40, paddingBottom: 56, display: 'flex', flexDirection: 'column', gap: 24 }}>

            {/* ── Header ────────────────────────────────── */}
            <header className="ruled fade-up-1 flex items-end justify-between flex-wrap gap-2">
                <div>
                    <h1 style={{ fontSize: 28, fontFamily: 'var(--font-display)' }}>History</h1>
                    <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                        {source === 'firestore' ? 'Real-time from Firestore' : 'Polling via REST API'}
                        {' — '}<span className="tabular" style={{ fontFamily: 'var(--font-mono)' }}>{entries.length}</span> records
                    </p>
                </div>
                <div className="flex items-center gap-1.5 text-xs"
                    style={{
                        color: source === 'rest' ? 'var(--accent-gold)' : 'var(--accent-green)',
                        fontFamily: 'var(--font-display)',
                        letterSpacing: '0.1em',
                    }}
                    aria-label={source === 'firestore' ? 'Live data' : 'Polling REST API'}>
                    <span className="w-1.5 h-1.5 rounded-full" style={{ background: 'currentColor' }} />
                    {source === 'rest' ? <><WifiOff size={11} aria-hidden="true" /> POLLING</> : <><RefreshCw size={11} aria-hidden="true" /> LIVE</>}
                </div>
            </header>

            {/* ── Firestore blocked notice ───────────────── */}
            {source === 'rest' && !loading && (
                <div className="card p-3 flex items-center gap-2"
                    style={{ borderColor: 'rgba(217,119,6,0.3)', background: 'rgba(217,119,6,0.05)' }}>
                    <WifiOff size={13} style={{ color: 'var(--accent-gold)', flexShrink: 0 }} aria-hidden="true" />
                    <p className="text-xs" style={{ color: 'var(--accent-gold)', fontFamily: 'var(--font-body)' }}>
                        Firestore may be blocked by an ad blocker — using REST fallback. Whitelist <code>firestore.googleapis.com</code> to restore live updates.
                    </p>
                </div>
            )}

            {/* ── Filter tabs ────────────────────────────── */}
            {!loading && entries.length > 0 && (
                <div role="tablist" aria-label="Filter by verdict" className="flex gap-1 flex-wrap fade-up-2">
                    {FILTER_TABS.map(({ key, label, color }) => (
                        <button key={key}
                            role="tab"
                            aria-selected={filter === key}
                            onClick={() => setFilter(key)}
                            className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold transition-colors"
                            style={{
                                fontFamily: 'var(--font-display)',
                                letterSpacing: '0.07em',
                                background: filter === key ? 'var(--bg-elevated)' : 'transparent',
                                color: filter === key ? color : 'var(--text-muted)',
                                border: `1px solid ${filter === key ? 'var(--border-light)' : 'var(--border)'}`,
                                cursor: 'pointer',
                                borderRadius: 2,
                                minHeight: 44,
                            }}>
                            {label}
                            <span style={{
                                background: 'var(--bg-hover)',
                                padding: '0 5px',
                                borderRadius: 2,
                                fontSize: 10,
                                fontFamily: 'var(--font-mono)',
                                color: filter === key ? color : 'var(--text-muted)',
                            }}>
                                {verdictCounts[key]}
                            </span>
                        </button>
                    ))}
                </div>
            )}

            {/* ── Loading skeleton ──────────────────────── */}
            {loading && (
                <div className="space-y-2" aria-live="polite" aria-label="Loading history">
                    {[...Array(5)].map((_, i) => <SkeletonCard key={i} lines={2} />)}
                </div>
            )}

            {/* ── Empty state ────────────────────────────── */}
            {!loading && entries.length === 0 && (
                <div className="card p-16 text-center fade-up">
                    <Clock size={28} aria-hidden="true" style={{ color: 'var(--text-muted)', margin: '0 auto 12px' }} />
                    <p style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
                        No verifications yet
                    </p>
                    <p className="mt-1 text-sm" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                        Run your first fact-check on the Verify tab.
                    </p>
                </div>
            )}

            {/* ── Table ─────────────────────────────────── */}
            {filtered.length > 0 && (
                <div className="card overflow-hidden fade-up-3">
                    {/* Table header */}
                    <div className="px-4 py-2 grid items-center"
                        style={{
                            gridTemplateColumns: '1fr 56px 90px 110px',
                            gap: '0 12px',
                            borderBottom: '1px solid var(--border)',
                            background: 'var(--bg-elevated)',
                        }}
                        role="row">
                        <ColHeader field="text_preview" sort={sort} dir={dir} onSort={handleSort}>Claim</ColHeader>
                        <div style={{ textAlign: 'right' }}>
                            <ColHeader field="final_score" sort={sort} dir={dir} onSort={handleSort}>Score</ColHeader>
                        </div>
                        <ColHeader field="timestamp" sort={sort} dir={dir} onSort={handleSort}>Time</ColHeader>
                        <span className="text-xs font-semibold uppercase"
                            style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.1em', color: 'var(--text-muted)' }}>
                            Verdict
                        </span>
                    </div>

                    {/* Rows */}
                    <ul className="divide-y" style={{ '--tw-divide-color': 'var(--border)' }} role="list" aria-label="Verification history" aria-live="polite">
                        {filtered.map((e, i) => (
                            <li key={e.id}
                                className="px-4 py-3 grid items-center fade-up hover:bg-[var(--bg-elevated)] transition-colors"
                                role="button"
                                tabIndex={0}
                                onClick={() => setSelectedId(e.id)}
                                onKeyDown={ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); setSelectedId(e.id) } }}
                                style={{
                                    gridTemplateColumns: '1fr 56px 90px 110px',
                                    gap: '0 12px',
                                    animationDelay: `${Math.min(i * 25, 200)}ms`,
                                    borderBottom: '1px solid var(--border)',
                                    cursor: 'pointer',
                                }}>
                                <div className="min-w-0">
                                    <p className="text-sm truncate" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
                                        {e.text_preview || 'No preview'}
                                    </p>
                                    <span className="text-xs px-1.5 py-0.5 mt-1 inline-block"
                                        style={{
                                            background: 'var(--bg-elevated)',
                                            color: 'var(--text-muted)',
                                            fontFamily: 'var(--font-display)',
                                            letterSpacing: '0.08em',
                                            fontSize: 9,
                                            borderRadius: 2,
                                        }}>
                                        {e.input_type?.toUpperCase() ?? 'TEXT'}
                                    </span>
                                </div>
                                <span className="tabular font-bold text-sm"
                                    style={{ color: scoreColor(e.final_score), fontFamily: 'var(--font-mono)', textAlign: 'right', display: 'block' }}>
                                    {Math.round(e.final_score)}
                                </span>
                                <time className="text-xs tabular" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', whiteSpace: 'nowrap' }}
                                    dateTime={e.timestamp}>
                                    {timeAgo(e.timestamp)}
                                </time>
                                <VerdictBadge verdict={e.verdict} size="sm" />
                            </li>
                        ))}
                    </ul>
                </div>
            )}

            {/* ── No results after filter ─────────────────── */}
            {!loading && entries.length > 0 && filtered.length === 0 && (
                <p className="text-center text-sm py-8" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                    No {filter} verifications found.
                </p>
            )}

            {/* ── Detail Modal ──────────────────────────── */}
            {selectedId && (
                <DetailModal id={selectedId} onClose={() => setSelectedId(null)} />
            )}
        </main>
    )
}
