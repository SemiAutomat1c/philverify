import { useState, useRef, useId } from 'react'
import { api } from '../api.js'
import { scoreColor } from '../utils/format.js'
import ScoreGauge from '../components/ScoreGauge.jsx'
import VerdictBadge from '../components/VerdictBadge.jsx'
import { FileText, Link2, Image, Video, Loader2, ChevronRight, AlertCircle } from 'lucide-react'

/* ── Tab definitions ────────────────────────────────────── */
const TABS = [
    { id: 'text', icon: FileText, label: 'Text' },
    { id: 'url', icon: Link2, label: 'URL' },
    { id: 'image', icon: Image, label: 'Image' },
    { id: 'video', icon: Video, label: 'Video' },
]

/* ── Atomic sub-components (architect-review: Single Responsibility) ── */
function SectionHeading({ children }) {
    return (
        <p className="font-display text-xs font-semibold uppercase tracking-widest mb-3"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--text-muted)', letterSpacing: '0.15em' }}>
            {children}
        </p>
    )
}

function MetaRow({ label, value, color }) {
    return (
        <div className="flex justify-between items-center py-2"
            style={{ borderBottom: '1px solid var(--border)' }}>
            <span className="text-xs" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                {label}
            </span>
            <span className="tabular text-xs font-bold" style={{ color: color || 'var(--text-primary)' }}>
                {value}
            </span>
        </div>
    )
}

function ScoreBar({ label, value, color, index = 0 }) {
    return (
        <div className="space-y-1.5">
            <div className="flex justify-between text-xs">
                <span style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>{label}</span>
                <span className="tabular font-bold" style={{ color }}>{Math.round(value)}%</span>
            </div>
            <div className="h-1 rounded-none" style={{ background: 'var(--bg-hover)' }}
                role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}
                aria-label={label}>
                <div className="h-1 bar-fill"
                    style={{
                        width: `${value}%`,
                        background: color,
                        animationDelay: `${index * 100}ms`,
                    }} />
            </div>
        </div>
    )
}

/* ── Main Page ──────────────────────────────────────────── */
export default function VerifyPage() {
    const [tab, setTab] = useState('text')
    const [input, setInput] = useState('')
    const [file, setFile] = useState(null)
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(null)
    const [error, setError] = useState(null)
    const fileRef = useRef()
    /* web-design-guidelines: label needs htmlFor — use useId for unique IDs */
    const inputId = useId()
    const errorId = useId()

    const canSubmit = !loading && (tab === 'text' || tab === 'url' ? input.trim() : file)

    async function handleSubmit(e) {
        e.preventDefault()
        if (!canSubmit) return
        setLoading(true); setError(null); setResult(null)
        try {
            let res
            if (tab === 'text') res = await api.verifyText(input)
            else if (tab === 'url') res = await api.verifyUrl(input)
            else if (tab === 'image') res = await api.verifyImage(file)
            else res = await api.verifyVideo(file)
            setResult(res)
        } catch (err) {
            setError(err.message)
        } finally {
            setLoading(false)
        }
    }

    function handleTabChange(id) {
        setTab(id); setInput(''); setFile(null); setResult(null); setError(null)
    }

    const entities = result?.entities || {}
    const allEntities = [
        ...(entities.persons || []).map(e => ({ label: e, type: 'Person' })),
        ...(entities.organizations || []).map(e => ({ label: e, type: 'Org' })),
        ...(entities.locations || []).map(e => ({ label: e, type: 'Place' })),
        ...(entities.dates || []).map(e => ({ label: e, type: 'Date' })),
    ]

    const finalColor = result ? scoreColor(result.final_score) : 'var(--text-muted)'

    return (
        <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
            {/* Page header */}
            <header className="ruled fade-up-1">
                <h1 style={{ fontSize: 32, fontFamily: 'var(--font-display)' }}>
                    Fact Check
                </h1>
                <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                    Paste text, a URL, or upload media — we'll verify credibility instantly.
                </p>
            </header>

            {/* Input card */}
            <section aria-label="Input panel" className="card p-6 space-y-4 fade-up-2">
                {/* Tab bar — web-design-guidelines: role="tablist" */}
                <div role="tablist" aria-label="Input type" className="flex gap-1">
                    {TABS.map(({ id, icon: Icon, label }) => {
                        const active = tab === id
                        return (
                            <button key={id}
                                role="tab"
                                aria-selected={active}
                                aria-controls={`panel-${id}`}
                                id={`tab-${id}`}
                                onClick={() => handleTabChange(id)}
                                className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold transition-colors"
                                style={{
                                    fontFamily: 'var(--font-display)',
                                    letterSpacing: '0.08em',
                                    background: active ? 'var(--accent-red)' : 'var(--bg-elevated)',
                                    color: active ? '#fff' : 'var(--text-secondary)',
                                    border: 'none',
                                    cursor: 'pointer',
                                    borderRadius: 2,
                                }}>
                                <Icon size={12} aria-hidden="true" />
                                {label.toUpperCase()}
                            </button>
                        )
                    })}
                </div>

                <form onSubmit={handleSubmit} className="space-y-4"
                    aria-describedby={error ? errorId : undefined}>
                    {/* Label — web-design-guidelines: inputs need labels */}
                    {(tab === 'text' || tab === 'url') ? (
                        <div>
                            <label htmlFor={inputId} className="sr-only">
                                {tab === 'url' ? 'Enter a URL to verify' : 'Enter text or headline to verify'}
                            </label>
                            <textarea
                                id={inputId}
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                placeholder={tab === 'url' ? 'https://rappler.com/…' : 'Paste claim or headline here…'}
                                rows={tab === 'url' ? 2 : 5}
                                /* web-design-guidelines: autocomplete + type */
                                autoComplete="off"
                                spellCheck={tab === 'url' ? 'false' : 'true'}
                                className="w-full resize-none p-4 text-sm"
                                style={{
                                    background: 'var(--bg-elevated)',
                                    border: '1px solid var(--border)',
                                    color: 'var(--text-primary)',
                                    fontFamily: 'var(--font-body)',
                                    borderRadius: 2,
                                    outline: 'none',
                                }}
                                onFocus={e => e.target.style.borderColor = 'var(--accent-red)'}
                                onBlur={e => e.target.style.borderColor = 'var(--border)'}
                                aria-label={tab === 'url' ? 'URL input' : 'Claim text input'}
                            />
                        </div>
                    ) : (
                        /* File drop zone */
                        <div>
                            <label htmlFor={`file-${tab}`} className="sr-only">
                                Upload {tab === 'image' ? 'an image' : 'a video or audio file'}
                            </label>
                            <div
                                onClick={() => fileRef.current?.click()}
                                onKeyDown={e => e.key === 'Enter' && fileRef.current?.click()}
                                tabIndex={0}
                                role="button"
                                aria-label={`Upload ${tab} file. ${file ? `Selected: ${file.name}` : 'No file selected'}`}
                                className="p-10 text-center cursor-pointer transition-colors"
                                style={{
                                    background: 'var(--bg-elevated)',
                                    border: `1px dashed ${file ? 'var(--accent-red)' : 'var(--border)'}`,
                                    borderRadius: 2,
                                }}>
                                <input ref={fileRef} id={`file-${tab}`} type="file" className="sr-only"
                                    accept={tab === 'image' ? 'image/*' : 'video/*,audio/*'}
                                    onChange={e => setFile(e.target.files[0])} />
                                {file
                                    ? <p className="text-sm font-semibold" style={{ color: 'var(--accent-red)', fontFamily: 'var(--font-display)' }}>{file.name}</p>
                                    : <p className="text-sm" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                                        Click or press Enter to upload {tab === 'image' ? 'image' : 'video / audio'}
                                    </p>
                                }
                            </div>
                        </div>
                    )}

                    {/* Submit — web-design-guidelines: specific button label, spinner during request */}
                    <button type="submit" disabled={!canSubmit}
                        className="flex items-center gap-2 px-5 py-2.5 text-xs font-bold transition-colors"
                        style={{
                            fontFamily: 'var(--font-display)',
                            letterSpacing: '0.1em',
                            background: canSubmit ? 'var(--accent-red)' : 'var(--bg-elevated)',
                            color: canSubmit ? '#fff' : 'var(--text-muted)',
                            border: 'none',
                            cursor: canSubmit ? 'pointer' : 'not-allowed',
                            borderRadius: 2,
                        }}
                        aria-busy={loading}>
                        {loading
                            ? <><Loader2 size={13} className="animate-spin" aria-hidden="true" /> ANALYZING…</>
                            : <><ChevronRight size={13} aria-hidden="true" /> VERIFY CLAIM</>
                        }
                    </button>
                </form>
            </section>

            {/* Error — web-design-guidelines: errors inline, include fix */}
            {error && (
                <div id={errorId} role="alert"
                    className="card p-4 flex items-start gap-2"
                    style={{ borderColor: 'rgba(220,38,38,0.4)' }}>
                    <AlertCircle size={15} style={{ color: '#f87171', marginTop: 1, flexShrink: 0 }} aria-hidden="true" />
                    <div>
                        <p className="text-sm font-semibold" style={{ color: '#f87171', fontFamily: 'var(--font-display)' }}>
                            Verification failed
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                            {error} — Check that the backend server is running on port 8000.
                        </p>
                    </div>
                </div>
            )}

            {/* Results */}
            {result && (
                <section aria-label="Verification results" className="space-y-4">

                    {/* Top row — gauge + verdict banner */}
                    <div className="grid gap-4 fade-up-1" style={{ gridTemplateColumns: '180px 1fr' }}>
                        {/* Gauge panel */}
                        <div className="card p-5 flex flex-col items-center justify-center gap-3">
                            <ScoreGauge score={result.final_score} size={140} />
                            <VerdictBadge verdict={result.verdict} size="banner" />
                        </div>

                        {/* Meta panel */}
                        <div className="card p-5 fade-up-2">
                            <SectionHeading>Analysis Details</SectionHeading>
                            <MetaRow label="Language" value={result.language} />
                            <MetaRow label="Sentiment" value={result.sentiment} />
                            <MetaRow label="Emotion" value={result.emotion} />
                            <MetaRow label="Confidence" value={`${result.confidence?.toFixed(1)}%`}
                                color={finalColor} />
                            <MetaRow label="Processed in" value={`${result.processing_time_ms?.toFixed(0)} ms`}
                                color="var(--accent-cyan)" />
                        </div>
                    </div>

                    {/* Score breakdown */}
                    <div className="card p-5 fade-up-3">
                        <SectionHeading>Score Breakdown</SectionHeading>
                        <div className="space-y-4">
                            <ScoreBar label="ML Classifier (Layer 1)" value={result.layer1?.confidence || 0} color="var(--accent-cyan)" index={0} />
                            <ScoreBar label="Evidence Score (Layer 2)" value={result.layer2?.evidence_score || 0} color="var(--accent-gold)" index={1} />
                            <ScoreBar label="Final Credibility Score" value={result.final_score} color={finalColor} index={2} />
                        </div>
                    </div>

                    {/* Named entities */}
                    {allEntities.length > 0 && (
                        <div className="card p-5 fade-up-4">
                            <SectionHeading>Named Entities ({allEntities.length})</SectionHeading>
                            <ul className="flex flex-wrap gap-2" role="list">
                                {allEntities.map((e, i) => (
                                    <li key={i}
                                        className="flex items-center gap-1.5 px-2.5 py-1 text-xs"
                                        style={{
                                            background: 'var(--bg-elevated)',
                                            border: '1px solid var(--border)',
                                            borderRadius: 2,
                                        }}>
                                        <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', fontSize: 9, letterSpacing: '0.1em' }}>
                                            {e.type.toUpperCase()}
                                        </span>
                                        <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>{e.label}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Evidence sources */}
                    {result.layer2?.sources?.length > 0 && (
                        <div className="card p-5 fade-up-5">
                            <SectionHeading>Evidence Sources</SectionHeading>
                            <ul className="space-y-2" role="list">
                                {result.layer2.sources.map((src, i) => (
                                    <li key={i}>
                                        <a href={src.url} target="_blank" rel="noreferrer"
                                            className="block p-3 transition-colors"
                                            style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 2 }}>
                                            <p className="text-xs font-semibold mb-0.5" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
                                                {src.title}
                                            </p>
                                            <p className="text-xs tabular" style={{ color: 'var(--text-muted)' }}>
                                                {src.source} · {(src.similarity * 100).toFixed(0)}% match
                                            </p>
                                        </a>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </section>
            )}
        </main>
    )
}
