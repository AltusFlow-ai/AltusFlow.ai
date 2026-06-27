import React from 'react'
import { NICHE_COLORS } from '../App.jsx'

export default function NicheBadge({ niche, small }) {
  const cfg = NICHE_COLORS[niche] || { color: '#6b7280', bg: 'rgba(107,114,128,0.15)', text: '#9ca3af', label: niche || 'Unknown' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      background: cfg.bg, color: cfg.text,
      border: `1px solid ${cfg.color}33`,
      borderRadius: 20, padding: small ? '2px 8px' : '3px 10px',
      fontSize: small ? 11 : 12, fontWeight: 500, whiteSpace: 'nowrap',
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.color, flexShrink: 0 }} />
      {cfg.label}
    </span>
  )
}
