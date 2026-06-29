import React, { useState, useEffect, useCallback } from 'react'

export default function Pods() {
  const [pods, setPods]       = useState([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState({})

  const load = useCallback(async () => {
    try {
      const r = await fetch('/api/admin/pods')
      if (r.ok) {
        const data = await r.json()
        setPods(Array.isArray(data) ? data : Object.values(data || {}))
      }
    } catch (_) {}
    finally { setLoading(false) }
  }, [])

  useEffect(() => {
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [load])

  const runNow = async (slug) => {
    setScanning(s => ({ ...s, [slug]: true }))
    try {
      await fetch(`/api/admin/pods/${slug}/run-now`, { method: 'POST' })
      setTimeout(() => { setScanning(s => ({ ...s, [slug]: false })); load() }, 5000)
    } catch (_) {
      setScanning(s => ({ ...s, [slug]: false }))
    }
  }

  const pausePod = async (slug) => {
    await fetch(`/api/admin/pods/${slug}/pause`, { method: 'POST' })
    load()
  }

  const resumePod = async (slug) => {
    await fetch(`/api/admin/pods/${slug}/resume`, { method: 'POST' })
    load()
  }

  const activePods  = pods.filter(p => !p.is_paused && !p.circuit_breaker_open)
  const errorPods   = pods.filter(p => p.circuit_breaker_open)

  const fmtTime = (ts) => {
    if (!ts) return 'Never'
    try { return new Date(ts).toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' }) }
    catch { return ts }
  }

  return (
    <div className="content">
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-label">Active pods</div>
          <div className="stat-value">{loading ? '…' : activePods.length}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total pods</div>
          <div className="stat-value">{loading ? '…' : pods.length}</div>
        </div>
        <div className={`stat-card ${errorPods.length === 0 ? 'rag-green' : ''}`}>
          <div className="stat-label">Circuit breakers</div>
          <div className="stat-value" style={{ fontSize: 14, color: errorPods.length === 0 ? 'var(--teal)' : 'var(--coral)' }}>
            {loading ? '…' : errorPods.length === 0 ? 'All closed' : `${errorPods.length} open`}
          </div>
        </div>
        <div className="stat-card rag-green">
          <div className="stat-label">Errors today</div>
          <div className="stat-value" style={{ color: 'var(--teal)' }}>0</div>
        </div>
      </div>

      {loading ? (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
          Loading pod data…
        </div>
      ) : pods.length === 0 ? (
        <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', fontSize: 13 }}>
          <div style={{ marginBottom: 12, fontSize: 15, fontWeight: 600, color: 'var(--text-primary)' }}>
            No pods yet
          </div>
          <div>Pods appear here after the first scan completes.</div>
          <div style={{ marginTop: 8 }}>Go to Command Center and click <strong>Run All Scans</strong> to start.</div>
        </div>
      ) : (
        <div className="pod-grid">
          {pods.map(pod => {
            const slug    = pod.pod_slug || pod.slug || pod.niche_slug || '—'
            const paused  = !!pod.is_paused
            const cbOpen  = !!pod.circuit_breaker_open
            const status  = cbOpen ? 'CB Open' : paused ? 'Paused' : 'Running'
            const statusCls = cbOpen ? 'error' : paused ? 'paused' : 'running'

            return (
              <div key={slug} className="pod-card">
                <div className="pod-card-header">
                  <div className="pod-name">{pod.pod_label || slug}</div>
                  <span className={`pod-status ${statusCls}`}>{status}</span>
                </div>
                <div className="pod-meta">
                  Last run: {fmtTime(pod.last_run_at || pod.last_run_created)}
                  {pod.next_run_at ? ` · Next: ${fmtTime(pod.next_run_at)}` : ''}
                </div>
                <div className="pod-meta">
                  {pod.prospects_found_today ?? pod.last_found ?? 0} prospects found
                  {pod.error_count ? ` · ${pod.error_count} errors` : ' · 0 errors'}
                </div>
                <div className="pod-actions">
                  <button
                    className="pod-btn run"
                    disabled={!!scanning[slug]}
                    onClick={() => runNow(slug)}
                  >
                    {scanning[slug] ? '…' : 'Run Now'}
                  </button>
                  {paused ? (
                    <button className="pod-btn" onClick={() => resumePod(slug)}>Resume</button>
                  ) : (
                    <button className="pod-btn" onClick={() => pausePod(slug)}>Pause</button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
