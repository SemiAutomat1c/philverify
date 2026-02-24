import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar.jsx'
import VerifyPage from './pages/VerifyPage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import TrendsPage from './pages/TrendsPage.jsx'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
        <Navbar />
        <main>
          <Routes>
            <Route path="/" element={<VerifyPage />} />
            <Route path="/history" element={<HistoryPage />} />
            <Route path="/trends" element={<TrendsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
