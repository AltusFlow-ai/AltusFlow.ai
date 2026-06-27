import React from 'react'

export default function Clients() {
  return (
    <div className="content">
      <div className="demo-label">🏢 CLIENTS SCREEN — Admin only — all client accounts</div>
      <div className="card" style={{ padding: 40, textAlign: 'center' }}>
        <div style={{ color: 'var(--text-tertiary)', marginBottom: 16 }}>No clients yet</div>
        <button className="btn btn-primary">Onboard first client →</button>
      </div>
    </div>
  )
}
