import React, { useState, useEffect, useCallback } from 'react'

const SOURCE_ICONS = {
  reddit:  { icon: '🔴', label: 'Reddit',  color: '#FF4500' },
  twitter: { icon: '🐦', label: 'Twitter', color: '#1DA1F2' },
}

const SEVERITY_COLORS = {
  high:   '#D85A30',
  medium: '#BA7517',
  low:    '#1D9E75',
}

function SourceBadge({ source, size = 12 }) {
  const s = SOURCE_ICONS[source] || { icon: '●', label: source, color: '#888' }
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      fontSize: size, fontWeight: 600,
      color: s.color,
      background: s.color + '18',
      border: `1px solid ${s.color}40`,
      borderRadius: 4, padding: '1px 5px',
    }}>
      {s.icon} {s.label}
    </span>
  )
}

function PainPointCard({ item, rank }) {
  const sev = SEVERITY_COLORS[item.severity] || SEVERITY_COLORS.low
  return (
    <div style={{
      display: 'flex', alignItems: 'flex-start', gap: 12,
      padding: '12px 14px',
      background: 'var(--bg-secondary)',
      border: `1px solid var(--border)`,
      borderLeft: `3px solid ${sev}`,
      borderRadius: 'var(--radius-md)',
    }}>
      <span style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-tertiary)', minWidth: 22, lineHeight: 1.3 }}>
        {rank}
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
          {item.topic}
          {item.cross_channel && (
            <span style={{
              marginLeft: 6, fontSize: 10, fontWeight: 700,
              color: '#7C3AED', background: '#7C3AED18',
              border: '1px solid #7C3AED40',
              borderRadius: 4, padding: '1px 5px',
              verticalAlign: 'middle',
            }}>
              CROSS-CHANNEL
            </span>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
          {item.sources.map(src => <SourceBadge key={src} source={src} />)}
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            {item.count} signal{item.count !== 1 ? 's' : ''} · intent {Math.round(item.avg_intent * 100)}%
          </span>
        </div>
      </div>
      <div style={{
        fontSize: 10, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.06em',
        color: sev, background: sev + '18', borderRadius: 4, padding: '2px 6px',
        flexShrink: 0,
      }}>
        {item.severity}
      </div>
    </div>
  )
}

export default function MarketPulseWidget({ podSlug }) {
  const [data, setData]       = useState(null)
  const [source, setSource]   = useState('all')
  const [loading, setLoading] = useState(true)
  const [copied, setCopied]   = useState(false)

  const load = useCallback(() => {
    const params = new URLSearchParams()
    if (podSlug)        params.set('pod', podSlug)
    if (source !== 'all') params.set('source', source)

    fetch(`/api/market-pulse?${params}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setData(d) })
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [podSlug, source])

  useEffect(() => {
    setLoading(true)
    load()
    const id = setInterval(load, 30_000)
    return () => clearInterval(id)
  }, [load])

  function copyHook() {
    if (!data?.daily_hook) return
    navigator.clipboard.writeText(data.daily_hook).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  const pain       = data?.pain_points || []
  const comps      = data?.competitor_mentions || []
  const bySource   = data?.by_source || {}
  const totalSigs  = data?.total_signals || 0

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Header row */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
            Market Pulse
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            {loading ? 'Loading…' : `${totalSigs} signal${totalSigs !== 1 ? 's' : ''} · last 7 days`}
          </div>
        </div>

        {/* Source filter */}
        <div style={{ display: 'flex', gap: 4 }}>
          {['all', 'reddit', 'twitter'].map(s => (
            <button
              key={s}
              onClick={() => setSource(s)}
              style={{
                fontSize: 11, fontWeight: 600, padding: '4px 10px',
                borderRadius: 6,
                border: `1px solid ${source === s ? 'var(--accent)' : 'var(--border)'}`,
                background: source === s ? 'var(--accent)' : 'transparent',
                color: source === s ? '#fff' : 'var(--text-secondary)',
                cursor: 'pointer', textTransform: 'capitalize',
              }}
            >
              {s === 'reddit' ? '🔴 Reddit' : s === 'twitter' ? '🐦 Twitter' : 'All'}
            </button>
          ))}
        </div>
      </div>

      {/* Per-source mini stats */}
      {source === 'all' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
          {Object.entries(bySource).map(([src, info]) => {
            const s = SOURCE_ICONS[src] || { icon: '●', color: '#888' }
            return (
              <div key={src} style={{
                padding: '10px 12px',
                background: 'var(--bg-secondary)',
                border: `1px solid ${s.color}30`,
                borderLeft: `3px solid ${s.color}`,
                borderRadius: 'var(--radius-md)',
              }}>
                <div style={{ fontSize: 11, color: s.color, fontWeight: 700, marginBottom: 2 }}>
                  {s.icon} {src.charAt(0).toUpperCase() + src.slice(1)}
                </div>
                <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>
                  {info.count}
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>signals</div>
              </div>
            )
          })}
        </div>
      )}

      {/* Pain points */}
      {pain.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--text-tertiary)' }}>
            Top Pain Points
          </div>
          {pain.slice(0, 5).map((item, i) => (
            <PainPointCard key={item.topic} item={item} rank={i + 1} />
          ))}
        </div>
      ) : !loading && (
        <div style={{
          textAlign: 'center', padding: '24px 16px',
          color: 'var(--text-tertiary)', fontSize: 13,
          background: 'var(--bg-secondary)',
          border: '1px dashed var(--border)',
          borderRadius: 'var(--radius-md)',
        }}>
          No signals yet — run a pod scan to populate this view.
        </div>
      )}

      {/* Daily outreach hook */}
      {data?.daily_hook && (
        <div style={{
          padding: '14px 16px',
          background: 'linear-gradient(135deg, #7C3AED12, #2563EB08)',
          border: '1px solid #7C3AED30',
          borderRadius: 'var(--radius-md)',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
            <span style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.07em', color: '#7C3AED' }}>
              Today's Cross-Channel Hook
            </span>
            <button
              onClick={copyHook}
              style={{
                fontSize: 11, fontWeight: 600,
                padding: '3px 8px', borderRadius: 5,
                border: '1px solid #7C3AED40',
                background: copied ? '#7C3AED' : 'transparent',
                color: copied ? '#fff' : '#7C3AED',
                cursor: 'pointer',
              }}
            >
              {copied ? 'Copied!' : 'Copy'}
            </button>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, fontStyle: 'italic' }}>
            "{data.daily_hook}"
          </p>
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-tertiary)' }}>
            Generated from{' '}
            {Object.entries(bySource)
              .filter(([, v]) => v.count > 0)
              .map(([src]) => `${SOURCE_ICONS[src]?.icon} ${src}`)
              .join(' + ')
            }{' '}signals
          </div>
        </div>
      )}

      {/* Competitor mentions */}
      {comps.length > 0 && (
        <div>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: 'uppercase', letterSpacing: '.07em', color: 'var(--text-tertiary)', marginBottom: 8 }}>
            Competitor Mentions
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {comps.map(c => (
              <span key={c.name} style={{
                display: 'inline-flex', alignItems: 'center', gap: 4,
                fontSize: 12, fontWeight: 600,
                padding: '3px 8px',
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border)',
                borderRadius: 20,
                color: 'var(--text-secondary)',
              }}>
                {c.name}
                <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>
                  ×{c.mentions}
                </span>
                {c.sources.map(s => (
                  <span key={s} title={s} style={{ fontSize: 10 }}>
                    {SOURCE_ICONS[s]?.icon}
                  </span>
                ))}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
