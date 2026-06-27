import React from 'react'

export default function Reports() {
  return (
    <div className="content">
      <div className="card" style={{ textAlign: 'center', padding: '60px 20px' }}>
        <div style={{ fontSize: 32, marginBottom: 12 }}>📄</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>
          No reports yet
        </div>
        <div style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>
          Reports will appear here once your first scan runs.
        </div>
      </div>
    </div>
  )
}
