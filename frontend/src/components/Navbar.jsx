import { NavLink } from 'react-router-dom'
import { Radar, Clock, TrendingUp, ShieldCheck } from 'lucide-react'

const NAV_LINKS = [
    { to: '/', icon: ShieldCheck, label: 'Verify' },
    { to: '/history', icon: Clock, label: 'History' },
    { to: '/trends', icon: TrendingUp, label: 'Trends' },
]

export default function Navbar() {
    return (
        /* semantic <header> — web-design-guidelines: semantic HTML */
        <header
            role="banner"
            style={{ background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}
            className="sticky top-0 z-50 flex items-center justify-between px-6 h-14"
        >
            {/* Logo */}
            <div className="flex items-center gap-2" aria-label="PhilVerify home">
                <Radar size={18} style={{ color: 'var(--accent-red)' }} aria-hidden="true" />
                <span className="font-display font-bold text-sm tracking-wide"
                    style={{ fontFamily: 'var(--font-display)', letterSpacing: '0.05em' }}>
                    PHIL<span style={{ color: 'var(--accent-red)' }}>VERIFY</span>
                </span>
            </div>

            {/* Nav — web-design-guidelines: use <nav> for navigation */}
            <nav aria-label="Main navigation">
                <ul className="flex items-center gap-1" role="list">
                    {NAV_LINKS.map(({ to, icon: Icon, label }) => (
                        <li key={to}>
                            <NavLink to={to} end={to === '/'}>
                                {({ isActive }) => (
                                    <div
                                        className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold transition-colors"
                                        style={{
                                            fontFamily: 'var(--font-display)',
                                            letterSpacing: '0.08em',
                                            color: isActive ? 'var(--text-primary)' : 'var(--text-muted)',
                                            borderBottom: isActive ? '2px solid var(--accent-red)' : '2px solid transparent',
                                        }}
                                    >
                                        {/* aria-hidden on decorative icons — web-design-guidelines */}
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
        </header>
    )
}
