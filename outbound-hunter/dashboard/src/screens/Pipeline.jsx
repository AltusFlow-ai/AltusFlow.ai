import React, { useState, useEffect } from 'react'

const NICHE_COLORS = { fa: 'var(--niche-fa)', tc: 'var(--niche-tc)', rc: 'var(--niche-rc)', cre: 'var(--niche-cre)', msp: 'var(--niche-msp)' }

export default function Pipeline() {
  const [stages, setStages]         = useState({ new_lead: { count: 14 }, replied: { count: 12 }, call_booked: { count: 0 }, proposal_sent: { count: 0 }, closed_won: { count: 0 } })
  const [subreddits, setSubreddits] = useState([
    { subreddit: 'Daytrading', prospects: 9,  avg_score: 8.6, reply_rate: 55.6 },
    { subreddit: 'Futures',    prospects: 7,  avg_score: 8.2, reply_rate: 42.9 },
    { subreddit: 'Forex',      prospects: 6,  avg_score: 7.9, reply_rate: 33.3 },
    { subreddit: 'options',    prospects: 5,  avg_score: 7.4, reply_rate: 20.0 },
  ])

  useEffect(() => {
    fetch('/api/pipeline/stages').then(r => r.ok ? r.json() : null).then(d => { if (d) setStages(d) }).catch(() => {})
    fetch('/api/pipeline/subreddit-breakdown').then(r => r.ok ? r.json() : null).then(d => { if (d) setSubreddits(d) }).catch(() => {})
  }, [])

  const maxSub = Math.max(...subreddits.map(s => s.prospects), 1)

  return (
    <div className="content">
      <div className="demo-label">📊 PIPELINE SCREEN — HubSpot stages + subreddit performance</div>

      <div className="stat-grid">
        <div className="stat-card"><div className="stat-label">Pipeline value</div><div className="stat-value">$0</div><div className="stat-delta">First client pending</div></div>
        <div className="stat-card"><div className="stat-label">Calls booked</div><div className="stat-value">0</div><div className="stat-delta">Week 1</div></div>
        <div className="stat-card"><div className="stat-label">Replies</div><div className="stat-value">12</div><div className="stat-delta up">25% reply rate</div></div>
        <div className="stat-card"><div className="stat-label">DMs sent total</div><div className="stat-value">47</div><div className="stat-delta up">↑ this week</div></div>
      </div>

      <div className="pipeline-stages">
        <div className="pipeline-stage"><div className="pipeline-num">{stages.new_lead?.count ?? 14}</div><div className="pipeline-label">New Lead</div></div>
        <div className="pipeline-stage"><div className="pipeline-num">{stages.replied?.count ?? 12}</div><div className="pipeline-label">Replied</div></div>
        <div className="pipeline-stage"><div className="pipeline-num">{stages.call_booked?.count ?? 0}</div><div className="pipeline-label">Call Booked</div></div>
        <div className="pipeline-stage"><div className="pipeline-num">{stages.proposal_sent?.count ?? 0}</div><div className="pipeline-label">Proposal Sent</div></div>
        <div className="pipeline-stage won"><div className="pipeline-num">{stages.closed_won?.count ?? 0}</div><div className="pipeline-label">Closed Won</div></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">Prospects by niche</div></div>
          <div className="bar-chart-row"><div className="bar-label">Fin. Advisors</div><div className="bar-track"><div className="bar-fill" style={{ width: '57%', background: 'var(--niche-fa)' }} /></div><div className="bar-value">8</div></div>
          <div className="bar-chart-row"><div className="bar-label">Trading Coaches</div><div className="bar-track"><div className="bar-fill" style={{ width: '29%', background: 'var(--niche-tc)' }} /></div><div className="bar-value">4</div></div>
          <div className="bar-chart-row"><div className="bar-label">Recruiters</div><div className="bar-track"><div className="bar-fill" style={{ width: '14%', background: 'var(--niche-rc)' }} /></div><div className="bar-value">2</div></div>
        </div>
        <div className="card">
          <div className="card-header"><div className="card-title">Top subreddits this week</div></div>
          {subreddits.slice(0, 4).map((s, i) => (
            <div key={i} className="bar-chart-row">
              <div className="bar-label">r/{s.subreddit}</div>
              <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.round((s.prospects / maxSub) * 100)}%`, background: 'var(--teal)' }} /></div>
              <div className="bar-value">{s.prospects}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
