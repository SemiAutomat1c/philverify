import { useState } from 'react'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip,
  ResponsiveContainer, Cell, ReferenceLine,
} from 'recharts'
import { PAGE_STYLE } from '../App.jsx'

// ── Eval results (from python -m ml.eval, seed=42, 79 train / 21 val) ─────────
const MODELS = [
  {
    name: 'BoW + LogReg',
    shortName: 'BoW+LR',
    accuracy: 52.4,
    tier: 'classical',
    lecture: 'Lecture 3',
    note: 'CountVectorizer loses TF weighting — raw counts hurt precision on short headlines',
  },
  {
    name: 'BoW + LogReg + Lemma',
    shortName: 'BoW+LR+L',
    accuracy: 52.4,
    tier: 'classical',
    lecture: 'Lectures 2–3',
    note: 'No change from non-lemmatized — WordNet is English-biased; Tagalog tokens unchanged',
  },
  {
    name: 'TF-IDF + LogReg',
    shortName: 'TFIDF+LR',
    accuracy: 61.9,
    tier: 'classical',
    lecture: 'Lecture 3',
    note: 'Sublinear TF weighting reduces dominance of high-frequency terms; best classical model',
  },
  {
    name: 'TF-IDF + NB',
    shortName: 'TFIDF+NB',
    accuracy: 42.9,
    tier: 'classical',
    lecture: 'Lectures 5–6',
    note: 'Feature independence assumption breaks on 79 samples; noisy probability estimates',
  },
  {
    name: 'TF-IDF + NB + Lemma',
    shortName: 'NB+Lemma',
    accuracy: 42.9,
    tier: 'classical',
    lecture: 'Lectures 2, 5–6',
    note: 'Lemmatization again neutral — confirms English-biased lemmatizer finding',
  },
  {
    name: 'LDA + LogReg',
    shortName: 'LDA+LR',
    accuracy: 42.9,
    tier: 'classical',
    lecture: 'Lecture 7',
    note: '5 topics over 79 documents is too few for stable topic distributions',
  },
  {
    name: 'XLM-RoBERTa',
    shortName: 'XLM-R',
    accuracy: 90.5,
    tier: 'transformer',
    lecture: 'Transfer Learning',
    note: 'Pretrained on 100+ languages including Filipino; fine-tuned on combined dataset',
  },
  {
    name: 'Tagalog-RoBERTa',
    shortName: 'TL-R',
    accuracy: 95.2,
    tier: 'transformer',
    lecture: 'Transfer Learning',
    note: 'Pretrained on TLUnified Filipino corpus; higher recall on Tagalog/Taglish posts',
  },
  {
    name: 'Ensemble',
    shortName: 'Ensemble',
    accuracy: 100.0,
    tier: 'ensemble',
    lecture: 'Ensemble Methods',
    note: 'Soft-vote average of XLM-R + Tagalog-RoBERTa logits; 100% on 21-sample holdout',
  },
]

const TIER_COLOR = {
  classical:   '#d97706',  // gold
  transformer: '#06b6d4',  // cyan
  ensemble:    '#16a34a',  // green
}

const TIER_LABEL = {
  classical:   'Classical ML',
  transformer: 'Transformer',
  ensemble:    'Ensemble',
}

const FINDINGS = [
  {
    lecture: 'Lecture 3',
    title: 'TF-IDF > Bag of Words',
    body: 'TF-IDF sublinear weighting outperforms raw BoW counts by +9.5%. Down-weighting high-frequency filler terms matters for short Filipino news headlines.',
    color: '#d97706',
  },
  {
    lecture: 'Lectures 5–6',
    title: 'Naive Bayes struggles at small scale',
    body: 'MultinomialNB reaches only 42.9% — 19pp below LogReg. Feature independence breaks down when training on 79 noisy, cross-lingual samples.',
    color: '#d97706',
  },
  {
    lecture: 'Lecture 7',
    title: 'LDA needs more documents',
    body: '5 topics over 79 training texts yields unstable distributions. Topic features are weak signal for 3-class classification; LDA would improve with 1000+ samples.',
    color: '#d97706',
  },
  {
    lecture: 'Lectures 2a–2c',
    title: 'Lemmatization: neutral on Tagalog',
    body: 'Zero accuracy change with WordNet lemmatization. English-biased lemmatizers return Tagalog tokens unchanged — confirms the tool is a no-op on Filipino text.',
    color: '#06b6d4',
  },
]

// ── Custom tooltip ─────────────────────────────────────────────────────────────
function ChartTooltip({ active, payload }) {
  if (!active || !payload?.length) return null
  const d = payload[0].payload
  return (
    <div style={{
      background: 'var(--bg-elevated)',
      border: '1px solid var(--border-light)',
      borderRadius: 4,
      padding: '10px 14px',
      fontFamily: 'var(--font-mono)',
      fontSize: 11,
      color: 'var(--text-primary)',
      maxWidth: 240,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 4 }}>{d.name}</div>
      <div style={{ color: TIER_COLOR[d.tier], marginBottom: 6 }}>
        {d.accuracy.toFixed(1)}% accuracy
      </div>
      <div style={{ color: 'var(--text-muted)', fontSize: 10, lineHeight: 1.5 }}>{d.note}</div>
    </div>
  )
}

// ── Tier legend pill ───────────────────────────────────────────────────────────
function TierPill({ tier }) {
  return (
    <span style={{
      display: 'inline-block',
      padding: '2px 8px',
      borderRadius: 2,
      fontSize: 9,
      fontFamily: 'var(--font-mono)',
      fontWeight: 700,
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
      background: `${TIER_COLOR[tier]}18`,
      color: TIER_COLOR[tier],
      border: `1px solid ${TIER_COLOR[tier]}40`,
    }}>
      {TIER_LABEL[tier]}
    </span>
  )
}

export default function BenchmarksPage() {
  const [activeRow, setActiveRow] = useState(null)

  return (
    <main style={{ ...PAGE_STYLE, paddingTop: 48, paddingBottom: 80 }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div className="fade-up-1" style={{ marginBottom: 40 }}>
        <div style={{
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          letterSpacing: '0.14em',
          color: 'var(--accent-red)',
          textTransform: 'uppercase',
          marginBottom: 10,
        }}>
          ML Course — Model Comparison
        </div>
        <h1 style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 800,
          fontSize: 32,
          letterSpacing: '-0.02em',
          color: 'var(--text-primary)',
          marginBottom: 12,
        }}>
          Model Benchmarks
        </h1>
        <p style={{
          fontFamily: 'var(--font-body)',
          fontSize: 14,
          color: 'var(--text-secondary)',
          lineHeight: 1.7,
          maxWidth: 560,
        }}>
          Comparison of 9 classifier variants on a 21-sample holdout from the
          handcrafted PhilVerify dataset (79 train / 21 val, seed 42). Classical
          models trained in-session; transformer checkpoints fine-tuned on the
          full combined dataset.
        </p>
      </div>

      {/* ── Key findings ───────────────────────────────────────────────────── */}
      <div className="fade-up-2" style={{ marginBottom: 48 }}>
        <h2 style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 700,
          fontSize: 11,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'var(--text-muted)',
          marginBottom: 16,
        }}>
          Key Findings
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(210px, 1fr))', gap: 12 }}>
          {FINDINGS.map((f) => (
            <div key={f.title} className="card" style={{ padding: '16px 18px' }}>
              <div style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                color: f.color,
                marginBottom: 6,
              }}>
                {f.lecture}
              </div>
              <div style={{
                fontFamily: 'var(--font-display)',
                fontWeight: 700,
                fontSize: 13,
                color: 'var(--text-primary)',
                marginBottom: 8,
                lineHeight: 1.3,
              }}>
                {f.title}
              </div>
              <p style={{
                fontFamily: 'var(--font-body)',
                fontSize: 11,
                color: 'var(--text-secondary)',
                lineHeight: 1.6,
                margin: 0,
              }}>
                {f.body}
              </p>
            </div>
          ))}
        </div>
      </div>

      {/* ── Bar chart ──────────────────────────────────────────────────────── */}
      <div className="fade-up-3 card" style={{ padding: '24px 20px', marginBottom: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 20 }}>
          <h2 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: '0.06em',
            color: 'var(--text-primary)',
            margin: 0,
          }}>
            Accuracy by Model
          </h2>
          <div style={{ display: 'flex', gap: 12 }}>
            {Object.entries(TIER_LABEL).map(([tier, label]) => (
              <div key={tier} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <span style={{ width: 8, height: 8, borderRadius: 2, background: TIER_COLOR[tier], display: 'inline-block' }} />
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--text-muted)', letterSpacing: '0.06em' }}>
                  {label.toUpperCase()}
                </span>
              </div>
            ))}
          </div>
        </div>
        <ResponsiveContainer width="100%" height={280}>
          <BarChart
            data={MODELS}
            layout="vertical"
            margin={{ top: 0, right: 40, left: 8, bottom: 0 }}
          >
            <CartesianGrid horizontal={false} stroke="rgba(245,240,232,0.04)" />
            <XAxis
              type="number"
              domain={[0, 100]}
              tickFormatter={v => `${v}%`}
              tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-muted)' }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              type="category"
              dataKey="shortName"
              width={72}
              tick={{ fontSize: 9, fontFamily: 'var(--font-mono)', fill: 'var(--text-secondary)' }}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(245,240,232,0.03)' }} />
            <ReferenceLine x={61.9} stroke="rgba(217,119,6,0.3)" strokeDasharray="3 3" label={{ value: 'Classical ceiling', position: 'top', fontSize: 8, fontFamily: 'var(--font-mono)', fill: '#d97706' }} />
            <Bar dataKey="accuracy" radius={[0, 2, 2, 0]} maxBarSize={20}>
              {MODELS.map((m) => (
                <Cell key={m.name} fill={TIER_COLOR[m.tier]} fillOpacity={activeRow === m.name ? 1 : 0.75} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* ── Full results table ─────────────────────────────────────────────── */}
      <div className="fade-up-4 card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '18px 20px 12px', borderBottom: '1px solid var(--border)' }}>
          <h2 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            fontSize: 13,
            letterSpacing: '0.06em',
            color: 'var(--text-primary)',
            margin: 0,
          }}>
            Full Results
          </h2>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              {['Model', 'Accuracy', 'Tier', 'Lecture', 'Note'].map(h => (
                <th key={h} style={{
                  padding: '8px 16px',
                  textAlign: h === 'Accuracy' ? 'right' : 'left',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 9,
                  fontWeight: 700,
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {MODELS.map((m, i) => (
              <tr
                key={m.name}
                onMouseEnter={() => setActiveRow(m.name)}
                onMouseLeave={() => setActiveRow(null)}
                style={{
                  borderBottom: i < MODELS.length - 1 ? '1px solid var(--border)' : 'none',
                  background: activeRow === m.name ? 'var(--bg-elevated)' : 'transparent',
                  transition: 'background 0.1s',
                  borderLeft: `3px solid ${activeRow === m.name ? TIER_COLOR[m.tier] : 'transparent'}`,
                }}
              >
                <td style={{ padding: '10px 16px', fontFamily: 'var(--font-display)', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)' }}>
                  {m.name}
                </td>
                <td style={{ padding: '10px 16px', textAlign: 'right', fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 700, color: TIER_COLOR[m.tier] }}>
                  {m.accuracy.toFixed(1)}%
                </td>
                <td style={{ padding: '10px 16px' }}>
                  <TierPill tier={m.tier} />
                </td>
                <td style={{ padding: '10px 16px', fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                  {m.lecture}
                </td>
                <td style={{ padding: '10px 16px', fontFamily: 'var(--font-body)', fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.5, maxWidth: 260 }}>
                  {m.note}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* ── Footer note ────────────────────────────────────────────────────── */}
      <p className="fade-up-5" style={{
        marginTop: 20,
        fontFamily: 'var(--font-mono)',
        fontSize: 10,
        color: 'var(--text-muted)',
        lineHeight: 1.6,
      }}>
        * Val set is 21 samples from a handcrafted 100-sample dataset — ensemble 100% reflects
        near-zero variance on a small holdout, not production accuracy. Transformer models were
        trained on the larger combined dataset; classical models trained on the 79-sample split.
      </p>

    </main>
  )
}
