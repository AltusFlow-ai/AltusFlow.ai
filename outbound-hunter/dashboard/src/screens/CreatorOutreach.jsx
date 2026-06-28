import React, { useState, useEffect, useCallback } from 'react'

const STAGES = [
  { key: 'identified',  label: 'Identified',    icon: '👁',  color: '#888',    bg: 'rgba(120,120,120,0.10)', border: 'rgba(120,120,120,0.25)', next: 'pitched',     nextLabel: '📨 Mark pitched' },
  { key: 'pitched',     label: 'Pitched',        icon: '📨',  color: '#BA7517', bg: 'rgba(186,117,23,0.12)',  border: 'rgba(186,117,23,0.30)',  next: 'replied',     nextLabel: '💬 They replied' },
  { key: 'replied',     label: 'Replied',        icon: '💬',  color: '#534AB7', bg: 'rgba(83,74,183,0.12)',   border: 'rgba(83,74,183,0.30)',   next: 'call_booked', nextLabel: '📅 Call booked' },
  { key: 'call_booked', label: 'Call booked',    icon: '📅',  color: '#534AB7', bg: 'rgba(83,74,183,0.18)',   border: 'rgba(83,74,183,0.40)',   next: 'deal_agreed', nextLabel: '🤝 Deal agreed' },
  { key: 'deal_agreed', label: 'Deal agreed',    icon: '🤝',  color: '#1D9E75', bg: 'rgba(29,158,117,0.12)',  border: 'rgba(29,158,117,0.30)',  next: 'live',        nextLabel: '🟢 Go live' },
  { key: 'live',        label: 'Live',           icon: '🟢',  color: '#1D9E75', bg: 'rgba(29,158,117,0.20)',  border: 'rgba(29,158,117,0.50)',  next: null,          nextLabel: null },
  { key: 'no_response', label: 'No response',    icon: '⏸',  color: '#666',    bg: 'rgba(100,100,100,0.08)', border: 'rgba(100,100,100,0.20)', next: 'pitched',     nextLabel: '🔄 Re-pitch' },
  { key: 'declined',    label: 'Declined',       icon: '✗',   color: '#D85A30', bg: 'rgba(216,90,48,0.10)',   border: 'rgba(216,90,48,0.25)',   next: null,          nextLabel: null },
]
const STAGE_MAP = Object.fromEntries(STAGES.map(s => [s.key, s]))

const COLLAB_TYPES = [
  { key: 'free_access', label: 'Free access',       desc: 'Give them free tool access for honest feedback' },
  { key: 'affiliate',   label: 'Affiliate',          desc: 'Rev share for every client they send' },
  { key: 'sponsored',   label: 'Sponsored mention',  desc: 'Paid placement in their content' },
  { key: 'co_content',  label: 'Co-content',         desc: 'Joint video, post, or newsletter' },
  { key: 'cross_promo', label: 'Cross-promo',        desc: 'Mutual audience swap' },
]

const PLATFORMS = ['youtube', 'x', 'newsletter', 'instagram', 'podcast', 'discord', 'reddit']
const PLATFORM_ICONS = { youtube: '▶️', x: '𝕏', newsletter: '📧', instagram: '📸', podcast: '🎙', discord: '💬', reddit: '🟠' }

function fmt(n) {
  if (!n) return ''
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000)    return `${Math.round(n / 1000)}k`
  return `${n}`
}

function StagePill({ stageKey }) {
  const s = STAGE_MAP[stageKey] || STAGE_MAP.identified
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 4,
      background: s.bg, border: `1px solid ${s.border}`, color: s.color,
      fontSize: 10, fontWeight: 700, padding: '2px 8px', borderRadius: 20,
      letterSpacing: '0.04em', textTransform: 'uppercase', whiteSpace: 'nowrap',
    }}>
      {s.icon} {s.label}
    </span>
  )
}

function CreatorCard({ creator, onUpdate }) {
  const [expanded,    setExpanded]    = useState(false)
  const [draft,       setDraft]       = useState(creator.draft || '')
  const [notes,       setNotes]       = useState(creator.notes || '')
  const [response,    setResponse]    = useState(creator.response || '')
  const [commission,  setCommission]  = useState(creator.commission_pct || '')
  const [promoCode,   setPromoCode]   = useState(creator.promo_code || '')
  const [stage,       setStage]       = useState(creator.status || 'identified')
  const [generating,  setGenerating]  = useState(false)
  const [saving,      setSaving]      = useState(false)
  const [copied,      setCopied]      = useState(false)
  const [dealOpen,    setDealOpen]    = useState(false)

  const currentStage = STAGE_MAP[stage] || STAGE_MAP.identified
  const collab = COLLAB_TYPES.find(c => c.key === creator.collab_type) || COLLAB_TYPES[0]

  const generateDraft = async () => {
    setGenerating(true)
    try {
      const r = await fetch(`/api/creator-outreach/${creator.id}/draft`, { method: 'POST' })
      const d = await r.json()
      if (d.ok) { setDraft(d.draft); setExpanded(true); onUpdate({ ...creator, draft: d.draft }) }
    } catch {}
    setGenerating(false)
  }

  const save = async (extra = {}) => {
    setSaving(true)
    try {
      await fetch(`/api/creator-outreach/${creator.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ draft, notes, response, commission_pct: commission, promo_code: promoCode, ...extra }),
      })
      onUpdate({ ...creator, draft, notes, response, commission_pct: commission, promo_code: promoCode, ...extra })
    } catch {}
    setSaving(false)
  }

  const moveStage = async (next) => {
    try {
      await fetch(`/api/creator-outreach/${creator.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status: next }),
      })
      setStage(next)
      onUpdate({ ...creator, status: next })
    } catch {}
  }

  const copy = async () => {
    try { await navigator.clipboard.writeText(draft); setCopied(true); setTimeout(() => setCopied(false), 2000) } catch {}
  }

  const showResponse = ['replied', 'call_booked', 'deal_agreed', 'live'].includes(stage) || !!response

  return (
    <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>

      {/* Compact row */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '14px 18px', cursor: 'pointer',
          borderBottom: expanded ? '1px solid var(--border)' : 'none',
        }}
      >
        <div style={{
          width: 38, height: 38, borderRadius: 8,
          background: 'var(--bg)', border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 18, flexShrink: 0,
        }}>
          {PLATFORM_ICONS[creator.platform] || '👤'}
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 3 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>
              @{creator.handle}
            </span>
            <span style={{ fontSize: 10, color: 'var(--text-tertiary)', background: 'var(--bg)', border: '1px solid var(--border)', padding: '1px 6px', borderRadius: 4 }}>
              {creator.platform}
            </span>
            {creator.followers > 0 && (
              <span style={{ fontSize: 11, fontWeight: 700, color: '#534AB7' }}>
                {fmt(creator.followers)}
              </span>
            )}
            {creator.collab_type && (
              <span style={{ fontSize: 10, color: '#1D9E75', background: 'rgba(29,158,117,0.1)', border: '1px solid rgba(29,158,117,0.25)', padding: '1px 6px', borderRadius: 4, fontWeight: 600 }}>
                {collab.label}
              </span>
            )}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {creator.content_angle || creator.niche?.replace(/-/g, ' ') || 'trading content'}
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
          {(creator.clients_attributed > 0) && (
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--teal)', background: 'rgba(29,158,117,0.1)', border: '1px solid rgba(29,158,117,0.25)', padding: '2px 8px', borderRadius: 20 }}>
              +{creator.clients_attributed} clients
            </span>
          )}
          <StagePill stageKey={stage} />
          <span style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div style={{ padding: '18px 18px', display: 'flex', flexDirection: 'column', gap: 16 }}>

          {/* Content angle */}
          {creator.content_angle && (
            <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
              <div style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 5 }}>CONTENT ANGLE</div>
              <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{creator.content_angle}</div>
            </div>
          )}

          {/* Partnership pitch */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 8 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>
                Partnership pitch
              </span>
              <div style={{ display: 'flex', gap: 6 }}>
                {draft && (
                  <button
                    onClick={copy}
                    style={{
                      background: copied ? 'rgba(29,158,117,0.15)' : 'var(--bg)',
                      color: copied ? 'var(--teal)' : 'var(--text-secondary)',
                      border: `1px solid ${copied ? 'rgba(29,158,117,0.4)' : 'var(--border)'}`,
                      padding: '4px 10px', borderRadius: 5, fontSize: 11, cursor: 'pointer', transition: 'all 0.15s',
                    }}
                  >
                    {copied ? '✓ Copied' : '📋 Copy'}
                  </button>
                )}
                <button
                  onClick={generateDraft}
                  disabled={generating}
                  style={{
                    background: generating ? 'var(--border)' : 'linear-gradient(135deg, #534AB7, #1D9E75)',
                    color: generating ? 'var(--text-tertiary)' : '#fff',
                    border: 'none', padding: '4px 12px', borderRadius: 5,
                    fontSize: 11, fontWeight: 700, cursor: generating ? 'wait' : 'pointer',
                  }}
                >
                  {generating ? '⏳ Drafting…' : draft ? '↻ Re-draft' : '✨ Hermes draft'}
                </button>
              </div>
            </div>
            <textarea
              value={draft}
              onChange={e => setDraft(e.target.value)}
              rows={5}
              placeholder="Click ✨ Hermes draft — Hermes writes a personalized pitch based on their content angle and the partnership type."
              style={{
                width: '100%', background: 'var(--bg)',
                border: `1px solid ${draft ? 'var(--border)' : 'rgba(83,74,183,0.3)'}`,
                borderRadius: 6, padding: '10px 12px', color: 'var(--text-primary)',
                fontSize: 12, lineHeight: 1.7, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Deal terms */}
          <div style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: dealOpen ? 12 : 0 }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em' }}>Deal terms</span>
              <button
                onClick={() => setDealOpen(o => !o)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', fontSize: 11, cursor: 'pointer' }}
              >
                {dealOpen ? 'Done' : '✏️ Edit'}
              </button>
            </div>

            {dealOpen ? (
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <div style={{ flex: 1, minWidth: 120 }}>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 4 }}>COMMISSION %</div>
                  <input
                    value={commission}
                    onChange={e => setCommission(e.target.value)}
                    placeholder="e.g. 20"
                    type="number"
                    style={{ width: '100%', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 5, padding: '6px 10px', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
                  />
                </div>
                <div style={{ flex: 1, minWidth: 140 }}>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 4 }}>PROMO CODE</div>
                  <input
                    value={promoCode}
                    onChange={e => setPromoCode(e.target.value)}
                    placeholder="e.g. CHARTGUYS20"
                    style={{ width: '100%', background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 5, padding: '6px 10px', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
                  />
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 20, marginTop: 10, flexWrap: 'wrap' }}>
                {[
                  { label: 'Type',        val: collab.label },
                  { label: 'Commission',  val: commission ? `${commission}%` : '—' },
                  { label: 'Promo code',  val: promoCode || '—' },
                  { label: 'Clients in',  val: creator.clients_attributed > 0 ? `${creator.clients_attributed}` : '—' },
                ].map(item => (
                  <div key={item.label}>
                    <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 3, letterSpacing: '0.04em' }}>{item.label.toUpperCase()}</div>
                    <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{item.val}</div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Their response */}
          {showResponse && (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Their response</div>
              <textarea
                value={response}
                onChange={e => setResponse(e.target.value)}
                rows={2}
                placeholder="Paste their reply — Hermes uses it when drafting follow-ups…"
                style={{
                  width: '100%', background: 'var(--bg)', border: '1px solid rgba(29,158,117,0.25)',
                  borderRadius: 6, padding: '8px 12px', color: 'var(--text-primary)',
                  fontSize: 12, lineHeight: 1.6, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit',
                }}
              />
            </div>
          )}

          {/* Notes */}
          <div>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>Notes</div>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              placeholder="Upload schedule, topics they care about, referral from, anything useful…"
              style={{
                width: '100%', background: 'var(--bg)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '8px 12px', color: 'var(--text-primary)',
                fontSize: 12, lineHeight: 1.6, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center', borderTop: '1px solid var(--border)', paddingTop: 14 }}>
            <button
              onClick={() => save()}
              disabled={saving}
              style={{ background: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border)', padding: '7px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer', opacity: saving ? 0.5 : 1 }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>

            {currentStage.next && (
              <button
                onClick={() => moveStage(currentStage.next)}
                style={{ background: 'var(--teal)', color: '#000', border: 'none', padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
              >
                {currentStage.nextLabel}
              </button>
            )}

            {stage === 'pitched' && (
              <>
                <button
                  onClick={() => moveStage('no_response')}
                  style={{ background: 'transparent', color: 'var(--text-tertiary)', border: '1px solid var(--border)', padding: '7px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
                >
                  No response
                </button>
                <button
                  onClick={() => moveStage('declined')}
                  style={{ background: 'transparent', color: '#D85A30', border: '1px solid rgba(216,90,48,0.3)', padding: '7px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
                >
                  Declined
                </button>
              </>
            )}

            {creator.profile_url && (
              <a
                href={creator.profile_url}
                target="_blank"
                rel="noreferrer"
                style={{ marginLeft: 'auto', fontSize: 11, color: 'var(--text-tertiary)', textDecoration: 'none' }}
              >
                View profile ↗
              </a>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default function CreatorOutreach() {
  const [creators,    setCreators]    = useState([])
  const [loading,     setLoading]     = useState(true)
  const [stageFilter, setStageFilter] = useState('all')
  const [showForm,    setShowForm]    = useState(false)
  const [submitting,  setSubmitting]  = useState(false)
  const [form, setForm] = useState({
    handle: '', platform: 'youtube', followers: '',
    content_angle: '', collab_type: 'free_access',
    commission_pct: '', promo_code: '', notes: '', profile_url: '',
  })

  const DEMO = [
    {
      id: 1, handle: 'TheChartGuys', platform: 'youtube', followers: 285000,
      content_angle: 'Daily market breakdowns + price action education. Posts Mon–Fri at 9am EST. Very engaged retail trading audience.',
      collab_type: 'affiliate', commission_pct: 20, promo_code: 'CHARTGUYS',
      status: 'replied', clients_attributed: 0,
      draft: "Been watching your price action content for a while — it's the clearest explanation of market structure I've seen for retail traders. We built a coaching platform for traders who are ready for real accountability beyond just watching videos. Open to giving you free access in exchange for honest feedback? No pitch, no strings.",
      response: "Sure, send me the link — I'll check it out this weekend",
      notes: 'Very quality-focused. Has a loyal audience that actually trades.',
      profile_url: 'https://youtube.com/@thechartguys',
    },
    {
      id: 2, handle: 'TraderLion', platform: 'x', followers: 180000,
      content_angle: 'Growth investing + momentum trading. Stock breakdowns and watchlists. Strong community.',
      collab_type: 'co_content', commission_pct: '', promo_code: '',
      status: 'pitched', clients_attributed: 0,
      draft: "Love the growth investor angle — the stock breakdown format you do is really strong. We're building a coaching layer for traders who want structure beyond watchlists. Open to co-creating something?",
      response: '', notes: 'Sent DM on X. Follow up in 5 days if no reply.',
      profile_url: '',
    },
    {
      id: 3, handle: 'SMBCapital', platform: 'youtube', followers: 420000,
      content_angle: 'Prop firm trading desk footage + professional trader interviews. Highest production quality in the space.',
      collab_type: 'sponsored', commission_pct: '', promo_code: 'SMB20',
      status: 'deal_agreed', clients_attributed: 3,
      draft: '',
      response: 'We do sponsored content for trading tools — send our media kit email to the team',
      notes: 'Professional team. High reach worth the investment. Need to go through media kit process.',
      profile_url: 'https://youtube.com/@smbcapital',
    },
    {
      id: 4, handle: 'TradingWithRayner', platform: 'newsletter', followers: 500000,
      content_angle: 'Systematic trading education newsletter. 500k subscribers, very high open rate. Global audience.',
      collab_type: 'affiliate', commission_pct: 30, promo_code: 'RAYNER30',
      status: 'live', clients_attributed: 7,
      draft: '',
      response: 'Love the product, happy to promote on rev-share basis — will include in next week\'s issue',
      notes: 'Best performing partner so far. Sends once/week. Very engaged list. Rayner personally reviewed the product.',
      profile_url: 'https://tradingwithrayner.com',
    },
    {
      id: 5, handle: 'Ripster47', platform: 'x', followers: 95000,
      content_angle: 'Futures and options flow analysis. Known for unusual options activity signals.',
      collab_type: 'free_access', commission_pct: '', promo_code: '',
      status: 'identified', clients_attributed: 0,
      draft: '', response: '', notes: 'Great fit for futures niche. Very engaged following. Add to pipeline.',
      profile_url: '',
    },
  ]

  const load = useCallback(async () => {
    try {
      const r = await fetch('/api/creator-outreach')
      if (r.ok) {
        const d = await r.json()
        if (Array.isArray(d) && d.length > 0) { setCreators(d); setLoading(false); return }
      }
    } catch {}
    setCreators([])
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const addCreator = async () => {
    if (!form.handle.trim()) return
    setSubmitting(true)
    try {
      await fetch('/api/creator-outreach', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, followers: Number(form.followers) || 0, status: 'identified' }),
      })
      setForm({ handle: '', platform: 'youtube', followers: '', content_angle: '', collab_type: 'free_access', commission_pct: '', promo_code: '', notes: '', profile_url: '' })
      setShowForm(false)
      await load()
    } catch {}
    setSubmitting(false)
  }

  const onUpdate = (updated) => setCreators(prev => prev.map(c => c.id === updated.id ? updated : c))

  const counts = {}
  creators.forEach(c => { counts[c.status] = (counts[c.status] || 0) + 1 })
  const filtered = stageFilter === 'all' ? creators : creators.filter(c => c.status === stageFilter)

  const totalClients = creators.reduce((a, c) => a + (c.clients_attributed || 0), 0)
  const liveCount    = creators.filter(c => c.status === 'live').length
  const inPlay       = creators.filter(c => ['replied','call_booked','deal_agreed'].includes(c.status)).length

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        {[
          { label: 'In pipeline',     val: creators.length, color: 'var(--text-primary)' },
          { label: 'Pitched',         val: (counts.pitched || 0), color: '#BA7517' },
          { label: 'In negotiation',  val: inPlay, color: '#534AB7' },
          { label: 'Live deals',      val: liveCount, color: '#1D9E75' },
          { label: 'Clients from creators', val: totalClients, color: '#D85A30' },
        ].map(s => (
          <div key={s.label} style={{ flex: 1, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: s.color, lineHeight: 1 }}>{s.val}</div>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4, fontWeight: 600, letterSpacing: '0.04em' }}>
              {s.label.toUpperCase()}
            </div>
          </div>
        ))}
      </div>

      {/* Pipeline stage tabs + add button */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14, flexWrap: 'wrap', gap: 10 }}>
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {[{ key: 'all', label: 'All', icon: '' }, ...STAGES].map(s => {
            const count = s.key === 'all' ? creators.length : (counts[s.key] || 0)
            const active = stageFilter === s.key
            const cfg = STAGE_MAP[s.key]
            return (
              <button
                key={s.key}
                onClick={() => setStageFilter(s.key)}
                style={{
                  background:  active ? (cfg ? cfg.bg   : 'rgba(83,74,183,0.15)') : 'transparent',
                  color:       active ? (cfg ? cfg.color : '#8B82D4')              : 'var(--text-tertiary)',
                  border:      active ? `1px solid ${cfg ? cfg.border : 'rgba(83,74,183,0.4)'}` : '1px solid transparent',
                  padding: '4px 11px', borderRadius: 20, fontSize: 11,
                  fontWeight: active ? 700 : 400, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', gap: 4,
                }}
              >
                {s.icon && <span style={{ fontSize: 10 }}>{s.icon}</span>}
                {s.key === 'all' ? 'All' : s.label}
                {count > 0 && (
                  <span style={{ fontSize: 9, fontWeight: 700, background: 'rgba(0,0,0,0.15)', padding: '1px 5px', borderRadius: 8 }}>
                    {count}
                  </span>
                )}
              </button>
            )
          })}
        </div>
        <button
          onClick={() => setShowForm(s => !s)}
          style={{ background: 'var(--teal)', color: '#000', border: 'none', padding: '8px 18px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap' }}
        >
          + Add creator
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--teal)', borderRadius: 10, padding: 20, marginBottom: 20, display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Add creator to pipeline</div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input
              value={form.handle}
              onChange={e => setForm(f => ({ ...f, handle: e.target.value }))}
              placeholder="Handle / username"
              style={{ flex: 2, minWidth: 160, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--text-primary)', fontSize: 12 }}
            />
            <select
              value={form.platform}
              onChange={e => setForm(f => ({ ...f, platform: e.target.value }))}
              style={{ flex: 1, minWidth: 120, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', color: 'var(--text-primary)', fontSize: 12, cursor: 'pointer' }}
            >
              {PLATFORMS.map(p => <option key={p} value={p}>{PLATFORM_ICONS[p] || ''} {p}</option>)}
            </select>
            <input
              value={form.followers}
              onChange={e => setForm(f => ({ ...f, followers: e.target.value }))}
              placeholder="Followers"
              type="number"
              style={{ flex: 1, minWidth: 110, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--text-primary)', fontSize: 12 }}
            />
          </div>

          <div>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 5 }}>CONTENT ANGLE — what do they cover?</div>
            <input
              value={form.content_angle}
              onChange={e => setForm(f => ({ ...f, content_angle: e.target.value }))}
              placeholder='e.g. "Futures day trading + prop firm content, daily uploads, very engaged audience"'
              style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
            />
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 180 }}>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 5 }}>PARTNERSHIP TYPE</div>
              <select
                value={form.collab_type}
                onChange={e => setForm(f => ({ ...f, collab_type: e.target.value }))}
                style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 10px', color: 'var(--text-primary)', fontSize: 12, cursor: 'pointer' }}
              >
                {COLLAB_TYPES.map(c => <option key={c.key} value={c.key}>{c.label} — {c.desc}</option>)}
              </select>
            </div>
            <div style={{ flex: 1, minWidth: 180 }}>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)', fontWeight: 700, marginBottom: 5 }}>PROFILE URL <span style={{ fontWeight: 400, opacity: 0.7 }}>(optional)</span></div>
              <input
                value={form.profile_url}
                onChange={e => setForm(f => ({ ...f, profile_url: e.target.value }))}
                placeholder="https://youtube.com/@..."
                style={{ width: '100%', background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px', color: 'var(--text-primary)', fontSize: 12, boxSizing: 'border-box' }}
              />
            </div>
          </div>

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={addCreator}
              disabled={submitting || !form.handle.trim()}
              style={{ background: 'var(--teal)', color: '#000', border: 'none', padding: '8px 20px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: submitting || !form.handle.trim() ? 'not-allowed' : 'pointer', opacity: !form.handle.trim() ? 0.5 : 1 }}
            >
              {submitting ? 'Adding…' : 'Add to pipeline'}
            </button>
            <button
              onClick={() => setShowForm(false)}
              style={{ background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border)', padding: '8px 16px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* List */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)', fontSize: 13 }}>Loading…</div>
      ) : filtered.length === 0 ? (
        <div style={{ textAlign: 'center', padding: 60, color: 'var(--text-tertiary)', fontSize: 13, lineHeight: 1.8 }}>
          {stageFilter === 'all'
            ? <>No creators yet.<br /><span style={{ fontSize: 12 }}>Add a trading YouTuber, newsletter writer, or X account above.</span></>
            : `No creators at "${STAGE_MAP[stageFilter]?.label}" stage`}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {filtered.map(c => <CreatorCard key={c.id} creator={c} onUpdate={onUpdate} />)}
        </div>
      )}
    </div>
  )
}
