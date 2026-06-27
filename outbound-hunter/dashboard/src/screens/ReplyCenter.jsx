import React, { useState, useEffect, useRef, useCallback } from 'react'

// ── Source config ─────────────────────────────────────────────────────────────
const SOURCE_CFG = {
  scrapebadger: { label: 'Scrape Badger', icon: '🎯', color: '#D85A30', bg: 'rgba(216,90,48,0.12)',  border: 'rgba(216,90,48,0.35)'  },
  post_comment:  { label: 'Post Comment',  icon: '💬', color: '#534AB7', bg: 'rgba(83,74,183,0.12)',  border: 'rgba(83,74,183,0.35)'  },
  cold_stream:   { label: 'Stream',        icon: '🔍', color: '#1D9E75', bg: 'rgba(29,158,117,0.12)', border: 'rgba(29,158,117,0.35)' },
  creator:       { label: 'Creator',       icon: '🤝', color: '#BA7517', bg: 'rgba(186,117,23,0.12)', border: 'rgba(186,117,23,0.35)' },
}

const SOURCE_TABS = [
  { key: 'all',          label: 'All',          icon: '📥' },
  { key: 'scrapebadger', label: 'Scrape Badger', icon: '🎯' },
  { key: 'post_comment', label: 'Post Comments', icon: '💬' },
  { key: 'cold_stream',  label: 'Stream',        icon: '🔍' },
  { key: 'creator',      label: 'Creators',      icon: '🤝' },
]

const NICHE_CLASS = {
  'financial-advisors':     'fa',
  'trading-coaches':        'tc',
  'recruiters':             'rc',
  'commercial-real-estate': 'cre',
  'msps':                   'msp',
  'altusflow-own':          'fa',
}

const AVATAR_COLORS = {
  fa:  { bg: '#E1F5EE', color: '#085041' },
  tc:  { bg: '#EEEDFE', color: '#3C3489' },
  rc:  { bg: '#FAEEDA', color: '#633806' },
  cre: { bg: '#EAF2FD', color: '#1A5490' },
  msp: { bg: '#FAECE7', color: '#712B13' },
}

const QUICK_BTNS = ['▶ Loom demo', '📄 Pitch page', '📅 Calendly', '💰 Price redirect', '📊 Case study']

function normalizeMode(m) {
  if (!m) return 'auto'
  if (m === 'full_auto') return 'auto'
  if (m === 'human_only') return 'human'
  return m
}

function initials(handle) {
  if (!handle) return '??'
  const parts = handle.replace(/[_-]/g, ' ').split(/\s+/)
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase()
  return handle.slice(0, 2).toUpperCase()
}

function timeAgo(dateStr) {
  if (!dateStr) return ''
  const diff = Date.now() - new Date(dateStr).getTime()
  const h = Math.floor(diff / 3_600_000)
  if (h < 1) return 'now'
  if (h < 24) return `${h}h`
  return `${Math.floor(h / 24)}d`
}

function SourceTag({ source, small }) {
  const cfg = SOURCE_CFG[source] || SOURCE_CFG.cold_stream
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 3,
      background: cfg.bg, border: `1px solid ${cfg.border}`,
      color: cfg.color, borderRadius: 4,
      fontSize: small ? 9 : 10, fontWeight: 700,
      padding: small ? '1px 5px' : '2px 7px',
      letterSpacing: '0.02em', whiteSpace: 'nowrap',
    }}>
      {cfg.icon} {cfg.label}
    </span>
  )
}

function openRedditDM(handle, message) {
  const clean = (handle || '').replace(/^u\//, '').replace(/^@/, '')
  const url   = `https://www.reddit.com/message/compose/?to=${encodeURIComponent(clean)}&message=${encodeURIComponent(message || '')}`
  window.open(url, 'reddit-dm', 'width=620,height=680,scrollbars=yes,resizable=yes,left=200,top=100')
}

function openXDM(handle) {
  const clean = (handle || '').replace(/^@/, '')
  window.open(`https://x.com/${encodeURIComponent(clean)}`, 'x-dm', 'width=620,height=680,scrollbars=yes,resizable=yes,left=200,top=100')
}

function SendButton({ platform, compose, onSend, sending, sent }) {
  const isX     = (platform || '').toLowerCase() === 'x'
  const disabled = !compose?.trim() || sending
  return (
    <button
      className="sbtn primary"
      onClick={onSend}
      disabled={disabled}
      style={{ opacity: disabled ? 0.5 : 1, minWidth: 160 }}
    >
      {sent ? '✓ Sent' : sending ? 'Opening…' : isX ? '↗ Open X profile' : '↗ Send via Reddit'}
    </button>
  )
}

// ── Sentiment shift badge ────────────────────────────────────────────────────
function SentimentShift({ convId, initialShift, ctx }) {
  const [shift,    setShift]    = useState(initialShift || null)
  const [loading,  setLoading]  = useState(false)
  const [fetched,  setFetched]  = useState(!!initialShift)

  const analyse = async () => {
    setLoading(true)
    try {
      const r = await fetch(`/api/conversations/${convId}/sentiment-shift`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          comment_body: ctx.post_text || '',
          post_title:   ctx.post_title || '',
          signal:       ctx.signal || '',
        }),
      })
      const d = await r.json()
      if (d.ok && d.sentiment) { setShift(d.sentiment); setFetched(true) }
    } catch {}
    setLoading(false)
  }

  // Auto-fetch once per conversation open if not yet stored
  useEffect(() => {
    if (!fetched && !loading) analyse()
  }, [convId])

  if (!shift && !loading) return null

  if (loading) return (
    <div style={{
      fontSize: 10, color: 'var(--text-tertiary)', fontStyle: 'italic',
      display: 'flex', alignItems: 'center', gap: 5,
    }}>
      <span style={{ display: 'inline-block', width: 8, height: 8, borderRadius: '50%', background: '#534AB7', opacity: 0.5 }} />
      Hermes reading sentiment…
    </div>
  )

  const intent  = shift.intent || 0
  const iColor  = intent >= 70 ? '#1D9E75' : intent >= 40 ? '#BA7517' : 'var(--text-tertiary)'
  const iBg     = intent >= 70 ? 'rgba(29,158,117,0.08)' : intent >= 40 ? 'rgba(186,117,23,0.08)' : 'rgba(255,255,255,0.03)'
  const iBorder = intent >= 70 ? 'rgba(29,158,117,0.25)' : intent >= 40 ? 'rgba(186,117,23,0.25)' : 'var(--border)'

  return (
    <div style={{
      background: iBg, border: `1px solid ${iBorder}`,
      borderRadius: 7, padding: '8px 10px',
      display: 'flex', flexDirection: 'column', gap: 4,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 7 }}>
        <span style={{ fontSize: 11 }}>🧠</span>
        <span style={{ fontSize: 10, fontWeight: 700, color: iColor, flex: 1 }}>
          {shift.label}
        </span>
        <span style={{
          fontSize: 10, fontWeight: 700, color: iColor,
          background: iBorder !== 'var(--border)' ? iBg : 'transparent',
          padding: '1px 6px', borderRadius: 8,
        }}>
          Intent {intent}%
        </span>
      </div>
      {shift.shift && (
        <div style={{ fontSize: 10, color: 'var(--text-secondary)', lineHeight: 1.5, paddingLeft: 18 }}>
          {shift.shift}
        </div>
      )}
    </div>
  )
}

// ── Context card — shows Hermes why this lead is here ────────────────────────
function ContextCard({ conv }) {
  const src = SOURCE_CFG[conv.source] || SOURCE_CFG.cold_stream
  const ctx = conv.source_context || {}
  const platform = (conv.platform || 'reddit').toLowerCase()
  const existingShift = ctx.sentiment_shift || null

  return (
    <div style={{
      margin: '0 14px 10px',
      background: src.bg, border: `1px solid ${src.border}`,
      borderRadius: 8, padding: '10px 14px',
      display: 'flex', flexDirection: 'column', gap: 6,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        <SourceTag source={conv.source} />
        <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
          {platform === 'x' ? '𝕏 Twitter/X' : `Reddit${conv.subreddit ? ` · r/${conv.subreddit}` : ''}`}
        </span>
        {/* Intent shown by SentimentShift for post_comment; legacy badge for others */}
        {conv.source !== 'post_comment' && ctx.intent != null && ctx.intent > 0 && (
          <span style={{
            marginLeft: 'auto', fontSize: 10, fontWeight: 700,
            color: ctx.intent >= 70 ? '#1D9E75' : ctx.intent >= 40 ? '#BA7517' : 'var(--text-tertiary)',
          }}>
            Intent {ctx.intent}%
          </span>
        )}
      </div>

      {ctx.signal && (
        <div style={{ fontSize: 11, color: 'var(--text-primary)', fontWeight: 600 }}>
          Signal: <span style={{ color: src.color }}>"{ctx.signal}"</span>
        </div>
      )}

      {ctx.post_text && (
        <div style={{
          fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic',
          lineHeight: 1.5, borderLeft: `2px solid ${src.border}`, paddingLeft: 8,
        }}>
          "{ctx.post_text.slice(0, 220)}{ctx.post_text.length > 220 ? '…' : ''}"
        </div>
      )}

      {ctx.post_url && (
        <a
          href={ctx.post_url} target="_blank" rel="noreferrer"
          style={{
            fontSize: 10, color: src.color, textDecoration: 'none',
            display: 'inline-flex', alignItems: 'center', gap: 4,
          }}
        >
          ↗ View original post
        </a>
      )}

      {conv.source === 'post_comment' && ctx.post_title && (
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
          Commented on: <span style={{ color: 'var(--text-secondary)' }}>{ctx.post_title}</span>
        </div>
      )}

      {/* Sentiment Shift — only for post_comment leads */}
      {conv.source === 'post_comment' && (
        <SentimentShift
          convId={conv.id}
          initialShift={existingShift}
          ctx={ctx}
        />
      )}

      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', borderTop: `1px solid ${src.border}`, paddingTop: 6, marginTop: 2 }}>
        💡 Hermes context: {
          conv.source === 'scrapebadger' ? 'High-intent lead found by Scrape Badger — they explicitly expressed this pain. Reference their post in your opener.' :
          conv.source === 'post_comment' ? 'Warm lead — they engaged with your value post. They already know who you are. Lower friction than cold.' :
          conv.source === 'creator'      ? 'Creator partnership lead — focus on audience overlap and mutual value, not your product.' :
          'Stream lead — found via live pain signal monitoring. They posted publicly about this struggle.'
        }
      </div>
    </div>
  )
}

// ── Demo data ────────────────────────────────────────────────────────────────
const DEMO_CONVS = [
  {
    id: 1, handle: 'futurestrader99', platform: 'reddit', subreddit: 'Daytrading',
    niche: 'trading-coaches', mode: 'assist', unread: true, source: 'scrapebadger',
    source_context: { signal: 'blown account', post_text: 'Down 40% in 3 days on NQ. I know exactly what I did wrong but I keep repeating it. Starting to think I need outside help.', post_url: 'https://reddit.com/r/Daytrading/comments/abc123', intent: 87 },
    last_message: 'Down 40% in 3 days on NQ. I know exactly what I did wrong but I keep repeating it.',
    last_at: new Date(Date.now() - 2*3600000).toISOString(),
  },
  {
    id: 2, handle: 'revenge_trader_dm', platform: 'reddit', subreddit: 'Futures',
    niche: 'trading-coaches', mode: 'auto', unread: true, source: 'post_comment',
    source_context: { signal: 'revenge trading', post_text: 'Loved this post. I literally did exactly this last Tuesday — down $800, kept going, ended down $2,400. When does this stop?', post_title: 'What I\'m seeing in r/Daytrading this week — patterns worth knowing about', post_url: 'https://reddit.com/r/Daytrading/comments/xyz789' },
    last_message: 'Loved this post. I literally did exactly this last Tuesday — down $800, kept going, ended down $2,400.',
    last_at: new Date(Date.now() - 5*3600000).toISOString(),
  },
  {
    id: 3, handle: 'TraderLion', platform: 'reddit', subreddit: '',
    niche: 'trading-coaches', mode: 'human', unread: false, source: 'creator',
    source_context: { signal: 'audience collaboration', post_text: 'Open to collab opportunities with trading educators focused on momentum. DMs open.', post_url: 'https://x.com/TraderLion' },
    last_message: 'Open to collab opportunities with trading educators focused on momentum.',
    last_at: new Date(Date.now() - 14*3600000).toISOString(),
  },
  {
    id: 4, handle: 'losing_streak_guy', platform: 'reddit', subreddit: 'Daytrading',
    niche: 'trading-coaches', mode: 'assist', unread: false, source: 'cold_stream',
    source_context: { signal: 'keep losing', post_text: '6 months in and still not profitable. Tried everything on YouTube. Starting to think this isn\'t for me.', post_url: 'https://reddit.com/r/Daytrading/comments/def456', intent: 62 },
    last_message: '6 months in and still not profitable. Tried everything on YouTube.',
    last_at: new Date(Date.now() - 26*3600000).toISOString(),
  },
]

const DEMO_MESSAGES = {
  1: [
    { id: 1, sender: 'prospect', body: 'Down 40% in 3 days on NQ. I know exactly what I did wrong but I keep repeating it. Starting to think I need outside help.', sent_at: new Date(Date.now() - 5*3600000).toISOString() },
    { id: 2, sender: 'human',    body: "That loop of knowing what you're doing wrong but still doing it — that's not a strategy problem, it's a process problem. What does your daily loss limit look like right now?", sent_at: new Date(Date.now() - 4*3600000).toISOString() },
    { id: 3, sender: 'prospect', body: "Honestly don't have one. I just trade until I feel like stopping or until I've given back too much.", sent_at: new Date(Date.now() - 2*3600000).toISOString() },
  ],
  2: [
    { id: 4, sender: 'prospect', body: "Loved this post. I literally did exactly this last Tuesday — down $800, kept going, ended down $2,400. When does this stop?", sent_at: new Date(Date.now() - 6*3600000).toISOString() },
    { id: 5, sender: 'human',    body: "It stops when the cost of stopping is less painful than the cost of continuing. For most people that's a hard daily max — you hit it, platform closes, you go for a walk. Sounds rigid but it's the only thing that actually works.", sent_at: new Date(Date.now() - 5*3600000).toISOString() },
  ],
  3: [
    { id: 6, sender: 'human',    body: "Hey — big fan of what you're building with TraderLion. We work exclusively with momentum trading educators and I think there's a real audience overlap worth exploring. Open to a quick call?", sent_at: new Date(Date.now() - 15*3600000).toISOString() },
    { id: 7, sender: 'prospect', body: "Yeah I saw your posts. What kind of collab are you thinking?", sent_at: new Date(Date.now() - 14*3600000).toISOString() },
  ],
  4: [
    { id: 8, sender: 'prospect', body: "6 months in and still not profitable. Tried everything on YouTube. Starting to think this isn't for me.", sent_at: new Date(Date.now() - 27*3600000).toISOString() },
  ],
}

// ── Main component ───────────────────────────────────────────────────────────
export default function ReplyCenter() {
  const [convs,      setConvs]      = useState([])
  const [active,     setActive]     = useState(null)
  const [messages,   setMessages]   = useState([])
  const [convMode,   setConvMode]   = useState('auto')
  const [compose,    setCompose]    = useState('')
  const [suggestion, setSuggestion] = useState(null)
  const [sourceTab,  setSourceTab]  = useState('all')
  const [sending,         setSending]         = useState(false)
  const [sent,            setSent]            = useState(false)
  const [search,          setSearch]          = useState('')
  const [trackLink,       setTrackLink]       = useState(null)
  const [trackLinkCopied, setTrackLinkCopied] = useState(false)
  const bottomRef                   = useRef(null)

  const loadConvs = useCallback(async (tab = 'all') => {
    const url = tab !== 'all' ? `/api/conversations?source=${tab}` : '/api/conversations'
    try {
      const r = await fetch(url)
      const d = r.ok ? await r.json() : []
      const list = Array.isArray(d) && d.length > 0 ? d : DEMO_CONVS
      setConvs(list)
      if (!active) selectConv(list[0])
    } catch {
      setConvs(DEMO_CONVS)
      selectConv(DEMO_CONVS[0])
    }
  }, [active])

  useEffect(() => { loadConvs(sourceTab) }, [sourceTab])

  function selectConv(conv) {
    if (!conv) return
    setActive(conv)
    setConvMode(normalizeMode(conv.mode))
    setCompose('')
    setSuggestion(null)
    setSent(false)
    if (DEMO_MESSAGES[conv.id]) setMessages(DEMO_MESSAGES[conv.id])
    fetch(`/api/conversations/${conv.id}/messages`)
      .then(r => r.ok ? r.json() : [])
      .then(msgs => { if (Array.isArray(msgs) && msgs.length > 0) setMessages(msgs) })
      .catch(() => {})
    fetch(`/api/conversations/${conv.id}/hermes-suggestion`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.suggestion) setSuggestion(d.suggestion) })
      .catch(() => {})
  }

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: 'smooth' }) }, [messages])

  const handleSend = async () => {
    if (!compose.trim() || !active) return
    setSending(true)
    const platform = (active.platform || 'reddit').toLowerCase()
    if (platform === 'x') openXDM(active.handle)
    else openRedditDM(active.handle, compose)
    try {
      await fetch(`/api/conversations/${active.id}/send`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ body: compose }),
      })
      setMessages(m => [...m, { id: Date.now(), sender: 'human', body: compose, sent_at: new Date().toISOString() }])
      setCompose('')
      setSent(true)
      setTimeout(() => setSent(false), 3000)
    } catch {}
    setSending(false)
  }

  const visibleConvs = convs.filter(c => {
    if (search && !c.handle?.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const counts = convs.reduce((acc, c) => {
    acc[c.source] = (acc[c.source] || 0) + 1
    return acc
  }, {})

  const nicheKey    = NICHE_CLASS[active?.niche] || 'tc'
  const avatarColors = AVATAR_COLORS[nicheKey] || AVATAR_COLORS.tc
  const platform    = (active?.platform || 'reddit').toLowerCase()

  return (
    <div className="reply-layout">

      {/* ── Conversation list ── */}
      <div className="conv-list" style={{ width: 240 }}>

        {/* Source filter tabs */}
        <div style={{ padding: '10px 10px 6px', borderBottom: '1px solid var(--border)' }}>
          {SOURCE_TABS.map(t => {
            const cnt = t.key === 'all' ? convs.length : (counts[t.key] || 0)
            const active_tab = sourceTab === t.key
            return (
              <button
                key={t.key}
                onClick={() => setSourceTab(t.key)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  width: '100%', padding: '5px 8px', marginBottom: 2, borderRadius: 6,
                  background: active_tab ? 'rgba(83,74,183,0.12)' : 'transparent',
                  border: active_tab ? '1px solid rgba(83,74,183,0.3)' : '1px solid transparent',
                  color: active_tab ? '#8B82D4' : 'var(--text-secondary)',
                  fontSize: 11, fontWeight: active_tab ? 700 : 400,
                  cursor: 'pointer', textAlign: 'left',
                }}
              >
                <span>{t.icon} {t.label}</span>
                {cnt > 0 && (
                  <span style={{
                    background: active_tab ? 'rgba(83,74,183,0.2)' : 'var(--bg)',
                    border: '1px solid var(--border)',
                    color: active_tab ? '#8B82D4' : 'var(--text-tertiary)',
                    fontSize: 9, fontWeight: 700,
                    padding: '1px 5px', borderRadius: 10,
                  }}>{cnt}</span>
                )}
              </button>
            )
          })}
        </div>

        {/* Search */}
        <div className="conv-search">
          <input
            placeholder="Search handle..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>

        {/* Conversation items */}
        <div className="conv-items">
          {visibleConvs.map(c => {
            const ck  = NICHE_CLASS[c.niche] || 'tc'
            const ac  = AVATAR_COLORS[ck] || AVATAR_COLORS.tc
            const src = SOURCE_CFG[c.source] || SOURCE_CFG.cold_stream
            const isActive = active?.id === c.id
            return (
              <div
                key={c.id}
                className={'conv-item' + (isActive ? ' active' : '')}
                onClick={() => selectConv(c)}
              >
                {c.unread
                  ? <div className="conv-unread" />
                  : <div style={{ width: 7, flexShrink: 0 }} />
                }
                <div className="conv-avatar" style={{ background: ac.bg, color: ac.color }}>
                  {initials(c.handle)}
                  <div className={'conv-platform-dot ' + (c.platform || 'reddit')} />
                </div>
                <div className="conv-body">
                  <div className="conv-meta">
                    <SourceTag source={c.source} small />
                    <span className="conv-time" style={{ marginLeft: 'auto' }}>{timeAgo(c.last_at)}</span>
                  </div>
                  <div className="conv-name">
                    {platform === 'x' ? '@' : 'u/'}{c.handle}
                  </div>
                  <div className="conv-preview">{c.last_message}</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Thread area ── */}
      <div className="thread-area">
        {!active ? (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-tertiary)', fontSize: 14 }}>
            Select a conversation
          </div>
        ) : (
          <>
            {/* Prospect bar */}
            <div className="prospect-bar">
              <div className="prospect-bar-avatar" style={{ background: avatarColors.bg, color: avatarColors.color }}>
                {initials(active.handle)}
              </div>
              <div className="prospect-bar-info">
                <div className="prospect-bar-name">
                  {platform === 'x' ? '@' : 'u/'}{active.handle}
                  <SourceTag source={active.source} small />
                </div>
                <div className="prospect-bar-sub">
                  {platform === 'x' ? '𝕏 Twitter/X' : `r/${active.subreddit || '—'}`}
                </div>
              </div>
              <div className="conv-mode-toggle">
                <span style={{ fontSize: 10, color: 'var(--text-tertiary)', marginRight: 4 }}>Hermes:</span>
                {['auto', 'assist', 'human'].map(m => (
                  <button
                    key={m}
                    className={'ctoggle' + (convMode === m ? ` active-${m}` : '')}
                    onClick={() => setConvMode(m)}
                  >
                    {m.charAt(0).toUpperCase() + m.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            {/* Context card */}
            <ContextCard conv={active} />

            {/* Thread */}
            <div className="thread">
              {messages.map(m => {
                const isUs = m.sender === 'human'
                return (
                  <div key={m.id} className={'msg-wrap' + (isUs ? ' us' : '')}>
                    {isUs && <div className="hermes-sent-badge">Sent</div>}
                    <div className={'msg ' + (isUs ? 'us' : 'them')}>{m.body}</div>
                    <div className="msg-time">
                      {m.sent_at ? new Date(m.sent_at).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : ''}
                    </div>
                  </div>
                )
              })}
              <div ref={bottomRef} />
            </div>

            {/* Input section */}
            <div className="input-section">

              {convMode === 'auto' && (
                <>
                  <div className="auto-status">
                    <div className="pulse auto" />
                    <div style={{ flex: 1 }}>
                      <div className="auto-status-text">Hermes is handling this conversation</div>
                      <div className="auto-status-sub">Next message queued · sends in 4 minutes</div>
                    </div>
                    <button className="takeover-btn" onClick={() => setConvMode('assist')}>Take over</button>
                  </div>
                  <div className="queued-msg">
                    <div className="queued-msg-label">
                      <span>QUEUED — Touch 2 · Loom video</span>
                      <span style={{ color: 'var(--text-tertiary)' }}>sends in 4 min</span>
                    </div>
                    <div className="queued-msg-text">
                      {suggestion || "Here's a 3-minute video of the system running — real prospects with messages drafted in real time: [Loom link]. Worth a 20-min call?"}
                    </div>
                    <div className="queue-actions">
                      <button className="qa-btn send-now">Send now</button>
                      <button className="qa-btn edit" onClick={() => setConvMode('assist')}>Edit before sending</button>
                      <button className="qa-btn">Skip this</button>
                    </div>
                  </div>
                  <div className="dm-script" style={{ padding: '0 14px 10px' }}>
                    <div className="dm-script-label">DM SCRIPT — Hermes sequence</div>
                    <div className="dm-step done"><div className="dm-step-num">✓</div>Touch 1 — personalised opener referencing exact post</div>
                    <div className="dm-step current"><div className="dm-step-num">→</div>Touch 2 — Loom video · "here it is in practice"</div>
                    <div className="dm-step pending"><div className="dm-step-num">3</div>Touch 3 — direct Calendly ask (day 7 if no reply)</div>
                    <div className="dm-step pending"><div className="dm-step-num">4</div>If reply positive → pitch page → book call</div>
                  </div>
                </>
              )}

              {(convMode === 'assist' || convMode === 'human') && (
                <div className="assist-input">
                  {convMode === 'human' && (
                    <div className="hermes-watching">
                      👁 Hermes is watching — will suggest but won't send automatically
                    </div>
                  )}
                  <div className="quick-row">
                    <span className="quick-label">Quick:</span>
                    {QUICK_BTNS.slice(0, convMode === 'human' ? 4 : 5).map(b => (
                      <button key={b} className="qbtn">{b}</button>
                    ))}
                  </div>
                  <div className="compose-wrap">
                    <textarea
                      className="compose-ta"
                      placeholder={convMode === 'human' ? 'Type your message — full control...' : 'Type your reply — Hermes will suggest as you type...'}
                      value={compose}
                      onChange={e => setCompose(e.target.value)}
                    />
                    <button className="attach-icon">📎</button>
                  </div>
                  {suggestion && (
                    <div className={`hermes-rec${convMode === 'human' ? ' human-mode' : ''}`}>
                      <div className="hermes-rec-label">
                        {convMode === 'human' ? 'Hermes recommends (won\'t auto-send)' : 'Hermes suggests adding this'}
                      </div>
                      <div className="hermes-rec-text">{suggestion}</div>
                      <div className="hermes-rec-actions">
                        <button className={`hbtn ${convMode === 'human' ? 'use-human' : 'use'}`}
                          onClick={() => setCompose(convMode === 'human' ? suggestion : c => (c + ' ' + suggestion).trim())}>
                          Use this ↵
                        </button>
                        <button className="hbtn dismiss" onClick={() => setSuggestion(null)}>Dismiss</button>
                      </div>
                    </div>
                  )}
                  <div className="compose-footer" style={{ marginTop: 8 }}>
                    <span className={`char-counter${compose.length > 270 ? ' warn' : ''}`}>{compose.length} / 300</span>
                    {/* Tracking link — generates a unique URL for this lead so signups can be attributed */}
                    <button
                      title="Generate a tracked link to paste into your DM — attributes signups back to this conversation"
                      onClick={async () => {
                        try {
                          const r = await fetch('/api/attribution/link', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                              conversation_id: active.id,
                              prospect_id:     active.prospect_id,
                              pod_slug:        active.niche_segment || active.niche,
                              source_platform: active.platform || 'reddit',
                            }),
                          })
                          const d = await r.json()
                          if (d.tracking_url) {
                            setTrackLink(d.tracking_url)
                            await navigator.clipboard.writeText(d.tracking_url)
                            setTrackLinkCopied(true)
                            setTimeout(() => setTrackLinkCopied(false), 3000)
                          }
                        } catch {}
                      }}
                      style={{
                        background: trackLinkCopied ? 'rgba(29,158,117,0.12)' : 'transparent',
                        color: trackLinkCopied ? 'var(--teal)' : 'var(--text-tertiary)',
                        border: `1px solid ${trackLinkCopied ? 'rgba(29,158,117,0.4)' : 'var(--border)'}`,
                        borderRadius: 5, padding: '3px 8px', fontSize: 10,
                        fontWeight: 600, cursor: 'pointer', transition: 'all 0.15s',
                      }}
                    >
                      {trackLinkCopied ? '✓ Link copied!' : '🔗 Track link'}
                    </button>
                    <div className="send-btns">
                      <SendButton platform={active.platform} compose={compose} onSend={handleSend} sending={sending} sent={sent} />
                    </div>
                  </div>
                </div>
              )}

            </div>
          </>
        )}
      </div>
    </div>
  )
}
