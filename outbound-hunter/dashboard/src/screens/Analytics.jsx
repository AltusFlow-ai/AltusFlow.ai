import React, { useState, useEffect } from 'react'
import MarketPulseWidget from '../components/MarketPulseWidget.jsx'

export default function Analytics() {
  const [funnel, setFunnel] = useState({ scraped: 14, qualified: 8, contacted: 8, engaged: 4, booked: 0 })
  const [metrics, setMetrics] = useState({ total_scraped: 14, qual_rate: 57, avg_speed_h: 3.2, engagement_rate: 25 })

  useEffect(() => {
    fetch('/api/analytics/funnel').then(r => r.ok ? r.json() : null).then(d => { if (d) setFunnel(d) }).catch(() => {})
    fetch('/api/analytics/metrics').then(r => r.ok ? r.json() : null).then(d => { if (d) setMetrics(d) }).catch(() => {})
  }, [])

  const f = funnel
  const scraped   = f.scraped   || 14
  const qualified = f.qualified || 8
  const contacted = f.contacted || 8
  const engaged   = f.engaged   || 4
  const booked    = f.booked    || 0

  function pct(n, d) { return d > 0 ? Math.round((n / d) * 100) : 0 }

  return (
    <div className="content">
      <div className="demo-label">📈 ANALYTICS SCREEN — Funnel + RAG metrics</div>

      <div className="stat-grid">
        <div className="stat-card rag-green">
          <div className="stat-label">Total scraped</div>
          <div className="stat-value">{metrics.total_scraped ?? 14}</div>
          <div className="stat-delta up">Always green</div>
        </div>
        <div className="stat-card rag-green">
          <div className="stat-label">Qualification rate</div>
          <div className="stat-value">{metrics.qual_rate ?? 57}%</div>
          <div className="stat-delta up">↑ Above 30% target</div>
        </div>
        <div className="stat-card rag-green">
          <div className="stat-label">Speed to touch</div>
          <div className="stat-value">{metrics.avg_speed_h ?? 3.2}h</div>
          <div className="stat-delta up">↑ Under 24h target</div>
        </div>
        <div className="stat-card rag-amber">
          <div className="stat-label">Engagement rate</div>
          <div className="stat-value">{metrics.engagement_rate ?? 25}%</div>
          <div className="stat-delta up">↑ Above 15% target</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Conversion funnel — Scraped → Qualified → Contacted → Engaged → Booked</div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Scraped</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar" style={{ width: '100%' }}>{scraped} · 100%</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Qualified</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar" style={{ width: `${pct(qualified, scraped)}%` }}>{qualified} · {pct(qualified, scraped)}%</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Contacted</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar" style={{ width: `${pct(contacted, scraped)}%` }}>{contacted} · 100%</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Engaged</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar drop" style={{ width: `${pct(engaged, scraped)}%` }}>{engaged} · {pct(engaged, contacted)}%</div></div>
        </div>
        <div className="funnel-step">
          <div className="funnel-label">Booked</div>
          <div className="funnel-bar-wrap"><div className="funnel-bar drop" style={{ width: `${Math.max(7, pct(booked, scraped))}%`, opacity: booked === 0 ? 0.5 : 1 }}>{booked}</div></div>
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 12, background: 'var(--bg-secondary)', padding: 10, borderRadius: 'var(--radius-md)' }}>
          💡 Diagnosis: Contacted to Engaged drop is the focus area — message quality or follow-up timing. Consider reviewing drafted message style or tightening signal phrases.
        </div>
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
