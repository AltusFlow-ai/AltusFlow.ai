/**
 * NicheDelivery.jsx — Per-niche client delivery report.
 *
 * Shows lead flow per pod/niche, which client owns each pod,
 * and week-over-week delivery stats. Reps use this to package
 * and send weekly lead batches to each coaching client.
 */

import React, { useState, useEffect, useCallback } from 'react'
import { NICHE_COLORS } from '../constants.js'

const POD_META = {
  'daytrading':             { icon: '📈', client: 'Day Trading Coach',    platforms: ['reddit', 'twitter'] },
  'futures':                { icon: '⚡', client: 'Futures Coach',         platforms: ['reddit', 'twitter'] },
  'swing-trading':          { icon: '🌊', client: 'Swing Trading Coach',   platforms: ['reddit', 'twitter'] },
  'crypto':                 { icon: '₿',  client: 'Crypto Coach',          platforms: ['twitter', 'reddit'] },
  'options':                { icon: '🎯', client: 'Options Coach',          platforms: ['reddit', 'twitter'] },
  'financial-advisors':     { icon: '💼', client: 'FA Lead Gen Client',    platforms: ['reddit', 'linkedin', 'twitter'] },
  'trading-coaches':        { icon: '🏆', client: 'Trading Coach Network', platforms: ['reddit', 'twitter'] },
  'business-coaches':       { icon: '📊', client: 'Business Coach Client', platforms: ['linkedin', 'reddit'] },
  'commercial-real-estate': { icon: '🏢', client: 'CRE Broker Client',     platforms: ['linkedin', 'reddit'] },
  'msps':                   { icon: '🖥', client: 'MSP Client',            platforms: ['reddit', 'linkedin'] },
  'recruiters':             { icon: '🔍', client: 'Recruiting Client',     platforms: ['linkedin', 'reddit'] },
}

const TRADING_PODS = ['daytrading', 'futures', 'swing-trading', 'crypto', 'options']

const DEMO_STATS = TRADING_PODS.map((slug, i) => ({
  pod_slug:          slug,
  label:             NICHE_COLORS[slug]?.label || slug,
  leads_this_week:   [14, 9, 11, 22, 7][i],
  leads_last_week:   [10, 12, 8, 18, 5][i],
  total_leads:       [87, 61, 73, 144, 38][i],
  qualified:         [31, 22, 28, 51, 14][i],
  sent_to_client:    [24, 18, 21, 39, 10][i],
  last_delivery:     new Date(Date.now() - [2,5,3,1,7][i] * 86400000).toISOString(),
  top_platform:      ['reddit','twitter','reddit','twitter','reddit'][i],
  hot_signal:        [
    'blown account day trading',
    'failed prop firm eval',
    'breakout failed swing',
    'got liquidated crypto',
    'IV crush destroyed trade',
  ][i],
}))

function PlatformPill({ name }) {
  const colors = {
    reddit:   { bg: 'rgba(255,69,0,0.12)',   color: '#FF6314', label: 'Reddit' },
    twitter:  { bg: 'rgba(29,155,240,0.12)', color: '#1D9BF0', label: 'X / Twitter' },
    linkedin: { bg: 'rgba(0,119,181,0.12)',  color: '#0077B5', label: 'LinkedIn' },
    discord:  { bg: 'rgba(88,101,242,0.12)', color: '#5865F2', label: 'Discord' },
  }
  const c = colors[name] || { bg: 'rgba(83,74,183,0.12)', color: '#8B82D4', label: name }
  return (
    <span style={{
      fontSize: 10, fontWeight: 600, padding: '2px 7px', borderRadius: 10,
      background: c.bg, color: c.color,
    }}>
      {c.label}
    </span>
  )
}

function DeliveryCard({ stat, onPackage }) {
  const [packaging, setPackaging] = useState(false)
  const [packaged,  setPackaged]  = useState(false)
  const nc = NICHE_COLORS[stat.pod_slug] || { color: '#534AB7', bg: 'rgba(83,74,183,0.15)', label: stat.label }
  const meta = POD_META[stat.pod_slug] || {}
  const trend = stat.leads_this_week - stat.leads_last_week
  const trendUp = trend > 0

  const fmtDate = (iso) => {
    if (!iso) return '—'
    try {
      const d = new Date(iso)
      const now = new Date()
      const diff = Math.floor((now - d) / 86400000)
      if (diff === 0) return 'Today'
      if (diff === 1) return 'Yesterday'
      return `${diff}d ago`
    } catch { return '—' }
  }

  const handlePackage = async () => {
    setPackaging(true)
    try {
      await fetch(`/api/delivery/package`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pod_slug: stat.pod_slug }),
      })
      setPackaged(true)
      onPackage?.(stat.pod_slug)
      setTimeout(() => setPackaged(false), 3000)
    } catch {}
    setPackaging(false)
  }

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderLeft: `3px solid ${nc.color}`,
      borderRadius: 10, padding: 20,
      display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <span style={{ fontSize: 22 }}>{meta.icon || '📡'}</span>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              {nc.label}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
              → {meta.client || 'Unassigned'}
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {(meta.platforms || []).map(p => <PlatformPill key={p} name={p} />)}
        </div>
      </div>

      {/* Stats row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
        {[
          { label: 'This week',     val: stat.leads_this_week, highlight: true },
          { label: 'Last week',     val: stat.leads_last_week, highlight: false },
          { label: 'Total leads',   val: stat.total_leads,     highlight: false },
          { label: 'Sent to client',val: stat.sent_to_client,  highlight: false },
        ].map(s => (
          <div key={s.label} style={{
            background: s.highlight ? nc.bg : 'var(--bg)',
            border: `1px solid ${s.highlight ? nc.color + '40' : 'var(--border)'}`,
            borderRadius: 8, padding: '10px 12px', textAlign: 'center',
          }}>
            <div style={{
              fontSize: 22, fontWeight: 700, lineHeight: 1,
              color: s.highlight ? nc.color : 'var(--text-primary)',
            }}>
              {s.val}
            </div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 4, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
              {s.label}
            </div>
          </div>
        ))}
      </div>

      {/* Trend + hot signal */}
      <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{
          fontSize: 11, fontWeight: 700, padding: '3px 9px', borderRadius: 20,
          background: trendUp ? 'rgba(29,158,117,0.12)' : 'rgba(216,90,48,0.12)',
          color: trendUp ? '#1D9E75' : '#D85A30',
          border: `1px solid ${trendUp ? 'rgba(29,158,117,0.3)' : 'rgba(216,90,48,0.3)'}`,
        }}>
          {trendUp ? `▲ +${trend}` : `▼ ${trend}`} vs last week
        </span>

        {stat.hot_signal && (
          <span style={{
            fontSize: 10, color: '#BA7517', fontStyle: 'italic',
          }}>
            🔥 Top signal: "{stat.hot_signal}"
          </span>
        )}

        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)' }}>
          Last delivery: {fmtDate(stat.last_delivery)}
        </span>
      </div>

      {/* Actions */}
      <div style={{
        display: 'flex', gap: 8, borderTop: '1px solid var(--border)', paddingTop: 12,
      }}>
        <button
          onClick={handlePackage}
          disabled={packaging}
          style={{
            background: packaged ? 'rgba(29,158,117,0.15)' : nc.bg,
            color: packaged ? '#1D9E75' : nc.color,
            border: `1px solid ${packaged ? 'rgba(29,158,117,0.4)' : nc.color + '50'}`,
            padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 700,
            cursor: packaging ? 'wait' : 'pointer', transition: 'all 0.15s',
          }}
        >
          {packaged ? '✓ Packaged!' : packaging ? '⏳ Packaging…' : '📦 Package leads'}
        </button>

        <button
          onClick={() => window.open(`/api/delivery/export?pod_slug=${stat.pod_slug}&format=csv`, '_blank')}
          style={{
            background: 'var(--bg)', color: 'var(--text-secondary)',
            border: '1px solid var(--border)',
            padding: '7px 14px', borderRadius: 6, fontSize: 12,
            cursor: 'pointer',
          }}
        >
          ⬇ Export CSV
        </button>

        <button
          onClick={() => window.open(`/dashboard/prospects?pod=${stat.pod_slug}`, '_self')}
          style={{
            background: 'transparent', color: 'var(--text-tertiary)',
            border: '1px solid var(--border)',
            padding: '7px 14px', borderRadius: 6, fontSize: 12,
            cursor: 'pointer',
          }}
        >
          View leads →
        </button>
      </div>
    </div>
  )
}

function SummaryBar({ stats }) {
  const totalWeek  = stats.reduce((s, r) => s + r.leads_this_week, 0)
  const totalAll   = stats.reduce((s, r) => s + r.total_leads, 0)
  const totalSent  = stats.reduce((s, r) => s + r.sent_to_client, 0)
  const qualified  = stats.reduce((s, r) => s + r.qualified, 0)

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 10, marginBottom: 24 }}>
      {[
        { label: 'Leads this week', val: totalWeek, color: '#1D9E75'  },
        { label: 'Qualified',       val: qualified,  color: '#534AB7' },
        { label: 'Sent to clients', val: totalSent,  color: '#E8A020' },
        { label: 'Total in system', val: totalAll,   color: 'var(--text-primary)' },
      ].map(s => (
        <div key={s.label} style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 10, padding: '14px 18px',
        }}>
          <div style={{ fontSize: 26, fontWeight: 700, color: s.color, lineHeight: 1 }}>{s.val}</div>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.04em' }}>
            {s.label}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function NicheDelivery() {
  const [stats,   setStats]   = useState([])
  const [loading, setLoading] = useState(true)
  const [podFilter, setPodFilter] = useState('trading')

  const loadStats = useCallback(async () => {
    try {
      const r = await fetch('/api/delivery/stats')
      if (r.ok) {
        const d = await r.json()
        if (Array.isArray(d) && d.length > 0) { setStats(d); setLoading(false); return }
      }
    } catch {}
    setStats(DEMO_STATS)
    setLoading(false)
  }, [])

  useEffect(() => { loadStats() }, [loadStats])

  const allPods     = [...new Set(stats.map(s => s.pod_slug))]
  const tradingPods = stats.filter(s => TRADING_PODS.includes(s.pod_slug))
  const otherPods   = stats.filter(s => !TRADING_PODS.includes(s.pod_slug))
  const shown       = podFilter === 'trading' ? tradingPods : podFilter === 'other' ? otherPods : stats

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <div className="demo-label" style={{ marginBottom: 20 }}>
        📦 NICHE DELIVERY — weekly lead packages per pod
      </div>

      {loading ? (
        <div style={{ color: 'var(--text-tertiary)', fontSize: 13, padding: 20 }}>Loading delivery stats…</div>
      ) : (
        <>
          <SummaryBar stats={stats} />

          {/* Pod filter */}
          <div style={{ display: 'flex', gap: 8, marginBottom: 20 }}>
            {[
              { key: 'trading', label: '📈 Trading pods' },
              { key: 'other',   label: '💼 Other pods' },
              { key: 'all',     label: 'All pods' },
            ].map(f => (
              <button
                key={f.key}
                onClick={() => setPodFilter(f.key)}
                style={{
                  background: podFilter === f.key ? 'rgba(83,74,183,0.15)' : 'var(--bg)',
                  color: podFilter === f.key ? '#8B82D4' : 'var(--text-secondary)',
                  border: `1px solid ${podFilter === f.key ? 'rgba(83,74,183,0.4)' : 'var(--border)'}`,
                  padding: '6px 14px', borderRadius: 6, fontSize: 12,
                  fontWeight: podFilter === f.key ? 700 : 400,
                  cursor: 'pointer',
                }}
              >
                {f.label}
              </button>
            ))}
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            {shown.map(stat => (
              <DeliveryCard key={stat.pod_slug} stat={stat} onPackage={loadStats} />
            ))}
            {shown.length === 0 && (
              <div style={{ color: 'var(--text-tertiary)', fontSize: 13, padding: '20px 0' }}>
                No pods in this group yet.
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
