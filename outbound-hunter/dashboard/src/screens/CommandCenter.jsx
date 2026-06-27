import React, { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'

// ── Plan badge styles ─────────────────────────────────────────────────────────
const PLAN_STYLE = {
  starter: { background: 'rgba(255,255,255,0.06)', color: 'var(--text-tertiary)' },
  pro:     { background: 'rgba(29,158,117,0.15)',  color: 'var(--teal)' },
  agency:  { background: 'rgba(83,74,183,0.15)',   color: 'var(--purple)' },
}

// ── RAG dot ───────────────────────────────────────────────────────────────────
function RagDot({ color, size = 10 }) {
  return (
    <div style={{
      width: size, height: size, borderRadius: '50%',
      background: color, flexShrink: 0,
    }} />
  )
}

// ── Top KPI card ──────────────────────────────────────────────────────────────
function KPI({ label, value, sub, accent }) {
  return (
    <div className="stat-card" style={{ flex: 1 }}>
      <div className="stat-label">{label}</div>
      <div className="stat-value" style={accent ? { color: accent } : {}}>
        {value ?? '—'}
      </div>
      {sub && (
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 4 }}>{sub}</div>
      )}
    </div>
  )
}

// ── Funnel mini stat ──────────────────────────────────────────────────────────
function FunnelStat({ label, value, color }) {
  return (
    <div style={{ textAlign: 'center' }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || 'var(--text-primary)', lineHeight: 1 }}>
        {value ?? 0}
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 5, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </div>
    </div>
  )
}

// ── Client card ───────────────────────────────────────────────────────────────
function ClientCard({ tenant, onScan, scanning }) {
  const navigate = useNavigate()
  const s        = tenant.stats || {}
  const plan     = tenant.plan  || 'starter'

  const ragColor = !tenant.db_exists
    ? 'var(--coral)'
    : s.pending > 20
      ? 'var(--amber)'
      : 'var(--teal)'

  const fmtTs = (ts) => {
    if (!ts) return 'Never'
    try {
      return new Date(ts).toLocaleString('en-US', {
        month: 'short', day: 'numeric',
        hour: 'numeric', minute: '2-digit',
      })
    } catch { return ts }
  }

  return (
    <div className="card" style={{ padding: 22, display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
          <div style={{ paddingTop: 4 }}>
            <RagDot color={ragColor} size={9} />
          </div>
          <div>
            <div style={{ fontWeight: 600, fontSize: 15, color: 'var(--text-primary)', lineHeight: 1.3 }}>
              {tenant.company_name}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 3 }}>
              {tenant.slug}
            </div>
          </div>
        </div>

        <span style={{
          fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
          letterSpacing: '0.07em', padding: '3px 9px', borderRadius: 20,
          flexShrink: 0,
          ...(PLAN_STYLE[plan] || PLAN_STYLE.starter),
        }}>
          {plan}
        </span>
      </div>

      {/* Last scan row */}
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', display: 'flex', alignItems: 'center', gap: 8 }}>
        <span>Last scan: {fmtTs(tenant.last_scan)}</span>
        {!tenant.db_exists && (
          <span style={{
            fontSize: 10, color: 'var(--coral)', fontWeight: 600,
            background: 'rgba(216,90,48,0.12)', padding: '2px 7px', borderRadius: 10,
          }}>
            DB not initialized
          </span>
        )}
      </div>

      {/* Funnel */}
      <div style={{
        display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)',
        gap: 8, padding: '14px 0',
        borderTop: '1px solid var(--border)',
        borderBottom: '1px solid var(--border)',
      }}>
        <FunnelStat label="Found"   value={s.total}   color="var(--text-primary)" />
        <FunnelStat label="Queue"   value={s.pending}  color={s.pending > 0 ? 'var(--amber)' : 'var(--text-secondary)'} />
        <FunnelStat label="Sent"    value={s.sent}     color="var(--text-secondary)" />
        <FunnelStat label="Replied" value={s.replied}  color="var(--blue)" />
        <FunnelStat label="Booked"  value={s.booked}   color="var(--teal)" />
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button
          className="btn btn-primary"
          style={{ flex: 1, fontSize: 12 }}
          onClick={() => navigate('/dashboard/prospects')}
        >
          View prospects →
        </button>
        <button
          className="btn"
          style={{ fontSize: 12, minWidth: 80, opacity: scanning ? 0.5 : 1 }}
          disabled={scanning}
          onClick={() => onScan(tenant.slug)}
        >
          {scanning ? '…' : '▶ Scan'}
        </button>
      </div>
    </div>
  )
}

// ── Pod health card ───────────────────────────────────────────────────────────
function PodCard({ pod }) {
  const cb     = !!pod.circuit_breaker_open
  const paused = !!pod.is_paused
  const color  = cb ? 'var(--coral)' : paused ? 'var(--amber)' : 'var(--teal)'
  const label  = cb ? '⚠ CB open' : paused ? 'Paused' : 'Running'

  return (
    <div className="card" style={{ padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 10 }}>
      <RagDot color={color} size={8} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 12, fontWeight: 500,
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
          color: 'var(--text-primary)',
        }}>
          {pod.pod_label || pod.slug}
        </div>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>
          {label} · {pod.prospects_found_today ?? 0} found today
        </div>
      </div>
      {cb && (
        <span style={{
          fontSize: 9, fontWeight: 700, color: 'var(--coral)',
          background: 'rgba(216,90,48,0.12)', padding: '2px 6px', borderRadius: 8,
        }}>
          OPEN
        </span>
      )}
    </div>
  )
}

// ── Main screen ───────────────────────────────────────────────────────────────
export default function CommandCenter() {
  const navigate                   = useNavigate()
  const [data, setData]            = useState(null)
  const [loading, setLoading]      = useState(true)
  const [err, setErr]              = useState(null)
  const [scanning, setScanning]    = useState({})
  const [runningAll, setRunningAll] = useState(false)

  const load = useCallback(async () => {
    try {
      const r = await fetch('/api/command-center')
      if (!r.ok) throw new Error(`HTTP ${r.status}`)
      setData(await r.json())
      setErr(null)
    } catch (e) {
      setErr(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 60_000)
    return () => clearInterval(id)
  }, [load])

  const handleScan = useCallback(async (slug) => {
    setScanning(s => ({ ...s, [slug]: true }))
    try {
      await fetch('/api/command-center/run-all', { method: 'POST' })
      setTimeout(() => {
        setScanning(s => ({ ...s, [slug]: false }))
        load()
      }, 4000)
    } catch {
      setScanning(s => ({ ...s, [slug]: false }))
    }
  }, [load])

  const handleRunAll = useCallback(async () => {
    setRunningAll(true)
    try {
      await fetch('/api/command-center/run-all', { method: 'POST' })
      setTimeout(() => { setRunningAll(false); load() }, 4000)
    } catch {
      setRunningAll(false)
    }
  }, [load])

  // ── Loading ────────────────────────────────────────────────────────────────
  if (loading) return (
    <div className="content" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: 300 }}>
      <div style={{ color: 'var(--text-tertiary)', fontSize: 13 }}>Loading agency overview…</div>
    </div>
  )

  if (err) return (
    <div className="content">
      <div className="card" style={{ padding: 24 }}>
        <span style={{ color: 'var(--coral)' }}>Failed to load: {err}</span>
        <button className="btn" style={{ marginLeft: 16, fontSize: 12 }} onClick={load}>Retry</button>
      </div>
    </div>
  )

  const tenants = data?.tenants || []
  const pods    = data?.pods    || []

  // Agency-wide aggregate
  const agg = tenants.reduce((a, t) => {
    const s = t.stats || {}
    return {
      pending:    a.pending    + (s.pending    || 0),
      sent:       a.sent       + (s.sent       || 0),
      replied:    a.replied    + (s.replied    || 0),
      booked:     a.booked     + (s.booked     || 0),
      closed_won: a.closed_won + (s.closed_won || 0),
    }
  }, { pending: 0, sent: 0, replied: 0, booked: 0, closed_won: 0 })

  const podsRunning = pods.filter(p => !p.circuit_breaker_open && !p.is_paused).length
  const podAlerts   = pods.filter(p => p.circuit_breaker_open).length

  return (
    <div className="content">

      {/* ── Agency KPI row ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 28 }}>
        <KPI label="Active clients"   value={tenants.length} />
        <KPI label="In queue"         value={agg.pending}    accent={agg.pending > 0 ? 'var(--amber)' : undefined} sub="needs review" />
        <KPI label="Sent this cycle"  value={agg.sent} />
        <KPI label="Booked"           value={agg.booked}     accent="var(--teal)" />
        <KPI label="Closed won"       value={agg.closed_won} accent="var(--teal)" />
      </div>

      {/* ── Client accounts ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
          Client accounts — {tenants.length} active
        </div>
        <button
          className="btn btn-primary"
          style={{ fontSize: 11, opacity: runningAll ? 0.5 : 1 }}
          disabled={runningAll}
          onClick={handleRunAll}
        >
          {runningAll ? 'Scanning all…' : '▶ Run all scans'}
        </button>
      </div>

      {tenants.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: 'center' }}>
          <div style={{ color: 'var(--text-tertiary)', marginBottom: 16, fontSize: 14 }}>
            No clients onboarded yet
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginBottom: 20 }}>
            Run <code style={{ background: 'var(--bg-tertiary)', padding: '2px 6px', borderRadius: 4 }}>python create_admin.py</code> to create the first client tenant.
          </div>
          <button className="btn btn-primary" onClick={() => navigate('/dashboard/settings')}>
            Go to Settings →
          </button>
        </div>
      ) : (
        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))',
          gap: 16,
        }}>
          {tenants.map(t => (
            <ClientCard
              key={t.slug}
              tenant={t}
              onScan={handleScan}
              scanning={!!scanning[t.slug]}
            />
          ))}
        </div>
      )}

      {/* ── Pod health grid ────────────────────────────────────────────────── */}
      <div style={{ marginTop: 32 }}>
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          marginBottom: 12,
        }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.07em' }}>
            Pod health — {podsRunning}/{pods.length} running
            {podAlerts > 0 && (
              <span style={{ color: 'var(--coral)', marginLeft: 8 }}>
                · {podAlerts} circuit {podAlerts === 1 ? 'breaker' : 'breakers'} open
              </span>
            )}
          </div>
          <button
            className="btn"
            style={{ fontSize: 11 }}
            onClick={() => navigate('/dashboard/pods')}
          >
            Manage pods →
          </button>
        </div>

        {pods.length === 0 ? (
          <div className="card" style={{ padding: 20, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 12 }}>
            No pod data — orchestrator may not be running
          </div>
        ) : (
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: 10,
          }}>
            {pods.map(pod => (
              <PodCard key={pod.slug || pod.id} pod={pod} />
            ))}
          </div>
        )}
      </div>

      {/* ── Onboard prompt ─────────────────────────────────────────────────── */}
      <div style={{
        marginTop: 32, padding: '20px 24px',
        background: 'var(--bg-secondary)',
        border: '1px solid var(--border)',
        borderRadius: 'var(--radius-lg)',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        gap: 16,
      }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 4 }}>Add a new client</div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
            Run <code style={{ background: 'var(--bg-tertiary)', padding: '2px 6px', borderRadius: 4 }}>python create_admin.py</code> in the terminal to onboard a new tenant and initialize their database.
          </div>
        </div>
        <button className="btn" style={{ fontSize: 12, flexShrink: 0 }} onClick={() => navigate('/dashboard/pods')}>
          View pods →
        </button>
      </div>

    </div>
  )
}
