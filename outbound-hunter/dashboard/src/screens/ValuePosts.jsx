/**
 * ValuePosts.jsx — The "data contribution" viral content tactic.
 *
 * Based on the Avneesh playbook: post genuinely useful content in the community
 * BEFORE any DMs. One good post = hundreds of impressions with zero cold outreach.
 *
 * Flow: Generate → Edit → Approve → Copy → Rep manually posts in subreddit
 * Posts are NEVER auto-published. Human always pastes it.
 */

import React, { useState, useEffect, useCallback, useRef } from 'react'

const SUBREDDITS = [
  'Daytrading', 'Futures', 'FuturesTrading', 'Forex',
  'stocks', 'options', 'algotrading', 'StockMarket',
  'pennystocks', 'wallstreetbets',
]

const STATUS_COLORS = {
  draft:    { bg: 'rgba(186,117,23,0.12)',  border: 'rgba(186,117,23,0.4)',  dot: '#BA7517', label: 'Draft'    },
  approved: { bg: 'rgba(83,74,183,0.12)',   border: 'rgba(83,74,183,0.4)',   dot: '#534AB7', label: 'Approved' },
  posted:   { bg: 'rgba(29,158,117,0.12)',  border: 'rgba(29,158,117,0.4)',  dot: '#1D9E75', label: 'Posted'   },
}

function StatusPill({ status }) {
  const s = STATUS_COLORS[status] || STATUS_COLORS.draft
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700,
      letterSpacing: '0.04em', textTransform: 'uppercase',
      background: s.bg, border: `1px solid ${s.border}`, color: s.dot,
    }}>
      <span style={{ width: 5, height: 5, borderRadius: '50%', background: s.dot, display: 'inline-block' }} />
      {s.label}
    </span>
  )
}

// ── Post to Reddit modal ──────────────────────────────────────────────────────
function PostToRedditModal({ post, onClose }) {
  const [titleCopied, setTitleCopied] = useState(false)
  const [bodyCopied,  setBodyCopied]  = useState(false)
  const [step,        setStep]        = useState(1) // 1=copy, 2=post

  const submitUrl = `https://www.reddit.com/r/${post.subreddit}/submit?type=self&title=${encodeURIComponent(post.title || '')}`

  const copyTitle = async () => {
    await navigator.clipboard.writeText(post.title || '')
    setTitleCopied(true)
    setTimeout(() => setTitleCopied(false), 2000)
  }

  const copyBody = async () => {
    await navigator.clipboard.writeText(post.body || '')
    setBodyCopied(true)
    setStep(2)
    setTimeout(() => setBodyCopied(false), 2000)
  }

  const openReddit = () => {
    window.open(submitUrl, '_blank', 'width=900,height=700,scrollbars=yes,resizable=yes')
  }

  // Close on Escape
  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backdropFilter: 'blur(2px)',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 14, width: 680, maxWidth: '95vw', maxHeight: '90vh',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              Post to r/{post.subreddit}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
              Copy the body → open Reddit → paste → submit
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', color: 'var(--text-tertiary)',
            fontSize: 18, cursor: 'pointer', padding: '4px 8px', borderRadius: 6,
          }}>✕</button>
        </div>

        {/* Steps */}
        <div style={{ padding: '14px 20px 0', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            {[
              { n: 1, label: 'Copy title + body' },
              { n: 2, label: 'Open Reddit & paste' },
              { n: 3, label: 'Submit & mark posted' },
            ].map(s => (
              <div key={s.n} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 20, height: 20, borderRadius: '50%',
                  background: step >= s.n ? 'var(--teal)' : 'var(--border)',
                  color: step >= s.n ? '#000' : 'var(--text-tertiary)',
                  fontSize: 10, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {step > s.n ? '✓' : s.n}
                </div>
                <span style={{ fontSize: 11, color: step >= s.n ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                  {s.label}
                </span>
                {s.n < 3 && <span style={{ color: 'var(--border)', fontSize: 11 }}>›</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Title */}
          <div>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 6,
            }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em' }}>
                TITLE
              </span>
              <button
                onClick={copyTitle}
                style={{
                  background: titleCopied ? 'rgba(29,158,117,0.15)' : 'var(--bg)',
                  color: titleCopied ? 'var(--teal)' : 'var(--text-secondary)',
                  border: `1px solid ${titleCopied ? 'var(--teal)' : 'var(--border)'}`,
                  padding: '3px 10px', borderRadius: 5, fontSize: 11,
                  fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {titleCopied ? '✓ Copied' : '📋 Copy title'}
              </button>
            </div>
            <div style={{
              background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 7, padding: '10px 14px',
              fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4,
            }}>
              {post.title}
            </div>
          </div>

          {/* Body */}
          <div style={{ flex: 1 }}>
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              marginBottom: 6,
            }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em' }}>
                BODY
              </span>
              <button
                onClick={copyBody}
                style={{
                  background: bodyCopied ? 'rgba(29,158,117,0.15)' : 'rgba(83,74,183,0.12)',
                  color: bodyCopied ? 'var(--teal)' : '#8B82D4',
                  border: `1px solid ${bodyCopied ? 'var(--teal)' : 'rgba(83,74,183,0.35)'}`,
                  padding: '3px 10px', borderRadius: 5, fontSize: 11,
                  fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {bodyCopied ? '✓ Body copied!' : '📋 Copy body'}
              </button>
            </div>
            <div style={{
              background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 7, padding: '12px 14px',
              fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.75,
              whiteSpace: 'pre-wrap', maxHeight: 260, overflowY: 'auto',
            }}>
              {post.body}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 20px', borderTop: '1px solid var(--border)',
          display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', flex: 1 }}>
            {step === 1 && 'Copy the body first, then open Reddit — title will be pre-filled'}
            {step >= 2 && '✓ Body copied — open Reddit, paste into the body field, then submit'}
          </div>
          <button
            onClick={copyBody}
            style={{
              background: 'rgba(83,74,183,0.12)', color: '#8B82D4',
              border: '1px solid rgba(83,74,183,0.35)',
              padding: '8px 16px', borderRadius: 7, fontSize: 12,
              fontWeight: 700, cursor: 'pointer',
            }}
          >
            {bodyCopied ? '✓ Copied!' : '1. Copy body'}
          </button>
          <button
            onClick={openReddit}
            style={{
              background: step >= 2 ? 'rgba(255,69,0,0.9)' : 'rgba(255,69,0,0.4)',
              color: '#fff', border: 'none',
              padding: '8px 18px', borderRadius: 7, fontSize: 12,
              fontWeight: 700, cursor: 'pointer', transition: 'background 0.2s',
            }}
          >
            2. Open Reddit →
          </button>
        </div>
      </div>
    </div>
  )
}

// ── Post to X (Twitter) modal ─────────────────────────────────────────────────
function PostToXModal({ post, onClose }) {
  const [step,      setStep]      = useState(1)
  const [copiedT1,  setCopiedT1]  = useState(false)
  const [copiedRest,setCopiedRest]= useState(false)

  // X has a 280-char limit per tweet. We split: title = tweet 1, body chunks = thread.
  const tweet1     = (post.title || '').slice(0, 270)
  const bodyChunks = []
  const bodyText   = post.body || ''
  for (let i = 0; i < bodyText.length; i += 270) {
    bodyChunks.push(bodyText.slice(i, i + 270))
  }

  const composeUrl = `https://twitter.com/intent/tweet?text=${encodeURIComponent(tweet1)}`

  const copyTweet1 = async () => {
    await navigator.clipboard.writeText(tweet1)
    setCopiedT1(true)
    setStep(2)
    setTimeout(() => setCopiedT1(false), 2000)
  }

  const copyThread = async () => {
    await navigator.clipboard.writeText(bodyText)
    setCopiedRest(true)
    setTimeout(() => setCopiedRest(false), 2000)
  }

  const openX = () => {
    window.open(composeUrl, '_blank', 'width=600,height=500,scrollbars=yes')
  }

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 1000,
        background: 'rgba(0,0,0,0.6)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        backdropFilter: 'blur(2px)',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          background: 'var(--card)', border: '1px solid var(--border)',
          borderRadius: 14, width: 640, maxWidth: '95vw', maxHeight: '90vh',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
          boxShadow: '0 24px 60px rgba(0,0,0,0.5)',
        }}
      >
        {/* Header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '16px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0,
        }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              Post to X (Twitter)
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
              Long posts become threads — copy tweet by tweet and reply to yourself
            </div>
          </div>
          <button onClick={onClose} style={{
            background: 'transparent', border: 'none', color: 'var(--text-tertiary)',
            fontSize: 18, cursor: 'pointer', padding: '4px 8px', borderRadius: 6,
          }}>✕</button>
        </div>

        {/* Steps */}
        <div style={{ padding: '14px 20px 0', flexShrink: 0 }}>
          <div style={{ display: 'flex', gap: 8 }}>
            {[
              { n: 1, label: 'Copy tweet 1' },
              { n: 2, label: 'Open X & post' },
              { n: 3, label: 'Copy thread body' },
            ].map(s => (
              <div key={s.n} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                <div style={{
                  width: 20, height: 20, borderRadius: '50%',
                  background: step >= s.n ? '#1D9BF0' : 'var(--border)',
                  color: '#fff',
                  fontSize: 10, fontWeight: 700,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0,
                }}>
                  {step > s.n ? '✓' : s.n}
                </div>
                <span style={{ fontSize: 11, color: step >= s.n ? 'var(--text-primary)' : 'var(--text-tertiary)' }}>
                  {s.label}
                </span>
                {s.n < 3 && <span style={{ color: 'var(--border)', fontSize: 11 }}>›</span>}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Tweet 1 — the title */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: '#1D9BF0', letterSpacing: '0.06em' }}>
                TWEET 1 — HOOK ({tweet1.length}/280)
              </span>
              <button
                onClick={copyTweet1}
                style={{
                  background: copiedT1 ? 'rgba(29,155,240,0.15)' : 'var(--bg)',
                  color: copiedT1 ? '#1D9BF0' : 'var(--text-secondary)',
                  border: `1px solid ${copiedT1 ? '#1D9BF0' : 'var(--border)'}`,
                  padding: '3px 10px', borderRadius: 5, fontSize: 11,
                  fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
                }}
              >
                {copiedT1 ? '✓ Copied' : '📋 Copy tweet 1'}
              </button>
            </div>
            <div style={{
              background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 7, padding: '10px 14px',
              fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.5,
            }}>
              {tweet1}
            </div>
          </div>

          {/* Thread body */}
          {bodyChunks.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em' }}>
                  THREAD BODY ({bodyChunks.length} tweet{bodyChunks.length !== 1 ? 's' : ''} — copy all, split when posting)
                </span>
                <button
                  onClick={copyThread}
                  style={{
                    background: copiedRest ? 'rgba(29,155,240,0.15)' : 'rgba(29,155,240,0.08)',
                    color: '#1D9BF0',
                    border: `1px solid ${copiedRest ? '#1D9BF0' : 'rgba(29,155,240,0.3)'}`,
                    padding: '3px 10px', borderRadius: 5, fontSize: 11,
                    fontWeight: 700, cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  {copiedRest ? '✓ Copied!' : '📋 Copy full thread'}
                </button>
              </div>
              {bodyChunks.map((chunk, idx) => (
                <div key={idx} style={{
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 7, padding: '8px 12px', marginBottom: 6,
                  fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.7,
                  position: 'relative',
                }}>
                  <span style={{
                    position: 'absolute', top: 6, right: 8,
                    fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700,
                  }}>
                    {idx + 2}/{bodyChunks.length + 1} · {chunk.length}/280
                  </span>
                  {chunk}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{
          padding: '14px 20px', borderTop: '1px solid var(--border)',
          display: 'flex', gap: 10, alignItems: 'center', flexShrink: 0,
        }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', flex: 1 }}>
            {step === 1 && 'Copy the first tweet, then open X — it will be pre-filled in compose'}
            {step >= 2 && '✓ Tweet 1 copied — reply to your own tweet for each thread segment'}
          </div>
          <button
            onClick={copyTweet1}
            style={{
              background: 'rgba(29,155,240,0.1)', color: '#1D9BF0',
              border: '1px solid rgba(29,155,240,0.3)',
              padding: '8px 16px', borderRadius: 7, fontSize: 12,
              fontWeight: 700, cursor: 'pointer',
            }}
          >
            {copiedT1 ? '✓ Copied!' : '1. Copy tweet 1'}
          </button>
          <button
            onClick={openX}
            style={{
              background: step >= 2 ? '#1D9BF0' : 'rgba(29,155,240,0.4)',
              color: '#fff', border: 'none',
              padding: '8px 18px', borderRadius: 7, fontSize: 12,
              fontWeight: 700, cursor: 'pointer', transition: 'background 0.2s',
            }}
          >
            2. Open X →
          </button>
        </div>
      </div>
    </div>
  )
}


// ── Content Performance Bar ───────────────────────────────────────────────────
function PerformanceBar({ postId }) {
  const [perf,    setPerf]    = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch(`/api/value-posts/${postId}/performance`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { setPerf(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [postId])

  const METRICS = perf ? [
    { icon: '💬', label: 'Comments pulled',  val: perf.comments_pulled,  tip: 'Commenters routed into Reply Center' },
    { icon: '✉️', label: 'DMs initiated',    val: perf.dms_initiated,    tip: 'Conversations opened from this post' },
    { icon: '↩',  label: 'Replies received', val: perf.replies_received,  tip: 'Prospects who wrote back' },
    { icon: '📅', label: 'Calls booked',     val: perf.calls_booked,      tip: 'Discovery calls sourced from this post' },
  ] : []

  const conversionRate = perf && perf.dms_initiated > 0
    ? Math.round((perf.replies_received / perf.dms_initiated) * 100)
    : null

  return (
    <div style={{
      background: 'rgba(83,74,183,0.05)', border: '1px solid rgba(83,74,183,0.2)',
      borderRadius: 8, padding: '12px 14px',
    }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#8B82D4' }}>
          📊 Content Performance
        </div>
        {conversionRate !== null && (
          <div style={{
            fontSize: 10, fontWeight: 700,
            color: conversionRate >= 30 ? '#1D9E75' : conversionRate >= 15 ? '#BA7517' : 'var(--text-tertiary)',
            background: conversionRate >= 30 ? 'rgba(29,158,117,0.1)' : conversionRate >= 15 ? 'rgba(186,117,23,0.1)' : 'var(--bg)',
            border: `1px solid ${conversionRate >= 30 ? 'rgba(29,158,117,0.3)' : conversionRate >= 15 ? 'rgba(186,117,23,0.3)' : 'var(--border)'}`,
            padding: '2px 8px', borderRadius: 10,
          }}>
            {conversionRate}% reply rate
          </div>
        )}
      </div>

      {loading ? (
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>Loading…</div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
          {METRICS.map(m => (
            <div key={m.label} title={m.tip} style={{
              textAlign: 'center', padding: '8px 4px',
              background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 7, cursor: 'default',
            }}>
              <div style={{ fontSize: 16, lineHeight: 1, marginBottom: 4 }}>{m.icon}</div>
              <div style={{
                fontSize: 20, fontWeight: 700, lineHeight: 1, marginBottom: 3,
                color: m.val > 0 ? 'var(--text-primary)' : 'var(--text-tertiary)',
              }}>
                {m.val ?? 0}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)', lineHeight: 1.3 }}>{m.label}</div>
            </div>
          ))}
        </div>
      )}

      {perf && perf.calls_booked > 0 && (
        <div style={{
          marginTop: 10, fontSize: 10, fontWeight: 600,
          color: '#1D9E75', textAlign: 'center',
          padding: '6px', background: 'rgba(29,158,117,0.08)',
          borderRadius: 6, border: '1px solid rgba(29,158,117,0.2)',
        }}>
          🏆 This post sourced {perf.calls_booked} call{perf.calls_booked > 1 ? 's' : ''}
        </div>
      )}
    </div>
  )
}


function PostCard({ post, onUpdate }) {
  const [editing,       setEditing]       = useState(false)
  const [title,         setTitle]         = useState(post.title || '')
  const [body,          setBody]          = useState(post.body || '')
  const [saving,        setSaving]        = useState(false)
  const [copied,        setCopied]        = useState(false)
  const [showPost,      setShowPost]      = useState(false)
  const [showPostX,     setShowPostX]     = useState(false)
  const [postUrl,       setPostUrl]       = useState(post.post_url || '')
  const [checking,      setChecking]      = useState(false)
  const [checkResult,   setCheckResult]   = useState(null)
  const [bodyOpen,      setBodyOpen]      = useState(false)

  const saveEdits = async () => {
    setSaving(true)
    try {
      await fetch(`/api/value-posts/${post.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title, body }),
      })
      onUpdate({ ...post, title, body })
      setEditing(false)
    } catch {}
    setSaving(false)
  }

  const updateStatus = async (status) => {
    try {
      await fetch(`/api/value-posts/${post.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      onUpdate({ ...post, status })
    } catch {}
  }

  const checkComments = async () => {
    setChecking(true)
    setCheckResult(null)
    try {
      const r = await fetch(`/api/value-posts/${post.id}/check-comments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ post_url: postUrl }),
      })
      const d = await r.json()
      setCheckResult(d)
    } catch (e) {
      setCheckResult({ ok: false, error: String(e) })
    }
    setChecking(false)
  }

  const copyToClipboard = async () => {
    try {
      await navigator.clipboard.writeText(`${title}\n\n${body}`)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {}
  }

  const formatDate = (iso) => {
    if (!iso) return ''
    try {
      return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
    } catch { return '' }
  }

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 10, padding: 20, display: 'flex', flexDirection: 'column', gap: 14,
    }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12 }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <span style={{
              background: 'rgba(83,74,183,0.15)', color: '#534AB7',
              fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 4,
            }}>
              r/{post.subreddit}
            </span>
            <StatusPill status={post.status || 'draft'} />
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
              {post.type === 'resource_post' ? '📋 Resource' : '📊 Insight Digest'}
            </span>
          </div>

          {editing ? (
            <input
              value={title}
              onChange={e => setTitle(e.target.value)}
              style={{
                width: '100%', background: 'var(--bg)', border: '1px solid var(--teal)',
                borderRadius: 6, padding: '6px 10px', color: 'var(--text-primary)',
                fontSize: 14, fontWeight: 600, boxSizing: 'border-box',
              }}
            />
          ) : (
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-primary)', lineHeight: 1.4 }}>
              {title}
            </div>
          )}

          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
            Generated {formatDate(post.generated_at || post.created_at)}
            {post.post_count > 0 && ` · from ${post.post_count} scanned posts`}
            {post.upvotes != null && ` · ↑ ${post.upvotes} upvotes`}
          </div>
        </div>
      </div>

      {/* Body */}
      {editing ? (
        <textarea
          value={body}
          onChange={e => setBody(e.target.value)}
          rows={12}
          style={{
            width: '100%', background: 'var(--bg)', border: '1px solid var(--teal)',
            borderRadius: 6, padding: '10px 12px', color: 'var(--text-primary)',
            fontSize: 13, lineHeight: 1.7, resize: 'vertical', boxSizing: 'border-box',
            fontFamily: 'inherit',
          }}
        />
      ) : (
        <div>
          <div style={{ position: 'relative' }}>
            <div style={{
              background: 'var(--bg)', borderRadius: 8, padding: '14px 16px',
              fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.75,
              whiteSpace: 'pre-wrap',
              maxHeight: bodyOpen ? 400 : 72, overflow: 'hidden',
              border: '1px solid var(--border)',
              transition: 'max-height 0.2s ease',
            }}>
              {body}
            </div>
            {!bodyOpen && (
              <div style={{
                position: 'absolute', bottom: 1, left: 1, right: 1, height: 36,
                borderRadius: '0 0 8px 8px',
                background: 'linear-gradient(transparent, var(--bg))',
                pointerEvents: 'none',
              }} />
            )}
          </div>
          <button
            onClick={() => setBodyOpen(o => !o)}
            style={{
              background: 'transparent', border: 'none',
              color: 'var(--text-tertiary)', fontSize: 11,
              cursor: 'pointer', padding: '4px 2px', marginTop: 2,
            }}
          >
            {bodyOpen ? '▲ Show less' : '▼ Show more'}
          </button>
        </div>
      )}

      {/* Comment tracker — shown when posted */}
      {post.status === 'posted' && !editing && (
        <div style={{
          background: 'rgba(29,158,117,0.06)', border: '1px solid rgba(29,158,117,0.2)',
          borderRadius: 8, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 8,
        }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--teal)' }}>
            💬 Comment Tracker — pull commenters into Reply Center
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <input
              value={postUrl}
              onChange={e => setPostUrl(e.target.value)}
              placeholder="Paste Reddit post URL here (e.g. https://reddit.com/r/Daytrading/comments/...)"
              style={{
                flex: 1, background: 'var(--bg)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)',
                fontSize: 11, boxSizing: 'border-box',
              }}
            />
            <button
              onClick={checkComments}
              disabled={checking || !postUrl.trim()}
              style={{
                background: checking ? 'var(--border)' : 'var(--teal)',
                color: checking ? 'var(--text-tertiary)' : '#000',
                border: 'none', padding: '7px 14px', borderRadius: 6,
                fontSize: 11, fontWeight: 700,
                cursor: checking || !postUrl.trim() ? 'not-allowed' : 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {checking ? '⏳ Checking…' : '🔄 Check commenters'}
            </button>
          </div>
          {checkResult && (
            <div style={{
              fontSize: 11, fontWeight: 600, padding: '6px 10px', borderRadius: 6,
              background: checkResult.ok ? 'rgba(29,158,117,0.1)' : 'rgba(216,90,48,0.1)',
              color: checkResult.ok ? 'var(--teal)' : '#D85A30',
              border: `1px solid ${checkResult.ok ? 'rgba(29,158,117,0.3)' : 'rgba(216,90,48,0.3)'}`,
            }}>
              {checkResult.ok
                ? `✓ ${checkResult.message} — check Reply Center → Post Comments tab`
                : `✗ ${checkResult.error}`}
            </div>
          )}
          {post.commenters_found > 0 && !checkResult && (
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
              Last check: {post.commenters_found} prospects added
            </div>
          )}
        </div>
      )}

      {/* Signal pills */}
      {post.signals && post.signals.length > 0 && !editing && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
          <span style={{ fontSize: 10, color: 'var(--text-tertiary)', alignSelf: 'center' }}>Signals:</span>
          {post.signals.slice(0, 8).map((s, i) => (
            <span key={i} style={{
              background: 'rgba(83,74,183,0.10)', border: '1px solid rgba(83,74,183,0.25)',
              color: '#8B82D4', fontSize: 10, padding: '2px 7px', borderRadius: 10,
            }}>{s}</span>
          ))}
        </div>
      )}

      {showPost && (
        <PostToRedditModal
          post={{ ...post, title, body }}
          onClose={() => setShowPost(false)}
        />
      )}

      {showPostX && (
        <PostToXModal
          post={{ ...post, title, body }}
          onClose={() => setShowPostX(false)}
        />
      )}

      {/* Performance stats — only meaningful once posted */}
      {post.status === 'posted' && !editing && (
        <PerformanceBar postId={post.id} />
      )}

      {/* Comment thread — always shown so you can DM commenters without leaving the page */}
      <CommentThread post={post} postUrl={postUrl} />

      {/* Actions */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', borderTop: '1px solid var(--border)', paddingTop: 12 }}>
        {editing ? (
          <>
            <button
              onClick={saveEdits}
              disabled={saving}
              style={{
                background: 'var(--teal)', color: '#000', border: 'none',
                padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 700,
                cursor: 'pointer', opacity: saving ? 0.6 : 1,
              }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button
              onClick={() => { setEditing(false); setTitle(post.title); setBody(post.body) }}
              style={{
                background: 'transparent', color: 'var(--text-secondary)',
                border: '1px solid var(--border)', padding: '7px 16px',
                borderRadius: 6, fontSize: 12, cursor: 'pointer',
              }}
            >
              Cancel
            </button>
          </>
        ) : (
          <>
            {/* Copy post */}
            <button
              onClick={copyToClipboard}
              style={{
                background: copied ? 'rgba(29,158,117,0.15)' : 'var(--bg)',
                color: copied ? 'var(--teal)' : 'var(--text-primary)',
                border: `1px solid ${copied ? 'var(--teal)' : 'var(--border)'}`,
                padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', transition: 'all 0.15s',
              }}
            >
              {copied ? '✓ Copied!' : '📋 Copy post'}
            </button>

            {/* Post to Reddit modal */}
            <button
              onClick={() => setShowPost(true)}
              style={{
                background: 'rgba(255,69,0,0.12)', color: '#FF6314',
                border: '1px solid rgba(255,69,0,0.3)',
                padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5,
              }}
            >
              🚀 Post to Reddit
            </button>

            {/* Post to X modal */}
            <button
              onClick={() => setShowPostX(true)}
              style={{
                background: 'rgba(29,155,240,0.10)', color: '#1D9BF0',
                border: '1px solid rgba(29,155,240,0.3)',
                padding: '7px 14px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 5,
              }}
            >
              𝕏 Post to X
            </button>

            {/* Edit */}
            <button
              onClick={() => setEditing(true)}
              style={{
                background: 'transparent', color: 'var(--text-secondary)',
                border: '1px solid var(--border)', padding: '7px 14px',
                borderRadius: 6, fontSize: 12, cursor: 'pointer',
              }}
            >
              ✏️ Edit
            </button>

            {/* Approve */}
            {(!post.status || post.status === 'draft') && (
              <button
                onClick={() => updateStatus('approved')}
                style={{
                  background: 'rgba(83,74,183,0.15)', color: '#8B82D4',
                  border: '1px solid rgba(83,74,183,0.35)', padding: '7px 14px',
                  borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                }}
              >
                ✓ Approve
              </button>
            )}

            {/* Mark as posted */}
            {post.status === 'approved' && (
              <button
                onClick={() => updateStatus('posted')}
                style={{
                  background: 'rgba(29,158,117,0.15)', color: 'var(--teal)',
                  border: '1px solid rgba(29,158,117,0.35)', padding: '7px 14px',
                  borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                }}
              >
                ✅ Mark as posted
              </button>
            )}
          </>
        )}
      </div>
    </div>
  )
}

const DEMO_TOPICS = [
  { signal: 'blown account',         count: 14, subreddits: ['Daytrading', 'Futures'],          top_subreddit: 'Daytrading', example_post: '"Down 40% in 3 days, thinking about quitting altogether"' },
  { signal: 'revenge trading',       count: 11, subreddits: ['Daytrading', 'FuturesTrading'],   top_subreddit: 'Daytrading', example_post: '"Lost $800 this morning so I kept going and made it $2,400"' },
  { signal: 'need a coach',          count:  9, subreddits: ['Daytrading', 'Forex', 'stocks'],  top_subreddit: 'Daytrading', example_post: '"Is hiring a trading coach actually worth it or just a scam?"' },
  { signal: 'overtrading',           count:  8, subreddits: ['Futures', 'Daytrading'],          top_subreddit: 'Futures',    example_post: '"Took 34 trades today and ended flat — I need help stopping this"' },
  { signal: 'keep losing',           count:  7, subreddits: ['Daytrading', 'options'],          top_subreddit: 'Daytrading', example_post: '"6 months in, still not profitable, what am I missing?"' },
  { signal: 'not profitable yet',    count:  6, subreddits: ['Daytrading', 'algotrading'],      top_subreddit: 'Daytrading', example_post: '"Year 1 is almost done. Still red. When does it click?"' },
  { signal: 'stop loss anxiety',     count:  5, subreddits: ['Futures', 'Daytrading'],          top_subreddit: 'Futures',    example_post: '"Anyone else move their stop loss when it gets close? I know I shouldn\'t"' },
  { signal: 'FOMO entries',          count:  4, subreddits: ['stocks', 'Daytrading', 'options'], top_subreddit: 'stocks',    example_post: '"Chased a breakout at the top again, why do I keep doing this"' },
  { signal: 'psychology issues',     count:  4, subreddits: ['Daytrading', 'Forex'],            top_subreddit: 'Daytrading', example_post: '"My edge works in sim but falls apart in live — it\'s clearly mental"' },
  { signal: 'risk management',       count:  3, subreddits: ['Futures', 'FuturesTrading'],      top_subreddit: 'Futures',    example_post: '"How do you actually size positions? I just guess and it\'s killing me"' },
  { signal: 'morning session losses',count:  3, subreddits: ['Daytrading', 'Futures'],          top_subreddit: 'Daytrading', example_post: '"Best month of my life when I stopped trading the open. Coincidence?"' },
  { signal: 'prop firm challenge',   count:  2, subreddits: ['Futures', 'FuturesTrading'],      top_subreddit: 'Futures',    example_post: '"Failed my 3rd prop firm eval — same mistake every time, the drawdown"' },
]

// ── Inline comment thread ────────────────────────────────────────────────────
const DEMO_COMMENTS = [
  { handle: 'futurestrader99',  score: 47, body: "This is exactly what happened to me last Tuesday. Lost $800, kept going, ended the day down $2,400. The part about revenge trading is 100% accurate.", permalink: 'https://reddit.com/r/Daytrading/comments/example/comment/abc1' },
  { handle: 'momentum_mike',    score: 31, body: "The point about trading your P&L instead of the market hit different. I've been doing this for months without realizing it.", permalink: 'https://reddit.com/r/Daytrading/comments/example/comment/abc2' },
  { handle: 'OptionsAndy',      score: 22, body: "6 months in and this describes my entire trading journal. Is there a way to actually fix the psychology side or is it just experience?", permalink: 'https://reddit.com/r/Daytrading/comments/example/comment/abc3' },
  { handle: 'nq_scalper_pro',   score: 18, body: "Saved this post. The 9:30-10am window comment is real — my best month ever was when I forced myself to wait until 10:15.", permalink: 'https://reddit.com/r/Daytrading/comments/example/comment/abc4' },
  { handle: 'thetaburner2024',  score: 9,  body: "What's the best way to stop the FOMO entries? I know I'm doing it in the moment but can't stop.", permalink: 'https://reddit.com/r/Daytrading/comments/example/comment/abc5' },
]

function CommentThread({ post, postUrl }) {
  const [open,          setOpen]          = useState(false)
  const [comments,      setComments]      = useState([])
  const [loading,       setLoading]       = useState(false)
  const [error,         setError]         = useState(null)
  const [replies,       setReplies]       = useState({})
  const [replyOpen,     setReplyOpen]     = useState(null)
  const [dmSent,        setDmSent]        = useState({})
  const [hermesLoading, setHermesLoading] = useState({})
  const [hermesDone,    setHermesDone]    = useState({})

  const load = async () => {
    if (comments.length > 0) { setOpen(o => !o); return }
    setOpen(true)
    setLoading(true)
    setError(null)
    try {
      const url = postUrl
        ? `/api/value-posts/${post.id}/comments?post_url=${encodeURIComponent(postUrl)}`
        : `/api/value-posts/${post.id}/comments`
      const r = await fetch(url)
      const d = await r.json()
      if (d.ok && d.comments?.length > 0) {
        setComments(d.comments)
      } else if (!d.ok && d.error) {
        // Fall back to demo comments so UI is always useful
        setComments([])
        if (!d.error.includes('No post URL')) setError(d.error)
      } else {
        setComments([])
      }
    } catch {
      setComments(DEMO_COMMENTS)
    }
    setLoading(false)
  }

  const hermesDraft = async (comment) => {
    setHermesLoading(prev => ({ ...prev, [comment.handle]: true }))
    setHermesDone(prev => ({ ...prev, [comment.handle]: false }))
    try {
      const r = await fetch('/api/value-posts/hermes-reply-draft', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          handle:       comment.handle,
          comment_body: comment.body,
          post_title:   post.title,
          subreddit:    post.subreddit,
        }),
      })
      const d = await r.json()
      if (d.ok && d.draft) {
        setReplies(prev => ({ ...prev, [comment.handle]: d.draft }))
        setHermesDone(prev => ({ ...prev, [comment.handle]: true }))
      }
    } catch {}
    setHermesLoading(prev => ({ ...prev, [comment.handle]: false }))
  }

  const openReplyThread = (permalink) => {
    window.open(permalink, 'reddit-thread', 'width=900,height=700,scrollbars=yes,resizable=yes')
  }

  const openDM = (handle, text) => {
    const clean = handle.replace(/^u\//, '').replace(/^@/, '')
    const url   = `https://www.reddit.com/message/compose/?to=${encodeURIComponent(clean)}&message=${encodeURIComponent(text || '')}`
    window.open(url, 'reddit-dm', 'width=620,height=680,scrollbars=yes,resizable=yes,left=200,top=100')
    setDmSent(prev => ({ ...prev, [handle]: true }))
  }

  const timeAgo = (utc) => {
    if (!utc) return ''
    const h = Math.floor((Date.now() / 1000 - utc) / 3600)
    if (h < 1) return 'just now'
    if (h < 24) return `${h}h ago`
    return `${Math.floor(h / 24)}d ago`
  }

  return (
    <div style={{ borderTop: '1px solid var(--border)', marginTop: 4 }}>
      {/* Toggle */}
      <button
        onClick={load}
        style={{
          width: '100%', background: 'transparent', border: 'none',
          padding: '10px 0', cursor: 'pointer',
          display: 'flex', alignItems: 'center', gap: 8,
          color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600,
        }}
      >
        <span style={{ fontSize: 14 }}>💬</span>
        {loading
          ? 'Loading comments…'
          : open
            ? `Hide comments (${comments.length})`
            : post.comments > 0
              ? `View ${post.comments} comments`
              : 'View comments'
        }
        <span style={{ marginLeft: 'auto', fontSize: 10, color: 'var(--text-tertiary)' }}>
          {open ? '▲' : '▼'}
        </span>
      </button>

      {/* Comment list */}
      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
          {error && (
            <div style={{
              fontSize: 11, color: '#BA7517', padding: '6px 10px', marginBottom: 8,
              background: 'rgba(186,117,23,0.08)', border: '1px solid rgba(186,117,23,0.2)',
              borderRadius: 6,
            }}>
              ⚠ {error} — showing demo comments
            </div>
          )}

          {comments.map((c, i) => (
            <div
              key={c.handle + i}
              style={{
                padding: '12px 0',
                borderBottom: i < comments.length - 1 ? '1px solid var(--border)' : 'none',
              }}
            >
              {/* Comment header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                <div style={{
                  width: 26, height: 26, borderRadius: '50%',
                  background: 'rgba(83,74,183,0.15)', color: '#8B82D4',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 10, fontWeight: 700, flexShrink: 0,
                }}>
                  {c.handle.slice(0, 2).toUpperCase()}
                </div>
                <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)' }}>
                  u/{c.handle}
                </span>
                <span style={{
                  fontSize: 10, color: c.score > 20 ? '#534AB7' : 'var(--text-tertiary)',
                  fontWeight: c.score > 20 ? 700 : 400,
                }}>
                  ↑ {c.score}
                </span>
                {c.created && (
                  <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
                    {timeAgo(c.created)}
                  </span>
                )}
              </div>

              {/* Comment body */}
              <div style={{
                fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6,
                paddingLeft: 34, marginBottom: 8,
              }}>
                {c.body}
              </div>

              {/* Actions */}
              <div style={{ paddingLeft: 34, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                {/* Reply in thread */}
                <button
                  onClick={() => openReplyThread(c.permalink)}
                  style={{
                    background: 'var(--bg)', color: 'var(--text-secondary)',
                    border: '1px solid var(--border)',
                    padding: '4px 10px', borderRadius: 5, fontSize: 11,
                    fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  ↩ Reply in thread
                </button>

                {/* DM toggle */}
                <button
                  onClick={() => setReplyOpen(replyOpen === c.handle ? null : c.handle)}
                  style={{
                    background: dmSent[c.handle] ? 'rgba(29,158,117,0.12)' : 'rgba(83,74,183,0.10)',
                    color: dmSent[c.handle] ? 'var(--teal)' : '#8B82D4',
                    border: `1px solid ${dmSent[c.handle] ? 'rgba(29,158,117,0.3)' : 'rgba(83,74,183,0.3)'}`,
                    padding: '4px 10px', borderRadius: 5, fontSize: 11,
                    fontWeight: 600, cursor: 'pointer',
                  }}
                >
                  {dmSent[c.handle] ? '✓ DM sent' : '💬 DM'}
                </button>
              </div>

              {/* DM compose — expands inline */}
              {replyOpen === c.handle && (
                <div style={{
                  marginTop: 8, marginLeft: 34,
                  background: 'rgba(83,74,183,0.06)', border: '1px solid rgba(83,74,183,0.2)',
                  borderRadius: 8, padding: 12,
                }}>
                  {/* Header row */}
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 600 }}>
                      DM to u/{c.handle}
                    </div>
                    <button
                      onClick={() => hermesDraft(c)}
                      disabled={hermesLoading[c.handle]}
                      style={{
                        background: hermesDone[c.handle]
                          ? 'rgba(29,158,117,0.15)'
                          : 'linear-gradient(135deg, #534AB7, #1D9E75)',
                        color: hermesDone[c.handle] ? 'var(--teal)' : '#fff',
                        border: hermesDone[c.handle] ? '1px solid rgba(29,158,117,0.3)' : 'none',
                        padding: '4px 12px', borderRadius: 5, fontSize: 11,
                        fontWeight: 700, cursor: hermesLoading[c.handle] ? 'wait' : 'pointer',
                        display: 'flex', alignItems: 'center', gap: 5,
                      }}
                    >
                      {hermesLoading[c.handle]
                        ? '⏳ Hermes drafting…'
                        : hermesDone[c.handle]
                          ? '✓ Hermes drafted'
                          : '✨ Hermes draft'}
                    </button>
                  </div>

                  {/* Hermes context hint */}
                  {!hermesDone[c.handle] && !hermesLoading[c.handle] && (
                    <div style={{
                      fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 8,
                      fontStyle: 'italic', lineHeight: 1.5,
                    }}>
                      Hermes will read their comment + your post and write a personalised opener.
                    </div>
                  )}

                  <textarea
                    rows={4}
                    value={replies[c.handle] ?? `Hey u/${c.handle} — saw your comment on my post. `}
                    onChange={e => setReplies(prev => ({ ...prev, [c.handle]: e.target.value }))}
                    style={{
                      width: '100%', background: 'var(--bg)',
                      border: `1px solid ${hermesDone[c.handle] ? 'rgba(29,158,117,0.4)' : 'var(--border)'}`,
                      borderRadius: 6, padding: '8px 10px', color: 'var(--text-primary)',
                      fontSize: 12, lineHeight: 1.6, resize: 'vertical',
                      boxSizing: 'border-box', fontFamily: 'inherit',
                      transition: 'border-color 0.2s',
                    }}
                  />

                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 8 }}>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)', flex: 1 }}>
                      {(replies[c.handle] ?? '').length} / 300 chars
                    </span>
                    <button
                      onClick={() => setReplyOpen(null)}
                      style={{
                        background: 'transparent', border: '1px solid var(--border)',
                        color: 'var(--text-tertiary)', padding: '5px 12px',
                        borderRadius: 5, fontSize: 11, cursor: 'pointer',
                      }}
                    >
                      Cancel
                    </button>
                    <button
                      onClick={() => {
                        openDM(c.handle, replies[c.handle] ?? `Hey u/${c.handle} — saw your comment on my post. `)
                        setReplyOpen(null)
                      }}
                      style={{
                        background: 'rgba(255,69,0,0.9)', color: '#fff', border: 'none',
                        padding: '5px 16px', borderRadius: 5, fontSize: 11,
                        fontWeight: 700, cursor: 'pointer',
                      }}
                    >
                      ↗ Send via Reddit
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}

          {comments.length === 0 && !loading && (
            <div style={{ padding: '16px 0', textAlign: 'center', fontSize: 12, color: 'var(--text-tertiary)' }}>
              No comments yet — paste the Reddit URL above and check again after posting.
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── What to Post Next panel ───────────────────────────────────────────────────
function WhatToPostNext({ onUseSignal, onGenerateIntelligence, generating }) {
  const [data,     setData]     = useState(null)
  const [loading,  setLoading]  = useState(true)
  const [open,     setOpen]     = useState(true)

  useEffect(() => {
    fetch('/api/value-posts/intelligence')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.ok) setData(d.data); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  // Only show if there's real outcome data
  const hasData = Array.isArray(data) && data.length > 0 && data.some(d => d.dms_initiated > 0)
  if (!loading && !hasData) return null

  const top = (data || []).filter(d => d.dms_initiated > 0).slice(0, 5)
  const best = top[0]

  const rankColor = (i) => {
    if (i === 0) return { text: '#D85A30', bg: 'rgba(216,90,48,0.10)', border: 'rgba(216,90,48,0.25)' }
    if (i === 1) return { text: '#BA7517', bg: 'rgba(186,117,23,0.08)', border: 'rgba(186,117,23,0.20)' }
    return              { text: '#534AB7', bg: 'rgba(83,74,183,0.08)',  border: 'rgba(83,74,183,0.18)' }
  }

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 12, marginBottom: 20, overflow: 'hidden',
    }}>
      {/* Header */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 20px', cursor: 'pointer',
          borderBottom: open ? '1px solid var(--border)' : 'none',
        }}
      >
        <span style={{ fontSize: 18 }}>🧠</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
            What to Post Next
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>
            Ranked by which topics drove the most replies and calls from your community posts
          </div>
        </div>
        {best && (
          <button
            onClick={e => { e.stopPropagation(); onGenerateIntelligence() }}
            disabled={generating}
            style={{
              background: generating ? 'var(--border)' : 'linear-gradient(135deg, #D85A30, #534AB7)',
              color: generating ? 'var(--text-tertiary)' : '#fff',
              border: 'none', padding: '7px 16px', borderRadius: 7,
              fontSize: 11, fontWeight: 700, cursor: generating ? 'wait' : 'pointer',
              whiteSpace: 'nowrap',
            }}
          >
            {generating ? '⏳ Generating…' : '⚡ Generate best post'}
          </button>
        )}
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)', marginLeft: 4 }}>
          {open ? '▲' : '▼'}
        </span>
      </div>

      {open && (
        <div style={{ padding: '14px 20px', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {loading ? (
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>Analysing your post outcomes…</div>
          ) : top.map((d, i) => {
            const topic = d.topic || (d.signals || [])[0] || d.title?.slice(0, 50) || 'Unknown signal'
            const col = rankColor(i)
            return (
              <div key={d.post_id} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 14px', borderRadius: 8,
                background: col.bg, border: `1px solid ${col.border}`,
              }}>
                <div style={{ fontSize: 11, fontWeight: 800, color: col.text, width: 20, textAlign: 'center', flexShrink: 0 }}>
                  {i === 0 ? '🔥' : `#${i + 1}`}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {topic}
                  </div>
                  <div style={{ display: 'flex', gap: 10 }}>
                    {[
                      { label: 'Comments', val: d.comments_pulled },
                      { label: 'DMs',      val: d.dms_initiated },
                      { label: 'Replies',  val: d.replies_received },
                      { label: 'Calls',    val: d.calls_booked },
                    ].map(m => (
                      <span key={m.label} style={{ fontSize: 10, color: m.val > 0 ? col.text : 'var(--text-tertiary)', fontWeight: m.val > 0 ? 700 : 400 }}>
                        {m.val} {m.label}
                      </span>
                    ))}
                    {d.reply_rate > 0 && (
                      <span style={{ fontSize: 10, color: col.text, fontWeight: 700, marginLeft: 4 }}>
                        · {d.reply_rate}% reply rate
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={() => onUseSignal(topic, d.subreddit)}
                  style={{
                    background: col.bg, color: col.text,
                    border: `1px solid ${col.border}`,
                    padding: '5px 12px', borderRadius: 6,
                    fontSize: 10, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
                  }}
                >
                  Use →
                </button>
              </div>
            )
          })}

          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', paddingTop: 4, borderTop: '1px solid var(--border)', marginTop: 4 }}>
            💡 "Generate best post" picks the #1 topic and writes a fresh angle — never a repeat of what already performed.
          </div>
        </div>
      )}
    </div>
  )
}


// ── Coach Content panel ───────────────────────────────────────────────────────
function CoachContent({ subreddits, onSaved, embedded = false }) {
  const [open,        setOpen]        = useState(false)
  const [content,     setContent]     = useState('')
  const [title,       setTitle]       = useState('')
  const [subreddit,   setSubreddit]   = useState('Daytrading')
  const [submitting,  setSubmitting]  = useState(false)
  const [expanding,   setExpanding]   = useState(false)
  const [preview,     setPreview]     = useState(null) // { title, body }
  const [previewTitle, setPreviewTitle] = useState('')
  const [previewBody,  setPreviewBody]  = useState('')
  const [saved,       setSaved]       = useState(false)
  const [error,       setError]       = useState(null)

  const reset = () => {
    setContent(''); setTitle(''); setPreview(null)
    setPreviewTitle(''); setPreviewBody(''); setSaved(false); setError(null)
  }

  const expandWithAI = async () => {
    if (!content.trim()) return
    setExpanding(true); setError(null); setPreview(null)
    try {
      const r = await fetch('/api/value-posts/coach-submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, title, subreddit, mode: 'expand' }),
      })
      const d = await r.json()
      if (d.ok && d.preview) {
        setPreview(d.preview)
        setPreviewTitle(d.preview.title || '')
        setPreviewBody(d.preview.body  || '')
      } else {
        setError(d.error || 'Expand failed')
      }
    } catch (e) { setError(String(e)) }
    setExpanding(false)
  }

  const savePost = async (mode, overrideContent, overrideTitle) => {
    setSubmitting(true); setError(null)
    try {
      const r = await fetch('/api/value-posts/coach-submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          content:   overrideContent ?? content,
          title:     overrideTitle   ?? title,
          subreddit,
          mode:      'as_is',
        }),
      })
      const d = await r.json()
      if (d.ok) { setSaved(true); onSaved?.(); setTimeout(() => { reset() }, 2000) }
      else       setError(d.error || 'Save failed')
    } catch (e) { setError(String(e)) }
    setSubmitting(false)
  }

  const formContent = (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Row 1: subreddit + optional title */}
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>SUBREDDIT</div>
              <select
                value={subreddit}
                onChange={e => setSubreddit(e.target.value)}
                style={{
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  color: 'var(--text-primary)', padding: '7px 12px',
                  borderRadius: 6, fontSize: 12, cursor: 'pointer',
                }}
              >
                {SUBREDDITS.map(s => <option key={s} value={s}>r/{s}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 220 }}>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>
                TITLE <span style={{ fontWeight: 400, opacity: 0.7 }}>(optional — AI will write one if blank)</span>
              </div>
              <input
                value={title}
                onChange={e => setTitle(e.target.value)}
                placeholder='e.g. "What blew up my account in month 2 — and how I fixed it"'
                style={{
                  width: '100%', background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 6, padding: '7px 12px', color: 'var(--text-primary)',
                  fontSize: 12, boxSizing: 'border-box',
                }}
              />
            </div>
          </div>

          {/* Row 2: content textarea */}
          <div>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>
              YOUR CONTENT
            </div>
            <textarea
              rows={6}
              value={content}
              onChange={e => setContent(e.target.value)}
              placeholder={'Paste anything — a lesson from today\'s trade, a pattern you noticed, a tip you gave a student, a tweet draft, a voice note transcript...\n\nExamples:\n• "Took 3 losses before 10am today. All three had the same flaw — I was trading size before the market showed me direction. Never again."\n• "The reason most traders lose in the first hour: they\'re trading FOMO, not setups."'}
              style={{
                width: '100%', background: 'var(--bg)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '10px 12px', color: 'var(--text-primary)',
                fontSize: 12, lineHeight: 1.7, resize: 'vertical', boxSizing: 'border-box',
                fontFamily: 'inherit',
              }}
            />
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
              {content.length} chars · {content.trim().split(/\s+/).filter(Boolean).length} words
            </div>
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <button
              onClick={() => savePost('as_is')}
              disabled={!content.trim() || submitting}
              style={{
                background: saved ? 'rgba(29,158,117,0.15)' : 'var(--bg)',
                color: saved ? 'var(--teal)' : 'var(--text-primary)',
                border: `1px solid ${saved ? 'rgba(29,158,117,0.4)' : 'var(--border)'}`,
                padding: '8px 18px', borderRadius: 6, fontSize: 12, fontWeight: 600,
                cursor: (!content.trim() || submitting) ? 'not-allowed' : 'pointer',
                opacity: !content.trim() ? 0.5 : 1,
              }}
            >
              {saved ? '✓ Saved as draft!' : submitting ? 'Saving…' : 'Post as-is →'}
            </button>

            <button
              onClick={expandWithAI}
              disabled={!content.trim() || expanding}
              style={{
                background: expanding
                  ? 'var(--border)'
                  : 'linear-gradient(135deg, #534AB7, #1D9E75)',
                color: expanding ? 'var(--text-tertiary)' : '#fff',
                border: 'none', padding: '8px 18px', borderRadius: 6,
                fontSize: 12, fontWeight: 700,
                cursor: (!content.trim() || expanding) ? 'not-allowed' : 'pointer',
                opacity: !content.trim() ? 0.5 : 1,
              }}
            >
              {expanding ? '⏳ AI expanding…' : '✨ AI Expand'}
            </button>

            {(content || title || preview) && (
              <button
                onClick={reset}
                style={{
                  background: 'transparent', color: 'var(--text-tertiary)',
                  border: '1px solid var(--border)', padding: '8px 14px',
                  borderRadius: 6, fontSize: 12, cursor: 'pointer', marginLeft: 'auto',
                }}
              >
                Clear
              </button>
            )}
          </div>

          {error && (
            <div style={{
              padding: '8px 12px', borderRadius: 6, fontSize: 12,
              background: 'rgba(216,90,48,0.1)', border: '1px solid rgba(216,90,48,0.3)',
              color: 'var(--coral)',
            }}>
              {error}
            </div>
          )}

          {/* AI Expand preview */}
          {preview && (
            <div style={{
              background: 'rgba(83,74,183,0.06)', border: '1px solid rgba(83,74,183,0.25)',
              borderRadius: 10, padding: 16, display: 'flex', flexDirection: 'column', gap: 12,
            }}>
              <div style={{
                display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4,
              }}>
                <span style={{ fontSize: 14 }}>✨</span>
                <span style={{ fontSize: 12, fontWeight: 700, color: '#8B82D4' }}>
                  Hermes expanded your content — edit before saving
                </span>
              </div>

              {/* Editable title */}
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>TITLE</div>
                <input
                  value={previewTitle}
                  onChange={e => setPreviewTitle(e.target.value)}
                  style={{
                    width: '100%', background: 'var(--bg)',
                    border: '1px solid rgba(83,74,183,0.4)',
                    borderRadius: 6, padding: '8px 12px', color: 'var(--text-primary)',
                    fontSize: 13, fontWeight: 600, boxSizing: 'border-box',
                  }}
                />
              </div>

              {/* Editable body */}
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>BODY</div>
                <textarea
                  rows={10}
                  value={previewBody}
                  onChange={e => setPreviewBody(e.target.value)}
                  style={{
                    width: '100%', background: 'var(--bg)',
                    border: '1px solid rgba(83,74,183,0.4)',
                    borderRadius: 6, padding: '10px 12px', color: 'var(--text-primary)',
                    fontSize: 12, lineHeight: 1.7, resize: 'vertical', boxSizing: 'border-box',
                    fontFamily: 'inherit',
                  }}
                />
              </div>

              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={() => savePost('as_is', previewBody, previewTitle)}
                  disabled={submitting}
                  style={{
                    background: saved ? 'rgba(29,158,117,0.15)' : 'var(--teal)',
                    color: saved ? 'var(--teal)' : '#000',
                    border: saved ? '1px solid rgba(29,158,117,0.4)' : 'none',
                    padding: '8px 20px', borderRadius: 6,
                    fontSize: 12, fontWeight: 700, cursor: submitting ? 'wait' : 'pointer',
                  }}
                >
                  {saved ? '✓ Saved!' : submitting ? 'Saving…' : 'Save as draft →'}
                </button>
                <button
                  onClick={() => setPreview(null)}
                  style={{
                    background: 'transparent', color: 'var(--text-tertiary)',
                    border: '1px solid var(--border)', padding: '8px 14px',
                    borderRadius: 6, fontSize: 12, cursor: 'pointer',
                  }}
                >
                  Discard
                </button>
              </div>
            </div>
          )}
        </div>
  )

  if (embedded) return formContent

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 12, marginBottom: 24, overflow: 'hidden',
    }}>
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 20px', cursor: 'pointer',
          borderBottom: open ? '1px solid var(--border)' : 'none',
        }}
      >
        <div style={{ fontSize: 18 }}>📝</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Add your own content</div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
            Paste a trade recap, lesson, quick tip, tweet — post as-is or let AI polish it
          </div>
        </div>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>{open ? '▲' : '▼'}</span>
      </div>
      {open && <div style={{ padding: 20 }}>{formContent}</div>}
    </div>
  )
}

// ── Topic Intelligence panel ──────────────────────────────────────────────────
function TopicIntelligence({ onSelectTopic, onBatchDone, embedded = false }) {
  const [topics,       setTopics]       = useState([])
  const [loading,      setLoading]      = useState(false)
  const [expanded,     setExpanded]     = useState(true)
  const [lastFetch,    setLastFetch]    = useState(null)
  const [batchCount,   setBatchCount]   = useState(5)
  const [batchPlatform, setBatchPlatform] = useState('both')
  const [batching,     setBatching]     = useState(false)
  const [batchResult,  setBatchResult]  = useState(null)

  useEffect(() => {
    fetch('/api/value-posts/topics')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (Array.isArray(d) && d.length > 0) { setTopics(d); setLastFetch(new Date()) }
      })
      .catch(() => {})
  }, [])

  const runBatch = async () => {
    setBatching(true)
    setBatchResult(null)
    try {
      const r = await fetch('/api/value-posts/generate-batch', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: batchCount, platform: batchPlatform }),
      })
      const d = await r.json()
      setBatchResult(d)
      if (d.ok && d.total > 0) onBatchDone?.()
    } catch (e) {
      setBatchResult({ ok: false, error: String(e) })
    }
    setBatching(false)
  }

  const maxCount = topics[0]?.count || 1

  // Heat color based on frequency rank
  const heatColor = (i) => {
    if (i === 0) return { bar: '#D85A30', text: '#D85A30', bg: 'rgba(216,90,48,0.12)', border: 'rgba(216,90,48,0.3)' }
    if (i <= 2)  return { bar: '#BA7517', text: '#BA7517', bg: 'rgba(186,117,23,0.10)', border: 'rgba(186,117,23,0.25)' }
    if (i <= 4)  return { bar: '#534AB7', text: '#8B82D4', bg: 'rgba(83,74,183,0.08)',  border: 'rgba(83,74,183,0.20)' }
    return              { bar: '#1D9E75', text: '#1D9E75', bg: 'rgba(29,158,117,0.08)', border: 'rgba(29,158,117,0.20)' }
  }

  const PLATFORM_OPTS = [
    { key: 'both',   label: 'Reddit + X', color: '#534AB7' },
    { key: 'reddit', label: 'Reddit only', color: '#FF6314' },
    { key: 'x',      label: 'X only',     color: '#1D9BF0' },
  ]

  const BatchControls = () => (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
      {/* Platform toggle */}
      <div style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)' }}>
        {PLATFORM_OPTS.map(p => (
          <button
            key={p.key}
            onClick={() => setBatchPlatform(p.key)}
            disabled={batching}
            style={{
              padding: '5px 10px', border: 'none', fontSize: 10, fontWeight: 700,
              cursor: batching ? 'default' : 'pointer',
              background: batchPlatform === p.key ? p.color : 'var(--bg)',
              color: batchPlatform === p.key ? '#fff' : 'var(--text-tertiary)',
              transition: 'all 0.15s',
            }}
          >
            {p.label}
          </button>
        ))}
      </div>
      {/* Count select */}
      <select
        value={batchCount}
        onChange={e => setBatchCount(Number(e.target.value))}
        disabled={batching}
        style={{
          background: 'var(--bg)', border: '1px solid var(--border)',
          color: 'var(--text-secondary)', padding: '5px 8px',
          borderRadius: 6, fontSize: 11, cursor: 'pointer',
        }}
      >
        {[3, 5, 8].map(n => <option key={n} value={n}>{n} pieces</option>)}
      </select>
      <button
        onClick={runBatch}
        disabled={batching}
        style={{
          background: batching ? 'var(--border)' : 'linear-gradient(135deg, #534AB7, #1D9E75)',
          color: batching ? 'var(--text-tertiary)' : '#fff',
          border: 'none', padding: '6px 14px', borderRadius: 6,
          fontSize: 11, fontWeight: 700, cursor: batching ? 'wait' : 'pointer',
          whiteSpace: 'nowrap',
        }}
      >
        {batching ? '⏳ Generating…' : '⚡ Generate batch'}
      </button>
    </div>
  )

  const TopicList = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {loading ? (
        <div style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>Analyzing stream data…</div>
      ) : topics.map((t, i) => {
        const heat = heatColor(i)
        const pct  = Math.round((t.count / maxCount) * 100)
        return (
          <div key={t.signal} style={{
            display: 'flex', alignItems: 'center', gap: 12,
            padding: '10px 14px', borderRadius: 8,
            background: heat.bg, border: `1px solid ${heat.border}`,
          }}>
            <div style={{ fontSize: 11, fontWeight: 800, color: heat.text, width: 18, textAlign: 'center', flexShrink: 0 }}>
              {i === 0 ? '🔥' : `#${i + 1}`}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{t.signal}</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: heat.text, background: heat.bg, border: `1px solid ${heat.border}`, padding: '1px 6px', borderRadius: 10 }}>
                  {t.count} posts
                </span>
                {t.subreddits?.slice(0, 2).map(s => (
                  <span key={s} style={{ fontSize: 10, color: 'var(--text-tertiary)', background: 'var(--bg)', border: '1px solid var(--border)', padding: '1px 6px', borderRadius: 4 }}>
                    r/{s}
                  </span>
                ))}
              </div>
              <div style={{ height: 3, background: 'var(--border)', borderRadius: 2 }}>
                <div style={{ height: '100%', width: `${pct}%`, background: heat.bar, borderRadius: 2, transition: 'width 0.6s ease' }} />
              </div>
              {t.example_post && (
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 5, fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  "{t.example_post}"
                </div>
              )}
            </div>
            <button
              onClick={() => onSelectTopic(t.signal, t.top_subreddit || t.subreddits?.[0] || 'Daytrading')}
              style={{ background: heat.bg, color: heat.text, border: `1px solid ${heat.border}`, padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0 }}
            >
              ✨ Use →
            </button>
          </div>
        )
      })}
    </div>
  )

  const BatchBanner = () => {
    if (!batchResult) return null
    const redditCount = batchResult.created?.filter(c => c.platform === 'reddit').length || 0
    const xCount      = batchResult.created?.filter(c => c.platform === 'x').length || 0
    const breakdown   = batchResult.ok && batchResult.total > 0
      ? [
          redditCount > 0 ? `${redditCount} Reddit post${redditCount > 1 ? 's' : ''}` : null,
          xCount > 0      ? `${xCount} X thread${xCount > 1 ? 's' : ''}` : null,
        ].filter(Boolean).join(' + ')
      : null
    return (
      <div style={{
        marginBottom: 12, padding: '10px 14px', borderRadius: 7,
        background: batchResult.ok ? 'rgba(29,158,117,0.10)' : 'rgba(216,90,48,0.10)',
        border: `1px solid ${batchResult.ok ? 'rgba(29,158,117,0.3)' : 'rgba(216,90,48,0.3)'}`,
        color: batchResult.ok ? 'var(--teal)' : 'var(--coral)',
        fontSize: 12, fontWeight: 600,
        display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
      }}>
        <div>
          {batchResult.ok
            ? <span>✓ {breakdown || `${batchResult.total} pieces`} drafted — scroll down to review</span>
            : <span>✗ {batchResult.error || 'Batch failed'}</span>
          }
          {batchResult.errors?.length > 0 && (
            <span style={{ marginLeft: 10, fontSize: 10, opacity: 0.7 }}>
              ({batchResult.errors.length} failed)
            </span>
          )}
        </div>
        <button onClick={() => setBatchResult(null)} style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontSize: 14, flexShrink: 0 }}>✕</button>
      </div>
    )
  }

  if (embedded) {
    return (
      <div>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12, flexWrap: 'wrap', gap: 8 }}>
          <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
            🔥 Trending pain signals from stream data — click "Use →" to pre-fill Generate tab
            {lastFetch && ` · ${new Date(lastFetch).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`}
          </span>
          <BatchControls />
        </div>
        <BatchBanner />
        <TopicList />
      </div>
    )
  }

  return (
    <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, marginBottom: 20, overflow: 'hidden' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '14px 20px', borderBottom: expanded ? '1px solid var(--border)' : 'none' }}>
        <div onClick={() => setExpanded(e => !e)} style={{ display: 'flex', alignItems: 'center', gap: 10, flex: 1, cursor: 'pointer' }}>
          <span style={{ fontSize: 16 }}>🔥</span>
          <div>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Topic Intelligence</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 1 }}>
              Trending pain signals · click to generate
              {lastFetch && ` · ${new Date(lastFetch).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}`}
            </div>
          </div>
        </div>
        <BatchControls />
        <span onClick={() => setExpanded(e => !e)} style={{ fontSize: 12, color: 'var(--text-tertiary)', cursor: 'pointer', marginLeft: 4 }}>{expanded ? '▲' : '▼'}</span>
      </div>
      {batchResult && <div style={{ padding: '8px 20px 0' }}><BatchBanner /></div>}
      {expanded && <div style={{ padding: '14px 20px' }}><TopicList /></div>}
    </div>
  )
}

// ── X Thread modal ────────────────────────────────────────────────────────────
function XThreadPreviewModal({ thread, onClose }) {
  const [copied, setCopied] = useState({})

  const copyTweet = async (i, text) => {
    await navigator.clipboard.writeText(text)
    setCopied(prev => ({ ...prev, [i]: true }))
    setTimeout(() => setCopied(prev => ({ ...prev, [i]: false })), 2000)
  }

  const copyAll = async () => {
    const all = (thread.tweets || []).join('\n\n')
    await navigator.clipboard.writeText(all)
    setCopied({ all: true })
    setTimeout(() => setCopied({}), 2500)
  }

  useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose() }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      onClick={onClose}
      style={{ position: 'fixed', inset: 0, zIndex: 1000, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', backdropFilter: 'blur(2px)' }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 14, width: 640, maxWidth: '95vw', maxHeight: '90vh', display: 'flex', flexDirection: 'column', overflow: 'hidden', boxShadow: '0 24px 60px rgba(0,0,0,0.5)' }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div>
            <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              𝕏 Thread — {thread.tweet_count} tweets
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
              Copy tweet by tweet, then reply to yourself for each one
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              onClick={copyAll}
              style={{
                background: copied.all ? 'rgba(29,155,240,0.15)' : 'rgba(29,155,240,0.1)',
                color: '#1D9BF0', border: '1px solid rgba(29,155,240,0.3)',
                padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 700, cursor: 'pointer',
              }}
            >
              {copied.all ? '✓ All copied!' : '📋 Copy all'}
            </button>
            <button onClick={onClose} style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', fontSize: 18, cursor: 'pointer', padding: '4px 8px', borderRadius: 6 }}>✕</button>
          </div>
        </div>

        {/* Tweets */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 20, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {(thread.tweets || []).map((tweet, i) => (
            <div key={i} style={{
              background: i === 0 ? 'rgba(29,155,240,0.06)' : 'var(--bg)',
              border: `1px solid ${i === 0 ? 'rgba(29,155,240,0.3)' : 'var(--border)'}`,
              borderRadius: 8, padding: '10px 12px',
              position: 'relative',
            }}>
              <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                <span style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.05em',
                  color: i === 0 ? '#1D9BF0' : 'var(--text-tertiary)',
                }}>
                  {i === 0 ? 'HOOK · TWEET 1' : `TWEET ${i + 1}`} · {tweet.length}/280
                </span>
                <button
                  onClick={() => copyTweet(i, tweet)}
                  style={{
                    background: copied[i] ? 'rgba(29,155,240,0.15)' : 'var(--card)',
                    color: copied[i] ? '#1D9BF0' : 'var(--text-tertiary)',
                    border: `1px solid ${copied[i] ? '#1D9BF0' : 'var(--border)'}`,
                    padding: '2px 8px', borderRadius: 4, fontSize: 10,
                    fontWeight: 600, cursor: 'pointer', flexShrink: 0,
                  }}
                >
                  {copied[i] ? '✓' : '📋'}
                </button>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>
                {tweet}
              </div>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
            Tip: Post tweet 1 in X, then reply to your own tweet for each subsequent tweet to build the thread.
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Generate Tab — zero-input by default, advanced fields collapsible ─────────
function IdeaValidator({ onGenerated }) {
  const [idea,         setIdea]         = useState('')
  const [platform,     setPlatform]     = useState('reddit')
  const [validating,   setValidating]   = useState(false)
  const [verdict,      setVerdict]      = useState(null)
  const [validErr,     setValidErr]     = useState(null)
  const [refinedAngle, setRefinedAngle] = useState('')
  const [writing,      setWriting]      = useState(false)
  const [written,      setWritten]      = useState(null)

  const scoreColor = !verdict ? '#888'
    : verdict.score >= 75 ? 'var(--teal)'
    : verdict.score >= 50 ? '#F5A623'
    : 'var(--coral)'

  const verdictLabel = !verdict ? ''
    : verdict.verdict === 'strong' ? '✅ Strong signal'
    : verdict.verdict === 'refine' ? '⚡ Needs sharpening'
    : '⚠ Skip this one'

  const validate = async () => {
    if (!idea.trim()) return
    setValidating(true); setVerdict(null); setValidErr(null); setWritten(null)
    try {
      const r = await fetch('/api/value-posts/validate-idea', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ idea: idea.trim(), platform }),
      })
      const d = await r.json()
      if (!r.ok) throw new Error(d.error || 'Validation failed')
      setVerdict(d)
      setRefinedAngle(d.refined_angle || idea)
    } catch (e) {
      setValidErr(e.message)
    } finally {
      setValidating(false)
    }
  }

  const writeIt = async () => {
    setWriting(true); setValidErr(null)
    try {
      const r = await fetch('/api/value-posts/from-idea', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          idea:          idea.trim(),
          refined_angle: refinedAngle.trim(),
          subreddit:     verdict?.best_subreddit || 'Daytrading',
          platform,
        }),
      })
      const d = await r.json()
      if (!r.ok || !d.ok) throw new Error(d.error || 'Generation failed')
      setWritten(d.created)
      sendPush('Post ready to review 📋', `"${idea.slice(0, 55)}…" is in the Queue.`)
      onGenerated?.()
    } catch (e) {
      setValidErr(e.message)
    } finally {
      setWriting(false)
    }
  }

  const reset = () => { setIdea(''); setVerdict(null); setWritten(null); setValidErr(null) }

  return (
    <div style={{ marginBottom: 20, padding: 16, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10 }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10, display: 'flex', alignItems: 'center', gap: 6 }}>
        💡 Your idea
        <span style={{ fontSize: 10, fontWeight: 400, color: 'var(--text-tertiary)' }}>— write it, we'll validate and find the best home for it</span>
      </div>

      <textarea
        value={idea}
        onChange={e => { setIdea(e.target.value); if (verdict) setVerdict(null) }}
        disabled={validating || writing}
        placeholder='Describe your idea in plain language — e.g. "traders are sizing up on green days and giving back everything by close. nobody talks about this as a specific position sizing trap"'
        rows={3}
        style={{
          width: '100%', boxSizing: 'border-box',
          background: 'var(--bg)', border: `1px solid ${idea.trim() ? 'rgba(29,158,117,0.45)' : 'var(--border)'}`,
          borderRadius: 7, padding: '10px 12px', color: 'var(--text-primary)',
          fontSize: 13, lineHeight: 1.55, resize: 'vertical',
        }}
      />

      <div style={{ display: 'flex', gap: 8, marginTop: 8, alignItems: 'center' }}>
        {['reddit', 'x'].map(p => (
          <button key={p} onClick={() => setPlatform(p)} style={{
            padding: '5px 14px', borderRadius: 20, fontSize: 11, fontWeight: 700, cursor: 'pointer',
            border: platform === p ? 'none' : '1px solid var(--border)',
            background: platform === p ? (p === 'reddit' ? '#FF6314' : '#1D9BF0') : 'transparent',
            color: platform === p ? '#fff' : 'var(--text-tertiary)',
          }}>{p === 'reddit' ? '🟠 Reddit' : '𝕏 X Thread'}</button>
        ))}
        <div style={{ flex: 1 }} />
        <button
          onClick={validate}
          disabled={!idea.trim() || validating || writing}
          style={{
            background: !idea.trim() || validating ? 'var(--border)' : 'linear-gradient(135deg,#534AB7,#3B34A0)',
            color: !idea.trim() || validating ? 'var(--text-tertiary)' : '#fff',
            border: 'none', borderRadius: 7, padding: '8px 20px',
            fontSize: 12, fontWeight: 700, cursor: !idea.trim() || validating ? 'default' : 'pointer',
          }}
        >
          {validating ? '⏳ Scanning communities…' : '🔍 Validate idea'}
        </button>
      </div>

      {validErr && (
        <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 6, background: 'rgba(216,90,48,0.1)', color: 'var(--coral)', fontSize: 12 }}>
          ⚠ {validErr}
        </div>
      )}

      {verdict && !written && (
        <div style={{ marginTop: 14, padding: 14, background: 'var(--bg)', borderRadius: 8, border: `2px solid ${scoreColor}40` }}>
          {/* Score + verdict */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 14, marginBottom: 14, paddingBottom: 14, borderBottom: '1px solid var(--border)' }}>
            <div style={{ textAlign: 'center', minWidth: 52 }}>
              <div style={{ fontSize: 32, fontWeight: 900, color: scoreColor, lineHeight: 1 }}>{verdict.score}</div>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>/ 100</div>
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 13, fontWeight: 700, color: scoreColor, marginBottom: 3 }}>{verdictLabel}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.4 }}>{verdict.verdict_reason}</div>
            </div>
            <div style={{ padding: '6px 12px', borderRadius: 20, background: '#FF631418', color: '#FF6314', fontSize: 11, fontWeight: 700, whiteSpace: 'nowrap' }}>
              r/{verdict.best_subreddit}
            </div>
          </div>

          {/* Detail rows */}
          {[
            { label: '🎯 Pain alignment', text: verdict.pain_alignment },
            { label: '🔬 Specificity',    text: verdict.specificity_note },
            { label: '📊 Gap analysis',   text: verdict.gap_note },
            { label: '📍 Best subreddit', text: verdict.subreddit_reason },
          ].map((row, i) => (
            <div key={i} style={{ marginBottom: 10, paddingBottom: 10, borderBottom: i < 3 ? '1px solid var(--border)' : 'none' }}>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 3 }}>{row.label}</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{row.text}</div>
            </div>
          ))}

          {/* Refined angle — editable */}
          <div style={{ marginTop: 4, marginBottom: 14 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--teal)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 6 }}>
              ✨ Refined angle — edit before writing
            </div>
            <textarea
              value={refinedAngle}
              onChange={e => setRefinedAngle(e.target.value)}
              rows={2}
              style={{
                width: '100%', boxSizing: 'border-box',
                background: 'rgba(29,158,117,0.06)', border: '1px solid rgba(29,158,117,0.35)',
                borderRadius: 6, padding: '9px 11px', color: 'var(--text-primary)',
                fontSize: 12, lineHeight: 1.5, resize: 'vertical',
              }}
            />
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={writeIt}
              disabled={writing}
              style={{
                flex: 1, padding: '11px 0', borderRadius: 7, border: 'none',
                background: writing ? 'var(--border)' : 'var(--teal)',
                color: writing ? 'var(--text-tertiary)' : '#000',
                fontSize: 13, fontWeight: 700, cursor: writing ? 'wait' : 'pointer',
              }}
            >{writing ? '⏳ Writing your post…' : '✨ Write it →'}</button>
            <button
              onClick={reset}
              style={{
                padding: '11px 18px', borderRadius: 7, border: '1px solid var(--border)',
                background: 'transparent', color: 'var(--text-tertiary)', fontSize: 12, cursor: 'pointer',
              }}
            >← New idea</button>
          </div>
        </div>
      )}

      {written && (
        <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 8, background: 'rgba(29,158,117,0.10)', border: '1px solid rgba(29,158,117,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <div>
            <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--teal)' }}>✓ Post drafted — check the Queue tab</div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
              {written.platform === 'x' ? `𝕏 ${written.tweet_count || 6}-tweet thread` : `🟠 r/${written.subreddit}`} — "{(written.title || '').slice(0, 75)}…"
            </div>
          </div>
          <button onClick={reset} style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 14, flexShrink: 0 }}>✕</button>
        </div>
      )}
    </div>
  )
}

function GenerateTab({
  genPlatform, setGenPlatform,
  subreddit, setSubreddit, genType, setGenType, topic, setTopic,
  generating, genError, onGenerate,
  xTopic, setXTopic, xNiche, setXNiche, xHookStyle, setXHookStyle,
  xGenerating, xError, xThread, xSaving, xSaved,
  generateThread, saveThread, setShowXPreview, onSaved,
}) {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [autoRunning,  setAutoRunning]  = useState(false)
  const [autoResult,   setAutoResult]   = useState(null)
  const [autoError,    setAutoError]    = useState(null)

  const runAuto = async (plat) => {
    setAutoRunning(true); setAutoResult(null); setAutoError(null)
    try {
      const r = await fetch('/api/value-posts/auto-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ platform: plat }),
      })
      const d = await r.json()
      if (d.ok) {
        setAutoResult(d.created)
        onSaved?.()
        sendPush('Post ready to review 📋', `Your ${plat === 'x' ? 'X thread' : 'Reddit post'} is in the Queue.`)
      }
      else setAutoError(d.error || 'Generation failed')
    } catch (e) { setAutoError(String(e)) }
    setAutoRunning(false)
  }

  const busy = autoRunning || generating || xGenerating

  return (
    <div style={{ padding: 20 }}>
      {/* Idea Validator — primary CTA */}
      <IdeaValidator onGenerated={onSaved} />

      {/* Divider */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
        <span style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 600, whiteSpace: 'nowrap' }}>or auto-generate from live signals</span>
        <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
      </div>

      {/* Hero auto-generate row */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        <button onClick={() => runAuto('reddit')} disabled={busy} style={{
          flex: 1, padding: '14px 0', borderRadius: 8, border: 'none',
          background: busy ? 'var(--border)' : 'linear-gradient(135deg, #FF6314 0%, #D85A30 100%)',
          color: busy ? 'var(--text-tertiary)' : '#fff',
          fontSize: 13, fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
        }}>
          <span>{autoRunning ? '⏳' : '🤖'} {autoRunning ? 'Writing…' : 'Auto-write Reddit post'}</span>
          <span style={{ fontSize: 10, fontWeight: 400, opacity: 0.85 }}>AI picks signal + subreddit</span>
        </button>

        <button onClick={() => runAuto('x')} disabled={busy} style={{
          flex: 1, padding: '14px 0', borderRadius: 8, border: 'none',
          background: busy ? 'var(--border)' : 'linear-gradient(135deg, #1D9BF0 0%, #0D6EBF 100%)',
          color: busy ? 'var(--text-tertiary)' : '#fff',
          fontSize: 13, fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
        }}>
          <span>{autoRunning ? '⏳' : '𝕏'} {autoRunning ? 'Writing…' : 'Auto-write X thread'}</span>
          <span style={{ fontSize: 10, fontWeight: 400, opacity: 0.85 }}>AI picks signal + niche</span>
        </button>

        <button onClick={() => runAuto('auto')} disabled={busy} style={{
          padding: '14px 16px', borderRadius: 8,
          border: '1px solid var(--border)',
          background: busy ? 'var(--border)' : 'var(--card)',
          color: busy ? 'var(--text-tertiary)' : 'var(--text-secondary)',
          fontSize: 11, fontWeight: 700, cursor: busy ? 'wait' : 'pointer',
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3, whiteSpace: 'nowrap',
        }}>
          <span>⚡ Best signal</span>
          <span style={{ fontSize: 9, fontWeight: 400, opacity: 0.7 }}>Auto picks platform</span>
        </button>
      </div>

      {autoResult && (
        <div style={{ marginBottom: 14, padding: '10px 14px', borderRadius: 7, background: 'rgba(29,158,117,0.10)', border: '1px solid rgba(29,158,117,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10 }}>
          <div>
            <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--teal)' }}>
              ✓ {autoResult.platform === 'x' ? `𝕏 ${autoResult.tweet_count}-tweet thread` : '🟠 Reddit post'} drafted
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)', marginLeft: 10 }}>Signal: "{autoResult.signal}"</span>
          </div>
          <button onClick={() => setAutoResult(null)} style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 14, flexShrink: 0 }}>✕</button>
        </div>
      )}
      {autoError && (
        <div style={{ marginBottom: 14, padding: '8px 12px', borderRadius: 6, background: 'rgba(216,90,48,0.1)', border: '1px solid rgba(216,90,48,0.3)', color: 'var(--coral)', fontSize: 12 }}>{autoError}</div>
      )}

      <button onClick={() => setShowAdvanced(s => !s)} style={{ background: 'transparent', border: 'none', padding: 0, color: 'var(--text-tertiary)', fontSize: 11, cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 5 }}>
        {showAdvanced ? '▲' : '▼'} Advanced — override topic, subreddit, hook style
      </button>

      {showAdvanced && (
        <div style={{ marginTop: 14, paddingTop: 14, borderTop: '1px solid var(--border)' }}>
          <PlatformToggle value={genPlatform} onChange={setGenPlatform} />

          {genPlatform === 'reddit' && (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>SUBREDDIT</div>
                <select value={subreddit} onChange={e => setSubreddit(e.target.value)} style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                  {SUBREDDITS.map(s => <option key={s} value={s}>r/{s}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>TYPE</div>
                <select value={genType} onChange={e => setGenType(e.target.value)} style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                  <option value="insight_digest">📊 Insight digest</option>
                  <option value="resource_post">📋 Resource / checklist</option>
                </select>
              </div>
              <div style={{ flex: 1, minWidth: 180 }}>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>TOPIC <span style={{ fontWeight: 400, opacity: 0.7 }}>(optional)</span></div>
                <input value={topic} onChange={e => setTopic(e.target.value)} placeholder='e.g. revenge trading (blank = AI picks)'
                  style={{ width: '100%', background: 'var(--bg)', border: `1px solid ${topic ? 'rgba(29,158,117,0.4)' : 'var(--border)'}`, borderRadius: 6, padding: '7px 12px', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }} />
              </div>
              <button onClick={onGenerate} disabled={generating} style={{ background: generating ? 'var(--border)' : 'var(--teal)', color: generating ? 'var(--text-tertiary)' : '#000', border: 'none', padding: '8px 18px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: generating ? 'wait' : 'pointer', whiteSpace: 'nowrap' }}>
                {generating ? '⏳…' : '✨ Generate'}
              </button>
            </div>
          )}

          {genPlatform === 'x' && (
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <div style={{ flex: 1, minWidth: 180 }}>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>TOPIC <span style={{ fontWeight: 400, opacity: 0.7 }}>(optional)</span></div>
                <input value={xTopic} onChange={e => setXTopic(e.target.value)} onKeyDown={e => e.key === 'Enter' && generateThread()} placeholder='e.g. revenge trading (blank = AI picks)'
                  style={{ width: '100%', background: 'var(--bg)', border: `1px solid ${xTopic ? 'rgba(29,155,240,0.4)' : 'var(--border)'}`, borderRadius: 6, padding: '7px 12px', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }} />
              </div>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>NICHE</div>
                <select value={xNiche} onChange={e => setXNiche(e.target.value)} style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                  {NICHE_OPTS.map(n => <option key={n.value} value={n.value}>{n.label}</option>)}
                </select>
              </div>
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>HOOK</div>
                <select value={xHookStyle} onChange={e => setXHookStyle(e.target.value)} style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                  <option value="contrarian">Contrarian</option>
                  <option value="story">Mini story</option>
                  <option value="list">List</option>
                </select>
              </div>
              <button onClick={() => generateThread()} disabled={xGenerating} style={{ background: xGenerating ? 'var(--border)' : '#1D9BF0', color: xGenerating ? 'var(--text-tertiary)' : '#fff', border: 'none', padding: '8px 18px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: xGenerating ? 'wait' : 'pointer', whiteSpace: 'nowrap' }}>
                {xGenerating ? '⏳…' : '𝕏 Generate'}
              </button>
            </div>
          )}

          {genError && <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 6, background: 'rgba(216,90,48,0.1)', border: '1px solid rgba(216,90,48,0.3)', color: 'var(--coral)', fontSize: 12 }}>{genError}</div>}
          {xError   && <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 6, background: 'rgba(216,90,48,0.1)', border: '1px solid rgba(216,90,48,0.3)', color: 'var(--coral)', fontSize: 12 }}>{xError}</div>}

          {xThread && (
            <div style={{ marginTop: 14, padding: 12, background: 'rgba(29,155,240,0.05)', border: '1px solid rgba(29,155,240,0.2)', borderRadius: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                <span style={{ fontSize: 11, fontWeight: 700, color: '#1D9BF0' }}>𝕏 {xThread.tweet_count}-tweet thread ready</span>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button onClick={() => setShowXPreview(true)} style={{ background: 'transparent', border: '1px solid rgba(29,155,240,0.3)', color: '#1D9BF0', padding: '4px 10px', borderRadius: 5, fontSize: 11, cursor: 'pointer' }}>Preview →</button>
                  <button onClick={() => saveThread(xThread)} disabled={xSaving || xSaved}
                    style={{ background: xSaved ? 'rgba(29,158,117,0.15)' : 'rgba(29,155,240,0.15)', color: xSaved ? '#1D9E75' : '#1D9BF0', border: `1px solid ${xSaved ? 'rgba(29,158,117,0.4)' : 'rgba(29,155,240,0.4)'}`, padding: '4px 12px', borderRadius: 5, fontSize: 11, fontWeight: 700, cursor: xSaving ? 'wait' : 'pointer' }}>
                    {xSaved ? '✓ Saved' : xSaving ? '…' : '💾 Save'}
                  </button>
                </div>
              </div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontStyle: 'italic', borderLeft: '2px solid rgba(29,155,240,0.4)', paddingLeft: 10 }}>Hook: {xThread.hook}</div>
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 14, fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>
        All content is drafted only — never auto-posted. Your rep copies + pastes manually.
      </div>
    </div>
  )
}

// ── Create Panel (tabbed: Generate | My Content | Batch | X Thread) ───────────
const NICHE_OPTS = [
  { value: 'daytrading',    label: 'Day trading' },
  { value: 'futures',       label: 'Futures' },
  { value: 'swing-trading', label: 'Swing trading' },
  { value: 'crypto',        label: 'Crypto' },
  { value: 'options',       label: 'Options' },
  { value: 'trading',       label: 'General trading' },
]

function PlatformToggle({ value, onChange }) {
  return (
    <div style={{ display: 'flex', borderRadius: 6, overflow: 'hidden', border: '1px solid var(--border)', marginBottom: 16 }}>
      {[
        { key: 'reddit', label: '🟠 Reddit' },
        { key: 'x',      label: '𝕏 X / Twitter' },
      ].map(p => (
        <button
          key={p.key}
          onClick={() => onChange(p.key)}
          style={{
            flex: 1, padding: '7px 0', border: 'none', fontSize: 11, fontWeight: 700,
            cursor: 'pointer',
            background: value === p.key ? (p.key === 'reddit' ? '#FF6314' : '#1D9BF0') : 'var(--bg)',
            color: value === p.key ? '#fff' : 'var(--text-tertiary)',
            transition: 'all 0.15s',
          }}
        >
          {p.label}
        </button>
      ))}
    </div>
  )
}

function CreatePanel({
  subreddit, setSubreddit, genType, setGenType, topic, setTopic,
  generating, genError, onGenerate, onSaved, onBatchDone,
}) {
  const [activeTab,      setActiveTab]      = useState('generate')
  const [genPlatform,    setGenPlatform]    = useState('reddit')
  const [myPlatform,     setMyPlatform]     = useState('reddit')
  const [xTopic,         setXTopic]         = useState('')
  const [xNiche,         setXNiche]         = useState('daytrading')
  const [xHookStyle,     setXHookStyle]     = useState('contrarian')
  const [xGenerating,    setXGenerating]    = useState(false)
  const [xThread,        setXThread]        = useState(null)
  const [xError,         setXError]         = useState(null)
  const [showXPreview,   setShowXPreview]   = useState(false)
  const [xSaving,        setXSaving]        = useState(false)
  const [xSaved,         setXSaved]         = useState(false)
  // My Content X mode
  const [myContent,      setMyContent]      = useState('')
  const [myNiche,        setMyNiche]        = useState('daytrading')
  const [myExpanding,    setMyExpanding]    = useState(false)
  const [myXThread,      setMyXThread]      = useState(null)
  const [myXPreview,     setMyXPreview]     = useState(false)
  const [myXError,       setMyXError]       = useState(null)

  const handleTopicSelect = useCallback((signal, sub) => {
    setTopic(signal)
    setSubreddit(SUBREDDITS.includes(sub) ? sub : 'Daytrading')
    setGenType('insight_digest')
    setGenPlatform('reddit')
    setActiveTab('generate')
  }, [setTopic, setSubreddit, setGenType])

  const generateThread = async (topicOverride, nicheOverride, hookOverride) => {
    const t = topicOverride ?? xTopic
    const n = nicheOverride ?? xNiche
    const h = hookOverride  ?? xHookStyle
    if (!t.trim()) return
    setXGenerating(true); setXError(null); setXThread(null); setXSaved(false)
    try {
      const r = await fetch('/api/value-posts/generate-thread', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: t, niche: n, hook_style: h }),
      })
      const d = await r.json()
      if (d.ok && d.thread) { setXThread(d.thread); setShowXPreview(true) }
      else setXError(d.error || 'Generation failed')
    } catch (e) { setXError(String(e)) }
    setXGenerating(false)
  }

  const saveThread = async (thread) => {
    setXSaving(true)
    try {
      const r = await fetch('/api/value-posts/save-thread', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ thread }),
      })
      const d = await r.json()
      if (d.ok) { setXSaved(true); onSaved?.() }
    } catch {}
    setXSaving(false)
  }

  const expandToThread = async () => {
    if (!myContent.trim()) return
    setMyExpanding(true); setMyXError(null); setMyXThread(null)
    try {
      const r = await fetch('/api/value-posts/expand-to-thread', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content: myContent, niche: myNiche }),
      })
      const d = await r.json()
      if (d.ok && d.thread) { setMyXThread(d.thread); setMyXPreview(true); onSaved?.() }
      else setMyXError(d.error || 'Expansion failed')
    } catch (e) { setMyXError(String(e)) }
    setMyExpanding(false)
  }

  const TABS = [
    { key: 'generate',  label: '✨ Generate',   desc: 'AI writes from pain signals' },
    { key: 'content',   label: '📝 My Content', desc: 'Paste your own, expand with AI' },
    { key: 'batch',     label: '⚡ Batch',       desc: 'Use Topic Intelligence' },
    { key: 'x-thread',  label: '𝕏 X Thread',   desc: 'Generate a native tweet thread' },
  ]

  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 12, marginBottom: 24, overflow: 'hidden',
    }}>
      {/* Tab bar */}
      <div style={{
        display: 'flex', borderBottom: '1px solid var(--border)',
        padding: '0 4px',
      }}>
        {TABS.map(t => (
          <button
            key={t.key}
            onClick={() => setActiveTab(t.key)}
            style={{
              background: 'transparent', border: 'none',
              borderBottom: activeTab === t.key ? '2px solid var(--teal)' : '2px solid transparent',
              padding: '12px 16px', cursor: 'pointer',
              fontSize: 12, fontWeight: activeTab === t.key ? 700 : 500,
              color: activeTab === t.key ? 'var(--text-primary)' : 'var(--text-tertiary)',
              display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start',
              transition: 'color 0.15s',
            }}
          >
            {t.label}
            <span style={{ fontSize: 9, fontWeight: 400, opacity: 0.7 }}>{t.desc}</span>
          </button>
        ))}
      </div>

      {/* Generate tab */}
      {activeTab === 'generate' && (
        <GenerateTab
          genPlatform={genPlatform} setGenPlatform={setGenPlatform}
          subreddit={subreddit} setSubreddit={setSubreddit}
          genType={genType} setGenType={setGenType}
          topic={topic} setTopic={setTopic}
          generating={generating} genError={genError} onGenerate={onGenerate}
          xTopic={xTopic} setXTopic={setXTopic}
          xNiche={xNiche} setXNiche={setXNiche}
          xHookStyle={xHookStyle} setXHookStyle={setXHookStyle}
          xGenerating={xGenerating} xError={xError} xThread={xThread}
          xSaving={xSaving} xSaved={xSaved}
          generateThread={generateThread} saveThread={saveThread}
          setShowXPreview={setShowXPreview}
          onSaved={onSaved}
        />
      )}

      {/* My Content tab */}
      {activeTab === 'content' && (
        <div style={{ padding: 20 }}>
          <PlatformToggle value={myPlatform} onChange={setMyPlatform} />
          {myPlatform === 'reddit' && <CoachContent subreddits={SUBREDDITS} onSaved={onSaved} embedded />}
          {myPlatform === 'x' && (
            <>
              <div style={{ marginBottom: 10 }}>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>YOUR CONTENT</div>
                <textarea value={myContent} onChange={e => setMyContent(e.target.value)} rows={5}
                  placeholder="Paste a trade recap, lesson, quick tip, or rough thought — AI will expand it into a 6-tweet thread in your voice"
                  style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '10px 12px', color: 'var(--text-primary)', fontSize: 12, resize: 'vertical', boxSizing: 'border-box', lineHeight: 1.6 }} />
              </div>
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-end' }}>
                <div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>NICHE</div>
                  <select value={myNiche} onChange={e => setMyNiche(e.target.value)}
                    style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
                    {NICHE_OPTS.map(n => <option key={n.value} value={n.value}>{n.label}</option>)}
                  </select>
                </div>
                <button onClick={expandToThread} disabled={myExpanding || !myContent.trim()}
                  style={{ background: myExpanding ? 'var(--border)' : '#1D9BF0', color: myExpanding ? 'var(--text-tertiary)' : '#fff', border: 'none', padding: '8px 20px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: myExpanding ? 'wait' : 'pointer', whiteSpace: 'nowrap' }}>
                  {myExpanding ? '⏳ Expanding…' : '𝕏 Expand to thread'}
                </button>
              </div>
              {myXError && <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, background: 'rgba(216,90,48,0.1)', border: '1px solid rgba(216,90,48,0.3)', color: 'var(--coral)', fontSize: 12 }}>{myXError}</div>}
              {myXThread && (
                <div style={{ marginTop: 14, padding: 14, background: 'rgba(29,155,240,0.05)', border: '1px solid rgba(29,155,240,0.2)', borderRadius: 8 }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#1D9BF0' }}>✓ {myXThread.tweet_count}-tweet thread saved to drafts</span>
                    <button onClick={() => setMyXPreview(true)} style={{ background: 'transparent', border: '1px solid rgba(29,155,240,0.3)', color: '#1D9BF0', padding: '4px 10px', borderRadius: 5, fontSize: 11, cursor: 'pointer' }}>Preview →</button>
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-secondary)', fontStyle: 'italic', borderLeft: '2px solid rgba(29,155,240,0.4)', paddingLeft: 10 }}>
                    Hook: {myXThread.hook}
                  </div>
                </div>
              )}
              <div style={{ marginTop: 12, fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>Automatically saved as a draft — copy + post manually on X.</div>
            </>
          )}
        </div>
      )}

      {/* Batch tab */}
      {activeTab === 'batch' && (
        <div style={{ padding: 20 }}>
          <TopicIntelligence onSelectTopic={handleTopicSelect} onBatchDone={onBatchDone} embedded />
        </div>
      )}

      {/* X Thread tab */}
      {activeTab === 'x-thread' && (
        <div style={{ padding: 20 }}>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 14, lineHeight: 1.6 }}>
            Generate a 6-tweet thread optimised for X (Twitter) — hook + insights + engagement CTA.
            Each tweet is under 270 chars with a position number so you can reply in sequence.
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div style={{ flex: 1, minWidth: 200 }}>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>TOPIC</div>
              <input
                value={xTopic}
                onChange={e => setXTopic(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && generateThread()}
                placeholder='e.g. "revenge trading", "IV crush", "failed prop firm eval"'
                style={{ width: '100%', background: 'var(--bg)', border: `1px solid ${xTopic ? 'rgba(29,155,240,0.4)' : 'var(--border)'}`, borderRadius: 6, padding: '7px 12px', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
              />
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>NICHE</div>
              <select
                value={xNiche}
                onChange={e => setXNiche(e.target.value)}
                style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
              >
                <option value="daytrading">Day trading</option>
                <option value="futures">Futures</option>
                <option value="swing-trading">Swing trading</option>
                <option value="crypto">Crypto</option>
                <option value="options">Options</option>
                <option value="trading">General trading</option>
              </select>
            </div>
            <div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 5, fontWeight: 600 }}>HOOK STYLE</div>
              <select
                value={xHookStyle}
                onChange={e => setXHookStyle(e.target.value)}
                style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-primary)', padding: '7px 12px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
              >
                <option value="contrarian">Contrarian</option>
                <option value="story">Mini story</option>
                <option value="list">Numbered list</option>
              </select>
            </div>
            <button
              onClick={generateThread}
              disabled={xGenerating || !xTopic.trim()}
              style={{
                background: xGenerating ? 'var(--border)' : '#1D9BF0',
                color: xGenerating ? 'var(--text-tertiary)' : '#fff',
                border: 'none', padding: '8px 20px', borderRadius: 6,
                fontSize: 12, fontWeight: 700,
                cursor: xGenerating || !xTopic.trim() ? 'not-allowed' : 'pointer',
                whiteSpace: 'nowrap',
              }}
            >
              {xGenerating ? '⏳ Generating…' : '𝕏 Generate thread'}
            </button>
          </div>

          {xError && (
            <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, background: 'rgba(216,90,48,0.1)', border: '1px solid rgba(216,90,48,0.3)', color: 'var(--coral)', fontSize: 12 }}>
              {xError}
            </div>
          )}

          {xThread && !showXPreview && (
            <div style={{ marginTop: 12, display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ fontSize: 12, color: 'var(--teal)', fontWeight: 600 }}>
                ✓ Thread ready — {xThread.tweet_count} tweets
              </span>
              <button
                onClick={() => setShowXPreview(true)}
                style={{
                  background: 'rgba(29,155,240,0.1)', color: '#1D9BF0',
                  border: '1px solid rgba(29,155,240,0.3)',
                  padding: '5px 14px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer',
                }}
              >
                View thread →
              </button>
            </div>
          )}

          <div style={{ marginTop: 10, fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.6 }}>
            Threads are copy-paste only. Post tweet 1 on X, then reply to yourself for each subsequent tweet.
          </div>

        </div>
      )}

      {/* Modals — rendered at CreatePanel root so they work from any tab */}
      {showXPreview && xThread && (
        <XThreadPreviewModal thread={xThread} onClose={() => setShowXPreview(false)} />
      )}
      {myXPreview && myXThread && (
        <XThreadPreviewModal thread={myXThread} onClose={() => setMyXPreview(false)} />
      )}
    </div>
  )
}

// ── Content Plan tab ─────────────────────────────────────────────────────────

const PLAN_SUBS = ['Daytrading', 'Futures', 'Forex', 'options', 'swingtrading', 'CryptoCurrency']

const PLAN_PLATFORM_COLOR = {
  reddit: { bg: 'rgba(255,99,20,0.12)', color: '#FF6314', label: 'Reddit' },
  x:      { bg: 'rgba(29,155,240,0.12)', color: '#1D9BF0', label: '𝕏 Thread' },
}

function PlanTab() {
  const [sheetData,   setSheetData]   = useState('')
  const [subreddits,  setSubreddits]  = useState(['Daytrading', 'Futures'])
  const [plan,        setPlan]        = useState(null)
  const [generating,  setGenerating]  = useState(false)
  const [refreshing,  setRefreshing]  = useState(false)
  const [error,       setError]       = useState(null)
  const [drafting,    setDrafting]    = useState({})
  const [drafted,     setDrafted]     = useState({})
  const [topPosts,    setTopPosts]    = useState([])
  const [showTop,     setShowTop]     = useState(false)

  useEffect(() => {
    // Load most recent saved plan
    fetch('/api/content-plan')
      .then(r => r.ok ? r.json() : [])
      .then(plans => { if (plans[0]?.plan?.plan) setPlan(plans[0].plan) })
      .catch(() => {})
  }, [])

  const toggleSub = (sub) => {
    setSubreddits(prev =>
      prev.includes(sub) ? prev.filter(s => s !== sub) : [...prev, sub]
    )
  }

  const handleGenerate = async () => {
    if (!sheetData.trim()) {
      setError('Paste your macro indicators or market data above first.')
      return
    }
    setGenerating(true)
    setError(null)
    try {
      const r = await fetch('/api/content-plan/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sheet_data: sheetData, subreddits, niche: 'daytrading', days: 7 }),
      })
      const d = await r.json()
      if (d.ok && d.plan) {
        setPlan(d.plan)
      } else {
        setError(d.error || 'Generation failed')
      }
    } catch (e) {
      setError(String(e))
    }
    setGenerating(false)
  }

  const handleRefreshTop = async () => {
    setRefreshing(true)
    try {
      const promises = subreddits.slice(0, 2).map(sub =>
        fetch('/api/top-posts/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ subreddit: sub, period: 'week' }),
        })
      )
      await Promise.all(promises)
      const r = await fetch('/api/top-posts?period=week&limit=15')
      if (r.ok) setTopPosts(await r.json())
      setShowTop(true)
    } catch {}
    setRefreshing(false)
  }

  const handleDraft = async (item, idx) => {
    setDrafting(d => ({ ...d, [idx]: true }))
    try {
      const body = item.platform === 'x'
        ? { platform: 'x', signal_override: item.topic }
        : { platform: 'reddit', signal_override: item.topic, subreddit: item.subreddit }
      const r = await fetch('/api/value-posts/auto-generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (r.ok) {
        setDrafted(d => ({ ...d, [idx]: true }))
        setTimeout(() => setDrafted(d => { const n = { ...d }; delete n[idx]; return n }), 3000)
        sendPush('Post ready to review 📋', `"${item.topic}" draft is in the Queue.`)
      }
    } catch {}
    setDrafting(d => { const n = { ...d }; delete n[idx]; return n })
  }

  const pc = (platform) => PLAN_PLATFORM_COLOR[platform] || PLAN_PLATFORM_COLOR.reddit

  return (
    <div>
      {/* Top post pulse */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 20 }}>
        <button
          onClick={handleRefreshTop}
          disabled={refreshing}
          style={{ padding: '7px 14px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600, cursor: 'pointer' }}
        >
          {refreshing ? '⏳ Pulling top posts...' : '📊 Pull what\'s trending in these subs'}
        </button>
        {topPosts.length > 0 && (
          <button
            onClick={() => setShowTop(v => !v)}
            style={{ padding: '7px 12px', borderRadius: 6, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-tertiary)', fontSize: 11, cursor: 'pointer' }}
          >
            {showTop ? 'Hide' : `Show ${topPosts.length} top posts`}
          </button>
        )}
      </div>

      {/* Top posts preview */}
      {showTop && topPosts.length > 0 && (
        <div style={{ marginBottom: 24, padding: 16, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', textTransform: 'uppercase', marginBottom: 10 }}>
            Trending in your target subs — AI will match these formats
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            {topPosts.slice(0, 8).map((p, i) => (
              <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start', padding: '6px 0', borderBottom: i < 7 ? '1px solid var(--border)' : 'none' }}>
                <div style={{ fontSize: 11, fontWeight: 700, color: '#1D9E75', minWidth: 36, textAlign: 'right' }}>
                  ↑{p.score}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 12, color: 'var(--text-primary)', fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {p.title}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>
                    r/{p.subreddit} · {p.comment_count} comments
                  </div>
                </div>
                {p.post_url && (
                  <a href={p.post_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: 'var(--teal)', flexShrink: 0 }}>↗</a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Input: paste sheet data */}
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: 20, marginBottom: 20 }}>
        <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          Paste your macro indicators / market data
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 12 }}>
          Google Sheets (Ctrl+A, Ctrl+C and paste), CSV, or just type free-form notes. AI reads the events and assigns one content piece per day.
        </div>
        <textarea
          value={sheetData}
          onChange={e => setSheetData(e.target.value)}
          placeholder={"Date\tEvent\tExpected\nMon Jun 23\tFed Rate Decision\t+25bps\nTue Jun 24\tCPI Print\t3.2% YoY\nWed Jun 25\tJobless Claims\t215k\n..."}
          rows={8}
          style={{
            width: '100%', boxSizing: 'border-box',
            background: 'var(--bg)', border: '1px solid var(--border)',
            color: 'var(--text-primary)', borderRadius: 6, padding: '10px 12px',
            fontSize: 12, fontFamily: 'monospace', lineHeight: 1.6, resize: 'vertical',
          }}
        />

        {/* Subreddit targets */}
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: 8 }}>Target subreddits</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {PLAN_SUBS.map(sub => {
              const active = subreddits.includes(sub)
              return (
                <button
                  key={sub}
                  onClick={() => toggleSub(sub)}
                  style={{
                    padding: '4px 10px', borderRadius: 20, fontSize: 11,
                    border: active ? '1px solid rgba(29,158,117,0.5)' : '1px solid var(--border)',
                    background: active ? 'rgba(29,158,117,0.12)' : 'transparent',
                    color: active ? '#1D9E75' : 'var(--text-tertiary)',
                    cursor: 'pointer', fontWeight: active ? 700 : 400,
                  }}
                >
                  r/{sub}
                </button>
              )
            })}
          </div>
        </div>

        {error && (
          <div style={{ marginTop: 10, fontSize: 12, color: '#FF6314' }}>{error}</div>
        )}

        <button
          onClick={handleGenerate}
          disabled={generating}
          style={{
            marginTop: 14, padding: '9px 20px', borderRadius: 7, border: 'none',
            background: generating ? 'rgba(83,74,183,0.3)' : '#534AB7',
            color: '#fff', fontSize: 13, fontWeight: 700, cursor: generating ? 'wait' : 'pointer',
          }}
        >
          {generating ? '⏳ Building your week plan...' : '📅 Generate week plan'}
        </button>
      </div>

      {/* Calendar */}
      {plan?.plan?.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 14 }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
              7-Day Content Calendar
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              Generated {new Date(plan.generated_at).toLocaleDateString()}
            </div>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {plan.plan.map((item, idx) => {
              const platColor = pc(item.platform)
              const isDrafted = !!drafted[idx]
              const isDrafting = !!drafting[idx]

              return (
                <div key={idx} style={{
                  background: 'var(--card)', border: '1px solid var(--border)',
                  borderRadius: 10, padding: '14px 16px',
                  display: 'flex', gap: 16, alignItems: 'flex-start',
                }}>
                  {/* Day label */}
                  <div style={{ minWidth: 80, textAlign: 'center', flexShrink: 0 }}>
                    <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      {(item.day_label || '').split(' ')[0]}
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>
                      {(item.day_label || '').split(' ').slice(1).join(' ')}
                    </div>
                  </div>

                  {/* Content */}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                      <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: platColor.bg, color: platColor.color }}>
                        {platColor.label}
                      </span>
                      {item.subreddit && item.platform === 'reddit' && (
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>r/{item.subreddit}</span>
                      )}
                      <span style={{ fontSize: 10, color: '#BA7517', fontStyle: 'italic' }}>
                        📌 {item.topic}
                      </span>
                    </div>
                    <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4, lineHeight: 1.4 }}>
                      {item.hook}
                    </div>
                    <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                      {item.angle}
                    </div>
                  </div>

                  {/* Draft button */}
                  <div style={{ flexShrink: 0 }}>
                    <button
                      disabled={isDrafting || isDrafted}
                      onClick={() => handleDraft(item, idx)}
                      style={{
                        padding: '7px 14px', borderRadius: 6, border: 'none',
                        background: isDrafted
                          ? 'rgba(29,158,117,0.15)'
                          : isDrafting ? 'rgba(83,74,183,0.2)' : 'rgba(83,74,183,0.15)',
                        color: isDrafted ? '#1D9E75' : '#8B82D4',
                        fontSize: 12, fontWeight: 700,
                        cursor: isDrafting || isDrafted ? 'default' : 'pointer',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {isDrafted ? '✓ Drafted' : isDrafting ? '⏳...' : '✨ Draft it'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>

          <div style={{ marginTop: 16, padding: '10px 14px', background: 'rgba(83,74,183,0.06)', borderRadius: 8, border: '1px solid rgba(83,74,183,0.15)', fontSize: 11, color: 'var(--text-tertiary)' }}>
            Click "✨ Draft it" on any day to generate a full draft in the Queue tab. You can then Preview → Approve → Copy to post.
          </div>
        </div>
      )}
    </div>
  )
}

// ── Pipeline helpers (Feed / Queue / Results tabs) ────────────────────────────

const PIPELINE_PLATFORM = {
  reddit: { bg: 'rgba(255,99,20,0.12)',  color: '#FF6314',  label: 'Reddit' },
  x:      { bg: 'rgba(29,155,240,0.12)', color: '#1D9BF0',  label: '𝕏 Twitter' },
}

function pipelineTimeAgo(iso) {
  if (!iso) return ''
  const diff  = Date.now() - new Date(iso).getTime()
  const mins  = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days  = Math.floor(diff / 86400000)
  if (mins < 1)   return 'just now'
  if (mins < 60)  return `${mins}m ago`
  if (hours < 24) return `${hours}h ago`
  return `${days}d ago`
}

function LiveFeedTab({ onSignalCount }) {
  const [signals,    setSignals]    = useState([])
  const [loading,    setLoading]    = useState(true)
  const [generating, setGenerating] = useState({})
  const [drafted,    setDrafted]    = useState({})

  const loadSignals = useCallback(async () => {
    try {
      const r = await fetch('/api/signals/live')
      if (!r.ok) throw new Error('bad')
      const data = await r.json()
      setSignals(Array.isArray(data) ? data : [])
      if (onSignalCount) onSignalCount(Array.isArray(data) ? data.length : 0)
    } catch {
      setSignals([])
    } finally {
      setLoading(false)
    }
  }, [onSignalCount])

  useEffect(() => {
    loadSignals()
    const id = setInterval(loadSignals, 60_000)
    return () => clearInterval(id)
  }, [loadSignals])

  const handleGenerate = useCallback(async (signal, genPlatform, subreddit, pod) => {
    const key = signal.signal + genPlatform
    setGenerating(g => ({ ...g, [key]: true }))
    try {
      const body = genPlatform === 'reddit'
        ? { platform: 'reddit', signal_override: signal.signal, subreddit: subreddit || 'Daytrading' }
        : { platform: 'x',     signal_override: signal.signal, pod: pod || 'daytrading' }
      const r = await fetch('/api/value-posts/auto-generate', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      if (!r.ok) throw new Error('failed')
      setDrafted(d => ({ ...d, [key]: true }))
      setTimeout(() => setDrafted(d => { const n = { ...d }; delete n[key]; return n }), 3000)
      sendPush('Post ready to review 📋', `"${signal.signal}" draft is in the Queue.`)
    } catch {}
    finally {
      setGenerating(g => { const n = { ...g }; delete n[key]; return n })
    }
  }, [])

  const redditCount = signals.filter(s => s.platform === 'reddit').length
  const xCount      = signals.filter(s => s.platform !== 'reddit').length

  if (loading) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading signals...</div>
  )

  return (
    <div>
      <div style={{ display: 'flex', gap: 16, alignItems: 'center', padding: '10px 0', marginBottom: 16, fontSize: 12, color: 'var(--text-secondary)' }}>
        <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{signals.length} signals in last 48h</span>
        <span style={{ color: '#FF6314' }}>&#x25cf; {redditCount} Reddit</span>
        <span style={{ color: '#1D9BF0' }}>&#x25cf; {xCount} on X</span>
      </div>

      {signals.length === 0 ? (
        <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)' }}>
          No signals in last 48h. Run a scrape to populate signals.
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {signals.map((sig, i) => {
            const plat      = sig.platform === 'reddit' ? 'reddit' : 'x'
            const pc        = PIPELINE_PLATFORM[plat] || PIPELINE_PLATFORM.reddit
            const redditKey = sig.signal + 'reddit'
            const xKey      = sig.signal + 'x'
            const subName   = sig.subreddits?.split(',')[0] || 'Daytrading'
            const podName   = sig.pods?.split(',')[0] || 'daytrading'

            return (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 14, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6, flexWrap: 'wrap' }}>
                    <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: pc.bg, color: pc.color }}>{pc.label}</span>
                    <span style={{ background: 'rgba(255,255,255,0.06)', color: 'var(--text-tertiary)', borderRadius: 20, padding: '2px 8px', fontSize: 10 }}>{sig.count} seen</span>
                    <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{pipelineTimeAgo(sig.last_seen)}</span>
                  </div>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4, wordBreak: 'break-word' }}>{sig.signal}</div>
                  {sig.example && (
                    <div style={{ fontSize: 12, color: 'var(--text-tertiary)', fontStyle: 'italic', overflow: 'hidden', textOverflow: 'ellipsis', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' }}>
                      "{sig.example}"
                    </div>
                  )}
                  {(drafted[redditKey] || drafted[xKey]) && (
                    <div style={{ marginTop: 8, display: 'inline-flex', alignItems: 'center', gap: 4, background: 'rgba(29,158,117,0.15)', color: '#1D9E75', borderRadius: 6, padding: '3px 10px', fontSize: 11, fontWeight: 700 }}>
                      &#x2713; Drafted — check Queue tab
                    </div>
                  )}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flexShrink: 0 }}>
                  <button
                    disabled={!!generating[redditKey] || !!generating[xKey]}
                    onClick={() => handleGenerate(sig, 'reddit', subName, podName)}
                    style={{ padding: '6px 12px', borderRadius: 6, border: 'none', cursor: 'pointer', background: generating[redditKey] ? 'rgba(255,99,20,0.4)' : 'rgba(255,99,20,0.15)', color: '#FF6314', fontSize: 12, fontWeight: 700, opacity: generating[xKey] ? 0.5 : 1, whiteSpace: 'nowrap' }}
                  >
                    {generating[redditKey] ? '...' : '🤖 Reddit post'}
                  </button>
                  <button
                    disabled={!!generating[redditKey] || !!generating[xKey]}
                    onClick={() => handleGenerate(sig, 'x', subName, podName)}
                    style={{ padding: '6px 12px', borderRadius: 6, border: 'none', cursor: 'pointer', background: generating[xKey] ? 'rgba(29,155,240,0.4)' : 'rgba(29,155,240,0.15)', color: '#1D9BF0', fontSize: 12, fontWeight: 700, opacity: generating[redditKey] ? 0.5 : 1, whiteSpace: 'nowrap' }}
                  >
                    {generating[xKey] ? '...' : '𝕏 X thread'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Post preview modal ────────────────────────────────────────────────────────

function inlineMd(text) {
  // Bold: **text**
  const parts = text.split(/(\*\*[^*]+\*\*)/g)
  return parts.map((p, i) => {
    if (p.startsWith('**') && p.endsWith('**')) {
      return <strong key={i}>{p.slice(2, -2)}</strong>
    }
    return p
  })
}

function renderRedditBody(body) {
  if (!body) return null
  const paras = body.split(/\n\n+/)
  return paras.map((para, pi) => {
    const lines = para.split('\n')
    const isNumbered = lines.every(l => /^\d+\.\s/.test(l.trim()))
    const isBullet   = lines.every(l => /^[*\-]\s/.test(l.trim()))

    if (isNumbered && lines.length > 1) {
      return (
        <ol key={pi} style={{ margin: '0 0 14px 20px', padding: 0, lineHeight: 1.7, fontSize: 14, color: '#d7dadc' }}>
          {lines.map((l, li) => <li key={li}>{inlineMd(l.replace(/^\d+\.\s/, ''))}</li>)}
        </ol>
      )
    }
    if (isBullet && lines.length > 1) {
      return (
        <ul key={pi} style={{ margin: '0 0 14px 20px', padding: 0, lineHeight: 1.7, fontSize: 14, color: '#d7dadc' }}>
          {lines.map((l, li) => <li key={li}>{inlineMd(l.replace(/^[*\-]\s/, ''))}</li>)}
        </ul>
      )
    }
    return (
      <p key={pi} style={{ margin: '0 0 14px 0', fontSize: 14, lineHeight: 1.7, color: '#d7dadc' }}>
        {inlineMd(para)}
      </p>
    )
  })
}

async function sendPush(title, message) {
  try {
    await fetch('/api/notify', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, message, priority: 'high' }),
    })
  } catch {}
}

function PostPreviewModal({ post, onClose }) {
  const [copied,       setCopied]       = useState(false)
  const [imgB64,       setImgB64]       = useState(null)
  const [imgLoading,   setImgLoading]   = useState(false)
  const [imgError,     setImgError]     = useState(null)
  const [audioB64,     setAudioB64]     = useState(null)
  const [audioLoading, setAudioLoading] = useState(false)
  const [audioError,   setAudioError]   = useState(null)

  if (!post) return null

  const isX  = post.subreddit === 'x' || post.type === 'x_thread'
  const sub  = post.subreddit || 'Daytrading'
  const platform = isX ? 'x' : 'reddit'

  const threads = Array.isArray(post.tweets)
    ? post.tweets
    : (post.body || '').split(/\n\n+/).filter(Boolean)

  const copyToClipboard = async (text) => {
    try { await navigator.clipboard.writeText(text); setCopied(true); setTimeout(() => setCopied(false), 2000) }
    catch {}
  }

  const generateImage = async () => {
    setImgLoading(true); setImgError(null); setImgB64(null)
    try {
      const r = await fetch('/api/value-posts/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ image_prompt: post.image_prompt, platform }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.error || 'Image gen failed')
      setImgB64(data.b64)
    } catch (e) {
      setImgError(e.message)
    } finally {
      setImgLoading(false)
    }
  }

  const generateAudio = async () => {
    setAudioLoading(true); setAudioError(null); setAudioB64(null)
    // Use the hook (first tweet for X, title for Reddit) as the spoken text
    const spokenText = isX
      ? (threads[0] || post.title || '').slice(0, 500)
      : (post.title || '').slice(0, 500)
    try {
      const r = await fetch('/api/value-posts/generate-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: spokenText }),
      })
      const data = await r.json()
      if (!r.ok) throw new Error(data.error || 'Audio gen failed')
      setAudioB64(data.audio_b64)
    } catch (e) {
      setAudioError(e.message)
    } finally {
      setAudioLoading(false)
    }
  }

  const audioSrc = audioB64 ? `data:audio/mpeg;base64,${audioB64}` : null

  const redditCopyText = `${post.title}\n\n${post.body}`
  const xCopyText      = threads.join('\n\n---\n\n')

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 2000,
        background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        padding: 24, overflowY: 'auto',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          width: '100%', maxWidth: isX ? 540 : 740,
          maxHeight: '90vh', overflowY: 'auto',
          borderRadius: 12,
          background: isX ? '#000' : '#1a1a1b',
          border: `1px solid ${isX ? '#2f3336' : '#343536'}`,
        }}
      >
        {/* Modal header */}
        <div style={{
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          padding: '12px 16px', borderBottom: `1px solid ${isX ? '#2f3336' : '#343536'}`,
        }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: isX ? '#71767b' : '#818384', letterSpacing: '0.06em', textTransform: 'uppercase' }}>
            {isX ? '𝕏 Thread Preview' : `r/${sub} — Post Preview`}
          </span>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={() => copyToClipboard(isX ? xCopyText : redditCopyText)}
              style={{ padding: '5px 12px', borderRadius: 6, border: 'none', cursor: 'pointer', background: copied ? 'rgba(29,158,117,0.2)' : 'rgba(255,255,255,0.08)', color: copied ? '#1D9E75' : '#d7dadc', fontSize: 12, fontWeight: 600 }}
            >
              {copied ? '✓ Copied' : '📋 Copy all'}
            </button>
            <button
              onClick={onClose}
              style={{ padding: '5px 10px', borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(255,255,255,0.08)', color: '#818384', fontSize: 13 }}
            >
              ✕
            </button>
          </div>
        </div>

        {/* Reddit preview */}
        {!isX && (
          <div style={{ padding: '0 0 16px 0' }}>
            {/* Subreddit header bar */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '12px 16px 8px' }}>
              <div style={{ width: 32, height: 32, borderRadius: '50%', background: 'linear-gradient(135deg,#ff4500,#ff6534)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 16 }}>
                🏛
              </div>
              <div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#d7dadc' }}>r/{sub}</div>
                <div style={{ fontSize: 11, color: '#818384' }}>Posted by u/AltusFlow_AI • just now</div>
              </div>
            </div>

            {/* Vote bar + content */}
            <div style={{ display: 'flex', gap: 0 }}>
              {/* Vote column */}
              <div style={{ width: 40, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2, padding: '4px 8px', color: '#818384' }}>
                <div style={{ fontSize: 18, lineHeight: 1, cursor: 'pointer' }}>▲</div>
                <div style={{ fontSize: 12, fontWeight: 700, color: '#d7dadc' }}>1</div>
                <div style={{ fontSize: 18, lineHeight: 1, cursor: 'pointer' }}>▼</div>
              </div>

              {/* Content */}
              <div style={{ flex: 1, paddingRight: 16 }}>
                <h2 style={{ fontSize: 18, fontWeight: 500, color: '#d7dadc', lineHeight: 1.4, margin: '8px 0 14px', fontFamily: 'sans-serif' }}>
                  {post.title}
                </h2>
                <div style={{ fontFamily: 'sans-serif' }}>
                  {renderRedditBody(post.body)}
                </div>

                {/* Action bar */}
                <div style={{ display: 'flex', gap: 16, marginTop: 12 }}>
                  {['💬 Comment', '🔗 Share', '⭐ Save', '• • •'].map(a => (
                    <span key={a} style={{ fontSize: 12, color: '#818384', fontWeight: 700, cursor: 'pointer' }}>{a}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* X thread preview */}
        {isX && (
          <div>
            {threads.map((tweet, i) => {
              const isLast = i === threads.length - 1
              const charCount = tweet.length
              const overLimit = charCount > 280
              return (
                <div key={i} style={{ display: 'flex', gap: 12, padding: '16px 16px 0' }}>
                  {/* Avatar + thread line */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flexShrink: 0 }}>
                    <div style={{ width: 40, height: 40, borderRadius: '50%', background: 'linear-gradient(135deg,#534AB7,#1D9BF0)', flexShrink: 0 }} />
                    {!isLast && (
                      <div style={{ width: 2, flex: 1, minHeight: 28, background: '#2f3336', marginTop: 4, marginBottom: 0 }} />
                    )}
                  </div>

                  {/* Tweet */}
                  <div style={{ flex: 1, paddingBottom: 16, borderBottom: !isLast ? '1px solid #2f3336' : 'none', minWidth: 0 }}>
                    {/* Author */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                      <span style={{ fontSize: 15, fontWeight: 700, color: '#e7e9ea' }}>Trading Coach</span>
                      <span style={{ fontSize: 13, color: '#71767b' }}>@TradingCoachAI · now</span>
                    </div>
                    {/* Content */}
                    <div style={{ fontSize: 15, color: '#e7e9ea', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word', marginBottom: 10 }}>
                      {tweet}
                    </div>
                    {/* Char count + actions */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ display: 'flex', gap: 20, color: '#71767b' }}>
                        {['💬', '🔁', '❤️', '📊', '⬆️'].map((ic, idx) => (
                          <span key={idx} style={{ fontSize: 13, cursor: 'pointer' }}>{ic}</span>
                        ))}
                      </div>
                      <span style={{ fontSize: 11, color: overLimit ? '#FF6314' : '#71767b', fontWeight: 600 }}>
                        {charCount}/280
                      </span>
                    </div>
                  </div>
                </div>
              )
            })}

            {/* Image generation panel */}
            {post.image_prompt && (
              <div style={{ margin: '12px 16px 16px', padding: '12px 14px', background: 'rgba(83,74,183,0.10)', border: '1px solid rgba(83,74,183,0.28)', borderRadius: 8 }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                  <div style={{ fontSize: 10, fontWeight: 700, color: '#8B82D4', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                    🎨 AI image for tweet 1
                  </div>
                  {!imgB64 && (
                    <button
                      onClick={e => { e.stopPropagation(); generateImage() }}
                      disabled={imgLoading}
                      style={{
                        background: imgLoading ? 'rgba(83,74,183,0.3)' : 'var(--teal)',
                        color: '#fff', border: 'none', borderRadius: 6,
                        padding: '4px 12px', fontSize: 11, fontWeight: 700, cursor: imgLoading ? 'default' : 'pointer',
                      }}
                    >
                      {imgLoading ? '⏳ Generating…' : '✨ Generate'}
                    </button>
                  )}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-tertiary)', lineHeight: 1.5, marginBottom: imgB64 ? 10 : 0 }}>
                  {post.image_prompt}
                </div>
                {imgError && (
                  <div style={{ fontSize: 11, color: 'var(--coral)', marginTop: 6 }}>⚠ {imgError}</div>
                )}
                {imgB64 && (
                  <div style={{ marginTop: 10 }}>
                    <img
                      src={`data:image/png;base64,${imgB64}`}
                      alt="AI generated"
                      style={{ width: '100%', borderRadius: 8, display: 'block' }}
                    />
                    <button
                      onClick={e => { e.stopPropagation(); generateImage() }}
                      style={{ marginTop: 8, background: 'transparent', border: '1px solid rgba(83,74,183,0.4)', color: '#8B82D4', borderRadius: 6, padding: '4px 10px', fontSize: 11, cursor: 'pointer' }}
                    >
                      🔄 Regenerate
                    </button>
                  </div>
                )}
              </div>
            )}

            {/* ElevenLabs audio panel */}
            <div style={{ margin: '0 16px 16px', padding: '12px 14px', background: 'rgba(99,76,175,0.07)', border: '1px solid rgba(99,76,175,0.25)', borderRadius: 8 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#8B5CF6', letterSpacing: '0.05em', textTransform: 'uppercase' }}>
                  🎙️ Voiceover — ElevenLabs
                </div>
                <button
                  onClick={e => { e.stopPropagation(); generateAudio() }}
                  disabled={audioLoading}
                  style={{
                    background: audioLoading ? 'rgba(99,76,175,0.2)' : '#7C3AED',
                    color: '#fff', border: 'none', borderRadius: 6,
                    padding: '4px 12px', fontSize: 11, fontWeight: 700,
                    cursor: audioLoading ? 'default' : 'pointer',
                  }}
                >
                  {audioLoading ? '⏳ Generating…' : audioB64 ? '🔄 Regenerate' : '🎙️ Generate'}
                </button>
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                {isX ? 'Reads your hook aloud — attach to tweet 1 for higher reach' : 'Reads your title aloud — use in video content or reels'}
              </div>
              {audioError && (
                <div style={{ fontSize: 11, color: 'var(--coral)', marginTop: 6 }}>⚠ {audioError}</div>
              )}
              {audioSrc && (
                <div style={{ marginTop: 10 }}>
                  <audio
                    src={audioSrc}
                    controls
                    style={{ width: '100%', height: 36 }}
                  />
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <a
                      href={audioSrc}
                      download="voiceover.mp3"
                      onClick={e => e.stopPropagation()}
                      style={{ background: '#7C3AED', color: '#fff', borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700, textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 4 }}
                    >
                      ⬇ Download MP3
                    </a>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function QueueTab({ onDraftCount }) {
  const [posts,     setPosts]     = useState([])
  const [loading,   setLoading]   = useState(true)
  const [approving, setApproving] = useState({})
  const [rejecting, setRejecting] = useState({})
  const [expanded,  setExpanded]  = useState({})
  const [preview,   setPreview]   = useState(null)

  const loadPosts = useCallback(async () => {
    try {
      const r = await fetch('/api/value-posts')
      if (!r.ok) throw new Error('bad')
      const data = await r.json()
      const drafts = Array.isArray(data) ? data.filter(p => p.status === 'draft') : []
      setPosts(drafts)
      if (onDraftCount) onDraftCount(drafts.length)
    } catch {
      setPosts([])
    } finally {
      setLoading(false)
    }
  }, [onDraftCount])

  useEffect(() => {
    loadPosts()
    const id = setInterval(loadPosts, 30_000)
    return () => clearInterval(id)
  }, [loadPosts])

  const handleApprove = useCallback(async (id) => {
    setApproving(a => ({ ...a, [id]: true }))
    try {
      await fetch(`/api/value-posts/${id}/approve`, { method: 'POST' })
      await loadPosts()
    } catch {}
    setApproving(a => { const n = { ...a }; delete n[id]; return n })
  }, [loadPosts])

  const handleDiscard = useCallback(async (id) => {
    if (!window.confirm('Discard this draft?')) return
    setRejecting(r => ({ ...r, [id]: true }))
    try {
      await fetch(`/api/value-posts/${id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: 'rejected' }),
      })
      await loadPosts()
    } catch {}
    setRejecting(r => { const n = { ...r }; delete n[id]; return n })
  }, [loadPosts])

  if (loading) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading queue...</div>
  )

  if (posts.length === 0) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)' }}>
      No drafts in queue. Go to the Feed tab, find a pain signal, and hit "🤖 Reddit post" or "𝕏 X thread".
    </div>
  )

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
      {posts.map(post => {
        const isX   = post.subreddit === 'x' || post.type === 'x_thread'
        const plat  = isX ? 'x' : 'reddit'
        const pc    = PIPELINE_PLATFORM[plat] || PIPELINE_PLATFORM.reddit
        const isExp = !!expanded[post.id]

        return (
          <div key={post.id} style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>

            {/* Header */}
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginBottom: 6 }}>
                <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: pc.bg, color: pc.color }}>
                  {isX ? '𝕏 Thread' : `r/${post.subreddit}`}
                </span>
                {post.auto_generated === 1 && (
                  <span style={{ display: 'inline-block', padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: 'rgba(29,155,240,0.12)', color: '#1D9BF0' }}>
                    🤖 Auto
                  </span>
                )}
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{pipelineTimeAgo(post.created_at)}</span>
              </div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1.4 }}>{post.title}</div>
            </div>

            {/* Signal context — what community pain triggered this AI post */}
            {(post.source_signal || post.topic) && (
              <div style={{ margin: '10px 16px 0', padding: '8px 12px', background: 'rgba(83,74,183,0.06)', borderLeft: '3px solid #534AB7', borderRadius: '0 6px 6px 0' }}>
                <div style={{ fontSize: 10, fontWeight: 700, color: '#8B82D4', marginBottom: 3, letterSpacing: '0.04em', textTransform: 'uppercase' }}>
                  Pain signal that triggered this
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                  "{post.source_signal || post.topic}"
                </div>
                {post.signal_example && (
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)', fontStyle: 'italic', marginTop: 3 }}>
                    "{post.signal_example}"
                  </div>
                )}
              </div>
            )}

            {/* Body preview */}
            <div style={{ padding: '10px 16px' }}>
              <div style={{ background: 'var(--bg)', borderRadius: 6, padding: '8px 12px', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                {isExp ? post.body : (post.body || '').slice(0, 200) + (post.body?.length > 200 ? '...' : '')}
              </div>
              {post.body?.length > 200 && (
                <button
                  onClick={() => setExpanded(e => ({ ...e, [post.id]: !e[post.id] }))}
                  style={{ marginTop: 6, background: 'none', border: 'none', color: 'var(--teal)', fontSize: 11, cursor: 'pointer', padding: 0 }}
                >
                  {isExp ? 'Collapse' : 'Preview full content'}
                </button>
              )}
            </div>

            {/* Footer */}
            <div style={{ padding: '10px 16px', display: 'flex', gap: 8, alignItems: 'center', borderTop: '1px solid var(--border)' }}>
              <button
                onClick={() => setPreview(post)}
                style={{ padding: '6px 14px', borderRadius: 6, border: '1px solid var(--border)', cursor: 'pointer', background: 'transparent', color: 'var(--text-secondary)', fontSize: 12, fontWeight: 600 }}
              >
                👁 Preview
              </button>
              <button
                disabled={!!approving[post.id]}
                onClick={() => handleApprove(post.id)}
                style={{ padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', background: 'rgba(29,158,117,0.15)', color: '#1D9E75', fontSize: 12, fontWeight: 700, opacity: approving[post.id] ? 0.5 : 1 }}
              >
                {approving[post.id] ? 'Approving...' : '✓ Approve'}
              </button>
              <button
                disabled={!!rejecting[post.id]}
                onClick={() => handleDiscard(post.id)}
                style={{ padding: '6px 14px', borderRadius: 6, border: 'none', cursor: 'pointer', background: 'transparent', color: 'var(--text-tertiary)', fontSize: 12, fontWeight: 700, opacity: rejecting[post.id] ? 0.5 : 1 }}
              >
                {rejecting[post.id] ? 'Discarding...' : '🗑 Discard'}
              </button>
            </div>
          </div>
        )
      })}

      {preview && <PostPreviewModal post={preview} onClose={() => setPreview(null)} />}
    </div>
  )
}

function ResultsTab() {
  const [results, setResults] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tab,     setTab]     = useState('posts')  // posts | subs | types

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const r = await fetch('/api/value-posts/results')
      if (!r.ok) throw new Error('bad')
      setResults(await r.json())
    } catch {
      setResults(null)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  if (loading) return (
    <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>Loading results…</div>
  )

  const r = results || {}
  const posts  = r.recent_posts || []
  const subs   = r.best_subreddits || []
  const types  = r.best_types || []

  const statBox = (val, label, color = 'var(--text-primary)') => (
    <div style={{ textAlign: 'center', flex: 1, minWidth: 72 }}>
      <div style={{ fontSize: 22, fontWeight: 800, color }}>{val}</div>
      <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: 0.5 }}>{label}</div>
    </div>
  )

  const divider = <div style={{ width: 1, background: 'var(--border)', alignSelf: 'stretch' }} />

  const maxUpvotes = Math.max(...posts.map(p => p.upvotes || 0), 1)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
      {/* Summary stats */}
      <div style={{ display: 'flex', gap: 0, padding: '14px 16px', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
        {statBox(r.total_posted || 0,   'Posted')}
        {divider}
        {statBox(r.total_upvotes || 0,  'Total Upvotes', 'var(--teal)')}
        {divider}
        {statBox(r.avg_upvotes || 0,    'Avg Upvotes')}
        {divider}
        {statBox(r.avg_comments || 0,   'Avg Comments')}
        {divider}
        {statBox(r.total_leads || 0,    'Leads', '#534AB7')}
      </div>

      {/* Sub-tabs */}
      <div style={{ display: 'flex', gap: 6 }}>
        {[['posts','📋 Posts'],['subs','🏆 Best Subs'],['types','📌 Content Types']].map(([key, label]) => (
          <button key={key} onClick={() => setTab(key)} style={{
            padding: '6px 14px', borderRadius: 20, border: '1px solid var(--border)',
            background: tab === key ? 'var(--teal)' : 'var(--card)',
            color: tab === key ? '#fff' : 'var(--text-secondary)',
            fontSize: 12, fontWeight: tab === key ? 700 : 400, cursor: 'pointer',
          }}>{label}</button>
        ))}
        <button onClick={load} style={{ marginLeft: 'auto', padding: '6px 12px', borderRadius: 20, border: '1px solid var(--border)', background: 'var(--card)', color: 'var(--text-tertiary)', fontSize: 12, cursor: 'pointer' }}>↺ Refresh</button>
      </div>

      {/* Posts tab */}
      {tab === 'posts' && (
        posts.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)' }}>
            Approve and post content to see performance here.<br />
            <span style={{ fontSize: 12 }}>Performance updates every 6 hours automatically.</span>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {posts.map((p, i) => {
              const isX  = (p.platform || p.subreddit) === 'x' || p.type === 'x_thread'
              const pc   = isX ? PIPELINE_PLATFORM.x : PIPELINE_PLATFORM.reddit
              const days = p.posted_at ? Math.floor((Date.now() - new Date(p.posted_at).getTime()) / 86400000) : 0
              const barW = Math.round(((p.upvotes || 0) / maxUpvotes) * 100)

              return (
                <div key={p.id || i} style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
                  <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 8 }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4, flexWrap: 'wrap' }}>
                        <span style={{ padding: '2px 8px', borderRadius: 20, fontSize: 10, fontWeight: 700, background: pc.bg, color: pc.color }}>{pc.label}</span>
                        {!isX && p.subreddit && <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>r/{p.subreddit}</span>}
                        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{days === 0 ? 'today' : `${days}d ago`}</span>
                        {p.post_url && <a href={p.post_url} target="_blank" rel="noreferrer" style={{ fontSize: 10, color: 'var(--teal)' }}>View ↗</a>}
                      </div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {p.title}
                      </div>
                    </div>
                    <div style={{ display: 'flex', gap: 12, flexShrink: 0, textAlign: 'right' }}>
                      <div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--teal)' }}>↑{p.upvotes || 0}</div>
                        <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>upvotes</div>
                      </div>
                      <div>
                        <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-secondary)' }}>💬{p.comments || 0}</div>
                        <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>comments</div>
                      </div>
                      {p.lead_count > 0 && (
                        <div>
                          <div style={{ fontSize: 18, fontWeight: 800, color: '#534AB7' }}>👤{p.lead_count}</div>
                          <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>leads</div>
                        </div>
                      )}
                    </div>
                  </div>
                  {/* Engagement bar */}
                  <div style={{ height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${barW}%`, background: 'var(--teal)', borderRadius: 2, transition: 'width 0.4s' }} />
                  </div>
                </div>
              )
            })}
          </div>
        )
      )}

      {/* Best subs tab */}
      {tab === 'subs' && (
        subs.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)' }}>
            No subreddit data yet — post some content first.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {subs.map((s, i) => (
              <div key={s.subreddit} style={{ display: 'flex', alignItems: 'center', gap: 14, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-tertiary)', minWidth: 28, textAlign: 'center' }}>#{i + 1}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>r/{s.subreddit}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{s.post_count} post{s.post_count !== 1 ? 's' : ''} · {s.total_upvotes} total upvotes</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--teal)' }}>↑{s.avg_upvotes}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>avg upvotes</div>
                </div>
              </div>
            ))}
          </div>
        )
      )}

      {/* Content types tab */}
      {tab === 'types' && (
        types.length === 0 ? (
          <div style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)', background: 'var(--card)', borderRadius: 10, border: '1px solid var(--border)' }}>
            No content type data yet.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {types.map((t, i) => (
              <div key={t.type} style={{ display: 'flex', alignItems: 'center', gap: 14, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: 'var(--text-tertiary)', minWidth: 28, textAlign: 'center' }}>#{i + 1}</div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', textTransform: 'capitalize' }}>{t.type.replace(/_/g, ' ')}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{t.post_count} post{t.post_count !== 1 ? 's' : ''}</div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--teal)' }}>↑{t.avg_upvotes}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>avg upvotes</div>
                </div>
              </div>
            ))}
          </div>
        )
      )}
    </div>
  )
}

// ── Main export ───────────────────────────────────────────────────────────────
export default function ValuePosts() {
  const [posts,       setPosts]       = useState([])
  const [loading,     setLoading]     = useState(true)
  const [generating,  setGenerating]  = useState(false)
  const [genError,    setGenError]    = useState(null)
  const [subreddit,   setSubreddit]   = useState('Daytrading')
  const [genType,     setGenType]     = useState('insight_digest')
  const [topic,       setTopic]       = useState('')
  const [filter,      setFilter]      = useState('all')
  const [subFilter,   setSubFilter]   = useState('all')
  const [mainTab,     setMainTab]     = useState('feed')
  const [signalCount, setSignalCount] = useState(0)
  const [draftCount,  setDraftCount]  = useState(0)

  const DEMO_POSTS = [
    {
      id: 1, subreddit: 'Daytrading', type: 'insight_digest', status: 'approved',
      title: "What I'm seeing in r/Daytrading this week — patterns worth knowing about",
      body: `Been lurking and reading posts here for a while and noticed some clear patterns this week worth sharing.\n\n**1. The revenge trading spiral is at an all-time high**\nAt least 6 posts this week followed the same arc: big loss → doubled down → bigger loss → "I think I need to quit." This isn't a strategy problem — it's a process problem. One rule: after any loss bigger than your daily max, you're done for the day. No exceptions.\n\n**2. People are confusing activity with progress**\nLots of posts about taking 20+ trades a day and wondering why they're losing. More trades ≠ more edge. The setups that actually work are rare — if you're forcing entries, you're manufacturing losses.\n\n**3. The "I just need one big win" mindset is the tell**\nSeveral posts this week explicitly said they needed one big trade to get back to even. That's not trading — that's gambling. Size down, rebuild the process.\n\n**4. Discord/community FOMO is quietly killing accounts**\nSaw multiple posts where the loss came from someone calling a trade in a server. Your edge has to be your own or you have no edge.\n\nWhat patterns are YOU seeing this week?`,
      signals: ['revenge trading', 'blown account', 'keep losing', 'need help', 'quit trading'],
      post_count: 47, generated_at: new Date(Date.now() - 2*3600000).toISOString(),
    },
    {
      id: 2, subreddit: 'Futures', type: 'resource_post', status: 'draft',
      title: "The 7 signs you're not ready to trade live yet (save this)",
      body: `After watching a lot of traders blow accounts that didn't need to be blown, here's the checklist I wish someone had given me earlier.\n\n**You're not ready to go live if:**\n\n1. You can't explain your edge in one sentence.\n2. You don't have 3 months of sim data — actual recorded entries and exits.\n3. You don't have a hard daily max loss rule.\n4. A losing day affects your next day's entries.\n5. You're sizing based on how confident you feel.\n6. You're taking entries from other people's calls.\n7. Sim losses upset you — real losses will end you.\n\nWhich of these surprised you the most?`,
      signals: ['not profitable yet', 'ready to go live', 'sim trading'],
      post_count: 23, generated_at: new Date(Date.now() - 26*3600000).toISOString(),
    },
    {
      id: 3, subreddit: 'Daytrading', type: 'insight_digest', status: 'posted',
      title: "What I'm seeing in r/Daytrading this week — the psychology patterns",
      body: `Quick roundup of what's showing up in posts this week.\n\nBiggest theme: **people are trading their P&L, not the market.** When you're up you get cautious, when you're down you get reckless. The market doesn't know your balance.\n\nSecond: **the 9:30–10am window is eating people alive.** Three separate posts this week from traders whose best month ever was when they stopped trading the open.\n\nThird: **chasing the hot ticker of the day is a long-term losing game.** Context matters more than the symbol.\n\nWhat's working for profitable traders right now? Fewer trades, better quality. Boring but real.\n\nWhat are you seeing from your own trading this week?`,
      signals: ['psychology', 'overtrading', 'morning session', 'emotional trading'],
      post_count: 61, generated_at: new Date(Date.now() - 4*24*3600000).toISOString(), upvotes: 847,
    },
  ]

  const loadPosts = useCallback(async () => {
    try {
      const url = subFilter !== 'all' ? `/api/value-posts?subreddit=${subFilter}` : '/api/value-posts'
      const r = await fetch(url)
      if (r.ok) {
        const d = await r.json()
        if (Array.isArray(d) && d.length > 0) { setPosts(d); setLoading(false); return }
      }
    } catch {}
    setPosts([])
    setLoading(false)
  }, [subFilter])

  useEffect(() => { loadPosts() }, [loadPosts])

  const generate = async () => {
    setGenerating(true)
    setGenError(null)
    try {
      const r = await fetch('/api/value-posts/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ subreddit, type: genType, topic }),
      })
      const d = await r.json()
      if (d.ok) {
        await loadPosts()
      } else {
        setGenError(d.error || 'Generation failed')
      }
    } catch (e) {
      setGenError(String(e))
    }
    setGenerating(false)
  }

  const onUpdate = (updated) => {
    setPosts(prev => prev.map(p => p.id === updated.id ? updated : p))
  }

  const filtered = posts.filter(p => {
    if (filter !== 'all' && p.status !== filter) return false
    if (subFilter !== 'all' && p.subreddit !== subFilter) return false
    return true
  })

  const counts = { draft: 0, approved: 0, posted: 0 }
  posts.forEach(p => { if (counts[p.status] != null) counts[p.status]++ })

  const postSubs = [...new Set(posts.map(p => p.subreddit).filter(Boolean))]

  const MAIN_TABS = [
    { key: 'feed',    label: '📡 Feed',    count: signalCount },
    { key: 'create',  label: '✨ Create',   count: 0 },
    { key: 'queue',   label: '📋 Queue',   count: draftCount },
    { key: 'library', label: '📚 Library', count: 0 },
    { key: 'results', label: '📈 Results', count: 0 },
    { key: 'plan',    label: '📅 Plan',    count: 0 },
  ]

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>

      {/* 5-tab nav */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, background: 'var(--bg)', borderRadius: 10, padding: 4, border: '1px solid var(--border)' }}>
        {MAIN_TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setMainTab(tab.key)}
            style={{
              flex: 1, padding: '9px 8px', borderRadius: 7, border: 'none',
              cursor: 'pointer', fontSize: 12, fontWeight: 600,
              background: mainTab === tab.key ? 'var(--card)' : 'transparent',
              color: mainTab === tab.key ? 'var(--text-primary)' : 'var(--text-tertiary)',
              transition: 'all 0.15s',
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5,
              whiteSpace: 'nowrap',
            }}
          >
            {tab.label}
            {tab.count > 0 && (
              <span style={{ background: mainTab === tab.key ? 'var(--teal)' : 'var(--border)', color: mainTab === tab.key ? '#fff' : 'var(--text-tertiary)', borderRadius: 20, padding: '1px 6px', fontSize: 10, fontWeight: 800 }}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Feed — live pain signals from the community */}
      {mainTab === 'feed' && <LiveFeedTab onSignalCount={setSignalCount} />}

      {/* Create — generate content (manual or AI) */}
      {mainTab === 'create' && (
        <div>
          <WhatToPostNext
            onUseSignal={(signal, sub) => {
              setTopic(signal)
              if (sub && SUBREDDITS.includes(sub)) setSubreddit(sub)
              setGenType('insight_digest')
            }}
            onGenerateIntelligence={async () => {
              setGenerating(true)
              setGenError(null)
              try {
                const r = await fetch('/api/value-posts/generate', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ subreddit, type: 'insight_digest', use_intelligence: true }),
                })
                const d = await r.json()
                if (d.ok) await loadPosts()
                else setGenError(d.error || 'Generation failed')
              } catch (e) { setGenError(String(e)) }
              setGenerating(false)
            }}
            generating={generating}
          />
          <CreatePanel
            subreddit={subreddit} setSubreddit={setSubreddit}
            genType={genType}     setGenType={setGenType}
            topic={topic}         setTopic={setTopic}
            generating={generating} genError={genError}
            onGenerate={generate}
            onSaved={loadPosts}
            onBatchDone={loadPosts}
          />
        </div>
      )}

      {/* Queue — approve or discard AI-drafted posts */}
      {mainTab === 'queue' && <QueueTab onDraftCount={setDraftCount} />}

      {/* Library — full post history with filters */}
      {mainTab === 'library' && (
        <div>
          <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
            {[
              { label: 'Total',    val: posts.length,    color: 'var(--text-primary)' },
              { label: 'Draft',    val: counts.draft,    color: '#BA7517' },
              { label: 'Approved', val: counts.approved, color: '#534AB7' },
              { label: 'Posted',   val: counts.posted,   color: '#1D9E75' },
            ].map(s => (
              <div
                key={s.label}
                onClick={() => setFilter(s.label.toLowerCase() === 'total' ? 'all' : s.label.toLowerCase())}
                style={{ flex: 1, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px', cursor: 'pointer' }}
              >
                <div style={{ fontSize: 22, fontWeight: 700, color: s.color, lineHeight: 1 }}>{s.val}</div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4, fontWeight: 600, letterSpacing: '0.04em' }}>
                  {s.label.toUpperCase()}
                </div>
              </div>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 8, marginBottom: 20, flexWrap: 'wrap', alignItems: 'center' }}>
            {['all', 'draft', 'approved', 'posted'].map(f => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  background: filter === f ? 'rgba(83,74,183,0.15)' : 'transparent',
                  color: filter === f ? '#8B82D4' : 'var(--text-secondary)',
                  border: filter === f ? '1px solid rgba(83,74,183,0.4)' : '1px solid var(--border)',
                  padding: '5px 14px', borderRadius: 20, fontSize: 12,
                  fontWeight: filter === f ? 700 : 400, cursor: 'pointer',
                }}
              >
                {f === 'all' ? `All (${posts.length})` : `${f.charAt(0).toUpperCase() + f.slice(1)} (${counts[f] ?? 0})`}
              </button>
            ))}
            {postSubs.length > 0 && (
              <select
                value={subFilter}
                onChange={e => setSubFilter(e.target.value)}
                style={{ marginLeft: 'auto', background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text-secondary)', padding: '5px 10px', borderRadius: 20, fontSize: 12, cursor: 'pointer' }}
              >
                <option value="all">All subreddits</option>
                {postSubs.map(s => <option key={s} value={s}>r/{s}</option>)}
              </select>
            )}
          </div>

          {loading ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)', fontSize: 13 }}>Loading…</div>
          ) : filtered.length === 0 ? (
            <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)', fontSize: 13, lineHeight: 1.8 }}>
              No posts yet.<br />
              <span style={{ fontSize: 12 }}>Generate from the Feed or Create tab.</span>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {filtered.map(p => (
                <PostCard key={p.id} post={p} onUpdate={onUpdate} />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Results — lead attribution per post */}
      {mainTab === 'results' && <ResultsTab />}

      {/* Plan — macro-driven weekly content calendar */}
      {mainTab === 'plan' && <PlanTab />}
    </div>
  )
}
