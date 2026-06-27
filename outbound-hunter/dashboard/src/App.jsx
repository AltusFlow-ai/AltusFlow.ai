import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import { BrowserRouter, Routes, Route, Navigate, useNavigate } from 'react-router-dom'
import Layout from './components/Layout.jsx'
import Prospects    from './screens/Prospects.jsx'
import ReplyCenter  from './screens/ReplyCenter.jsx'
import Journey      from './screens/Journey.jsx'
import Pipeline     from './screens/Pipeline.jsx'
import Analytics    from './screens/Analytics.jsx'
import Budget       from './screens/Budget.jsx'
import Learning     from './screens/Learning.jsx'
import Calls        from './screens/Calls.jsx'
import Reports      from './screens/Reports.jsx'
import Clients      from './screens/Clients.jsx'
import Pods         from './screens/Pods.jsx'
import Connections  from './screens/Connections.jsx'
import Settings      from './screens/Settings.jsx'
import LiveCall      from './screens/LiveCall.jsx'
import CommandCenter    from './screens/CommandCenter.jsx'
import ValuePosts    from './screens/ValuePosts.jsx'
import Contacts      from './screens/Contacts.jsx'
import LeadSources   from './screens/LeadSources.jsx'
import NicheDelivery    from './screens/NicheDelivery.jsx'
import ContentPipeline  from './screens/ContentPipeline.jsx'

// ── Global state ─────────────────────────────────────────────────────────────
export const AppContext = createContext(null)

export function useApp() { return useContext(AppContext) }

export { NICHE_COLORS, RAG } from './constants.js'

function AdminRoute({ children }) {
  const { user } = useApp()
  if (user === null) return null // still loading
  return user?.is_admin ? children : <Navigate to="/dashboard/prospects" replace />
}

export default function App() {
  const [user, setUser] = useState(undefined) // undefined = loading, null = failed, obj = loaded
  const [hermesMode, setHermesMode] = useState('auto') // 'auto' | 'assist' | 'human'
  const [hermesCallsOn, setHermesCallsOn] = useState(false)

  useEffect(() => {
    fetch('/api/me')
      .then(r => r.ok ? r.json() : null)
      .then(d => setUser(d))
      .catch(() => setUser(null))
  }, [])

  const toggleHermesCalls = useCallback((val) => {
    const next = typeof val === 'boolean' ? val : !hermesCallsOn
    setHermesCallsOn(next)
    fetch('/api/settings/hermes-calls', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ on: next }),
    }).catch(() => {})
  }, [hermesCallsOn])
  const [activeNiche, setActiveNiche] = useState('all') // niche filter: 'all' | 'fa' | 'tc' | 'rc' | 'cre' | 'msp'
  const [navStats, setNavStats]     = useState({ pending: 0, conversations: 0 })
  const [prevStats, setPrevStats]   = useState(null)
  const [pulse, setPulse]           = useState(false)

  const cycleHermes = useCallback(() => {
    setHermesMode(m =>
      m === 'auto' ? 'assist' : m === 'assist' ? 'human' : 'auto'
    )
  }, [])

  // Poll every 60s for nav badges
  const fetchNavStats = useCallback(async () => {
    try {
      const r = await fetch('/api/prospects/stats')
      if (!r.ok) return
      const d = await r.json()
      setNavStats(prev => {
        const next = { pending: d.pending_review ?? 0, conversations: d.unread_conversations ?? 0 }
        if (prevStats && (next.pending > prev.pending || next.conversations > prev.conversations)) {
          setPulse(true)
          setTimeout(() => setPulse(false), 2000)
        }
        setPrevStats(next)
        return next
      })
    } catch {}
  }, [prevStats])

  useEffect(() => {
    fetchNavStats()
    const id = setInterval(fetchNavStats, 60_000)
    return () => clearInterval(id)
  }, [fetchNavStats])

  return (
    <AppContext.Provider value={{ user, hermesMode, setHermesMode, cycleHermes, hermesCallsOn, setHermesCallsOn: toggleHermesCalls, activeNiche, setActiveNiche, navStats, pulse }}>
      <BrowserRouter>
        <Routes>
          <Route path="/dashboard" element={<Layout />}>
            <Route index element={<Navigate to="prospects" replace />} />
            <Route path="prospects"   element={<Prospects />} />
            <Route path="replies"     element={<ReplyCenter />} />
            <Route path="journey"     element={<Journey />} />
            <Route path="pipeline"    element={<Pipeline />} />
            <Route path="analytics"   element={<Analytics />} />
            <Route path="budget"      element={<Budget />} />
            <Route path="learning"    element={<Learning />} />
            <Route path="calls"       element={<Calls />} />
            <Route path="calls/live"  element={<LiveCall />} />
            <Route path="reports"     element={<Reports />} />
            <Route path="value-posts"     element={<ValuePosts />} />
            <Route path="contacts"        element={<Contacts />} />
            <Route path="lead-sources"    element={<LeadSources />} />
            <Route path="niche-delivery"    element={<NicheDelivery />} />
            <Route path="content-pipeline" element={<ContentPipeline />} />
            <Route path="settings"         element={<Settings />} />
            {/* Admin-only routes */}
            <Route path="command-center"  element={<AdminRoute><CommandCenter /></AdminRoute>} />
            <Route path="clients"         element={<AdminRoute><Clients /></AdminRoute>} />
            <Route path="pods"            element={<AdminRoute><Pods /></AdminRoute>} />
            <Route path="connections"     element={<AdminRoute><Connections /></AdminRoute>} />
            <Route path="budget"          element={<AdminRoute><Budget /></AdminRoute>} />
          </Route>
          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AppContext.Provider>
  )
}
