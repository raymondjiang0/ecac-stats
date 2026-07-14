import { Routes, Route, NavLink, Navigate } from 'react-router-dom'
import RosterPage from './pages/RosterPage'
import GamesPage from './pages/GamesPage'
import GameDetailPage from './pages/GameDetailPage'
import ReportsPage from './pages/ReportsPage'
import MethodologyPage from './pages/MethodologyPage'

const NAV = [
  { to: '/roster', label: 'Roster', icon: '⬡' },
  { to: '/games', label: 'Games', icon: '◈' },
  { to: '/reports', label: 'Reports', icon: '◉' },
  { to: '/methodology', label: 'Methodology', icon: '◎' },
]

export default function App() {
  return (
    <div className="app-shell">
      <nav className="nav-sidebar">
        <div className="nav-logo">
          <div className="nav-logo-title">ECAC Analytics</div>
          <div className="nav-logo-sub">Harvard Women's Hockey</div>
        </div>
        <div className="nav-links">
          {NAV.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}
            >
              <span className="nav-link-icon">{icon}</span>
              {label}
            </NavLink>
          ))}
        </div>
        <div style={{ padding: '16px 20px', borderTop: '1px solid var(--border)', fontSize: 10, color: 'var(--text-secondary)', letterSpacing: '0.06em' }}>
          Powered by 49ing Data Cockpit
        </div>
      </nav>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<Navigate to="/roster" replace />} />
          <Route path="/roster" element={<RosterPage />} />
          <Route path="/games" element={<GamesPage />} />
          <Route path="/games/:id" element={<GameDetailPage />} />
          <Route path="/reports" element={<ReportsPage />} />
          <Route path="/methodology" element={<MethodologyPage />} />
        </Routes>
      </main>
    </div>
  )
}
