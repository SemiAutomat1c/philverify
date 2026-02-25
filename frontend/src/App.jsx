import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import VerifyPage from './pages/VerifyPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import TrendsPage from './pages/TrendsPage.jsx'

/** Shared horizontal constraint — all pages + navbar use this */
export const PAGE_MAX_W = 960
export const PAGE_STYLE = {
  maxWidth: PAGE_MAX_W,
  width: '100%',
  margin: '0 auto',
  padding: '0 24px',
}

export default function App() {
  return (
    <BrowserRouter>
      {/* web-design-guidelines: skip link for keyboard/screen-reader users */}
      <a
        href="#main-content"
        className="sr-only focus-visible:not-sr-only"
        style={{
          position: 'fixed',
          top: 8,
          left: 8,
          zIndex: 9999,
          background: 'var(--accent-red)',
          color: '#fff',
          padding: '8px 16px',
          fontFamily: 'var(--font-display)',
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: '0.08em',
          borderRadius: 2,
          textDecoration: 'none',
        }}
      >
        Skip to content
      </a>
      <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
        <Navbar />
        <div id="main-content">
          <Routes>
            <Route path="/" element={<VerifyPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/trends" element={<TrendsPage />} />
          </Routes>
        </div>
      </div>
    </BrowserRouter>
  )
}
