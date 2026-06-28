import React, { useState } from 'react'

const TABS = ['Signal phrases', 'Best openers', 'Objections', 'Market intel', 'Call insights']

const EMPTY = {
  'Signal phrases': 'Signal phrases will appear here as Hermes scans conversations and tracks which phrases trigger replies.',
  'Best openers':   'High-performing opener templates will appear here after Hermes sends messages and tracks reply rates.',
  'Objections':     'Common objections and Hermes\'s best responses will appear here from call transcripts and DM threads.',
  'Market intel':   'Market signals and trend insights will appear here as Reddit scanning builds up.',
  'Call insights':  'Patterns from call transcripts will appear here after Hermes processes recordings.',
}

function EmptyTab({ tab }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '48px 24px' }}>
      <div style={{ fontSize: 28, marginBottom: 12 }}>🧠</div>
      <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
        No {tab.toLowerCase()} yet
      </div>
      <div style={{ fontSize: 12, color: 'var(--text-tertiary)', maxWidth: 360, margin: '0 auto', lineHeight: 1.6 }}>
        {EMPTY[tab]}
      </div>
    </div>
  )
}

export default function Learning() {
  const [tab, setTab] = useState('Signal phrases')

  return (
    <div className="content">
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            fontSize: 11, padding: '5px 13px', borderRadius: 6, cursor: 'pointer',
            border: `1px solid ${tab === t ? 'var(--teal)' : 'var(--border)'}`,
            background: tab === t ? 'rgba(29,158,117,0.12)' : 'transparent',
            color: tab === t ? 'var(--teal)' : 'var(--text-secondary)', fontWeight: tab === t ? 700 : 400,
          }}>
            {t}
          </button>
        ))}
      </div>
      <EmptyTab tab={tab} />
    </div>
  )
}
