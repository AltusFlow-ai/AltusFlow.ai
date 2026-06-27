import React from 'react'
import { RAG } from '../App.jsx'

export default function RAGBadge({ status, label, style }) {
  const cfg = RAG[status] || RAG.amber
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      background: cfg.bg, border: `1px solid ${cfg.border}44`,
      borderRadius: 20, padding: '3px 10px',
      fontSize: 12, color: cfg.dot, fontWeight: 500,
      ...style,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: '50%', background: cfg.dot, flexShrink: 0 }} />
      {label}
    </span>
  )
}
