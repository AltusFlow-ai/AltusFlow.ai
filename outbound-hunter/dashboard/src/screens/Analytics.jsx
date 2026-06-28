import React, { useState, useEffect } from 'react'
import MarketPulseWidget from '../components/MarketPulseWidget.jsx'

export default function Analytics() {
  const [funnel, setFunnel] = useState({ scraped: 0, qualified: 0, contacted: 0, engaged: 0, booked: 0 })
  const [metrics, setMetrics] = useState({ total_scraped: 0, qual_rate: 0, avg_speed_h: 0, engagement_rate: 0 })

  useEffect(() => {
    fetch('/api/analytics/funnel').then(r => r.ok ? r.json() : null).then(d => { if (d) setFunnel(d) }).catch(() => {})
    fetch('/api/analytics/metrics').then(r => r.ok ? r.json() : null).then(d => { if (d) setMetrics(d) }).catch(() => {})
  }, [])

  const f = funnel
  const scraped   = f.scraped   || 0
  const qualified = f.qualified || 0
  const contacted = f.contacted || 0
  const engaged   = f.engaged   || 0
  const booked    = f.booked    || 0

  function pct(n, d) { return d > 0 ? Math.round((n / d) * 100) : 0 }

  return (
    <div className="content">
      <div className="stat-grid">
        <div className="stat-card rag-green">
          <div className="stat-label">Total scraped</div>
          <div className="stat-value">{metrics.total_scraped ?? 0}</div>
          <div className="stat-delta">—</div>
        </div>
        <div className="stat-card rag-green">
          <div className="stat-label">Qualification rate</div>
          <div className="stat-value">{metrics.qual_rate ?? 0}%</div>
          <div className="stat-delta">Target: 30%+</div>
        </div>
        <div className="stat-card rag-green">
          <div className="stat-label">Speed to touch</div>
          <div className="stat-value">{metrics.avg_speed_h ?? 0}h</div>
          <div className="stat-delta">Target: under 24h</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Engagement rate</div>
          <div className="stat-value">{metrics.engagement_rate ?? 0}%</div>
          <div className="stat-delta">Target: 15%+</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Conversion funnel — Scraped → Qualified → Contacted → Engaged → Booked</div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Scraped</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar" style={{ width: '100%' }}>{scraped}</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Qualified</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar" style={{ width: `${pct(qualified, scraped)}%` }}>{qualified} · {pct(qualified, scraped)}%</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Contacted</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar" style={{ width: `${pct(contacted, scraped)}%` }}>{contacted} · {pct(contacted, scraped)}%</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Engaged</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar drop" style={{ width: `${pct(engaged, scraped)}%` }}>{engaged} · {pct(engaged, contacted)}%</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Booked</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar drop" style={{ width: `${pct(booked, scraped)}%`, opacity: booked === 0 ? 0.4 : 1 }}>{booked}</div></div>
        </div>
        {scraped === 0 && (
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 12, padding: '10px 0' }}>
            No data yet — funnel will populate after your first scan runs.
          </div>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Market Pulse — Reddit + Twitter signals</div>
        </div>
        <MarketPulseWidget />
      </div>
    </div>
  )
}
