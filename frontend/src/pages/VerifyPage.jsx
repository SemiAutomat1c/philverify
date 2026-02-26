import { useState, useRef, useId, useCallback, useEffect } from 'react'
import { api } from '../api'
import { scoreColor, VERDICT_MAP, scoreInterpretation, mlConfidenceExplanation, evidenceExplanation } from '../utils/format.js'
import { PAGE_STYLE } from '../App.jsx'
import ScoreGauge from '../components/ScoreGauge.jsx'
import VerdictBadge from '../components/VerdictBadge.jsx'
import WordHighlighter from '../components/WordHighlighter.jsx'
import SkeletonCard from '../components/SkeletonCard.jsx'
import { FileText, Link2, Image, Video, Loader2, ChevronRight, AlertCircle, Upload, CheckCircle2, XCircle, HelpCircle, ExternalLink, Layers, Brain, RefreshCw, Info } from 'lucide-react'

/* ── Tab definitions ────────────────────────────────────── */
const TABS = [
    { id: 'text', icon: FileText, label: 'Text' },
    { id: 'url', icon: Link2, label: 'URL' },
    { id: 'image', icon: Image, label: 'Image' },
    { id: 'video', icon: Video, label: 'Video' },
]

/* ── Stance icon map ──────────────────────────────────────── */
const STANCE_ICON = {
    'Supports': { Icon: CheckCircle2, color: 'var(--credible)' },
    'Refutes': { Icon: XCircle, color: 'var(--fake)' },
    'Not Enough Info': { Icon: HelpCircle, color: 'var(--text-muted)' },
}

/* ── Atomic sub-components (architect-review: Single Responsibility) ── */
function SectionHeading({ children, count }) {
    return (
        <p className="font-display text-xs font-semibold uppercase tracking-widest mb-3 flex items-center gap-2"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--text-muted)', letterSpacing: '0.15em' }}>
            {children}
            {count !== undefined && (
                <span style={{
                    background: 'var(--bg-hover)',
                    color: 'var(--text-secondary)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    padding: '1px 6px',
                    borderRadius: 2,
                }}>{count}</span>
            )}
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
            <div className="h-1.5 rounded-none" style={{ background: 'var(--bg-hover)' }}
                role="progressbar" aria-valuenow={Math.round(value)} aria-valuemin={0} aria-valuemax={100}
                aria-label={label}>
                <div className="h-1.5 bar-fill"
                    style={{
                        width: `${value}%`,
                        background: color,
                        animationDelay: `${index * 120}ms`,
                        borderRadius: 1,
                    }} />
            </div>
        </div>
    )
}

/** Layer verdict detail card — for both Layer 1 and Layer 2 */
function LayerCard({ title, icon: HeaderIcon, verdict, score, children, delay = 0 }) {
    const { cls } = VERDICT_MAP[verdict] ?? VERDICT_MAP['Unverified']
    return (
        <div className="card p-5 fade-up" style={{ animationDelay: `${delay}ms` }}>
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <HeaderIcon size={13} style={{ color: 'var(--accent-red)' }} aria-hidden="true" />
                    <SectionHeading>{title}</SectionHeading>
                </div>
                <VerdictBadge verdict={verdict} size="sm" />
            </div>
            {score !== undefined && (
                <ScoreBar label="Confidence" value={score} color={scoreColor(score)} index={0} />
            )}
            {children && <div className="mt-4">{children}</div>}
        </div>
    )
}

/** Triggered features feature breakdown chart */
function FeatureBreakdown({ features }) {
    if (!features?.length) return (
        <p className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
            No suspicious features detected
        </p>
    )
    return (
        <ul className="flex flex-wrap gap-1.5" role="list" aria-label="Triggered suspicious features">
            {features.map((f, i) => (
                <li key={i}
                    className="text-xs px-2 py-1"
                    style={{
                        background: 'rgba(220,38,38,0.1)',
                        color: '#f87171',
                        border: '1px solid rgba(220,38,38,0.25)',
                        borderRadius: 2,
                        fontFamily: 'var(--font-display)',
                        letterSpacing: '0.04em',
                    }}>
                    {f}
                </li>
            ))}
        </ul>
    )
}
/* ── URL article preview card ───────────────────────────── */
function URLPreviewCard({ preview, loading, url }) {
    if (loading && !preview) {
        return (
            <div className="flex items-center gap-2 px-3 py-2"
                style={{ background: 'var(--bg-elevated)', border: '1px solid var(--border)', borderRadius: 2 }}>
                <Loader2 size={11} className="animate-spin" style={{ color: 'var(--text-muted)', flexShrink: 0 }} aria-hidden="true" />
                <span className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>Fetching article preview…</span>
            </div>
        )
    }
    if (!preview) return null
    return (
        <a href={url} target="_blank" rel="noreferrer"
            className="flex gap-3 p-3 transition-colors"
            style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 2,
                textDecoration: 'none',
                display: 'flex',
            }}
            onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-light)'}
            onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}>
            {/* Thumbnail */}
            {preview.image && (
                <img
                    src={preview.image}
                    alt=""
                    aria-hidden="true"
                    onError={e => { e.currentTarget.style.display = 'none' }}
                    style={{
                        width: 72, height: 56,
                        objectFit: 'cover',
                        borderRadius: 2,
                        flexShrink: 0,
                        border: '1px solid var(--border)',
                    }} />
            )}
            <div className="flex-1 min-w-0">
                {/* Source row */}
                <div className="flex items-center gap-1.5 mb-1">
                    {preview.favicon && (
                        <img src={preview.favicon} alt="" aria-hidden="true"
                            onError={e => { e.currentTarget.style.display = 'none' }}
                            style={{ width: 12, height: 12, borderRadius: 2, flexShrink: 0 }} />
                    )}
                    <span className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', letterSpacing: '0.06em', textTransform: 'uppercase', fontSize: 10 }}>
                        {preview.site_name || preview.domain}
                    </span>
                    <ExternalLink size={9} style={{ color: 'var(--text-muted)', flexShrink: 0, marginLeft: 'auto' }} aria-hidden="true" />
                </div>
                {/* Title */}
                {preview.title && (
                    <p className="text-sm font-semibold"
                        style={{
                            color: 'var(--text-primary)',
                            fontFamily: 'var(--font-body)',
                            lineHeight: 1.4,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                        }}>
                        {preview.title}
                    </p>
                )}
                {/* Description */}
                {preview.description && (
                    <p className="text-xs mt-0.5"
                        style={{
                            color: 'var(--text-secondary)',
                            fontFamily: 'var(--font-body)',
                            lineHeight: 1.5,
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                        }}>
                        {preview.description}
                    </p>
                )}
            </div>
        </a>
    )
}
/* ── SessionStorage persistence key ─────────────────────── */
const STORAGE_KEY = 'philverify_verify_state'

function loadPersistedState() {
    try {
        const raw = sessionStorage.getItem(STORAGE_KEY)
        if (!raw) return null
        return JSON.parse(raw)
    } catch {
        return null
    }
}

function saveState(state) {
    try {
        sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state))
    } catch { /* quota exceeded — ignore */ }
}

/* ── Main Page ──────────────────────────────────────────── */
export default function VerifyPage() {
    const persisted = loadPersistedState()

    const [tab, setTab] = useState(persisted?.tab ?? 'text')
    const [input, setInput] = useState(persisted?.input ?? '')
    const [file, setFile] = useState(null)
    const [dragOver, setDragOver] = useState(false)
    const [loading, setLoading] = useState(false)
    const [result, setResult] = useState(persisted?.result ?? null)
    const [error, setError] = useState(null)
    const [submittedInput, setSubmittedInput] = useState(persisted?.submittedInput ?? null)
    const [urlPreview, setUrlPreview] = useState(null)
    const [urlPreviewLoading, setUrlPreviewLoading] = useState(false)
    const [extractedTextOpen, setExtractedTextOpen] = useState(false)
    const fileRef = useRef()
    const inputSectionRef = useRef()
    const inputId = useId()
    const errorId = useId()

    /* Revoke object URLs when submittedInput changes to avoid memory leaks */
    useEffect(() => {
        return () => {
            if (submittedInput?.fileUrl) URL.revokeObjectURL(submittedInput.fileUrl)
        }
    }, [submittedInput])

    /* Persist result + input to sessionStorage so state survives navigation/refresh */
    useEffect(() => {
        if (result) {
            // Strip non-serialisable file references before saving
            const serializableSubmittedInput = submittedInput
                ? { type: submittedInput.type, text: submittedInput.text, preview: submittedInput.preview ?? null }
                : null
            saveState({ tab, input, result, submittedInput: serializableSubmittedInput })
        }
    }, [result, submittedInput, tab, input])

    /* Debounced URL preview — fetches OG metadata 600ms after typing stops */
    useEffect(() => {
        if (tab !== 'url' || !input.trim()) { setUrlPreview(null); setUrlPreviewLoading(false); return }
        try { new URL(input.trim()) } catch { setUrlPreview(null); setUrlPreviewLoading(false); return }
        setUrlPreviewLoading(true)
        const timer = setTimeout(async () => {
            try {
                const preview = await api.preview(input.trim())
                setUrlPreview(preview)
            } catch {
                setUrlPreview(null)
            } finally {
                setUrlPreviewLoading(false)
            }
        }, 600)
        return () => { clearTimeout(timer); setUrlPreviewLoading(false) }
    }, [tab, input])

    const canSubmit = !loading && (tab === 'text' || tab === 'url' ? input.trim() : file)

    function isSocialUrl(s) {
        try {
            const h = new URL(s).hostname
            return h.includes('facebook.com') || h.includes('x.com') || h.includes('twitter.com')
        } catch { return false }
    }

    async function handleSubmit(e) {
        e.preventDefault()
        if (!canSubmit) return

        /* Capture what the user submitted before any state resets */
        const previewUrl = (tab === 'image' || tab === 'video') && file
            ? URL.createObjectURL(file)
            : null
        setSubmittedInput({ type: tab, text: input, file: file, fileUrl: previewUrl, preview: tab === 'url' ? urlPreview : null })
        setLoading(true); setError(null); setResult(null)
        sessionStorage.removeItem(STORAGE_KEY)
        try {
            let res
            if (tab === 'text') res = await api.verifyText(input)
            else if (tab === 'url') res = await api.verifyUrl(input)
            else if (tab === 'image') res = await api.verifyImage(file)
            else res = await api.verifyVideo(file)
            setResult(res)
        } catch (err) {
            setError(typeof err.message === 'string' ? err.message : String(err))
        } finally {
            setLoading(false)
        }
    }

    function handleTabChange(id) {
        setTab(id); setInput(''); setFile(null); setResult(null); setError(null); setSubmittedInput(null); setUrlPreview(null)
        sessionStorage.removeItem(STORAGE_KEY)
    }

    function handleVerifyAgain() {
        setResult(null); setError(null); setExtractedTextOpen(false)
        sessionStorage.removeItem(STORAGE_KEY)
        // Smooth-scroll back to the input panel
        requestAnimationFrame(() => {
            inputSectionRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
        })
    }

    /* Drag-and-drop handlers */
    const handleDrop = useCallback((e) => {
        e.preventDefault(); setDragOver(false)
        const dropped = e.dataTransfer.files[0]
        if (dropped) setFile(dropped)
    }, [])

    /* Paste handler — reads the first file/image item from clipboard */
    const handlePaste = useCallback((e) => {
        if (tab !== 'image' && tab !== 'video') return
        const items = e.clipboardData?.items
        if (!items) return
        for (const item of items) {
            if (item.kind === 'file') {
                const pasted = item.getAsFile()
                if (pasted) {
                    e.preventDefault()
                    setFile(pasted)
                    return
                }
            }
        }
    }, [tab])

    /* Global paste listener — works even when the drop zone isn't focused */
    useEffect(() => {
        if (tab !== 'image' && tab !== 'video') return
        document.addEventListener('paste', handlePaste)
        return () => document.removeEventListener('paste', handlePaste)
    }, [tab, handlePaste])

    const entities = result?.entities || {}
    const allEntities = [
        ...(entities.persons || []).map(e => ({ label: e, type: 'Person', color: 'var(--accent-cyan)' })),
        ...(entities.organizations || []).map(e => ({ label: e, type: 'Org', color: 'var(--accent-gold)' })),
        ...(entities.locations || []).map(e => ({ label: e, type: 'Place', color: '#8b5cf6' })),
        ...(entities.dates || []).map(e => ({ label: e, type: 'Date', color: 'var(--text-muted)' })),
    ]

    const finalColor = result ? scoreColor(result.final_score) : 'var(--text-muted)'
    const triggerWords = result?.layer1?.triggered_features ?? []

    return (
        <main style={{ ...PAGE_STYLE, paddingTop: 40, paddingBottom: 56, display: 'flex', flexDirection: 'column', gap: 24 }}>

            {/* ── Page header ─────────────────────────────── */}
            <header className="ruled fade-up-1">
                <h1 style={{ fontSize: 28, fontFamily: 'var(--font-display)' }}>Fact Check</h1>
                <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                    Paste text, a URL, or upload media — we'll verify credibility instantly.
                </p>
            </header>

            {/* ── Input card ──────────────────────────────── */}
            <section ref={inputSectionRef} aria-label="Input panel" className="card p-6 space-y-4 fade-up-2">
                {/* Tab bar */}
                <div role="tablist" aria-label="Input type" className="flex gap-1.5 flex-wrap">
                    {TABS.map(({ id, icon: Icon, label }) => {
                        const active = tab === id
                        return (
                            <button key={id}
                                role="tab"
                                aria-selected={active}
                                aria-controls={`panel-${id}`}
                                id={`tab-${id}`}
                                onClick={() => handleTabChange(id)}
                                className="flex items-center gap-1.5 px-3 py-2 text-xs font-semibold transition-colors"
                                style={{
                                    fontFamily: 'var(--font-display)',
                                    letterSpacing: '0.08em',
                                    background: active ? 'var(--accent-red)' : 'var(--bg-elevated)',
                                    color: active ? '#fff' : 'var(--text-secondary)',
                                    border: 'none',
                                    cursor: 'pointer',
                                    borderRadius: 2,
                                    minHeight: 36, /* touch target */
                                }}>
                                <Icon size={12} aria-hidden="true" />
                                {label.toUpperCase()}
                            </button>
                        )
                    })}
                </div>

                <form onSubmit={handleSubmit} className="space-y-4"
                    aria-describedby={error ? errorId : undefined}>

                    {(tab === 'text' || tab === 'url') ? (
                        <div className="space-y-2">
                            <label htmlFor={inputId} className="sr-only">
                                {tab === 'url' ? 'Enter a URL to verify' : 'Enter text or headline to verify'}
                            </label>
                            <textarea
                                id={inputId}
                                value={input}
                                onChange={e => setInput(e.target.value)}
                                placeholder={tab === 'url'
                                    ? 'https://rappler.com/…'
                                    : 'Paste claim, headline, or social post here…'}
                                rows={tab === 'url' ? 2 : 5}
                                autoComplete="off"
                                spellCheck={tab === 'url' ? 'false' : 'true'}
                                name={tab === 'url' ? 'claim-url' : 'claim-text'}
                                className="w-full resize-none p-4 text-sm claim-textarea"
                                style={{
                                    background: 'var(--bg-elevated)',
                                    border: '1px solid var(--border)',
                                    color: 'var(--text-primary)',
                                    fontFamily: 'var(--font-body)',
                                    borderRadius: 2,
                                    lineHeight: 1.7,
                                }}
                                onFocus={e => e.target.style.borderColor = 'var(--accent-red)'}
                                onBlur={e => e.target.style.borderColor = 'var(--border)'}
                                aria-label={tab === 'url' ? 'URL input' : 'Claim text input'}
                            />
                            {/* Inline URL article preview while typing */}
                            {tab === 'url' && (urlPreviewLoading || urlPreview) && (
                                <URLPreviewCard preview={urlPreview} loading={urlPreviewLoading} url={input} />
                            )}
                        </div>
                    ) : (
                        /* Drag-and-drop file zone */
                        <div>
                            <label htmlFor={`file-${tab}`} className="sr-only">
                                Upload {tab === 'image' ? 'an image' : 'a video or audio file'}
                            </label>
                            <div
                                onClick={() => fileRef.current?.click()}
                                onKeyDown={e => e.key === 'Enter' && fileRef.current?.click()}
                                onDragOver={e => { e.preventDefault(); setDragOver(true) }}
                                onDragLeave={() => setDragOver(false)}
                                onDrop={handleDrop}
                                onPaste={handlePaste}
                                tabIndex={0}
                                role="button"
                                aria-label={`Upload ${tab} file. ${file ? `Selected: ${file.name}` : 'No file selected'}`}
                                className="p-10 text-center cursor-pointer transition-all"
                                style={{
                                    background: dragOver ? 'rgba(220,38,38,0.06)' : 'var(--bg-elevated)',
                                    border: `1px dashed ${file ? 'var(--accent-red)' : dragOver ? 'var(--accent-red)' : 'var(--border)'}`,
                                    borderRadius: 2,
                                    transform: dragOver ? 'scale(1.01)' : 'scale(1)',
                                }}>
                                <input ref={fileRef} id={`file-${tab}`} type="file" className="sr-only"
                                    name={tab === 'image' ? 'media-image' : 'media-video'}
                                    accept={tab === 'image' ? 'image/*' : 'video/*,audio/*'}
                                    onChange={e => setFile(e.target.files[0])} />
                                <Upload size={18} aria-hidden="true"
                                    style={{ margin: '0 auto 8px', color: file ? 'var(--accent-red)' : 'var(--text-muted)' }} />
                                {file
                                    ? <p className="text-sm font-semibold" style={{ color: 'var(--accent-red)', fontFamily: 'var(--font-display)' }}>{file.name}</p>
                                    : <>
                                        <p className="text-sm" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                                            Drop or click to upload {tab === 'image' ? 'image' : 'video / audio'}
                                        </p>
                                        <p className="text-xs mt-1" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', opacity: 0.6 }}>
                                            or press <kbd style={{ background: 'var(--bg-hover)', border: '1px solid var(--border)', borderRadius: 2, padding: '1px 5px', fontFamily: 'var(--font-mono)', fontSize: 10 }}>Ctrl+V</kbd> to paste from clipboard
                                        </p>
                                    </>
                                }
                            </div>
                        </div>
                    )}

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
                            minHeight: 44,
                        }}
                        aria-busy={loading}>
                        {loading
                            ? <><Loader2 size={13} className="animate-spin" aria-hidden="true" /> ANALYZING…</>
                            : <><ChevronRight size={13} aria-hidden="true" /> VERIFY CLAIM</>
                        }
                    </button>
                </form>
            </section>

            {/* ── Submitted input preview ──────────────────── */}
            {submittedInput && (loading || result || error) && (
                <div className="card p-4 fade-up" style={{ borderLeft: '3px solid var(--accent-red)' }}>
                    <p className="text-xs font-semibold uppercase tracking-widest mb-2"
                        style={{ fontFamily: 'var(--font-display)', color: 'var(--text-muted)', letterSpacing: '0.15em' }}>
                        Verified Input
                    </p>
                    {submittedInput.type === 'url' && (
                        <div className="space-y-2">
                            {/* Rich article card if preview is available */}
                            {submittedInput.preview
                                ? <URLPreviewCard preview={submittedInput.preview} loading={false} url={submittedInput.text} />
                                : (
                                    <a href={submittedInput.text} target="_blank" rel="noreferrer"
                                        className="flex items-center gap-2 text-sm"
                                        style={{ color: 'var(--accent-cyan)', fontFamily: 'var(--font-mono)', wordBreak: 'break-all', textDecoration: 'none' }}
                                        onMouseEnter={e => e.currentTarget.style.opacity = '0.8'}
                                        onMouseLeave={e => e.currentTarget.style.opacity = '1'}>
                                        <Link2 size={13} style={{ flexShrink: 0 }} aria-hidden="true" />
                                        <span className="flex-1">{submittedInput.text}</span>
                                        <ExternalLink size={11} style={{ flexShrink: 0, opacity: 0.6 }} aria-hidden="true" />
                                    </a>
                                )
                            }
                        </div>
                    )}
                    {submittedInput.type === 'text' && (
                        <p className="text-sm" style={{
                            color: 'var(--text-secondary)',
                            fontFamily: 'var(--font-body)',
                            lineHeight: 1.6,
                            whiteSpace: 'pre-wrap',
                            wordBreak: 'break-word',
                        }}>
                            {submittedInput.text.length > 300
                                ? submittedInput.text.slice(0, 300) + '…'
                                : submittedInput.text}
                        </p>
                    )}
                    {submittedInput.type === 'image' && (
                        <div className="flex items-start gap-3">
                            {submittedInput.fileUrl && (
                                <img
                                    src={submittedInput.fileUrl}
                                    alt="Submitted image preview"
                                    style={{
                                        width: 72, height: 72,
                                        objectFit: 'cover',
                                        borderRadius: 2,
                                        border: '1px solid var(--border)',
                                        flexShrink: 0,
                                    }} />
                            )}
                            <div>
                                <p className="text-sm font-semibold"
                                    style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                                    {submittedInput.file?.name}
                                </p>
                                <p className="text-xs mt-0.5"
                                    style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                    {submittedInput.file ? (submittedInput.file.size / 1024).toFixed(1) + ' KB' : ''}
                                </p>
                            </div>
                        </div>
                    )}
                    {submittedInput.type === 'video' && (
                        <div className="flex items-center gap-2">
                            <Video size={15} style={{ color: 'var(--text-muted)', flexShrink: 0 }} aria-hidden="true" />
                            <div>
                                <p className="text-sm font-semibold"
                                    style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                                    {submittedInput.file?.name}
                                </p>
                                <p className="text-xs mt-0.5"
                                    style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                                    {submittedInput.file ? (submittedInput.file.size / (1024 * 1024)).toFixed(2) + ' MB' : ''}
                                </p>
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* ── Error ───────────────────────────────────── */}
            {error && (
                <div id={errorId} role="alert"
                    className="card p-4 flex items-start gap-2"
                    style={{ borderColor: isSocialUrl(input) ? 'rgba(220,150,38,0.4)' : 'rgba(220,38,38,0.4)' }}>
                    <AlertCircle size={15} style={{ color: '#f87171', marginTop: 1, flexShrink: 0 }} aria-hidden="true" />
                    <div>
                        <p className="text-sm font-semibold" style={{ color: '#f87171', fontFamily: 'var(--font-display)' }}>
                            Verification failed
                        </p>
                        <p className="text-xs mt-0.5" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                            {error}
                            {/failed to fetch|network|ERR_/i.test(error) && (
                                <> — Make sure the backend is running at <code>localhost:8000</code>.</>
                            )}
                        </p>
                    </div>
                </div>
            )}

            {/* ── Skeleton loading state ───────────────────── */}
            {loading && (
                <section aria-label="Loading verification results" aria-live="polite" className="space-y-4">
                    <div className="grid gap-4" style={{ gridTemplateColumns: '180px 1fr' }}>
                        <SkeletonCard height={180} />
                        <SkeletonCard lines={5} />
                    </div>
                    <SkeletonCard lines={3} />
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                        <SkeletonCard lines={4} />
                        <SkeletonCard lines={4} />
                    </div>
                </section>
            )}

            {/* ── Results ──────────────────────────────────── */}
            {result && !loading && (
                <section aria-label="Verification results" className="space-y-4">

                    {/* Verify Again bar */}
                    <div className="flex items-center justify-between py-1">
                        <p className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', letterSpacing: '0.08em' }}>
                            LAST VERIFICATION
                        </p>
                        <button
                            onClick={handleVerifyAgain}
                            className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold transition-colors"
                            style={{
                                fontFamily: 'var(--font-display)',
                                letterSpacing: '0.08em',
                                background: 'var(--bg-elevated)',
                                color: 'var(--accent-red)',
                                border: '1px solid rgba(220,38,38,0.35)',
                                cursor: 'pointer',
                                borderRadius: 2,
                            }}
                            onMouseEnter={e => e.currentTarget.style.background = 'rgba(220,38,38,0.08)'}
                            onMouseLeave={e => e.currentTarget.style.background = 'var(--bg-elevated)'}
                            aria-label="Clear results and verify a new claim"
                        >
                            <RefreshCw size={11} aria-hidden="true" />
                            VERIFY AGAIN
                        </button>
                    </div>

                    {/* Row 1: Gauge + Verdict explanation + Meta */}
                    <div className="grid gap-4 fade-up-1" style={{ gridTemplateColumns: 'min(180px, 40%) 1fr' }}>
                        <div className="card p-5 flex flex-col items-center justify-center gap-3">
                            <ScoreGauge score={result.final_score} size={140} />
                            <VerdictBadge verdict={result.verdict} size="banner" />
                        </div>
                        <div className="card p-5 fade-up-2">
                            {/* Plain-language verdict explanation */}
                            <div className="mb-4 p-3" style={{
                                background: result.verdict === 'Credible' ? 'rgba(34,197,94,0.08)'
                                    : result.verdict === 'Likely Fake' ? 'rgba(220,38,38,0.08)'
                                    : 'rgba(234,179,8,0.08)',
                                border: `1px solid ${result.verdict === 'Credible' ? 'rgba(34,197,94,0.25)'
                                    : result.verdict === 'Likely Fake' ? 'rgba(220,38,38,0.25)'
                                    : 'rgba(234,179,8,0.25)'}`,
                                borderRadius: 2,
                            }}>
                                <div className="flex items-start gap-2">
                                    <Info size={13} style={{ color: finalColor, marginTop: 2, flexShrink: 0 }} aria-hidden="true" />
                                    <div>
                                        <p className="text-sm font-semibold mb-1" style={{ color: finalColor, fontFamily: 'var(--font-display)' }}>
                                            What does this mean?
                                        </p>
                                        <p className="text-xs" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)', lineHeight: 1.6 }}>
                                            {(VERDICT_MAP[result.verdict] ?? VERDICT_MAP['Unverified']).explanation}
                                        </p>
                                    </div>
                                </div>
                            </div>
                            <SectionHeading>Analysis Details</SectionHeading>
                            <MetaRow label="Language" value={result.language} />
                            <MetaRow label="Sentiment" value={result.sentiment} />
                            <MetaRow label="Emotion" value={result.emotion} />
                            <MetaRow label="Confidence" value={`${result.confidence?.toFixed(1)}%`} color={finalColor} />
                            {result.processing_time_ms && (
                                <MetaRow label="Processed in" value={`${result.processing_time_ms?.toFixed(0)} ms`} color="var(--accent-cyan)" />
                            )}
                        </div>
                    </div>

                    {/* Row 2: Score breakdown */}
                    <div className="card p-5 fade-up-3">
                        <SectionHeading>Score Breakdown</SectionHeading>
                        <p className="text-xs mb-4" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.6 }}>
                            The final score combines two layers of analysis. A score of 70+ means likely credible, 40–69 is uncertain, and below 40 is likely false.
                        </p>
                        <div className="space-y-4">
                            <ScoreBar label="ML Classifier (Layer 1 — 40% weight)" value={result.layer1?.confidence || 0} color="var(--accent-cyan)" index={0} />
                            <ScoreBar label="Evidence Cross-Check (Layer 2 — 60% weight)" value={result.layer2?.evidence_score || 0} color="var(--accent-gold)" index={1} />
                            <div style={{ borderTop: '1px solid var(--border)', paddingTop: 12 }}>
                                <ScoreBar label="Final Credibility Score" value={result.final_score} color={finalColor} index={2} />
                            </div>
                        </div>
                        <p className="text-xs mt-3" style={{ color: finalColor, fontFamily: 'var(--font-body)', lineHeight: 1.6, fontWeight: 600 }}>
                            {scoreInterpretation(result.final_score)}
                        </p>
                    </div>

                    {/* Row 2½: Extracted Text (collapsible) */}
                    {result.extracted_text && (
                        <div className="card fade-up-3" style={{ overflow: 'hidden' }}>
                            <button
                                onClick={() => setExtractedTextOpen(o => !o)}
                                className="w-full flex items-center justify-between px-5 py-3 transition-colors"
                                style={{
                                    background: 'none',
                                    border: 'none',
                                    cursor: 'pointer',
                                    borderBottom: extractedTextOpen ? '1px solid var(--border)' : 'none',
                                }}
                                onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'none'}
                                aria-expanded={extractedTextOpen}
                                aria-controls="extracted-text-panel"
                            >
                                <div className="flex items-center gap-2">
                                    <span className="text-xs font-semibold uppercase tracking-widest"
                                        style={{ fontFamily: 'var(--font-display)', color: 'var(--text-muted)', letterSpacing: '0.15em' }}>
                                        {result.input_type === 'image' ? 'OCR Extracted Text'
                                            : result.input_type === 'video' ? 'Transcribed Text'
                                            : result.input_type === 'url' ? 'Scraped Text'
                                            : 'Analyzed Text'}
                                    </span>
                                    <span className="text-xs tabular"
                                        style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                                        {result.extracted_text.length} chars
                                    </span>
                                </div>
                                <ChevronRight size={13}
                                    style={{
                                        color: 'var(--text-muted)',
                                        transform: extractedTextOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                                        transition: 'transform 200ms ease',
                                        flexShrink: 0,
                                    }}
                                    aria-hidden="true"
                                />
                            </button>
                            {extractedTextOpen && (
                                <div id="extracted-text-panel" className="px-5 py-4">
                                    {result.input_type === 'url' && (
                                        <p className="text-xs mb-3" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.5 }}>
                                            This is the text our scraper extracted from the URL. If it looks wrong or incomplete, the page may have been partially blocked.
                                        </p>
                                    )}
                                    {result.input_type === 'image' && (
                                        <p className="text-xs mb-3" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.5 }}>
                                            This is the text read from your image using OCR. Poor image quality may cause errors.
                                        </p>
                                    )}
                                    {result.input_type === 'video' && (
                                        <p className="text-xs mb-3" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.5 }}>
                                            This is the speech transcribed from your video/audio file.
                                        </p>
                                    )}
                                    <pre
                                        style={{
                                            whiteSpace: 'pre-wrap',
                                            wordBreak: 'break-word',
                                            fontFamily: 'var(--font-mono)',
                                            fontSize: 12,
                                            lineHeight: 1.7,
                                            color: 'var(--text-secondary)',
                                            background: 'var(--bg-elevated)',
                                            border: '1px solid var(--border)',
                                            borderRadius: 2,
                                            padding: '12px 14px',
                                            maxHeight: 280,
                                            overflowY: 'auto',
                                        }}
                                    >
                                        {result.extracted_text}
                                    </pre>
                                </div>
                            )}
                        </div>
                    )}

                    {/* Row 3: Layer cards (2 col, collapses to 1 on mobile) */}
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 fade-up-4">
                        {/* Layer 1 */}
                        <LayerCard
                            title="Layer 1 — AI Analysis"
                            icon={Brain}
                            verdict={result.layer1?.verdict}
                            score={result.layer1?.confidence}
                            delay={0}>
                            <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)', lineHeight: 1.6 }}>
                                {mlConfidenceExplanation(result.layer1?.confidence || 0, result.layer1?.verdict)}
                            </p>
                            <div className="mt-3">
                                <p className="text-xs mb-2" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', letterSpacing: '0.1em' }}>
                                    TRIGGERED FEATURES
                                </p>
                                <p className="text-xs mb-2" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.5 }}>
                                    {result.layer1?.triggered_features?.length > 0
                                        ? 'These patterns are commonly found in misleading content:'
                                        : ''}
                                </p>
                                <FeatureBreakdown features={result.layer1?.triggered_features} />
                            </div>
                        </LayerCard>

                        {/* Layer 2 */}
                        <LayerCard
                            title="Layer 2 — Evidence Check"
                            icon={Layers}
                            verdict={result.layer2?.verdict}
                            score={result.layer2?.evidence_score}
                            delay={80}>
                            <p className="text-xs mt-2" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)', lineHeight: 1.6 }}>
                                {evidenceExplanation(result.layer2?.evidence_score || 0, result.layer2?.sources)}
                            </p>
                            <p className="text-xs mt-3" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.6 }}>
                                <span style={{ color: 'var(--text-secondary)' }}>Claim searched: </span>
                                "{result.layer2?.claim_used || 'No claim extracted'}"
                            </p>
                        </LayerCard>
                    </div>

                    {/* Row 4: Suspicious Word Highlighter (only if text input) */}
                    {result.layer1?.triggered_features?.length > 0 && (
                        <div className="card p-5 fade-up-5">
                            <SectionHeading>Suspicious Signal Analysis</SectionHeading>
                            <WordHighlighter
                                text={result.layer2?.claim_used || ''}
                                triggerWords={triggerWords}
                                className="text-sm"
                            />
                        </div>
                    )}

                    {/* Row 5: Named Entities */}
                    {allEntities.length > 0 && (
                        <div className="card p-5 fade-up-5">
                            <SectionHeading count={allEntities.length}>Named Entities</SectionHeading>
                            <p className="text-xs mb-3" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.5 }}>
                                People, organizations, and places mentioned in the claim. These were used to search for related news articles.
                            </p>
                            <ul className="flex flex-wrap gap-2" role="list">
                                {allEntities.map((e, i) => (
                                    <li key={i}
                                        className="flex items-center gap-1.5 px-2.5 py-1 text-xs"
                                        style={{
                                            background: 'var(--bg-elevated)',
                                            border: `1px solid ${e.color}33`,
                                            borderRadius: 2,
                                        }}>
                                        <span style={{ color: e.color, fontFamily: 'var(--font-display)', fontSize: 9, letterSpacing: '0.1em' }}>
                                            {e.type.toUpperCase()}
                                        </span>
                                        <span style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>{e.label}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {/* Row 6: Evidence Sources */}
                    {result.layer2?.sources?.length > 0 && (
                        <div className="card p-5 fade-up-5">
                            <SectionHeading count={result.layer2.sources.length}>Evidence Sources</SectionHeading>
                            <p className="text-xs mb-3" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)', lineHeight: 1.5 }}>
                                News articles found that relate to this claim.
                                <span style={{ color: 'var(--credible)' }}> Supports</span> = confirms the claim,
                                <span style={{ color: 'var(--fake)' }}> Refutes</span> = contradicts it,
                                <span style={{ color: 'var(--text-muted)' }}> Not Enough Info</span> = related but neutral.
                                The % match shows how closely the article relates to the claim.
                            </p>
                            <ul className="space-y-2" role="list">
                                {result.layer2.sources.map((src, i) => {
                                    const { Icon: StanceIcon, color: stanceColor } = STANCE_ICON[src.stance] ?? STANCE_ICON['Not Enough Info']
                                    return (
                                        <li key={i}>
                                            <a href={src.url} target="_blank" rel="noreferrer"
                                                className="block p-3 transition-colors"
                                                style={{
                                                    background: 'var(--bg-elevated)',
                                                    border: '1px solid var(--border)',
                                                    borderRadius: 2,
                                                    cursor: 'pointer',
                                                }}
                                                onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--border-light)'}
                                                onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}>
                                                <div className="flex items-start gap-2">
                                                    <StanceIcon size={13} style={{ color: stanceColor, marginTop: 2, flexShrink: 0 }} aria-hidden="true" />
                                                    <div className="flex-1 min-w-0">
                                                        <p className="text-xs font-semibold mb-0.5 truncate"
                                                            style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-body)' }}>
                                                            {src.title}
                                                        </p>
                                                        <div className="flex items-center gap-2">
                                                            <span className="text-xs tabular" style={{ color: 'var(--text-muted)' }}>
                                                                {src.source_name || src.source}
                                                            </span>
                                                            <span className="text-xs tabular" style={{ color: stanceColor, fontFamily: 'var(--font-display)', letterSpacing: '0.06em' }}>
                                                                {src.stance}
                                                            </span>
                                                            <span className="text-xs tabular" style={{ color: 'var(--text-muted)' }}>
                                                                {(src.similarity * 100).toFixed(0)}% match
                                                            </span>
                                                        </div>
                                                    </div>
                                                    <ExternalLink size={11} style={{ color: 'var(--text-muted)', flexShrink: 0 }} aria-hidden="true" />
                                                </div>
                                            </a>
                                        </li>
                                    )
                                })}
                            </ul>
                        </div>
                    )}
                </section>
            )}
        </main>
    )
}
