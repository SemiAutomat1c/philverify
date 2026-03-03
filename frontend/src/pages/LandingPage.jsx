import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, Link2, Image, Video, ArrowRight, Database, ShieldCheck, Github, BookOpen, Clock, TrendingUp, RefreshCw } from 'lucide-react'
import { PAGE_STYLE } from '../App.jsx'

/* ─── data ──────────────────────────────────────────────────── */
const MODES = [
  {
    icon: FileText,
    label: 'Text',
    desc: 'Paste any headline, social media post, or claim — Tagalog, English, or Taglish.',
  },
  {
    icon: Link2,
    label: 'URL',
    desc: 'Drop a link to any Philippine news article and get instant credibility analysis.',
  },
  {
    icon: Image,
    label: 'Image',
    desc: 'Upload a screenshot — OCR extracts all visible text for full fact-checking.',
  },
  {
    icon: Video,
    label: 'Video',
    desc: 'Upload a clip — Whisper transcribes speech, frame OCR captures on-screen text.',
  },
]

const STEPS = [
  {
    num: '01',
    label: 'INPUT',
    icon: FileText,
    desc: 'Paste text, drop a URL, upload an image, or submit a video clip.',
  },
  {
    num: '02',
    label: 'ANALYZE',
    icon: Database,
    desc: 'NLP pipeline extracts claims, detects language, checks clickbait, and queries live evidence.',
  },
  {
    num: '03',
    label: 'VERDICT',
    icon: ShieldCheck,
    desc: 'Credibility score, entity breakdown, and source evidence — rendered in seconds.',
  },
]

const STATS = [
  { value: '70M+', label: 'Filipinos online', sub: 'one of the highest social media usage rates in the world' },
  { value: '6×', label: 'faster spread', sub: 'misinformation travels six times faster than verified news' },
  { value: '3.8B', label: 'fake engagements', sub: 'estimated fake-news interactions on PH social media annually' },
]

/* ─── component ─────────────────────────────────────────────── */
export default function LandingPage() {
  const navigate = useNavigate()
  const [tryInput, setTryInput] = useState('')

  function handleTrySubmit(e) {
    e.preventDefault()
    if (tryInput.trim()) {
      navigate('/verify', { state: { prefill: tryInput.trim() } })
    } else {
      navigate('/verify')
    }
  }

  return (
    <div style={{ background: 'var(--bg-base)', overflowX: 'hidden' }}>

      {/* ── Hero ─────────────────────────────────────────────── */}
      <section
        style={{
          minHeight: 'calc(100vh - 56px)',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          position: 'relative',
          overflow: 'hidden',
          borderBottom: '1px solid var(--border)',
          backgroundColor: '#0d0d0d',
          backgroundImage: [
            'repeating-linear-gradient(45deg, rgba(245,240,232,0.022) 0px, rgba(245,240,232,0.022) 1px, transparent 1px, transparent 28px)',
            'repeating-linear-gradient(-45deg, rgba(245,240,232,0.022) 0px, rgba(245,240,232,0.022) 1px, transparent 1px, transparent 28px)',
          ].join(', '),
        }}
      >
        {/* Red diagonal gradient overlay */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            inset: 0,
            background:
              'radial-gradient(ellipse 80% 60% at 60% 40%, rgba(220,38,38,0.07) 0%, transparent 70%)',
            pointerEvents: 'none',
          }}
        />

        {/* Animated scanline — single key animation per UX guidance */}
        <div
          aria-hidden
          style={{
            position: 'absolute',
            left: 0,
            right: 0,
            height: 1,
            background: 'linear-gradient(90deg, transparent 0%, var(--accent-red) 40%, var(--accent-red) 60%, transparent 100%)',
            opacity: 0.35,
            animation: 'scanline 3.5s cubic-bezier(0.4,0,0.6,1) infinite',
          }}
        />

        {/* Content — two-column: headline left, mock preview right */}
        <div style={{
          ...PAGE_STYLE,
          paddingTop: 80,
          paddingBottom: 80,
          display: 'flex',
          alignItems: 'center',
          gap: 64,
        }}>
          <div style={{ flex: '1 1 auto', minWidth: 0 }}>
          {/* Eyebrow */}
          <p
            className="fade-up-1"
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.25em',
              textTransform: 'uppercase',
              color: 'var(--accent-red)',
              marginBottom: 24,
            }}
          >
            Philippine Fact-Check Engine &nbsp;·&nbsp; Multimodal AI
          </p>

          {/* Main headline */}
          <h1
            className="fade-up-2"
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(2rem, 3.6vw, 3.8rem)',
              fontWeight: 800,
              lineHeight: 0.93,
              letterSpacing: '-0.03em',
              color: 'var(--text-primary)',
              marginBottom: 32,
              whiteSpace: 'nowrap',
            }}
          >
            VERIFY<br />
            BEFORE<br />
            <span style={{ color: 'var(--accent-red)' }}>YOU SHARE.</span>
          </h1>

          {/* Subline — #8: tighter max-width prevents bad wrapping at mid viewports */}
          <p
            className="fade-up-3"
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: 'clamp(1rem, 1.8vw, 1.15rem)',
              color: 'var(--text-secondary)',
              maxWidth: 440,
              lineHeight: 1.75,
              marginBottom: 48,
            }}
          >
            PhilVerify checks claims, URLs, images, and videos against live news evidence — built for Tagalog, English, and Taglish.
          </p>

          {/* CTA */}
          <div className="fade-up-4" style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
            <Link
              to="/verify"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 10,
                background: 'var(--accent-red)',
                color: '#fff',
                fontFamily: 'var(--font-display)',
                fontSize: 13,
                fontWeight: 700,
                letterSpacing: '0.15em',
                textTransform: 'uppercase',
                padding: '14px 28px',
                textDecoration: 'none',
                transition: 'background 0.2s ease-out, transform 0.15s ease-out',
                cursor: 'pointer',
              }}
              onMouseEnter={e => { e.currentTarget.style.background = '#b91c1c'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
              onMouseLeave={e => { e.currentTarget.style.background = 'var(--accent-red)'; e.currentTarget.style.transform = 'translateY(0)'; }}
            >
              Start Verifying
              <ArrowRight size={16} strokeWidth={2.5} />
            </Link>

            <a
              href="https://semiautomat1c-philverify-api.hf.space/docs"
              target="_blank"
              rel="noopener noreferrer"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 8,
                fontFamily: 'var(--font-display)',
                fontSize: 12,
                fontWeight: 600,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--text-secondary)',
                textDecoration: 'none',
                borderBottom: '1px solid var(--border)',
                paddingBottom: 2,
                transition: 'color 0.2s ease-out, border-color 0.2s ease-out',
                cursor: 'pointer',
              }}
              onMouseEnter={e => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.borderColor = 'var(--text-primary)'; }}
              onMouseLeave={e => { e.currentTarget.style.color = 'var(--text-secondary)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
            >
              API Docs
            </a>
          </div>
          </div>{/* end left col */}

          {/* Right column: mock result card — faithful miniature of the real output */}
          <div
            className="hero-mock"
            aria-hidden="true"
            style={{
              flex: '0 0 340px',
              width: 340,
              background: 'var(--bg-base)',
              border: '1px solid var(--border)',
              position: 'relative',
              overflow: 'hidden',
              alignSelf: 'stretch',
              flexShrink: 0,
              display: 'flex',
              flexDirection: 'column',
            }}
          >
            {/* Fade-out at bottom */}
            <div style={{
              position: 'absolute',
              bottom: 0, left: 0, right: 0, height: 120,
              background: 'linear-gradient(transparent, var(--bg-base))',
              zIndex: 2,
              pointerEvents: 'none',
            }} />

            {/* Header bar */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '8px 12px',
              borderBottom: '1px solid var(--border)',
              background: 'var(--bg-surface)',
            }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Last Verification</span>
              <span style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                fontFamily: 'var(--font-display)', fontSize: 8, fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase',
                color: 'var(--accent-red)', cursor: 'default',
              }}>
                <RefreshCw size={8} strokeWidth={2} /> Verify Again
              </span>
            </div>

            <div style={{ padding: '10px 12px', display: 'flex', flexDirection: 'column', gap: 8 }}>

              {/* Row 1: gauge + verdict explanation */}
              <div style={{ display: 'grid', gridTemplateColumns: '80px 1fr', gap: 8 }}>
                {/* Gauge */}
                <div style={{
                  background: 'var(--bg-surface)',
                  border: '1px solid var(--border)',
                  display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
                  padding: '10px 6px', gap: 6,
                }}>
                  <svg width="52" height="52" viewBox="0 0 52 52" fill="none">
                    <circle cx="26" cy="26" r="22" stroke="var(--bg-elevated)" strokeWidth="5" fill="none"/>
                    <circle cx="26" cy="26" r="22" stroke="#dc2626" strokeWidth="5" fill="none"
                      strokeDasharray={`${2*Math.PI*22*0.32} ${2*Math.PI*22*(1-0.32)}`}
                      strokeDashoffset={2*Math.PI*22*0.25} strokeLinecap="butt" transform="rotate(-90 26 26)"/>
                    <text x="26" y="29" textAnchor="middle" fill="#dc2626" fontSize="13" fontWeight="800" fontFamily="Syne, sans-serif">32</text>
                  </svg>
                  <span style={{ fontFamily: 'var(--font-display)', fontSize: 7, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-muted)' }}>Credibility</span>
                  <span style={{
                    fontFamily: 'var(--font-display)', fontSize: 8, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase',
                    padding: '2px 6px', background: 'rgba(220,38,38,0.15)', color: '#f87171', border: '1px solid rgba(220,38,38,0.4)',
                  }}>✕ False</span>
                </div>
                {/* Verdict box + meta */}
                <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: '8px' }}>
                  <div style={{ padding: '6px 7px', background: 'rgba(220,38,38,0.08)', border: '1px solid rgba(220,38,38,0.25)', marginBottom: 7 }}>
                    <p style={{ fontFamily: 'var(--font-display)', fontSize: 8, fontWeight: 700, color: '#f87171', marginBottom: 2 }}>What does this mean?</p>
                    <p style={{ fontFamily: 'var(--font-body)', fontSize: 8, color: 'var(--text-secondary)', lineHeight: 1.5 }}>Strong signs of false or misleading content. Verify from trusted sources.</p>
                  </div>
                  <p style={{ fontFamily: 'var(--font-display)', fontSize: 7, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 4 }}>Analysis Details</p>
                  {[['Language','English'],['Sentiment','neutral'],['Emotion','neutral'],['Confidence','73.9%'],['Processed in','33412 ms']].map(([k,v],i) => (
                    <div key={k} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 0', borderBottom: i < 4 ? '1px solid var(--border)' : 'none' }}>
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 8, color: 'var(--text-muted)' }}>{k}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, color: i >= 3 ? '#dc2626' : 'var(--text-secondary)' }}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Score breakdown */}
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: '8px' }}>
                <p style={{ fontFamily: 'var(--font-display)', fontSize: 7, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 6 }}>Score Breakdown</p>
                {[
                  ['ML Classifier (Layer 1 — 40% weight)', 74, 'var(--accent-cyan, #22d3ee)'],
                  ['Evidence Cross-Check (Layer 2 — 60% weight)', 36, '#f59e0b'],
                  ['Final Credibility Score', 32, '#dc2626'],
                ].map(([label, val, color]) => (
                  <div key={label} style={{ marginBottom: 6 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 2 }}>
                      <span style={{ fontFamily: 'var(--font-body)', fontSize: 8, color: 'var(--text-muted)' }}>{label}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 8, fontWeight: 700, color }}>{val}%</span>
                    </div>
                    <div style={{ height: 3, background: 'var(--bg-elevated)' }}>
                      <div style={{ width: `${val}%`, height: '100%', background: color }} />
                    </div>
                  </div>
                ))}
                <p style={{ fontFamily: 'var(--font-body)', fontSize: 8, color: '#dc2626', marginTop: 4, fontWeight: 600 }}>Likely false — multiple red flags and contradicting evidence found.</p>
              </div>

              {/* Layer cards */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
                {[
                  { title: 'Layer 1 — AI Analysis', score: 74, verdict: '? Unverified', body: 'The AI model found this mostly consistent with credible content.' },
                  { title: 'Layer 2 — Evidence Check', score: 36, verdict: '? Unverified', body: 'Found 5 related articles — some contradict or debunk this claim.' },
                ].map(({ title, score, verdict, body }) => (
                  <div key={title} style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: '8px' }}>
                    <p style={{ fontFamily: 'var(--font-display)', fontSize: 7, fontWeight: 800, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--text-primary)', marginBottom: 3 }}>{title}</p>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
                      <span style={{ fontFamily: 'var(--font-display)', fontSize: 7, fontWeight: 700, padding: '1px 5px', background: 'rgba(234,179,8,0.12)', color: '#fbbf24', border: '1px solid rgba(234,179,8,0.3)' }}>{verdict}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, fontWeight: 700, color: '#fbbf24' }}>{score}%</span>
                    </div>
                    <div style={{ height: 2, background: 'var(--bg-elevated)', marginBottom: 5 }}>
                      <div style={{ width: `${score}%`, height: '100%', background: '#fbbf24' }} />
                    </div>
                    <p style={{ fontFamily: 'var(--font-body)', fontSize: 8, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{body}</p>
                  </div>
                ))}
              </div>

              {/* Named Entities */}
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: '8px' }}>
                <p style={{ fontFamily: 'var(--font-display)', fontSize: 7, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 5 }}>Named Entities <span style={{ color: 'var(--accent-red)' }}>1</span></p>
                <div style={{ display: 'flex', gap: 4 }}>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '2px 6px', background: 'var(--bg-elevated)', border: '1px solid rgba(239,68,68,0.2)' }}>
                    <span style={{ fontFamily: 'var(--font-display)', fontSize: 7, letterSpacing: '0.1em', color: '#f87171' }}>PERSON</span>
                    <span style={{ fontFamily: 'var(--font-body)', fontSize: 8, color: 'var(--text-primary)' }}>Marcos</span>
                  </span>
                </div>
              </div>

              {/* Evidence Sources */}
              <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', padding: '8px' }}>
                <p style={{ fontFamily: 'var(--font-display)', fontSize: 7, fontWeight: 700, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--text-muted)', marginBottom: 5 }}>Evidence Sources <span style={{ color: 'var(--accent-red)' }}>5</span></p>
                {[
                  ['PBBM: 1.4K OFWs want out, PH in talks with Middle East authorities', 'Philippine News Agency', '18%'],
                  ['PNP: No continuing killings under Marcos administration', 'Inquirer.net', '46%'],
                  ['Marcos hoping for ceasefire in the Middle East', 'ABS-CBN', '34%'],
                  ['Marcos manages to silence the press', 'The Manila Times', '45%'],
                ].map(([title, source, pct]) => (
                  <div key={title} style={{ padding: '5px 6px', background: 'var(--bg-elevated)', border: '1px solid var(--border)', marginBottom: 4 }}>
                    <p style={{ fontFamily: 'var(--font-body)', fontSize: 8, color: 'var(--text-primary)', marginBottom: 2, lineHeight: 1.4 }}>{title}</p>
                    <div style={{ display: 'flex', gap: 8 }}>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 7, color: 'var(--text-muted)' }}>{source}</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 7, color: 'var(--text-muted)' }}>Not Enough Info</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 7, color: 'var(--text-muted)' }}>{pct} match</span>
                    </div>
                  </div>
                ))}
              </div>

            </div>
          </div>
        </div>
      </section>

      {/* ── Why It Matters — stats ───────────────────────────── */}
      <section
        style={{
          borderBottom: '1px solid var(--border)',
          background: 'var(--bg-surface)',
        }}
      >
        <div
          className="landing-stats"
          style={{
            ...PAGE_STYLE,
            paddingTop: 0,
            paddingBottom: 0,
          }}
        >
          {STATS.map((s, i) => (
            <div
              key={s.value}
              style={{
                padding: '48px 0',
                borderRight: i < STATS.length - 1 ? '1px solid var(--border)' : 'none',
                paddingRight: i < STATS.length - 1 ? 40 : 0,
                paddingLeft: i > 0 ? 40 : 0,
              }}
            >
              <div
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: 'clamp(2rem, 5vw, 3.5rem)',
                  fontWeight: 800,
                  color: 'var(--accent-red)',
                  letterSpacing: '-0.03em',
                  lineHeight: 1,
                  marginBottom: 8,
                }}
              >
                {s.value}
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: 11,
                  fontWeight: 700,
                  letterSpacing: '0.2em',
                  textTransform: 'uppercase',
                  color: 'var(--text-primary)',
                  marginBottom: 8,
                }}
              >
                {s.label}
              </div>
              <div
                style={{
                  fontFamily: 'var(--font-body)',
                  fontSize: 13,
                  color: 'var(--text-muted)',
                  lineHeight: 1.5,
                }}
              >
                {s.sub}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* ── Input Modes ──────────────────────────────────────── */}
      <section style={{ borderBottom: '1px solid var(--border)' }}>
        <div style={{ ...PAGE_STYLE, paddingTop: 80, paddingBottom: 80 }}>
          <p
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.25em',
              textTransform: 'uppercase',
              color: 'var(--text-muted)',
              marginBottom: 12,
            }}
          >
            What can you verify
          </p>
          <h2
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(1.6rem, 4vw, 2.8rem)',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: 'var(--text-primary)',
              marginBottom: 48,
              maxWidth: 520,
            }}
          >
            Four ways to submit a claim.
          </h2>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
              gap: 1,
              border: '1px solid var(--border)',
            }}
          >
            {MODES.map(({ icon: Icon, label, desc }) => (
              <Link
                key={label}
                to={`/verify?tab=${label.toLowerCase()}`}
                style={{ textDecoration: 'none' }}
              >
                <div
                  className="card"
                  style={{
                    padding: '32px 28px',
                    borderRadius: 0,
                    border: 'none',
                    borderLeft: '3px solid transparent',
                    transition: 'border-color 0.2s ease-out, background 0.2s ease-out',
                    cursor: 'pointer',
                    height: '100%',
                    display: 'flex',
                    flexDirection: 'column',
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderLeftColor = 'var(--accent-red)'
                    e.currentTarget.style.background = 'var(--bg-elevated)'
                    const cta = e.currentTarget.querySelector('.mode-cta')
                    if (cta) { cta.style.opacity = '1'; cta.style.transform = 'translateY(0)' }
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderLeftColor = 'transparent'
                    e.currentTarget.style.background = 'var(--bg-surface)'
                    const cta = e.currentTarget.querySelector('.mode-cta')
                    if (cta) { cta.style.opacity = '0'; cta.style.transform = 'translateY(5px)' }
                  }}
                >
                  <Icon
                    size={28}
                    strokeWidth={1.4}
                    style={{ color: 'var(--accent-red)', marginBottom: 20 }}
                  />
                  <div
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: 17,
                      fontWeight: 800,
                      letterSpacing: '-0.01em',
                      color: 'var(--text-primary)',
                      marginBottom: 10,
                    }}
                  >
                    {label}
                  </div>
                  <p
                    style={{
                      fontFamily: 'var(--font-body)',
                      fontSize: 13,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.6,
                      flex: 1,
                    }}
                  >
                    {desc}
                  </p>
                  <div
                    className="mode-cta"
                    style={{
                      marginTop: 18,
                      display: 'flex',
                      alignItems: 'center',
                      gap: 6,
                      fontFamily: 'var(--font-display)',
                      fontSize: 11,
                      fontWeight: 700,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase',
                      color: 'var(--accent-red)',
                      opacity: 0,
                      transform: 'translateY(5px)',
                      transition: 'opacity 0.2s ease-out, transform 0.2s ease-out',
                    }}
                  >
                    Try {label} <ArrowRight size={12} strokeWidth={2.5} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Inline CTA Teaser ─────────────────────────────── */}
      <section style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
        <div style={{ ...PAGE_STYLE, paddingTop: 48, paddingBottom: 48, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            letterSpacing: '0.2em',
            textTransform: 'uppercase',
            color: 'var(--text-muted)',
            marginBottom: 16,
          }}>
            Try it now — no account needed
          </p>
          <form onSubmit={handleTrySubmit} style={{ display: 'flex', gap: 0, width: '100%' }}>
            <input
              type="text"
              value={tryInput}
              onChange={e => setTryInput(e.target.value)}
              placeholder="Paste any claim, headline, or URL…"
              style={{
                flex: 1,
                background: 'var(--bg-surface)',
                border: '1px solid var(--border)',
                borderRight: 'none',
                color: 'var(--text-primary)',
                fontFamily: 'var(--font-body)',
                fontSize: 15,
                padding: '14px 20px',
                outline: 'none',
              }}
              onFocus={e => e.target.style.borderColor = 'var(--accent-red)'}
              onBlur={e => e.target.style.borderColor = 'var(--border)'}
            />
            <button
              type="submit"
              style={{
                background: 'var(--accent-red)',
                color: '#fff',
                border: 'none',
                fontFamily: 'var(--font-display)',
                fontSize: 12,
                fontWeight: 700,
                letterSpacing: '0.15em',
                textTransform: 'uppercase',
                padding: '14px 24px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
                whiteSpace: 'nowrap',
                transition: 'background 0.2s ease-out',
              }}
              onMouseEnter={e => e.currentTarget.style.background = '#b91c1c'}
              onMouseLeave={e => e.currentTarget.style.background = 'var(--accent-red)'}
            >
              Verify <ArrowRight size={14} strokeWidth={2.5} />
            </button>
          </form>
        </div>
      </section>

      {/* ── How It Works ─────────────────────────────────────── */}
      <section style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-surface)' }}>
        <div style={{ ...PAGE_STYLE, paddingTop: 80, paddingBottom: 80 }}>
          <p
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.25em',
              textTransform: 'uppercase',
              color: 'var(--text-muted)',
              marginBottom: 12,
            }}
          >
            The process
          </p>
          <h2
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(1.6rem, 4vw, 2.8rem)',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: 'var(--text-primary)',
              marginBottom: 64,
              maxWidth: 480,
            }}
          >
            From claim to verdict in seconds.
          </h2>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: 0,
            }}
          >
            {STEPS.map(({ num, label, icon: Icon, desc }, i) => (
              <div
                key={num}
                style={{
                  padding: '0 40px 0 0',
                  borderRight: i < STEPS.length - 1 ? '1px solid var(--border)' : 'none',
                  marginRight: i < STEPS.length - 1 ? 40 : 0,
                }}
              >
                {/* Step number pill */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
                  <div
                    style={{
                      width: 40,
                      height: 40,
                      borderRadius: 2,
                      background: i === 0 ? 'var(--accent-red)' : 'var(--bg-elevated)',
                      border: i === 0 ? 'none' : '1px solid var(--border-light)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0,
                    }}
                  >
                    <Icon size={16} strokeWidth={1.8}
                      style={{ color: i === 0 ? '#fff' : 'var(--text-secondary)' }}
                    />
                  </div>
                  <div>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: 10,
                        fontWeight: 700,
                        color: 'var(--text-muted)',
                        letterSpacing: '0.2em',
                        display: 'block',
                      }}
                    >
                      {num}
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-display)',
                        fontSize: 12,
                        fontWeight: 700,
                        letterSpacing: '0.2em',
                        textTransform: 'uppercase',
                        color: i === 0 ? 'var(--accent-red)' : 'var(--text-primary)',
                      }}
                    >
                      {label}
                    </span>
                  </div>
                </div>
                {/* Connector line under icon for non-last items */}
                <div style={{
                  width: 24,
                  height: 2,
                  background: i === 0 ? 'var(--accent-red)' : 'var(--border)',
                  marginBottom: 20,
                }} />
                <p
                  style={{
                    fontFamily: 'var(--font-body)',
                    fontSize: 15,
                    color: 'var(--text-secondary)',
                    lineHeight: 1.7,
                    maxWidth: 280,
                  }}
                >
                  {desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA band ───────────────────────────────────── */}
      <section style={{ background: 'var(--accent-red)' }}>
        <div
          style={{
            ...PAGE_STYLE,
            paddingTop: 80,
            paddingBottom: 80,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            textAlign: 'center',
            gap: 24,
          }}
        >
          <p
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 11,
              letterSpacing: '0.25em',
              textTransform: 'uppercase',
              color: 'rgba(255,255,255,0.6)',
            }}
          >
            Free to use &nbsp;·&nbsp; No account needed
          </p>
          <h2
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(1.6rem, 3.5vw, 3rem)',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: '#fff',
              lineHeight: 1.05,
              maxWidth: 700,
            }}
          >
            STOP MISINFORMATION.<br />START VERIFYING.
          </h2>
          <Link
            to="/verify"
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 10,
              background: '#fff',
              color: 'var(--accent-red)',
              fontFamily: 'var(--font-display)',
              fontSize: 13,
              fontWeight: 700,
              letterSpacing: '0.15em',
              textTransform: 'uppercase',
              padding: '14px 32px',
              textDecoration: 'none',
              marginTop: 8,
              transition: 'background 0.2s ease-out, transform 0.15s ease-out',
              cursor: 'pointer',
            }}
            onMouseEnter={e => { e.currentTarget.style.background = '#f5f0e8'; e.currentTarget.style.transform = 'translateY(-1px)'; }}
            onMouseLeave={e => { e.currentTarget.style.background = '#fff'; e.currentTarget.style.transform = 'translateY(0)'; }}
          >
            Verify a Claim Now
            <ArrowRight size={16} strokeWidth={2.5} />
          </Link>
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────── */}
      <footer style={{ borderTop: '1px solid var(--border)', background: 'var(--bg-base)' }}>
        <div
          style={{
            ...PAGE_STYLE,
            paddingTop: 48,
            paddingBottom: 48,
            display: 'grid',
            gridTemplateColumns: 'auto 1fr auto',
            gap: 48,
            alignItems: 'start',
          }}
          className="footer-grid"
        >
          {/* Brand */}
          <div>
            <div style={{
              fontFamily: 'var(--font-display)',
              fontSize: 13,
              fontWeight: 800,
              letterSpacing: '0.1em',
              color: 'var(--text-primary)',
              marginBottom: 8,
            }}>
              PHIL<span style={{ color: 'var(--accent-red)' }}>VERIFY</span>
            </div>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
              letterSpacing: '0.1em',
              lineHeight: 1.6,
            }}>
              ML2 Final Project<br />
              MIT License · {new Date().getFullYear()}
            </div>
          </div>

          {/* Nav links */}
          <div style={{ display: 'flex', gap: 48, flexWrap: 'wrap' }}>
            <div>
              <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: '0.2em',
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                marginBottom: 12,
              }}>App</div>
              {[
                { label: 'Verify', to: '/verify', internal: true },
                { label: 'History', to: '/history', internal: true },
                { label: 'Trends', to: '/trends', internal: true },
              ].map(({ label, to, internal }) => (
                <div key={label} style={{ marginBottom: 8 }}>
                  {internal
                    ? <Link to={to} style={{
                        fontFamily: 'var(--font-body)',
                        fontSize: 13,
                        color: 'var(--text-secondary)',
                        textDecoration: 'none',
                        transition: 'color 0.15s ease-out',
                      }}
                      onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
                      onMouseLeave={e => e.currentTarget.style.color = 'var(--text-secondary)'}
                    >{label}</Link>
                    : null
                  }
                </div>
              ))}
            </div>
            <div>
              <div style={{
                fontFamily: 'var(--font-display)',
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: '0.2em',
                textTransform: 'uppercase',
                color: 'var(--text-muted)',
                marginBottom: 12,
              }}>Resources</div>
              {[
                { label: 'API Docs', href: 'https://semiautomat1c-philverify-api.hf.space/docs' },
                { label: 'GitHub', href: 'https://github.com/SemiAutomat1c/philverify' },
              ].map(({ label, href }) => (
                <div key={label} style={{ marginBottom: 8 }}>
                  <a href={href} target="_blank" rel="noopener noreferrer" style={{
                    fontFamily: 'var(--font-body)',
                    fontSize: 13,
                    color: 'var(--text-secondary)',
                    textDecoration: 'none',
                    transition: 'color 0.15s ease-out',
                  }}
                  onMouseEnter={e => e.currentTarget.style.color = 'var(--text-primary)'}
                  onMouseLeave={e => e.currentTarget.style.color = 'var(--text-secondary)'}
                  >{label}</a>
                </div>
              ))}
            </div>
          </div>

          {/* Disclaimer */}
          <div style={{ maxWidth: 220 }}>
            <div style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
              lineHeight: 1.6,
              letterSpacing: '0.03em',
            }}>
              For research and educational purposes only. Use responsibly when verifying information on social media.
            </div>
          </div>
        </div>

        {/* Bottom rule */}
        <div style={{ borderTop: '1px solid var(--border)' }}>
          <div style={{
            ...PAGE_STYLE,
            paddingTop: 16,
            paddingBottom: 16,
          }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
              letterSpacing: '0.1em',
            }}>
              Built with FastAPI · React · Whisper · Tesseract · NewsAPI
            </span>
          </div>
        </div>
      </footer>

    </div>
  )
}
