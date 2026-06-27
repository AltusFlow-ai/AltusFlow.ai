import React from 'react'

const PODS = [
  { name: 'altusflow-own',          lastRun: '4:15 PM', found: 14, errors: 0 },
  { name: 'financial-advisors',     lastRun: '8:00 PM', found: 8,  errors: 0 },
  { name: 'trading-coaches',        lastRun: '4:15 PM', found: 4,  errors: 0 },
  { name: 'recruiters',             lastRun: '4:15 PM', found: 2,  errors: 0 },
  { name: 'commercial-real-estate', lastRun: '4:15 PM', found: 0,  errors: 0 },
  { name: 'msps',                   lastRun: '4:15 PM', found: 0,  errors: 0 },
]

export default function Pods() {
  return (
    <div className="content">
      

      <div className="stat-grid">
        <div className="stat-card"><div className="stat-label">Active pods</div><div className="stat-value">6</div></div>
        <div className="stat-card"><div className="stat-label">Last scan</div><div className="stat-value">4:15 PM</div></div>
        <div className="stat-card rag-green"><div className="stat-label">Errors today</div><div className="stat-value" style={{ color: 'var(--teal)' }}>0</div></div>
        <div className="stat-card rag-green"><div className="stat-label">Circuit breakers</div><div className="stat-value" style={{ fontSize: 14, color: 'var(--teal)' }}>All closed</div></div>
      </div>

      <div className="pod-grid">
        {PODS.map(pod => (
          <div key={pod.name} className="pod-card">
            <div className="pod-card-header">
              <div className="pod-name">{pod.name}</div>
              <span className="pod-status running">Running</span>
            </div>
            <div className="pod-meta">Last run: {pod.lastRun} · Next: 4:15 PM today</div>
            <div className="pod-meta">{pod.found} prospects found · {pod.errors} errors</div>
            <div className="pod-actions">
              <button className="pod-btn run">Run Now</button>
              <button className="pod-btn">Pause</button>
              <button className="pod-btn">Logs</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
