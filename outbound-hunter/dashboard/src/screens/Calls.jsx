import React, { useState, useRef, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useApp } from '../App.jsx'
import { ALL_CALLS, NICHE_KEY } from '../data/calls.js'

const OUTCOME_STYLE = {
  booked:    { color: 'var(--teal)',    bg: 'rgba(29,158,117,0.12)',  label: '● Booked' },
  callback:  { color: '#BA7517',        bg: 'rgba(186,117,23,0.12)',  label: '◌ Callback' },
  no_answer: { color: 'var(--text-tertiary)', bg: 'var(--bg-primary)', label: '– Voicemail' },
  uploaded:  { color: '#534AB7',        bg: 'rgba(83,74,183,0.12)',   label: '⬆ Uploaded' },
}

const NICHE_BADGE = {
  'Financial Advisor': { color: '#1D9E75', bg: 'rgba(29,158,117,0.12)' },
  'Trading Coach':     { color: '#534AB7', bg: 'rgba(83,74,183,0.12)' },
  'Recruiter':         { color: '#BA7517', bg: 'rgba(186,117,23,0.12)' },
}

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function CallCard({ call, active, onClick }) {
  const os = OUTCOME_STYLE[call.outcome] || OUTCOME_STYLE.uploaded
  const nb = NICHE_BADGE[call.niche]
  return (
    <div
      onClick={onClick}
      style={{
        padding: '11px 13px', borderRadius: 8, cursor: 'pointer', marginBottom: 6,
        background: active ? 'var(--bg-secondary)' : 'transparent',
        border: `1px solid ${active ? 'var(--teal)' : 'var(--border)'}`,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 4 }}>
        <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-primary)' }}>
          {call.name !== 'Unknown' ? call.name : call.caller}
        </div>
        <span style={{ fontSize: 9, fontWeight: 600, color: os.color, background: os.bg, borderRadius: 4, padding: '2px 6px' }}>
          {os.label}
        </span>
      </div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        {nb && (
          <span style={{ fontSize: 9, fontWeight: 600, color: nb.color, background: nb.bg, borderRadius: 3, padding: '1px 5px' }}>
            {call.niche}
          </span>
        )}
        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
          {call.duration} · {timeAgo(call.date)}
          {call.source === 'uploaded' && ' · Uploaded'}
        </span>
      </div>
    </div>
  )
}

export default function Calls() {
  const { activeNiche } = useApp()
  const navigate = useNavigate()
  const location = useLocation()
  const [calls, setCalls] = useState([])
  const [active, setActive] = useState(null)
  const [tab, setTab] = useState('summary')

  // Auto-select call when navigated from Journey
  useEffect(() => {
    const callId = location.state?.callId
    if (!callId) return
    const match = ALL_CALLS.find(c => c.id === callId)
    if (match) { setActive(match); setTab('summary') }
  }, [location.state])
  const [uploading, setUploading] = useState(false)
  const [uploadMsg, setUploadMsg] = useState('')
  const [simulating, setSimulating] = useState(false)
  const fileRef = useRef(null)

  async function handleSimulate() {
    setSimulating(true)
    try {
      const r = await fetch('/api/calls/simulate', { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        navigate('/dashboard/calls/live')
      } else {
        alert(d.error || 'Could not start simulation')
        setSimulating(false)
      }
    } catch {
      alert('Network error — is Flask running?')
      setSimulating(false)
    }
  }

  // Filter by active niche
  const filtered = activeNiche === 'all'
    ? calls
    : calls.filter(c => c.nicheKey === activeNiche || (!c.nicheKey && activeNiche === 'all'))

  const displayed = activeNiche === 'all' ? calls : filtered
  const booked    = displayed.filter(c => c.outcome === 'booked').length
  const callbacks = displayed.filter(c => c.outcome === 'callback').length

  async function handleUpload(e) {
    const file = e.target.files[0]
    if (!file) return
    setUploading(true)
    setUploadMsg('')
    const fd = new FormData()
    fd.append('file', file)
    try {
      const r = await fetch('/api/calls/upload', { method: 'POST', body: fd })
      const d = await r.json()
      if (d.ok && d.call) {
        const newCall = {
          id: Date.now(),
          caller: `Uploaded: ${d.call.filename || file.name}`,
          name: d.call.name || 'Unknown',
          niche: d.call.niche || 'Unknown',
          nicheKey: d.call.nicheKey || NICHE_KEY[d.call.niche] || null,
          date: new Date().toISOString(),
          duration: d.call.duration || '—',
          outcome: d.call.outcome || 'uploaded',
          outcomeLabel: d.call.outcome === 'booked' ? 'Booked' : 'Uploaded',
          source: 'uploaded',
          summary: d.call.summary || `Uploaded: ${file.name}`,
          transcript: d.call.transcript || [],
          learnings: d.call.learnings || [],
        }
        setCalls(prev => [newCall, ...prev])
        setActive(newCall)
        setTab('summary')
        setUploadMsg(`Transcribed + parsed · ${d.call.niche || 'Unknown niche'}`)
      } else {
        setUploadMsg(d.error || 'Upload failed')
      }
    } catch {
      setUploadMsg('Network error — is Flask running?')
    }
    setUploading(false)
    e.target.value = ''
  }

  return (
    <div className="content">
      <div className="stat-grid" style={{ marginBottom: 14 }}>
        <div className="stat-card rag-green"><div className="stat-label">Calls{activeNiche !== 'all' ? ` · ${activeNiche.toUpperCase()}` : ' this week'}</div><div className="stat-value">{displayed.length}</div></div>
        <div className="stat-card rag-green"><div className="stat-label">Booked</div><div className="stat-value">{booked}</div><div className="stat-delta up">from calls</div></div>
        <div className="stat-card rag-amber"><div className="stat-label">Callbacks</div><div className="stat-value">{callbacks}</div></div>
        <div className="stat-card"><div className="stat-label">Avg duration</div><div className="stat-value">5:18</div></div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '260px 1fr', gap: 12 }}>
        {/* Call list */}
        <div>
          {/* Simulate + Upload buttons */}
          <div style={{ marginBottom: 10, display: 'flex', flexDirection: 'column', gap: 6 }}>
            <button
              onClick={handleSimulate}
              disabled={simulating}
              style={{
                width: '100%', padding: '8px 0', borderRadius: 7, fontSize: 11, fontWeight: 700,
                border: 'none', background: simulating ? 'var(--border)' : '#ef4444',
                color: '#fff', cursor: simulating ? 'default' : 'pointer',
              }}
            >
              {simulating ? '⏳ Starting…' : '▶ Simulate Live Call'}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".mp3,.mp4,.m4a,.wav,.mov,.webm,.ogg,.aac"
              style={{ display: 'none' }}
              onChange={handleUpload}
            />
            <button
              onClick={() => fileRef.current?.click()}
              disabled={uploading}
              style={{
                width: '100%', padding: '7px 0', borderRadius: 7, fontSize: 11, fontWeight: 600,
                border: '1px dashed var(--border)', background: 'transparent',
                color: uploading ? 'var(--text-tertiary)' : 'var(--teal)', cursor: uploading ? 'default' : 'pointer',
              }}
            >
              {uploading ? '⏳ Transcribing…' : '⬆ Upload Recording'}
            </button>
            {uploadMsg && (
              <div style={{ fontSize: 10, color: uploadMsg.includes('error') || uploadMsg.includes('fail') ? 'var(--coral)' : 'var(--teal)', lineHeight: 1.4 }}>
                {uploadMsg}
              </div>
            )}
          </div>

          {displayed.length === 0 ? (
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)', padding: '16px 0', textAlign: 'center' }}>
              No calls for this niche yet
            </div>
          ) : (
            displayed.map(c => (
              <CallCard key={c.id} call={c} active={active?.id === c.id} onClick={() => { setActive(c); setTab('summary') }} />
            ))
          )}
        </div>

        {/* Detail panel */}
        {active && (
          <div className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: 12, gap: 12 }}>
              <div>
                <div style={{ fontWeight: 700, fontSize: 14 }}>{active.name !== 'Unknown' ? active.name : active.caller}</div>
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
                  {active.source === 'uploaded' ? active.caller : active.caller}
                  {' · '}{active.niche}{' · '}{active.duration}{' · '}{timeAgo(active.date)}
                </div>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
                <span style={{ fontSize: 11, fontWeight: 600, color: (OUTCOME_STYLE[active.outcome] || OUTCOME_STYLE.uploaded).color, background: (OUTCOME_STYLE[active.outcome] || OUTCOME_STYLE.uploaded).bg, borderRadius: 5, padding: '3px 10px' }}>
                  {active.outcomeLabel}
                </span>
                {active.source === 'uploaded' && (
                  <span style={{ fontSize: 9, color: '#534AB7', background: 'rgba(83,74,183,0.1)', borderRadius: 3, padding: '1px 6px', fontWeight: 600 }}>
                    UPLOADED RECORDING
                  </span>
                )}
              </div>
            </div>

            <div style={{ display: 'flex', gap: 8, marginBottom: 12 }}>
              {['summary', 'transcript', 'learnings'].map(t => (
                <button key={t} onClick={() => setTab(t)} style={{
                  fontSize: 11, padding: '4px 12px', borderRadius: 6, border: '1px solid var(--border)',
                  background: tab === t ? 'var(--teal)' : 'transparent',
                  color: tab === t ? '#fff' : 'var(--text-secondary)', cursor: 'pointer',
                }}>
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {tab === 'summary' && (
              <p style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>{active.summary}</p>
            )}

            {tab === 'transcript' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {(active.transcript || []).length === 0 ? (
                  <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>No transcript available.</p>
                ) : (active.transcript || []).map((line, i) => (
                  <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
                    <span style={{
                      fontSize: 10, fontWeight: 700, flexShrink: 0, marginTop: 2,
                      color: line.speaker === 'Hermes' ? 'var(--teal)' : 'var(--text-tertiary)',
                      width: 60, textAlign: 'right',
                    }}>
                      {line.speaker}
                    </span>
                    <p style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, margin: 0 }}>{line.text}</p>
                  </div>
                ))}
              </div>
            )}

            {tab === 'learnings' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                {(active.learnings || []).length === 0 ? (
                  <p style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>No learnings parsed yet.</p>
                ) : (active.learnings || []).map((l, i) => (
                  <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '6px 10px', background: 'var(--bg-primary)', borderRadius: 6, borderLeft: '3px solid var(--teal)' }}>
                    {l}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
