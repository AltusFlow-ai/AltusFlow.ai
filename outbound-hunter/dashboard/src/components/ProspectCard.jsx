import React, { useState, useRef } from 'react'
import { ThumbsUp, SkipForward, MessageSquare } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import NicheBadge from './NicheBadge.jsx'

function scoreColor(s) {
  if (s >= 8) return '#1D9E75'
  if (s >= 5) return '#BA7517'
  return '#D85A30'
}
function scoreBg(s) {
  if (s >= 8) return 'rgba(29,158,117,0.15)'
  if (s >= 5) return 'rgba(186,117,23,0.15)'
  return 'rgba(216,90,48,0.12)'
}

export default function ProspectCard({ prospect, onApprove, onSkip }) {
  const [msg, setMsg]       = useState(prospect.drafted_message || '')
  const [state, setState]   = useState('idle') // idle | approving | approved | skipping | skipped
  const cardRef             = useRef(null)
  const navigate            = useNavigate()
  const charColor           = msg.length > 300 ? '#D85A30' : msg.length > 270 ? '#BA7517' : '#1D9E75'

  async function handleApprove() {
    setState('approving')
    const ok = await onApprove(prospect.id, msg)
    if (ok) {
      setState('approved')
      if (cardRef.current) {
        cardRef.current.style.transition = 'all .4s ease'
        cardRef.current.style.transform  = 'translateX(60px)'
        cardRef.current.style.opacity    = '0'
        cardRef.current.style.border     = '1px solid #1D9E75'
        cardRef.current.style.background = 'rgba(29,158,117,0.05)'
      }
    } else {
      setState('idle')
    }
  }

  async function handleSkip() {
    setState('skipping')
    await onSkip(prospect.id)
    if (cardRef.current) {
      cardRef.current.style.transition = 'opacity .35s'
      cardRef.current.style.opacity    = '0.18'
    }
    setState('skipped')
  }

  const p = prospect
  return (
    <div ref={cardRef} style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
      borderRadius: 'var(--radius-lg)',
      padding: '18px 20px',
      marginBottom: 12,
      transition: 'border-color .2s',
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 14 }}>
        <div style={{
          width: 36, height: 36, borderRadius: '50%',
          background: 'var(--accent)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 14, fontWeight: 600, flexShrink: 0,
        }}>
          {(p.handle || p.name || '?')[0].toUpperCase()}
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: 14 }}>
              {p.platform === 'reddit' ? `u/${p.handle || p.name}` : (p.name || 'Unknown')}
            </span>
            <span style={{
              background: scoreBg(p.icp_score), color: scoreColor(p.icp_score),
              border: `1px solid ${scoreColor(p.icp_score)}44`,
              borderRadius: 20, padding: '2px 8px', fontSize: 11, fontWeight: 600,
            }}>
              ICP {p.icp_score}/10
            </span>
            {p.icp_score >= 9 && (
              <span style={{ background:'rgba(29,158,117,0.15)',color:'#1D9E75',borderRadius:20,padding:'2px 8px',fontSize:11,fontWeight:600 }}>
                auto ⚡
              </span>
            )}
            <NicheBadge niche={p.niche_segment || p.niche} small />
          </div>
          <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 4, display:'flex',gap:8,flexWrap:'wrap' }}>
            {p.subreddit && <span style={{ color: '#ff4500' }}>r/{p.subreddit}</span>}
            {p.post_date && <span>{p.post_date.slice(0,10)}</span>}
            {p.outreach_method === 'find_twitter' && (
              <a href={p.twitter_search_url} target="_blank" rel="noreferrer"
                style={{ color:'#BA7517',border:'1px solid #BA751744',borderRadius:4,padding:'1px 6px' }}>
                Send via Twitter →
              </a>
            )}
            {p.outreach_method === 'reddit_dm' && (
              <a href={p.profile_url} target="_blank" rel="noreferrer"
                style={{ color:'#ff4500',border:'1px solid #ff450044',borderRadius:4,padding:'1px 6px' }}>
                Send Reddit DM →
              </a>
            )}
            {p.outreach_method === 'find_linkedin' && (
              <a href={p.linkedin_search_url} target="_blank" rel="noreferrer"
                style={{ color:'#0077b5',border:'1px solid #0077b544',borderRadius:4,padding:'1px 6px' }}>
                LinkedIn search →
              </a>
            )}
          </div>
        </div>
      </div>

      {/* Post text */}
      <div style={{
        background: 'var(--bg-tertiary)',
        borderLeft: '3px solid var(--accent)',
        borderRadius: '0 var(--radius-md) var(--radius-md) 0',
        padding: '12px 14px',
        marginBottom: 12,
        fontSize: 13, color: '#d1d5db', lineHeight: 1.7, whiteSpace: 'pre-wrap',
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: 'var(--accent)', letterSpacing: '.08em', marginBottom: 6 }}>
          THEIR EXACT POST
        </div>
        {p.post_text}
        <div style={{ display:'flex',gap:12,marginTop:8,fontSize:11,color:'var(--text-tertiary)' }}>
          {p.post_url && <a href={p.post_url} target="_blank" rel="noreferrer" style={{ color:'var(--accent)' }}>View on Reddit</a>}
          {p.signal_phrase && <span>Matched: "{p.signal_phrase}"</span>}
        </div>
      </div>

      {/* Message */}
      <div style={{ marginBottom: 12 }}>
        <div style={{ display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:6 }}>
          <span style={{ fontSize: 10, fontWeight: 600, color: 'var(--text-tertiary)', letterSpacing: '.07em' }}>
            OUTREACH MESSAGE
          </span>
          <span style={{ fontSize: 11, color: charColor }}>{msg.length} chars</span>
        </div>
        <textarea
          value={msg}
          onChange={e => setMsg(e.target.value)}
          style={{
            width: '100%', background: 'var(--bg-tertiary)',
            border: `1px solid ${msg.length > 300 ? '#D85A30' : 'var(--border)'}`,
            borderRadius: 'var(--radius-md)', padding: '10px 12px',
            color: 'var(--text-primary)', fontSize: 13, lineHeight: 1.6,
            resize: 'vertical', minHeight: 80, outline: 'none',
          }}
          onFocus={e => e.target.style.borderColor = 'rgba(29,158,117,0.4)'}
          onBlur={e => e.target.style.borderColor = msg.length > 300 ? '#D85A30' : 'var(--border)'}
        />
      </div>

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8 }}>
        <button onClick={handleApprove} disabled={state !== 'idle'} style={{
          flex: 1, background: 'var(--accent)', color: '#fff',
          border: 'none', borderRadius: 'var(--radius-md)',
          padding: '9px 0', fontSize: 13, fontWeight: 600,
          opacity: state === 'approving' ? .6 : 1, cursor: state !== 'idle' ? 'not-allowed' : 'pointer',
          display:'flex',alignItems:'center',justifyContent:'center',gap:6,
        }}>
          <ThumbsUp size={14} />
          {state === 'approving' ? 'Approving…' : 'Approve'}
        </button>
        <button onClick={handleSkip} disabled={state !== 'idle'} style={{
          background: 'transparent', color: 'var(--text-secondary)',
          border: '1px solid var(--border)', borderRadius: 'var(--radius-md)',
          padding: '9px 16px', fontSize: 13, cursor: 'pointer',
          display:'flex',alignItems:'center',gap:6,
        }}>
          <SkipForward size={14} /> Skip
        </button>
        <button onClick={() => navigate(`/dashboard/replies?id=${p.id}`)} style={{
          background: 'transparent', color: '#534AB7',
          border: '1px solid rgba(83,74,183,0.3)', borderRadius: 'var(--radius-md)',
          padding: '9px 14px', fontSize: 13, cursor: 'pointer',
          display:'flex',alignItems:'center',gap:6,
        }}>
          <MessageSquare size={14} /> Reply Center
        </button>
      </div>
    </div>
  )
}
