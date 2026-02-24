import { useEffect, useState } from 'react'
import { api } from '../api.js'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts'

const CHART_COLORS = ['#dc2626', '#d97706', '#06b6d4', '#8b5cf6', '#16a34a', '#ec4899']

/** Custom tooltip — uses CSS vars, avoids hardcoded formats */
const ChartTooltip = ({ active, payload }) => {
    if (!active || !payload?.length) return null
    return (
        <div className="card-elevated px-3 py-2"
            role="tooltip" aria-live="polite">
            <p className="text-xs font-bold" style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)' }}>
                {payload[0].payload.name ?? payload[0].payload.topic}
            </p>
            <p className="tabular text-xs mt-0.5" style={{ color: 'var(--text-secondary)' }}>
                Count: {payload[0].value}
            </p>
        </div>
    )
}

function ChartSection({ title, data, dataKey }) {
    if (!data?.length) return null
    return (
        <section aria-label={title} className="card p-5 fade-up-2">
            <p className="text-xs font-semibold uppercase mb-4"
                style={{ fontFamily: 'var(--font-display)', color: 'var(--text-muted)', letterSpacing: '0.15em' }}>
                {title}
            </p>
            {/* web-design-guidelines: font-variant-numeric tabular-nums for data */}
            <ResponsiveContainer width="100%" height={200}>
                <BarChart data={data} margin={{ top: 0, right: 0, left: -20, bottom: 0 }}>
                    <XAxis dataKey={dataKey}
                        tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'var(--font-display)' }}
                        axisLine={false} tickLine={false} />
                    <YAxis
                        tick={{ fontSize: 11, fill: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}
                        axisLine={false} tickLine={false} />
                    <Tooltip content={<ChartTooltip />}
                        cursor={{ fill: 'rgba(245,240,232,0.03)' }} />
                    <Bar dataKey="count" radius={[2, 2, 0, 0]}>
                        {data.map((_, i) => (
                            <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                    </Bar>
                </BarChart>
            </ResponsiveContainer>
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

    if (loading) return (
        <p className="text-center py-24 text-sm" style={{ color: 'var(--text-muted)' }}
            aria-live="polite">Loading trends…</p>
    )

    if (error) return (
        <p role="alert" className="text-center py-24 text-sm" style={{ color: '#f87171' }}>
            Error: {error}
        </p>
    )

    const entityData = Object.entries(data?.top_entities || {})
        .sort(([, a], [, b]) => b - a).slice(0, 8)
        .map(([name, count]) => ({ name, count }))

    const topicData = (data?.top_fake_topics || []).slice(0, 8)

    const verdicts = [
        { label: 'VERIFIED', count: data?.verdict_distribution?.Credible ?? 0, color: 'var(--credible)' },
        { label: 'UNVERIFIED', count: data?.verdict_distribution?.Unverified ?? 0, color: 'var(--unverified)' },
        { label: 'FALSE', count: data?.verdict_distribution?.['Likely Fake'] ?? 0, color: 'var(--fake)' },
    ]
    const hasData = entityData.length > 0 || verdicts.some(v => v.count > 0)

    return (
        <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
            <header className="ruled fade-up-1">
                <h1 style={{ fontSize: 32, fontFamily: 'var(--font-display)' }}>Trends</h1>
                <p className="mt-1 text-sm" style={{ color: 'var(--text-secondary)', fontFamily: 'var(--font-body)' }}>
                    Aggregated patterns from verified claims
                </p>
            </header>

            {/* Verdict distribution stats */}
            <div className="grid grid-cols-3 gap-3 fade-up-1" role="list" aria-label="Verdict distribution">
                {verdicts.map(({ label, count, color }) => (
                    <div key={label} className="card p-5 text-center" role="listitem">
                        {/* web-design-guidelines: numerals for counts, tabular */}
                        <p className="tabular font-bold" style={{ fontSize: 36, color, fontFamily: 'var(--font-mono)' }}>
                            {count}
                        </p>
                        <p className="mt-1 text-xs" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-display)', letterSpacing: '0.12em' }}>
                            {label}
                        </p>
                    </div>
                ))}
            </div>

            <ChartSection title="Top Named Entities" data={entityData} dataKey="name" />
            <ChartSection title="Top Fake News Topics" data={topicData} dataKey="topic" />

            {!hasData && (
                <div className="card p-12 text-center fade-up">
                    <p style={{ color: 'var(--text-primary)', fontFamily: 'var(--font-display)', fontWeight: 700 }}>
                        No trend data yet
                    </p>
                    <p className="text-sm mt-1" style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-body)' }}>
                        Run some verifications first to see patterns emerge here.
                    </p>
                </div>
            )}
        </main>
    )
}
