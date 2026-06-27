import React, { useState, useEffect } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useApp } from '../App.jsx'

const PAGE_META = {
  prospects:   ['Today\'s prospects',  'Scanner ran 4:15 PM · 14 qualified · 6 auto-approved'],
  replies:     ['Reply center',        '3 unread · all platforms in one place'],
  journey:     ['Journey',             'Full prospect timeline from Reddit post to closed deal'],
  pipeline:    ['Pipeline',            'All prospects across every stage · HubSpot synced'],
  analytics:   ['Analytics',           'Funnel performance · RAG metrics · speed to touch'],
  budget:      ['Budget',              'Every marketing dollar tracked in real time'],
  learning:    ['Learning',            'What Hermes has learned about your market'],
  calls:       ['Calls',               'Hermes voice · transcripts · learnings fed back to model'],
  reports:     ['Reports',             'Monthly PDFs auto-generated on the 1st'],
  'lead-sources':   ['Lead Sources',   'All 4 channels side by side — volume, reply rate, and conversion per source'],
  'value-posts':    ['Attract',        'Generate & approve content · paste your own · batch from topic intelligence'],
  'contacts':       ['Contacts',        'Warm leads, past clients, referral sources — people you already know'],
  'command-center': ['Command Center', 'Agency ops · all clients · pod health · pipeline at a glance'],
  clients:          ['Clients',        'All active client accounts'],
  pods:        ['Pods',                '6 pods active · orchestrator running · 0 errors'],
  connections: ['Connections',         'All API integrations in one place'],
  settings:    ['Settings',            'Account · niche config · team · plan · notifications'],
}

const MODE_LABELS = {
  auto:   'Hermes — Full Auto',
  assist: 'Hermes — Assist',
  human:  'Human Only',
}

export default function Topbar() {
  const { hermesMode, cycleHermes } = useApp()
  const location = useLocation()
  const navigate = useNavigate()
  const [phoneConnected, setPhoneConnected] = useState(null)

  const screen = location.pathname.split('/').pop()
  const [title, sub] = PAGE_META[screen] || ['AltusFlow', '']

  useEffect(() => {
    fetch('/api/connections')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setPhoneConnected(!!d.twilio) })
      .catch(() => setPhoneConnected(false))
  }, [])

  return (
    <div className="topbar">
      <div className="topbar-left">
        <div className="topbar-title">{title}</div>
        <div className="topbar-sub">{sub}</div>
      </div>
      <div className="topbar-right">

        {/* Phone status pill */}
        {phoneConnected !== null && (
          <div
            onClick={phoneConnected ? undefined : () => navigate('/dashboard/connections')}
            title={phoneConnected ? 'Twilio connected' : 'Click to connect phone'}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              padding: '4px 10px', borderRadius: 20,
              border: `1px solid ${phoneConnected ? 'rgba(29,158,117,0.4)' : 'rgba(216,90,48,0.4)'}`,
              background: phoneConnected ? 'rgba(29,158,117,0.08)' : 'rgba(216,90,48,0.08)',
              cursor: phoneConnected ? 'default' : 'pointer',
              userSelect: 'none',
            }}
          >
            <div style={{
              width: 7, height: 7, borderRadius: '50%',
              background: phoneConnected ? 'var(--teal)' : 'var(--coral)',
              flexShrink: 0,
            }} />
            <span style={{
              fontSize: 11, fontWeight: 600,
              color: phoneConnected ? 'var(--teal)' : 'var(--coral)',
            }}>
              {phoneConnected ? 'Phone connected' : 'Phone disconnected'}
            </span>
            {!phoneConnected && (
              <span style={{ fontSize: 10, color: 'var(--coral)', opacity: 0.7 }}>→</span>
            )}
          </div>
        )}

        <div className={`mode-pill ${hermesMode}`} onClick={cycleHermes}>
          <div className={`pulse ${hermesMode}`} />
          <span>{MODE_LABELS[hermesMode]}</span>
        </div>
        {screen === 'prospects' && (
          <button className="btn btn-primary">Approve all 9+ →</button>
        )}
      </div>
    </div>
  )
}
