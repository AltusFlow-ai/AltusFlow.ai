import React, { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

const OUTCOMES = [
  { key: 'booked',    label: '📅 Booked',    color: 'var(--teal)' },
  { key: 'callback',  label: '◌ Callback',   color: '#BA7517' },
  { key: 'voicemail', label: '📭 Voicemail',  color: 'var(--text-tertiary)' },
  { key: 'no_answer', label: '✗ No answer',  color: 'var(--text-tertiary)' },
]

function fmt(s) {
  return `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export default function LiveCall() {
  const navigate = useNavigate()
  const [transcript,  setTranscript]  = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [prospect,    setProspect]    = useState({})
  const [elapsed,     setElapsed]     = useState(0)
  const [outcome,     setOutcome]     = useState(null)
  const [saving,      setSaving]      = useState(false)
  const [noKey,       setNoKey]       = useState(false)
  const txRef   = useRef(null)
  const startTs = useRef(Date.now())

  // ── SSE connection ──────────────────────────────────────────────────────────
  useEffect(() => {
    const es = new EventSource('/api/calls/live-stream')

    es.addEventListener('init', e => {
      const d = JSON.parse(e.data)
      setTranscript(d.transcript  || [])
      setSuggestions(d.suggestions || [])
      setProspect(d.prospect || {})
      if (d.started_at) startTs.current = d.started_at * 1000
      if (!d.active) {
        // No active call — go back
        navigate('/dashboard/calls')
      }
    })

    es.addEventListener('call_started', e => {
      const d = JSON.parse(e.data)
      setTranscript([])
      setSuggestions([])
      startTs.current = Date.now()
    })

    es.addEventListener('transcript', e => {
      const line = JSON.parse(e.data)
      setTranscript(prev => [...prev.filter(l => !(!l.final && l.speaker === line.speaker)), line].slice(-120))
    })

    es.addEventListener('partial', e => {
      const line = JSON.parse(e.data)
      setTranscript(prev => {
        const last = prev[prev.length - 1]
        if (last && !last.final && last.speaker === line.speaker) {
          return [...prev.slice(0, -1), { ...line, final: false }]
        }
        return [...prev, { ...line, final: false }].slice(-120)
      })
    })

    es.addEventListener('suggestion', e => {
      const s = JSON.parse(e.data)
      setSuggestions(prev => [s, ...prev].slice(0, 5))
    })

    es.addEventListener('call_ended', () => {
      setSaving(true)
      setTimeout(() => navigate('/dashboard/calls'), 3000)
    })

    es.onerror = () => {
      setNoKey(true)
    }

    return () => es.close()
  }, [navigate])

  // ── Timer ───────────────────────────────────────────────────────────────────
  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTs.current) / 1000))
    }, 1000)
    return () => clearInterval(id)
  }, [])

  // ── Auto-scroll transcript ──────────────────────────────────────────────────
  useEffect(() => {
    if (txRef.current) {
      txRef.current.scrollTop = txRef.current.scrollHeight
    }
  }, [transcript])

  // ── Detected signals (last 10 YOU / THEM lines) ────────────────────────────
  const signals = transcript
    .filter(l => l.final && l.speaker === 'THEM')
    .slice(-6)
    .map(l => l.text)

  if (saving) {
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
        height: '100vh', background: 'var(--bg)',
      }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>💾</div>
        <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 8 }}>Saving call…</div>
        <div style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>Transcript + learnings saved. Returning to Calls.</div>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: 'var(--bg)', overflow: 'hidden' }}>

      {/* Pulse animation */}
      <style>{`
        @keyframes pulse-live {
          0%   { box-shadow: 0 0 0 0 rgba(239,68,68,0.6); }
          70%  { box-shadow: 0 0 0 8px rgba(239,68,68,0); }
          100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
        }
        .tx-line { animation: fadeInTx 0.15s ease; }
        @keyframes fadeInTx { from { opacity:0; transform:translateY(4px) } to { opacity:1; transform:none } }
      `}</style>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '14px 20px', borderBottom: '1px solid var(--border)',
        background: 'rgba(10,10,10,0.95)', backdropFilter: 'blur(10px)',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <div style={{
            width: 10, height: 10, borderRadius: '50%', background: '#ef4444',
            animation: 'pulse-live 1.5s infinite',
            flexShrink: 0,
          }} />
          <span style={{ fontWeight: 700, fontSize: 13, color: '#ef4444', letterSpacing: '0.08em' }}>LIVE</span>
          <span style={{ fontWeight: 700, fontSize: 16, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
            {fmt(elapsed)}
          </span>
          {prospect.name && (
            <>
              <span style={{ color: 'var(--border)' }}>·</span>
              <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>{prospect.name}</span>
              {prospect.niche && (
                <span style={{ fontSize: 10, fontWeight: 700, color: '#534AB7', background: 'rgba(83,74,183,0.15)', borderRadius: 3, padding: '2px 7px' }}>
                  {prospect.niche}
                </span>
              )}
            </>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>🧠 Hermes listening</span>
        </div>
      </div>

      {/* ── Main two-column layout ──────────────────────────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 320px', flex: 1, overflow: 'hidden' }}>

        {/* Transcript panel */}
        <div ref={txRef} style={{
          overflowY: 'auto', padding: '20px 24px',
          borderRight: '1px solid var(--border)',
          display: 'flex', flexDirection: 'column', gap: 2,
        }}>
          {transcript.length === 0 && (
            <div style={{ color: 'var(--text-tertiary)', fontSize: 13, marginTop: 40, textAlign: 'center' }}>
              {noKey
                ? '⚠ Connect Deepgram in Connections to enable live transcription'
                : '⏳ Waiting for speech…'}
            </div>
          )}
          {transcript.map((line, i) => {
            const isYou = line.speaker === 'YOU'
            return (
              <div key={i} className="tx-line" style={{
                display: 'flex', gap: 14, alignItems: 'flex-start',
                padding: '6px 0',
                opacity: line.final ? 1 : 0.6,
              }}>
                <span style={{
                  fontSize: 10, fontWeight: 800, width: 38, flexShrink: 0,
                  color: isYou ? 'var(--teal)' : '#9ca3af',
                  marginTop: 3, textAlign: 'right', letterSpacing: '0.04em',
                }}>
                  {line.speaker}
                </span>
                <span style={{
                  fontSize: 14, color: isYou ? 'var(--text-primary)' : '#d1d5db',
                  lineHeight: 1.6, fontStyle: line.final ? 'normal' : 'italic',
                }}>
                  {line.text}
                </span>
              </div>
            )
          })}
        </div>

        {/* Hermes panel */}
        <div style={{
          overflowY: 'auto', padding: '16px',
          display: 'flex', flexDirection: 'column', gap: 14,
          background: 'var(--bg-primary)',
        }}>

          {/* Suggestion */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#534AB7', letterSpacing: '0.08em', marginBottom: 8 }}>
              ⚡ HERMES SUGGESTS
            </div>
            {suggestions.length === 0 ? (
              <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontStyle: 'italic', lineHeight: 1.5 }}>
                Listening… suggestion will appear after a few exchanges.
              </div>
            ) : (
              <div style={{
                background: 'rgba(83,74,183,0.1)', border: '1px solid rgba(83,74,183,0.25)',
                borderRadius: 8, padding: '12px 14px',
                fontSize: 13, color: '#c4c4e8', lineHeight: 1.6,
              }}>
                {suggestions[0].text}
              </div>
            )}
          </div>

          {/* Previous suggestions */}
          {suggestions.length > 1 && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 6 }}>
                EARLIER
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {suggestions.slice(1).map((s, i) => (
                  <div key={i} style={{
                    fontSize: 11, color: 'var(--text-tertiary)', padding: '7px 10px',
                    background: 'var(--bg-secondary)', borderRadius: 6, lineHeight: 1.5,
                  }}>
                    {s.text}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Signals heard */}
          {signals.length > 0 && (
            <div>
              <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14 }} />
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 8 }}>
                📌 SIGNALS HEARD
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
                {signals.map((s, i) => (
                  <div key={i} style={{
                    fontSize: 11, color: 'var(--text-secondary)', padding: '5px 9px',
                    background: 'var(--bg-secondary)', borderRadius: 5,
                    borderLeft: '3px solid var(--teal)', lineHeight: 1.4,
                  }}>
                    {s.length > 80 ? s.slice(0, 80) + '…' : s}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Outcome selection */}
          <div style={{ borderTop: '1px solid var(--border)', paddingTop: 14, marginTop: 'auto' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 8 }}>
              OUTCOME
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 6 }}>
              {OUTCOMES.map(o => (
                <button
                  key={o.key}
                  onClick={() => setOutcome(o.key)}
                  style={{
                    padding: '7px 8px', borderRadius: 6, fontSize: 11, fontWeight: 600,
                    border: `1px solid ${outcome === o.key ? o.color : 'var(--border)'}`,
                    background: outcome === o.key ? `${o.color}18` : 'transparent',
                    color: outcome === o.key ? o.color : 'var(--text-secondary)',
                    cursor: 'pointer',
                  }}
                >
                  {o.label}
                </button>
              ))}
            </div>
          </div>

        </div>
      </div>

      {/* ── Footer ─────────────────────────────────────────────────────────── */}
      <div style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '12px 20px', borderTop: '1px solid var(--border)',
        background: 'rgba(10,10,10,0.95)', flexShrink: 0,
      }}>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          {transcript.filter(l => l.final).length} lines · {transcript.filter(l => l.final && l.speaker === 'THEM').length} from them
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <button
            onClick={() => navigate('/dashboard/calls')}
            style={{
              padding: '7px 18px', borderRadius: 7, fontSize: 12, fontWeight: 600,
              border: '1px solid var(--border)', background: 'transparent',
              color: 'var(--text-secondary)', cursor: 'pointer',
            }}
          >
            Back to calls
          </button>
          <button
            onClick={() => { setSaving(true); setTimeout(() => navigate('/dashboard/calls'), 2500) }}
            style={{
              padding: '7px 20px', borderRadius: 7, fontSize: 12, fontWeight: 600,
              border: 'none', background: 'var(--teal)', color: '#fff', cursor: 'pointer',
            }}
          >
            💾 Save + End
          </button>
        </div>
      </div>

    </div>
  )
}
