import React, { useState, useEffect } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { useApp } from '../App.jsx'

// ── Zone definitions ──────────────────────────────────────────────────────────
const ZONES = [
  { key: 'hunt',    label: 'Hunt',    color: '#1D9E75' },
  { key: 'convert', label: 'Convert', color: '#534AB7' },
  { key: 'report',  label: 'Report',  color: '#E8A020' },
  { key: 'admin',   label: 'Admin',   color: '#555E6B' },
]

const ZONE_ROUTES = {
  hunt:    ['/dashboard/prospects', '/dashboard/lead-sources', '/dashboard/value-posts', '/dashboard/contacts'],
  convert: ['/dashboard/replies', '/dashboard/calls', '/dashboard/journey', '/dashboard/pipeline'],
  report:  ['/dashboard/niche-delivery', '/dashboard/analytics', '/dashboard/reports', '/dashboard/clients'],
  admin:   ['/dashboard/command-center', '/dashboard/pods', '/dashboard/connections', '/dashboard/budget', '/dashboard/learning', '/dashboard/settings'],
}

const ZONE_ITEMS = {
  hunt: [
    { to: '/dashboard/prospects',       label: 'Prospects',        icon: '🎯', badge: 'pending' },
    { to: '/dashboard/lead-sources',    label: 'Lead Sources',     icon: '🔍' },
    { to: '/dashboard/value-posts',     label: 'Content',          icon: '✍️' },
    { to: '/dashboard/contacts',        label: 'Contacts',         icon: '👤' },
  ],
  convert: [
    { to: '/dashboard/replies',   label: 'Reply Center', icon: '💬', badge: 'conversations' },
    { to: '/dashboard/calls',     label: 'Calls',        icon: '📞' },
    { to: '/dashboard/journey',   label: 'Journey',      icon: '🔗' },
    { to: '/dashboard/pipeline',  label: 'Pipeline',     icon: '📊' },
  ],
  report: [
    { to: '/dashboard/niche-delivery', label: 'Delivery',  icon: '📦' },
    { to: '/dashboard/analytics',      label: 'Analytics', icon: '📈' },
    { to: '/dashboard/reports',        label: 'Reports',   icon: '📄' },
    { to: '/dashboard/clients',        label: 'Clients',   icon: '🏢' },
  ],
  admin: [
    { to: '/dashboard/command-center', label: 'Command Center', icon: '🖥' },
    { to: '/dashboard/pods',           label: 'Pods',           icon: '⚡' },
    { to: '/dashboard/connections',    label: 'Connections',    icon: '🔌' },
    { to: '/dashboard/budget',         label: 'Budget',         icon: '💰' },
    { to: '/dashboard/learning',       label: 'Learning',       icon: '🧠' },
    { to: '/dashboard/settings',       label: 'Settings',       icon: '⚙️' },
  ],
}

function detectZone(pathname) {
  for (const [zone, routes] of Object.entries(ZONE_ROUTES)) {
    if (routes.some(r => pathname.startsWith(r))) return zone
  }
  return 'hunt'
}

function NavItem({ to, children }) {
  return (
    <NavLink
      to={to}
      className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
      style={{ textDecoration: 'none' }}
    >
      {children}
    </NavLink>
  )
}

export default function Sidebar() {
  const location = useLocation()
  const { user, hermesMode, setHermesMode, hermesCallsOn, setHermesCallsOn, navStats } = useApp()
  const isAdmin = user?.is_admin ?? true // default true while loading so layout doesn't flash

  const [activeZone, setActiveZone] = useState(() => detectZone(location.pathname))

  // Sync zone when navigating via NavLink (e.g. clicking a nav item changes the route)
  useEffect(() => {
    const detected = detectZone(location.pathname)
    // If non-admin lands on admin zone, fall back to hunt
    if (detected === 'admin' && !isAdmin) setActiveZone('hunt')
    else setActiveZone(detected)
  }, [location.pathname, isAdmin])

  const visibleZones = isAdmin ? ZONES : ZONES.filter(z => z.key !== 'admin')

  const zone  = ZONES.find(z => z.key === activeZone)
  // For non-admins, hide the Clients item from the report zone
  const items = (ZONE_ITEMS[activeZone] || []).filter(item =>
    isAdmin || item.to !== '/dashboard/clients'
  )

  return (
    <div className="sidebar" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>

      {/* Logo */}
      <div className="sidebar-logo">
        <img src="/static/dashboard/logo.png" alt="AltusFlow" style={{ height: 32, width: 'auto', display: 'block', flexShrink: 0 }} />
        <div className="sidebar-logo-text">AltusFlow<span>.ai</span></div>
      </div>

      {/* Zone tabs */}
      <div style={{
        display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5,
        padding: '0 12px', marginBottom: 12,
      }}>
        {visibleZones.map(z => {
          const isActive = activeZone === z.key
          return (
            <button
              key={z.key}
              onClick={() => setActiveZone(z.key)}
              style={{
                padding: '7px 6px', borderRadius: 7, border: 'none',
                fontSize: 11, fontWeight: 700, cursor: 'pointer',
                background: isActive ? z.color : 'var(--bg)',
                color: isActive ? '#fff' : 'var(--text-tertiary)',
                transition: 'all 0.15s',
                letterSpacing: '0.02em',
              }}
            >
              {z.label}
            </button>
          )
        })}
      </div>

      {/* Zone nav items */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
          <div style={{
            fontSize: 9, fontWeight: 700, color: zone?.color || 'var(--text-tertiary)',
            letterSpacing: '0.1em', textTransform: 'uppercase',
            padding: '0 16px', marginBottom: 6,
          }}>
            {zone?.label}
          </div>

          {items.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => 'nav-item' + (isActive ? ' active' : '')}
              style={{ textDecoration: 'none' }}
            >
              {item.icon} {item.label}
              {item.badge === 'pending' && navStats.pending > 0 && (
                <span className="nav-badge">{navStats.pending}</span>
              )}
              {item.badge === 'conversations' && navStats.conversations > 0 && (
                <span className="nav-badge amber">{navStats.conversations}</span>
              )}
            </NavLink>
          ))}
      </div>

      {/* Assistant status strip */}
      <div style={{
        margin: '8px 12px', padding: '8px 10px', borderRadius: 8,
        background: 'var(--bg)', border: '1px solid var(--border)',
        display: 'flex', flexDirection: 'column', gap: 6,
      }}>
        {/* Mode row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)' }}>
            Assistant
          </span>
          <div style={{ display: 'flex', gap: 4 }}>
            {['auto', 'assist', 'human'].map(m => (
              <button
                key={m}
                onClick={() => setHermesMode(m)}
                style={{
                  padding: '2px 7px', borderRadius: 4, border: 'none',
                  fontSize: 9, fontWeight: 700, cursor: 'pointer',
                  background: hermesMode === m
                    ? m === 'auto' ? 'rgba(29,158,117,0.2)' : m === 'assist' ? 'rgba(232,160,32,0.2)' : 'rgba(100,100,100,0.2)'
                    : 'transparent',
                  color: hermesMode === m
                    ? m === 'auto' ? '#1D9E75' : m === 'assist' ? '#E8A020' : '#888'
                    : 'var(--text-tertiary)',
                  textTransform: 'uppercase', letterSpacing: '0.04em',
                }}
              >
                {m === 'auto' ? 'Auto' : m === 'assist' ? 'Assist' : 'Manual'}
              </button>
            ))}
          </div>
        </div>

        {/* Calls toggle */}
        <div
          onClick={() => setHermesCallsOn(!hermesCallsOn)}
          style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', cursor: 'pointer' }}
        >
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
            📞 Answers calls
          </span>
          <div style={{
            width: 28, height: 16, borderRadius: 8, position: 'relative',
            background: hermesCallsOn ? 'var(--teal)' : 'var(--border)',
            transition: 'background 0.2s', flexShrink: 0,
          }}>
            <div style={{
              position: 'absolute', top: 2, left: hermesCallsOn ? 12 : 2,
              width: 12, height: 12, borderRadius: '50%', background: '#fff',
              transition: 'left 0.2s',
            }} />
          </div>
        </div>
      </div>

      {/* Bottom bar: user + logout */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '10px 14px', borderTop: '1px solid var(--border)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, minWidth: 0 }}>
          <div className="user-avatar" style={{ width: 28, height: 28, fontSize: 11, flexShrink: 0 }}>
            {(user?.company_name || user?.email || 'AU').slice(0, 2).toUpperCase()}
          </div>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {user?.company_name || user?.email || 'Loading…'}
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)' }}>
              {isAdmin ? 'Admin' : 'Client'}
            </div>
          </div>
        </div>
        <a
          href="/logout"
          style={{ fontSize: 10, color: 'var(--text-tertiary)', textDecoration: 'none', flexShrink: 0, padding: '3px 6px', borderRadius: 4, border: '1px solid var(--border)' }}
        >
          Log out
        </a>
      </div>

    </div>
  )
}
