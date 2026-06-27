import React, { useState, useEffect, useCallback, useRef } from 'react'

const NICHE_CLASS = {
  'financial-advisors':     'fa',
  'trading-coaches':        'tc',
  'recruiters':             'rc',
  'commercial-real-estate': 'cre',
  'msps':                   'msp',
  'altusflow-own':          'fa',
}

const NICHE_LABEL = {
  'financial-advisors':     'Financial Advisor',
  'trading-coaches':        'Trading Coach',
  'recruiters':             'Recruiter',
  'commercial-real-estate': 'CRE Broker',
  'msps':                   'MSP',
  'altusflow-own':          'AltusFlow BD',
}

const TABS = [
  ['pending_review',  'Pending review'],
  ['auto_approved',   'Auto-approved'],
  ['sent',            'Sent'],
  ['replied',         'Replied'],
  ['booked',          'Booked'],
]

const NICHE_PILLS = [
  ['all', 'All'],
  ['fa',  'Financial Advisors'],
  ['tc',  'Trading Coaches'],
  ['rc',  'Recruiters'],
  ['cre', 'CRE'],
  ['msp', 'MSPs'],
]

// ── Live stream badge ─────────────────────────────────────────────────────────
function StreamBadge() {
  const [s, setS] = useState(null)
  useEffect(() => {
    const load = () => fetch('/api/stream/status').then(r => r.ok ? r.json() : null).then(d => d && setS(d)).catch(() => {})
    load()
    const id = setInterval(load, 15_000)
    return () => clearInterval(id)
  }, [])

  if (!s) return null
  const color  = s.running ? 'var(--teal)' : 'var(--coral)'
  const label  = s.running ? 'Live' : 'Stream offline'
  const subs   = (s.subreddits || []).length

  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 7,
      padding: '4px 12px', borderRadius: 20,
      border: `1px solid ${s.running ? 'rgba(29,158,117,0.35)' : 'rgba(216,90,48,0.35)'}`,
      background: s.running ? 'rgba(29,158,117,0.07)' : 'rgba(216,90,48,0.07)',
      fontSize: 11, fontWeight: 600,
    }}>
      <div style={{
        width: 7, height: 7, borderRadius: '50%', background: color,
        ...(s.running ? { animation: 'pulse 2s infinite' } : {}),
      }} />
      <span style={{ color }}>
        {label}{s.running && subs ? ` · ${subs} subreddits` : ''}
      </span>
      {s.running && s.prospects_found > 0 && (
        <span style={{ color: 'var(--text-tertiary)', fontWeight: 400 }}>
          · {s.prospects_found} found this session
        </span>
      )}
    </div>
  )
}

// ── Mod outreach section ──────────────────────────────────────────────────────
// ⚠️ These are SUBREDDIT MODERATORS — not prospects / sales leads.
// Reps must send an intro before posting in a subreddit.
function ModOutreachSection() {
  const [items, setItems]       = useState([])
  const [open, setOpen]         = useState(false)
  const [drafts, setDrafts]     = useState({})
  const [sending, setSending]   = useState({})

  useEffect(() => {
    fetch('/api/mod-outreach?status=pending_review')
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (d.length) { setItems(d); setOpen(true) } })
      .catch(() => {})
  }, [])

  if (items.length === 0) return null

  const handleDraftChange = (id, val) => setDrafts(d => ({ ...d, [id]: val }))

  const handleApprove = async (item) => {
    setSending(s => ({ ...s, [item.id]: true }))
    const draft = drafts[item.id] ?? item.draft
    if (draft !== item.draft) {
      await fetch(`/api/mod-outreach/${item.id}/draft`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft }),
      }).catch(() => {})
    }
    await fetch(`/api/mod-outreach/${item.id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'sent' }),
    }).catch(() => {})
    setItems(i => i.filter(x => x.id !== item.id))
    setSending(s => ({ ...s, [item.id]: false }))
  }

  const handleDismiss = async (id) => {
    await fetch(`/api/mod-outreach/${id}`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'dismissed' }),
    }).catch(() => {})
    setItems(i => i.filter(x => x.id !== id))
  }

  return (
    <div style={{ marginTop: 28 }}>
      {/* Warning header — always visible */}
      <div
        onClick={() => setOpen(o => !o)}
        style={{
          display: 'flex', alignItems: 'center', gap: 10,
          padding: '10px 16px', borderRadius: 'var(--radius-md)',
          background: 'rgba(186,117,23,0.10)',
          border: '1px solid rgba(186,117,23,0.35)',
          cursor: 'pointer', userSelect: 'none',
        }}
      >
        <span style={{ fontSize: 16 }}>⚠️</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--amber)' }}>
            MOD INTRODUCTIONS — {items.length} pending
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
            These are subreddit moderators, not prospects. Approve each intro before you can post in their subreddit.
          </div>
        </div>
        <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{open ? '▲' : '▼'}</span>
      </div>

      {open && (
        <div style={{ marginTop: 10, display: 'flex', flexDirection: 'column', gap: 10 }}>
          {items.map(item => {
            const draft = drafts[item.id] ?? item.draft ?? ''
            return (
              <div key={item.id} style={{
                padding: 16, borderRadius: 'var(--radius-md)',
                background: 'var(--bg-secondary)',
                border: '1px solid rgba(186,117,23,0.25)',
              }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                  <span style={{
                    fontSize: 10, fontWeight: 700, textTransform: 'uppercase',
                    padding: '2px 8px', borderRadius: 10,
                    background: 'rgba(186,117,23,0.15)', color: 'var(--amber)',
                  }}>MOD</span>
                  <span style={{ fontWeight: 600, fontSize: 13 }}>r/{item.subreddit}</span>
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>· {item.niche}</span>
                </div>

                <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 8 }}>
                  Hermes drafted this intro — edit before approving:
                </div>
                <textarea
                  value={draft}
                  onChange={e => handleDraftChange(item.id, e.target.value)}
                  style={{
                    width: '100%', padding: 10, borderRadius: 6,
                    background: 'var(--bg-tertiary)', border: '1px solid var(--border)',
                    color: 'var(--text-primary)', fontSize: 12,
                    resize: 'vertical', minHeight: 80, lineHeight: 1.5,
                  }}
                />

                <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                  <button
                    className="btn btn-primary"
                    style={{ fontSize: 12 }}
                    disabled={!!sending[item.id]}
                    onClick={() => handleApprove(item)}
                  >
                    {sending[item.id] ? 'Sending…' : 'Approve → Send to mods'}
                  </button>
                  <button
                    className="btn"
                    style={{ fontSize: 12 }}
                    onClick={() => handleDismiss(item.id)}
                  >
                    Dismiss
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

function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

function scoreClass(score) {
  if (score >= 8.5) return 'score-high'
  if (score >= 6)   return 'score-mid'
  return 'score-low'
}

function ProspectCard({ p, onApprove, onSkip }) {
  const [dmMsg,       setDmMsg]       = useState(p.drafted_message || '')
  const [commentMsg,  setCommentMsg]  = useState(p.call_opener || '')
  const [draftTab,    setDraftTab]    = useState(p.call_opener ? 'comment' : 'dm')

  // Thread context state
  const [ctxOpen,     setCtxOpen]     = useState(false)
  const [ctxSummary,  setCtxSummary]  = useState(p.context_summary || null)
  const [ctxLoading,  setCtxLoading]  = useState(false)
  const [ctxError,    setCtxError]    = useState(null)

  // DM-log state (conversation moved to DM — high intent)
  const [dmLogged,    setDmLogged]    = useState(false)
  const [dmLogging,   setDmLogging]   = useState(false)

  // X-specific send state
  const [xCopied,     setXCopied]     = useState(false)
  const [xSent,       setXSent]       = useState(false)

  const nicheKey   = NICHE_CLASS[p.niche] || 'fa'
  const isAuto     = p.status === 'auto_approved'
  const isX        = p.platform === 'twitter' || p.platform === 'x'
  const hasComment = !!p.call_opener
  const threadUrl  = p.post_url || (p.subreddit ? `https://reddit.com/r/${p.subreddit}` : null)
  // Extract tweet ID from post_url for X reply intent
  const tweetId    = isX && p.post_url ? p.post_url.split('/status/')[1] : null

  const expandContext = async () => {
    if (ctxSummary) { setCtxOpen(o => !o); return }
    setCtxOpen(true)
    setCtxLoading(true)
    setCtxError(null)
    try {
      const r = await fetch(`/api/prospects/${p.id}/context`, { method: 'POST' })
      const d = await r.json()
      if (d.ok) setCtxSummary(d.summary)
      else setCtxError(d.error || 'Failed')
    } catch (e) { setCtxError(String(e)) }
    setCtxLoading(false)
  }

  const logDmMoved = async () => {
    setDmLogging(true)
    try {
      await fetch(`/api/prospects/${p.id}/dm-log`, { method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ note: '' }),
      })
      setDmLogged(true)
    } catch {}
    setDmLogging(false)
  }

  // Parse context summary into bullet lines for rendering
  const ctxBullets = ctxSummary
    ? ctxSummary.split('\n').filter(l => l.trim().startsWith('•') || l.trim().startsWith('-'))
    : []

  return (
    <div className={`prospect-card${nicheKey !== 'fa' ? ' ' + nicheKey : ''}`}>
      {/* ── Meta row ── */}
      <div className="prospect-meta">
        <span className={`niche-badge niche-${nicheKey}`}>{NICHE_LABEL[p.niche] || p.niche}</span>
        {p.subreddit && <><span className="prospect-meta-text">r/{p.subreddit}</span><span className="prospect-meta-text">·</span></>}
        <span className="prospect-meta-text">{p.post_date ? timeAgo(p.post_date) : '2h ago'}</span>
        {p.source === 'live_stream' && (
          <span style={{
            fontSize: 9, fontWeight: 800, textTransform: 'uppercase',
            letterSpacing: '0.08em', padding: '2px 6px', borderRadius: 8,
            background: 'rgba(29,158,117,0.18)', color: 'var(--teal)',
            border: '1px solid rgba(29,158,117,0.3)',
          }}>LIVE</span>
        )}
        <span className={`platform-badge ${isX ? 'platform-x' : 'platform-reddit'}`} style={{ marginLeft: 'auto' }}>
          {isX ? '𝕏' : 'Reddit'}
        </span>
      </div>

      {/* ── Name + score ── */}
      <div className="prospect-top">
        <div className="prospect-username">{isX ? '' : 'u/'}{p.handle}</div>
        <div className="prospect-scores">
          <span className={scoreClass(p.icp_score)}>{p.icp_score} / 10</span>
          {isAuto && <span className="auto-badge">Auto ✓</span>}
        </div>
      </div>

      {/* ── Original post ── */}
      <div className="prospect-post">"{p.post_text}"</div>

      {/* ── Thread context strip ── */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 8 }}>
        <button
          onClick={expandContext}
          style={{
            display: 'inline-flex', alignItems: 'center', gap: 5,
            background: ctxOpen ? 'rgba(83,74,183,0.12)' : 'transparent',
            color: ctxOpen ? '#8B82D4' : 'var(--text-tertiary)',
            border: `1px solid ${ctxOpen ? 'rgba(83,74,183,0.35)' : 'var(--border)'}`,
            borderRadius: 20, padding: '3px 11px', fontSize: 11, fontWeight: 600,
            cursor: 'pointer', transition: 'all 0.15s',
          }}
        >
          {ctxLoading ? '⏳' : '🔍'} {ctxSummary ? (ctxOpen ? 'Hide context' : 'Thread context') : 'Expand context'}
        </button>

        {threadUrl && (
          <a
            href={threadUrl}
            target="_blank"
            rel="noreferrer"
            style={{
              display: 'inline-flex', alignItems: 'center', gap: 4,
              color: 'var(--text-tertiary)', fontSize: 11, fontWeight: 600,
              textDecoration: 'none', padding: '3px 10px',
              border: '1px solid var(--border)', borderRadius: 20,
              transition: 'color 0.15s',
            }}
            onMouseEnter={e => e.currentTarget.style.color = 'var(--teal)'}
            onMouseLeave={e => e.currentTarget.style.color = 'var(--text-tertiary)'}
          >
            ↗ View thread
          </a>
        )}
      </div>

      {/* ── Context summary panel ── */}
      {ctxOpen && (
        <div style={{
          background: 'rgba(83,74,183,0.06)', border: '1px solid rgba(83,74,183,0.20)',
          borderRadius: 8, padding: '12px 14px', marginBottom: 10,
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#8B82D4',
            textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 8 }}>
            Hermes · Thread intel
          </div>
          {ctxLoading && (
            <div style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
              Reading the thread…
            </div>
          )}
          {ctxError && (
            <div style={{ fontSize: 12, color: 'var(--coral)' }}>{ctxError}</div>
          )}
          {!ctxLoading && ctxSummary && (
            ctxBullets.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
                {ctxBullets.map((line, i) => {
                  const clean = line.replace(/^[•\-]\s*/, '')
                  const label = clean.match(/^\[([A-Z]+)\]/)
                  const rest  = label ? clean.slice(label[0].length).trim() : clean
                  const colors = ['#BA7517', '#534AB7', '#1D9E75']
                  return (
                    <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                      {label && (
                        <span style={{
                          fontSize: 9, fontWeight: 800, padding: '2px 6px', borderRadius: 4,
                          background: `${colors[i] || '#888'}22`, color: colors[i] || '#888',
                          whiteSpace: 'nowrap', marginTop: 1,
                        }}>
                          {label[1]}
                        </span>
                      )}
                      <span style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
                        {rest}
                      </span>
                    </div>
                  )
                })}
              </div>
            ) : (
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
                {ctxSummary}
              </div>
            )
          )}
        </div>
      )}

      {/* ── Draft tabs — Public Comment first, then DM ── */}
      <div style={{ display: 'flex', gap: 0, marginBottom: 8, borderBottom: '1px solid var(--border)' }}>
        {hasComment && (
          <button
            onClick={() => setDraftTab('comment')}
            style={{
              padding: '6px 12px', fontSize: 11, fontWeight: 600, border: 'none',
              background: 'none', cursor: 'pointer',
              color: draftTab === 'comment' ? 'var(--teal)' : 'var(--text-tertiary)',
              borderBottom: draftTab === 'comment' ? '2px solid var(--teal)' : '2px solid transparent',
            }}
          >
            {isX ? '💬 Reply on X' : '💬 Public comment'}
          </button>
        )}
        <button
          onClick={() => setDraftTab('dm')}
          style={{
            padding: '6px 12px', fontSize: 11, fontWeight: 600, border: 'none',
            background: 'none', cursor: 'pointer',
            color: draftTab === 'dm' ? 'var(--teal)' : 'var(--text-tertiary)',
            borderBottom: draftTab === 'dm' ? '2px solid var(--teal)' : '2px solid transparent',
          }}
        >
          {isX ? '✉️ DM on X' : '✉️ DM'}
        </button>
      </div>

      {draftTab === 'comment' && hasComment ? (
        <>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 6 }}>
            {isX
              ? 'Reply publicly to their tweet — gets seen, warms them up before any DM. Keep under 280 chars.'
              : 'Post this as a helpful reply to their thread — gets seen by everyone, not just them. Send BEFORE the DM.'}
          </div>
          <textarea
            className="prospect-message"
            value={commentMsg}
            onChange={e => setCommentMsg(e.target.value)}
          />
          <div className={`char-counter${commentMsg.length > (isX ? 270 : 900) ? ' warn' : ''}`}>
            {commentMsg.length}{isX ? ' / 280' : ' chars'}
          </div>
          <div className="prospect-actions">
            <button
              className="btn-approve"
              onClick={() => {
                navigator.clipboard?.writeText(commentMsg)
                if (isX && tweetId) {
                  window.open(
                    `https://x.com/intent/tweet?in_reply_to=${tweetId}&text=${encodeURIComponent(commentMsg)}`,
                    'x-reply', 'width=620,height=680,scrollbars=yes,resizable=yes,left=200,top=100'
                  )
                } else {
                  window.open(threadUrl || `https://reddit.com/r/${p.subreddit}`, '_blank')
                }
              }}
            >
              {isX ? 'Copy & Reply on X →' : 'Copy & Open thread →'}
            </button>
            <button
              style={{ fontSize: 11, color: 'var(--text-secondary)', background: 'none', border: 'none', cursor: 'pointer' }}
              onClick={() => setDraftTab('dm')}
            >
              {isX ? 'Next: DM on X →' : 'Next: review DM →'}
            </button>
          </div>
        </>
      ) : (
        <>
          <textarea
            className="prospect-message"
            value={dmMsg}
            onChange={e => setDmMsg(e.target.value)}
          />
          <div className={`char-counter${dmMsg.length > 270 ? ' warn' : ''}`}>{dmMsg.length} / 300</div>

          {isX ? (
            /* X — inline compose, never leaves dashboard */
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {xSent ? (
                <div style={{ fontSize: 12, color: 'var(--teal)', display: 'flex', alignItems: 'center', gap: 6, padding: '6px 0' }}>
                  ✓ Marked as sent — journey stage advanced
                </div>
              ) : (
                <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
                  <button
                    className="btn-approve"
                    onClick={async () => {
                      await navigator.clipboard?.writeText(dmMsg)
                      setXCopied(true)
                      setTimeout(() => setXCopied(false), 2000)
                    }}
                    style={{ minWidth: 120, transition: 'all 0.15s' }}
                  >
                    {xCopied ? '✓ Copied' : '📋 Copy message'}
                  </button>
                  <a
                    href={`https://x.com/${(p.handle || '').replace(/^@/, '')}`}
                    target="_blank"
                    rel="noreferrer"
                    style={{ fontSize: 11, color: 'var(--text-tertiary)', textDecoration: 'none' }}
                  >
                    ↗ Open their X
                  </a>
                  <button
                    onClick={() => { onApprove(p.id, dmMsg); setXSent(true) }}
                    style={{
                      marginLeft: 'auto', background: 'rgba(29,158,117,0.10)', color: 'var(--teal)',
                      border: '1px solid rgba(29,158,117,0.3)', borderRadius: 6,
                      padding: '6px 16px', fontSize: 11, fontWeight: 700, cursor: 'pointer',
                    }}
                  >
                    ✓ Mark as sent
                  </button>
                  <button className="btn-skip" onClick={() => onSkip(p.id)}>Skip</button>
                </div>
              )}
            </div>
          ) : (
            /* Reddit — popup compose pre-filled */
            <div className="prospect-actions">
              <button
                className="btn-approve"
                onClick={() => {
                  const handle = (p.handle || '').replace(/^u\//, '').replace(/^@/, '')
                  window.open(
                    `https://www.reddit.com/message/compose/?to=${encodeURIComponent(handle)}&message=${encodeURIComponent(dmMsg)}`,
                    'send-dm', 'width=620,height=680,scrollbars=yes,resizable=yes,left=200,top=100'
                  )
                  onApprove(p.id, dmMsg)
                }}
              >
                ↗ Send via Reddit
              </button>
              <button className="btn-skip" onClick={() => onSkip(p.id)}>Skip</button>
              <button className="btn btn-sm">View in Reply Center →</button>
            </div>
          )}

          {/* DM-moved signal — rep logs when conversation leaves Reddit thread and enters DM */}
          <div style={{
            marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            {dmLogged ? (
              <div style={{
                fontSize: 11, color: 'var(--teal)', display: 'flex', alignItems: 'center', gap: 5,
              }}>
                ✓ Logged as DM conversation — journey stage advanced
              </div>
            ) : (
              <>
                <button
                  onClick={logDmMoved}
                  disabled={dmLogging}
                  style={{
                    background: 'rgba(29,158,117,0.10)', color: 'var(--teal)',
                    border: '1px solid rgba(29,158,117,0.3)',
                    borderRadius: 6, padding: '4px 12px', fontSize: 11, fontWeight: 700,
                    cursor: dmLogging ? 'wait' : 'pointer', opacity: dmLogging ? 0.6 : 1,
                  }}
                >
                  {dmLogging ? '…' : isX ? '💬 They replied on X' : '💬 Moved to DM'}
                </button>
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                  {isX ? 'They replied to your tweet or DM? Log it — advances their Journey stage' : 'They replied privately? Log it — advances their Journey stage'}
                </span>
              </>
            )}
          </div>
        </>
      )}
    </div>
  )
}

export default function Prospects() {
  const [tab, setTab]         = useState('pending_review')
  const [niche, setNiche]     = useState('all')
  const [prospects, setProspects] = useState([
    { id: 1, platform: 'reddit', source: 'reddit', niche: 'financial-advisors', niche_segment: 'financial-advisors', handle: 'riaowner_chicago', subreddit: 'FinancialAdvisors', post_url: 'https://www.reddit.com/r/FinancialAdvisors/comments/1dz2k4p/been_a_cfp_for_8_years_and_this_is_the_first/', post_date: new Date(Date.now() - 2*3600000).toISOString(), icp_score: 9, status: 'pending_review', signal_phrase: 'pipeline dried up', post_text: 'Been a CFP for 8 years and this is the first quarter my pipeline has completely dried up. Referrals stopped, LinkedIn feels like shouting into a void. Anyone actually finding new clients without paying $5k/mo for leads?', drafted_message: "Saw your post — referral slowdowns are hitting a lot of FAs right now. Are you finding that the people you'd normally get referrals from are just quieter in general, or is it something else?", call_opener: "This is one of the most common things I see right now — referral networks going quiet for the first time in years. One thing that's been working: picking 3 former clients and asking them a specific question about their network, not asking for a referral. Changes the whole dynamic." },
    { id: 2, platform: 'reddit', source: 'live_stream', niche: 'trading-coaches', niche_segment: 'trading-coaches', handle: 'futurestrader99', subreddit: 'Daytrading', post_url: 'https://www.reddit.com/r/Daytrading/comments/1e1m9qr/running_a_futures_trading_community_for_2_years/', post_date: new Date(Date.now() - 5*3600000).toISOString(), icp_score: 8, status: 'pending_review', signal_phrase: 'growing our trading community', post_text: 'Running a futures trading community for 2 years, 340 members but engagement is dying. People join, watch a few videos, then ghost. Tried Discord, Skype, even a private subreddit. Nothing sticks.', drafted_message: "Your retention problem is really common — most trading communities die at the content stage because members never get accountability. Have you tried pairing members for weekly P&L check-ins?", call_opener: "The ghosting pattern you're describing usually happens when there's no structured reason to come back. Accountability pods — pairs of members who share weekly P&L — solve this faster than any content format." },
    { id: 3, platform: 'twitter', source: 'twitter', niche: 'recruiters', niche_segment: 'recruiters', handle: 'recruiter_nyc', subreddit: '', post_url: 'https://twitter.com/recruiter_nyc/status/1234567890', post_date: new Date(Date.now() - 8*3600000).toISOString(), icp_score: 7, status: 'pending_review', signal_phrase: 'BD is brutal right now', post_text: 'BD is brutal right now. Clients are ghosting, candidates are flaking, and everyone wants a retained search fee but nobody wants to pay for one. Is this just NYC or is the whole market like this?', drafted_message: "Saw your tweet — the retained vs contingency tension is at an all-time high right now. Are you finding clients pushing back on fees specifically, or is it more about response time?" },
    { id: 4, platform: 'reddit', source: 'reddit', niche: 'financial-advisors', niche_segment: 'financial-advisors', handle: 'wealthmgr_dallas', subreddit: 'personalfinance', post_url: 'https://www.reddit.com/r/personalfinance/comments/1e4r8wz/i_need_to_book_more_discovery_calls_running/', post_date: new Date(Date.now() - 14*3600000).toISOString(), icp_score: 8, status: 'auto_approved', signal_phrase: 'need more booked calls', post_text: 'I need to book more discovery calls. Running Google ads ($800/mo), posting on LinkedIn daily, and still averaging 1-2 new inquiries per week. Feels like I should be getting more. What am I missing?', drafted_message: "The ad → call funnel for FAs is almost always broken at the landing page, not the ad. Are you sending them to a generic website or a specific page built around the offer?" },
    { id: 5, platform: 'reddit', source: 'reddit', niche: 'msps', niche_segment: 'msps', handle: 'msp_founder_ohio', subreddit: 'msp', post_url: 'https://www.reddit.com/r/msp/comments/1dw7p3n/were_a_6person_msp_in_the_midwest_been_around_5/', post_date: new Date(Date.now() - 20*3600000).toISOString(), icp_score: 7, status: 'pending_review', signal_phrase: 'struggling to find clients', post_text: 'We\'re a 6-person MSP in the midwest, been around 5 years. Every client we have came from referrals. Tried cold email — zero responses. Tried LinkedIn — one meeting in 3 months. How do other MSPs actually grow?', drafted_message: "Cold outreach for MSPs almost never works until you get hyper-specific on the vertical. Are you targeting a specific type of business, or going broad?" },
    { id: 6, platform: 'twitter', source: 'twitter', niche: 'commercial-real-estate', niche_segment: 'commercial-real-estate', handle: 'cre_broker_atl', subreddit: '', post_url: 'https://twitter.com/cre_broker_atl/status/9876543210', post_date: new Date(Date.now() - 26*3600000).toISOString(), icp_score: 6, status: 'pending_review', signal_phrase: 'deal flow slow', post_text: 'Deal flow is the slowest I\'ve seen since 2020. Buyers are waiting on rate cuts that keep not coming. Sellers still think it\'s 2021. Meanwhile I\'m just trying to keep the lights on. Anyone else in the same boat?', drafted_message: "The rate-cut waiting game is killing deal velocity everywhere right now. Are you pivoting toward lease renewals in the meantime, or trying to find motivated sellers who need to move regardless?" },
  ])
  const [stats, setStats]     = useState({
    found_today: 14, auto_approved: 6, pending_review: 8,
    reply_rate: 25, sent_week: 47, replied_week: 12, booked: 0,
  })

  const fetchData = useCallback(async () => {
    try {
      const [pRes, sRes] = await Promise.all([
        fetch(`/api/prospects?status=${tab}`),
        fetch('/api/prospects/stats'),
      ])
      if (pRes.ok) { const d = await pRes.json(); if (Array.isArray(d) && d.length > 0) setProspects(d) }
      if (sRes.ok) { const d = await sRes.json(); if (d && Object.keys(d).length > 0) setStats(s => ({ ...s, ...d })) }
    } catch {}
  }, [tab])

  useEffect(() => { fetchData() }, [fetchData])

  async function handleApprove(id, message) {
    try {
      await fetch(`/api/prospects/${id}/approve`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message }),
      })
    } catch {}
    setProspects(ps => ps.filter(p => p.id !== id))
  }

  function handleSkip(id) {
    setProspects(ps => ps.filter(p => p.id !== id))
  }

  const tabCounts = {
    pending_review: stats.pending_review ?? 8,
    auto_approved:  stats.auto_approved  ?? 6,
    sent:           stats.sent_week      ?? 47,
    replied:        stats.replied_week   ?? 12,
    booked:         stats.booked         ?? 0,
  }

  const nicheCountMap = { all: 14, fa: 8, tc: 4, rc: 2, cre: 0, msp: 0 }

  const filtered = niche === 'all'
    ? prospects
    : prospects.filter(p => (NICHE_CLASS[p.niche] || 'fa') === niche)

  return (
    <div className="content">
      {/* Stream status — shows live/offline, subreddit count, session finds */}
      <div style={{ marginBottom: 14 }}>
        <StreamBadge />
      </div>

      <div className="stat-grid">
        <div className="stat-card rag-green">
          <div className="stat-label">Found today</div>
          <div className="stat-value">{stats.found_today ?? 14}</div>
          <div className="stat-delta up">↑ 3 vs yesterday</div>
        </div>
        <div className="stat-card rag-green">
          <div className="stat-label">Auto-approved</div>
          <div className="stat-value">{stats.auto_approved ?? 6}</div>
          <div className="stat-delta">Score 9+ auto-queued</div>
        </div>
        <div className="stat-card rag-amber">
          <div className="stat-label">Pending review</div>
          <div className="stat-value">{stats.pending_review ?? 8}</div>
          <div className="stat-delta">Score 4–8 needs you</div>
        </div>
        <div className="stat-card rag-green">
          <div className="stat-label">Reply rate</div>
          <div className="stat-value">{stats.reply_rate ?? 25}%</div>
          <div className="stat-delta up">{stats.sent_week ?? 47} sent · {stats.replied_week ?? 12} replied</div>
        </div>
      </div>

      <div className="tab-row">
        {TABS.map(([key, label]) => (
          <button
            key={key}
            className={'tab' + (tab === key ? ' active' : '')}
            onClick={() => setTab(key)}
          >
            {label} ({tabCounts[key]})
          </button>
        ))}
      </div>

      <div className="niche-pills">
        {NICHE_PILLS.map(([key, label]) => (
          <button
            key={key}
            className={'niche-pill' + (niche === key ? ` active-${key === 'all' ? 'fa' : key}` : '')}
            onClick={() => setNiche(key)}
          >
            {label} ({nicheCountMap[key] ?? 0})
          </button>
        ))}
      </div>

      <div id="prospect-list">
        {filtered.length === 0 ? (
          <div className="card" style={{ padding: 40, textAlign: 'center', color: 'var(--text-tertiary)' }}>
            Stream is live — new posts appear here as they're found
          </div>
        ) : filtered.map(p => (
          <ProspectCard key={p.id} p={p} onApprove={handleApprove} onSkip={handleSkip} />
        ))}
      </div>

      {/* Mod outreach — clearly separated, never confused with prospects */}
      <ModOutreachSection />
    </div>
  )
}
