import React, { useState, useEffect } from 'react'

export default function Budget() {
  const [summary, setSummary]     = useState({ spent_month: 12, revenue_month: 0, roi: null, cac: 0.86 })
  const [transactions, setTxns]   = useState([
    { date: 'Jun 21', platform: 'Claude API',  description: '14 prospect drafts · altusflow-own pod', amount: -0.04 },
    { date: 'Jun 20', platform: 'Claude API',  description: '11 prospect drafts · altusflow-own pod', amount: -0.03 },
    { date: 'Jun 1',  platform: 'DocuSign',    description: 'Monthly personal plan',                  amount: -10.00 },
  ])

  useEffect(() => {
    fetch('/api/budget/summary').then(r => r.ok ? r.json() : null).then(d => { if (d) setSummary(d) }).catch(() => {})
    fetch('/api/budget/transactions').then(r => r.ok ? r.json() : null).then(d => { if (d) setTxns(d) }).catch(() => {})
  }, [])

  return (
    <div className="content">
      <div className="demo-label">💰 BUDGET SCREEN — Every marketing dollar tracked</div>

      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Spent this month</div>
          <div className="stat-value">${(summary.spent_month ?? 12).toFixed(2)}</div>
          <div className="stat-delta">Claude API only</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Revenue in</div>
          <div className="stat-value">${(summary.revenue_month ?? 0).toFixed(2)}</div>
          <div className="stat-delta">First client pending</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">ROI</div>
          <div className="stat-value">—</div>
          <div className="stat-delta">Pending first close</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">CAC so far</div>
          <div className="stat-value">${(summary.cac ?? 0.86).toFixed(2)}</div>
          <div className="stat-delta up">Very low</div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-title">Transaction ledger</div>
          <button className="btn btn-sm">Export CSV</button>
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: '80px 100px 1fr 70px', gap: 8, fontSize: 10, color: 'var(--text-tertiary)', padding: '4px 0', borderBottom: '0.5px solid var(--border)', marginBottom: 6 }}>
          <span>Date</span><span>Platform</span><span>Description</span><span style={{ textAlign: 'right' }}>Amount</span>
        </div>
        {transactions.map((t, i) => (
          <div key={i} style={{ display: 'grid', gridTemplateColumns: '80px 100px 1fr 70px', gap: 8, fontSize: 11, color: 'var(--text-secondary)', padding: '5px 0', borderBottom: '0.5px solid var(--border)' }}>
            <span>{t.date || t.created_at?.slice(0, 10)}</span>
            <span>{t.platform}</span>
            <span>{t.description}</span>
            <span style={{ textAlign: 'right', color: 'var(--coral)' }}>
              {typeof t.amount === 'number' ? (t.amount < 0 ? `-$${Math.abs(t.amount).toFixed(2)}` : `+$${t.amount.toFixed(2)}`) : t.amount}
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}
