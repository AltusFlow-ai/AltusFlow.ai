import React from 'react'

export default function StatCard({ label, value, sub, rag, icon: Icon, accent }) {
  const ragColors = { green: '#1D9E75', amber: '#BA7517', red: '#D85A30' }
  const borderColor = rag ? ragColors[rag] : (accent || 'var(--border)')
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: `1px solid ${borderColor}`,
      borderLeft: `3px solid ${borderColor}`,
      borderRadius: 'var(--radius-lg)',
      padding: '18px 20px',
      display: 'flex', flexDirection: 'column', gap: 6,
      minWidth: 0,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '.07em', textTransform: 'uppercase' }}>
          {label}
        </span>
        {Icon && <Icon size={15} color={borderColor} />}
      </div>
      <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>
        {value ?? '—'}
      </div>
      {sub && <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{sub}</div>}
    </div>
  )
}
