import React, { useState, useEffect } from 'react'

const NICHE_COLORS = { fa: 'var(--niche-fa)', tc: 'var(--niche-tc)', rc: 'var(--niche-rc)', cre: 'var(--niche-cre)', msp: 'var(--niche-msp)' }

export default function Pipeline() {
  const [stages, setStages]         = useState({ new_lead: { count: 0 }, replied: { count: 0 }, call_booked: { count: 0 }, proposal_sent: { count: 0 }, closed_won: { count: 0 } })
  const [subreddits, setSubreddits] = useState([])

  useEffect(() => {
    fetch('/api/pipeline/stages').then(r => r.ok ? r.json() : null).then(d => { if (d) setStages(d) }).catch(() => {})
    fetch('/api/pipeline/subreddit-breakdown').then(r => r.ok ? r.json() : null).then(d => { if (d) setSubreddits(d) }).catch(() => {})
  }, [])

  const maxSub = Math.max(...subreddits.map(s => s.prospects), 1)

  const totalDMs    = (stages.new_lead?.count ?? 0) + (stages.replied?.count ?? 0)
  const replyRate   = totalDMs > 0 ? Math.round(((stages.replied?.count ?? 0) / totalDMs) * 100) : 0

  return (
    <div className="content">
      <div className="stat-grid">
        <div className="stat-card"><div className="stat-label">Pipeline value</div><div className="stat-value">$0</div><div className="stat-delta">No closed deals yet</div></div>
        <div className="stat-card"><div className="stat-label">Calls booked</div><div className="stat-value">{stages.call_booked?.count ?? 0}</div><div className="stat-delta">—</div></div>
        <div className="stat-card"><div className="stat-label">Replies</div><div className="stat-value">{stages.replied?.count ?? 0}</div><div className="stat-delta">{replyRate}% reply rate</div></div>
        <div className="stat-card"><div className="stat-label">DMs sent total</div><div className="stat-value">{totalDMs}</div><div className="stat-delta">—</div></div>
      </div>

      <div className="pipeline-stages">
        <div className="pipeline-stage"><div className="pipeline-num">{stages.new_lead?.count ?? 0}</div><div className="pipeline-label">New Lead</div></div>
        <div className="pipeline-stage"><div className="pipeline-num">{stages.replied?.count ?? 0}</div><div className="pipeline-label">Replied</div></div>
        <div className="pipeline-stage"><div className="pipeline-num">{stages.call_booked?.count ?? 0}</div><div className="pipeline-label">Call Booked</div></div>
        <div className="pipeline-stage"><div className="pipeline-num">{stages.proposal_sent?.count ?? 0}</div><div className="pipeline-label">Proposal Sent</div></div>
        <div className="pipeline-stage won"><div className="pipeline-num">{stages.closed_won?.count ?? 0}</div><div className="pipeline-label">Closed Won</div></div>
      </div>

      <div className="card">
        <div className="card-header"><div className="card-title">Top subreddits this week</div></div>
        {subreddits.length === 0 ? (
          <div style={{ padding: '20px 0', textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
            No subreddit data yet — scans will populate this.
          </div>
        ) : subreddits.slice(0, 4).map((s, i) => (
          <div key={i} className="bar-chart-row">
            <div className="bar-label">r/{s.subreddit}</div>
            <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.round((s.prospects / maxSub) * 100)}%`, background: 'var(--teal)' }} /></div>
            <div className="bar-value">{s.prospects}</div>
          </div>
        ))}
      </div>
    </div>
  )
}
