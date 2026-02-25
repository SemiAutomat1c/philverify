import { NavLink, Link } from 'react-router-dom'
import { Radar, Clock, TrendingUp, ShieldCheck } from 'lucide-react'
import { PAGE_STYLE } from '../App.jsx'

const NAV_LINKS = [
    { to: '/', icon: ShieldCheck, label: 'Verify' },
    { to: '/history', icon: Clock, label: 'History' },
    { to: '/trends', icon: TrendingUp, label: 'Trends' },
]

export default function Navbar() {
    return (
        <header
            role="banner"
            style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}
            className="sticky top-0 z-50 h-14"
        >
            {/* Inner content aligned to same width as page content */}
            <div style={{
                ...PAGE_STYLE,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                height: '100%',
            }}>
                {/* Logo — Link to home */}
                <Link
                    to="/"
                    className="flex items-center gap-2"
                    aria-label="PhilVerify home"
                    style={{ textDecoration: 'none' }}
                >
                    <Radar size={18} style={{ color: 'var(--accent-red)' }} aria-hidden="true" />
                    <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: 13, letterSpacing: '0.05em', color: 'var(--text-primary)' }}>
                        PHIL<span style={{ color: 'var(--accent-red)' }}>VERIFY</span>
                    </span>
                </Link>

                {/* Nav */}
                <nav aria-label="Main navigation">
                    <ul className="flex items-center gap-2" role="list">
                        {NAV_LINKS.map(({ to, icon: Icon, label }) => (
                            <li key={to}>
                                <NavLink to={to} end={to === '/'} className="nav-link-item">
                                    {({ isActive }) => (
                                        <div
                                            className="flex items-center gap-2 px-4 py-2 text-xs font-semibold transition-colors"
                                            style={{
                                                fontFamily: 'var(--font-display)',
                                                letterSpacing: '0.08em',
                                                color: isActive ? 'var(--text-primary)' : 'var(--text-secondary)',
                                                borderBottom: isActive ? '2px solid var(--accent-red)' : '2px solid transparent',
                                                minHeight: 44,
                                                display: 'flex',
                                                alignItems: 'center',
                                            }}
                                        >
                                            <Icon size={13} aria-hidden="true" />
                                            {label}
                                        </div>
                                    )}
                                </NavLink>
                            </li>
                        ))}
                    </ul>
                </nav>

                {/* Live indicator */}
                <div className="flex items-center gap-1.5 text-xs tabular"
                    style={{ color: 'var(--text-muted)' }}
                    aria-label="API status: live">
                    <span className="w-1.5 h-1.5 rounded-full" aria-hidden="true"
                        style={{ background: 'var(--accent-green)' }} />
                    LIVE
                </div>
            </div>
        </header>
    )
}
