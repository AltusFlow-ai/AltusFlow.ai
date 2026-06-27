import React, { useEffect, useRef } from 'react'
import { Outlet, useNavigate, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar.jsx'
import Topbar from './Topbar.jsx'

export default function Layout() {
  const navigate = useNavigate()
  const location = useLocation()
  const wasActive = useRef(false)

  useEffect(() => {
    const poll = async () => {
      try {
        const r = await fetch('/api/calls/active')
        if (!r.ok) return
        const { active } = await r.json()
        const onLive = location.pathname === '/dashboard/calls/live'
        if (active && !onLive) {
          wasActive.current = true
          navigate('/dashboard/calls/live')
        } else if (!active && wasActive.current && onLive) {
          wasActive.current = false
          navigate('/dashboard/calls')
        }
        if (active) wasActive.current = true
        if (!active && !onLive) wasActive.current = false
      } catch {}
    }
    poll()
    const id = setInterval(poll, 3000)
    return () => clearInterval(id)
  }, [navigate, location.pathname])

  return (
    <div className="app">
      <Sidebar />
      <div className="main">
        <Topbar />
        <div className="content">
          <Outlet />
        </div>
      </div>
    </div>
  )
}
