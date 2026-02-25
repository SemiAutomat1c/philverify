import { useEffect, useState } from 'react'
import { api } from '../api'
import { PAGE_STYLE } from '../App.jsx'
import { scoreColor } from '../utils/format.js'
import SkeletonCard from '../components/SkeletonCard.jsx'
import {
    BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
    AreaChart, Area, CartesianGrid
} from 'recharts'

/* ── Brand colors for chart series ─────────────────────── */
const CHART_COLORS = ['#dc2626', '#d97706', '#06b6d4', '#8b5cf6', '#16a34a', '#ec4899', '#0ea5e9', '#f97316']

/* ── Custom tooltip — editorial style ──────────────────── */
const ChartTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    const entry = payload[0]
    return (
        <div role="tooltip" aria-live="polite"
            style={{
                background: 'var(--bg-elevated)',
                border: '1px solid var(--border)',
                borderRadius: 2,
                padding: '8px 12px',
            }}>
            <p className="text-xs font-bold" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                {entry.payload.name ?? entry.payload.topic}
            </p>
            <p className="tabular text-xs mt-0.5" style={{ color: entry.fill || 'var(--accent-cyan)', fontFamily: 'var(--font-mono)' }}>
                {entry.value} verifications
            </p>
        </div>
    )
}

/* ── Section heading ──────────────────────────────────── */
function SectionHeading({ children }) {
    return (
        <p className="text-xs font-semibold uppercase mb-4"
            style={{ fontFamily: 'var(--font-display)', color: 'var(--text-muted)', letterSpacing: '0.15em' }}>
            {children}
        </p>
    )
}

/* ── Bar chart section ────────────────────────────────── */
function ChartSection({ title, data, dataKey, description }) {
    if (!data?.length) return null
    return (
        <section aria-label={title} className="card p-5 fade-up-2">
            <div className="mb-4">
                <SectionHeading>{title}</SectionHeading>
                {description && (
                    <p className="text-xs -mt-2 mb-4" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                        {description}
                    </p>
                )}
            </div>
            <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 48 }}>
                    <CartesianGrid vertical={false} stroke="rgba(245,240,232,0.04)" />
                    <XAxis dataKey={dataKey}
                        tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}
                        tickFormatter={(val) => {
                            if (!val) return ''
                            const s = String(val)
                            return s.length > 18 ? s.slice(0, 18) + '…' : s
                        }}
                        angle={-30}
                        textAnchor="end"
                        interval={0}
                        axisLine={false} tickLine={false} />
                    <YAxis
                        tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}
                        axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(245,240,232,0.03)' }} />
                    <Bar dataKey="count" radius={[2, 2, 0, 0]} maxBarSize={48}>
                        {data.map((_, i) => (
                            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
        </section>
    )
}

/* ── Verdict area chart (time-series if available) ─────── */
function VerdictAreaChart({ data }) {
    if (!data?.length) return null
    return (
        <section aria-label="Verdict trend" className="card p-5 fade-up-3">
            <SectionHeading>Verdict Distribution Over Time</SectionHeading>
            <ResponsiveContainer width="100%" height={160}>
                <AreaChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <defs>
                        <linearGradient id="fillCredible" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--credible)" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="var(--credible)" stopOpacity={0} />
                        </linearGradient>
                        <linearGradient id="fillFake" x1="0" y1="0" x2="0" y2="1">
                            <stop offset="5%" stopColor="var(--fake)" stopOpacity={0.3} />
                            <stop offset="95%" stopColor="var(--fake)" stopOpacity={0} />
                        </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="rgba(245,240,232,0.04)" />
                    <XAxis dataKey="date"
                        tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}
                        axisLine={false} tickLine={false} />
                    <YAxis
                        tick={{ fontSize: 10, fill: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}
                        axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />} cursor={{ stroke: 'var(--border)', strokeWidth: 1 }} />
                    <Area type="monotone" dataKey="credible" stroke="var(--credible)" fill="url(#fillCredible)" strokeWidth={2} />
                    <Area type="monotone" dataKey="fake" stroke="var(--fake)" fill="url(#fillFake)" strokeWidth={2} />
                </AreaChart>
            </ResponsiveContainer>
            {/* Legend */}
            <div className="flex gap-4 mt-3">
                {[
                    { color: 'var(--credible)', label: 'Credible' },
                    { color: 'var(--fake)', label: 'False' },
                ].map(({ color, label }) => (
                    <div key={label} className="flex items-center gap-1.5">
                        <span className="w-3 h-0.5" style={{ background: color, display: 'inline-block' }} />
                        <span className="text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', letterSpacing: '0.08em' }}>
                            {label}
                        </span>
                    </div>
                ))}
            </div>
        </section>
    )
}

export default function TrendsPage() {
    const [data, setData] = useState(null)
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        api.trends()
            .then(setData)
            .catch(e => setError(e.message))
            .finally(() => setLoading(false))
    }, [])

    /* ── Derived data ─────────────────────────────────────── */
    // top_entities is an array of { entity, entity_type, count, fake_count, fake_ratio }
    const entityData = (data?.top_entities || [])
        .slice(0, 8)
        .map(e => ({ name: e.entity, count: e.count }))

    // top_topics is an array of { topic, count, dominant_verdict }
    const topicData = (data?.top_topics || []).slice(0, 8)

    const verdicts = [
        { label: 'VERIFIED', count: data?.verdict_distribution?.Credible ?? 0, color: 'var(--credible)' },
        { label: 'UNVERIFIED', count: data?.verdict_distribution?.Unverified ?? 0, color: 'var(--unverified)' },
        { label: 'FALSE', count: data?.verdict_distribution?.['Likely Fake'] ?? 0, color: 'var(--fake)' },
    ]
    const total = verdicts.reduce((s, v) => s + v.count, 0)
    const hasData = entityData.length > 0 || verdicts.some(v => v.count > 0)

    return (
        <main style={{ ...PAGE_STYLE, paddingTop: 40, paddingBottom: 56, display: 'flex', flexDirection: 'column', gap: 24 }}>

            {/* ── Page header ───────────────────────────── */}
            <header className="ruled fade-up-1">
                <h1 style={{ fontSize: 28, fontFamily: 'var(--font-display)' }}>Trends</h1>
                <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                    Aggregated misinformation patterns across all verified claims
                </p>
            </header>

            {/* ── Loading ────────────────────────────────── */}
            {loading && (
                <div className="space-y-4" aria-live="polite" aria-label="Loading trends">
                    <div className="grid grid-cols-3 gap-3">
                        {[0, 1, 2].map(i => <SkeletonCard key={i} height={96} />)}
                    </div>
                    <SkeletonCard height={220} />
                </div>
            )}

            {/* ── Error ──────────────────────────────────── */}
            {error && !loading && (
                <p role="alert" className="text-center py-12 text-sm" style={{ color: '#f87171' }}>
                    Error loading trends: {error}
                </p>
            )}

            {!loading && !error && (
                <>
                    {/* ── Impact stats ────────────────────────────────────────── */}
                    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 fade-up-1" role="list" aria-label="Verdict distribution">
                        {verdicts.map(({ label, count, color }) => {
                            const pct = total > 0 ? Math.round((count / total) * 100) : 0
                            return (
                                <div key={label} className="card p-5" role="listitem"
                                    style={{ borderTop: `3px solid ${color}` }}>
                                    {/* Large impact number — interactive-portfolio pattern */}
                                    <p className="tabular font-bold" style={{ fontSize: 40, color, fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
                                        {count}
                                    </p>
                                    <p className="mt-2 text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', letterSpacing: '0.12em' }}>
                                        {label}
                                    </p>
                                    {total > 0 && (
                                        <div className="mt-2 h-1" style={{ background: 'var(--bg-hover)', borderRadius: 1 }}>
                                            <div className="h-1 bar-fill" style={{ width: `${pct}%`, background: color, borderRadius: 1 }} />
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>

                    {/* ── Charts ─────────────────────────────── */}
                    <ChartSection
                        title="Top Named Entities"
                        data={entityData}
                        dataKey="name"
                        description="Most frequently appearing persons, organizations, and places in verified claims"
                    />

                    <ChartSection
                        title="Top Fake News Topics"
                        data={topicData}
                        dataKey="topic"
                        description="Recurring misinformation topics detected across false claims"
                    />

                    {/* ── Verdict trend over time ──────────────────── */}
                    <VerdictAreaChart data={data?.verdict_by_day || []} />

                    {/* ── Empty state ────────────────────── */}
                    {!hasData && (
                        <div className="card p-16 text-center fade-up">
                            <p style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 18 }}>
                                No trend data yet
                            </p>
                            <p className="text-sm mt-2" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                                Run some verifications first — patterns will emerge here as data accumulates.
                            </p>
                        </div>
                    )}
                </>
            )}
        </main>
    )
}
