import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { FileText, Link2, Image, Video, ArrowRight, Database, ShieldCheck, Github, BookOpen, Clock, TrendingUp } from 'lucide-react'
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

        {/* Content */}
        <div style={{ ...PAGE_STYLE, paddingTop: 80, paddingBottom: 80 }}>
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

          {/* Main headline — clamp as per UI/UX Pro Max exaggerated-minimalism */}
          <h1
            className="fade-up-2"
            style={{
              fontFamily: 'var(--font-display)',
              fontSize: 'clamp(2.8rem, 9vw, 7.5rem)',
              fontWeight: 800,
              lineHeight: 0.95,
              letterSpacing: '-0.03em',
              color: 'var(--text-primary)',
              marginBottom: 32,
              maxWidth: 820,
            }}
          >
            VERIFY<br />
            BEFORE<br />
            <span style={{ color: 'var(--accent-red)' }}>YOU SHARE.</span>
          </h1>

          {/* Subline */}
          <p
            className="fade-up-3"
            style={{
              fontFamily: 'var(--font-body)',
              fontSize: 'clamp(1rem, 2vw, 1.2rem)',
              color: 'var(--text-secondary)',
              maxWidth: 520,
              lineHeight: 1.7,
              marginBottom: 48,
            }}
          >
            PhilVerify checks claims, URLs, images, and videos against live news evidence — built for Tagalog, English, and Taglish content.
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
                to="/verify"
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
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.borderLeftColor = 'var(--accent-red)'
                    e.currentTarget.style.background = 'var(--bg-elevated)'
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.borderLeftColor = 'transparent'
                    e.currentTarget.style.background = 'var(--bg-surface)'
                  }}
                >
                  <Icon
                    size={20}
                    strokeWidth={1.5}
                    style={{ color: 'var(--accent-red)', marginBottom: 16 }}
                  />
                  <div
                    style={{
                      fontFamily: 'var(--font-display)',
                      fontSize: 13,
                      fontWeight: 700,
                      letterSpacing: '0.15em',
                      textTransform: 'uppercase',
                      color: 'var(--text-primary)',
                      marginBottom: 10,
                    }}
                  >
                    {label}
                  </div>
                  <p
                    style={{
                      fontFamily: 'var(--font-body)',
                      fontSize: 14,
                      color: 'var(--text-secondary)',
                      lineHeight: 1.6,
                    }}
                  >
                    {desc}
                  </p>
                </div>
              </Link>
            ))}
          </div>
        </div>
      </section>

      {/* ── Inline CTA Teaser ─────────────────────────────── */}
      <section style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-elevated)' }}>
        <div style={{ ...PAGE_STYLE, paddingTop: 48, paddingBottom: 48 }}>
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
          <form onSubmit={handleTrySubmit} style={{ display: 'flex', gap: 0, maxWidth: 640 }}>
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
              fontSize: 'clamp(1.8rem, 5vw, 3.5rem)',
              fontWeight: 800,
              letterSpacing: '-0.02em',
              color: '#fff',
              lineHeight: 1,
              maxWidth: 600,
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
