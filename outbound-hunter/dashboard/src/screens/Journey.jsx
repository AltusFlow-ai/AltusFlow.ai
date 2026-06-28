import React, { useState, useEffect, useRef, useCallback } from 'react'
import { useApp } from '../App.jsx'

const STAGE_ORDER = ['detected','qualified','approved','auto_approved','sent','replied','booked','closed_won','closed_lost']

const STATUS_LABEL = {
  pending:       'Pending review',
  auto_approved: 'Auto-approved',
  approved:      'Approved',
  sent:          'Sent',
  replied:       'Replied',
  booked:        'Call booked',
  skipped:       'Skipped',
  closed_won:    'Closed won',
  closed_lost:   'Closed lost',
}

function timeAgo(str) {
  if (!str) return ''
  const diff = Date.now() - new Date(str).getTime()
  const h = Math.floor(diff / 3600000)
  if (h < 1) return 'just now'
  if (h < 24) return `${h}h ago`
  return `${Math.floor(h / 24)}d ago`
}

export default function Journey() {
  const { activeNiche } = useApp()
  const [prospects, setProspects] = useState([])
  const [selected,  setSelected]  = useState(null)
  const [journey,   setJourney]   = useState(null)
  const [loading,   setLoading]   = useState(true)
  const [search,    setSearch]    = useState('')
  const [replyText, setReplyText] = useState('')
  const [replyMode, setReplyMode] = useState(false)
  const [saving,    setSaving]    = useState(false)

  const DEMO_PROSPECTS = [
    { id: 1, handle: 'futurestrader99',  platform: 'reddit', niche: 'trading-coaches',   icp_score: 8, status: 'replied',  latest_event: 'Moved to DM', latest_icon: '💬', latest_at: new Date(Date.now() - 1*3600000).toISOString(),  event_count: 4 },
    { id: 2, handle: 'riaowner_chicago', platform: 'reddit', niche: 'financial-advisors', icp_score: 9, status: 'sent',     latest_event: 'DM sent',     latest_icon: '✉️', latest_at: new Date(Date.now() - 4*3600000).toISOString(),  event_count: 2 },
    { id: 3, handle: 'wealthmgr_dallas', platform: 'reddit', niche: 'financial-advisors', icp_score: 8, status: 'booked',   latest_event: 'Call booked', latest_icon: '📅', latest_at: new Date(Date.now() - 12*3600000).toISOString(), event_count: 6 },
    { id: 4, handle: 'msp_founder_ohio', platform: 'reddit', niche: 'msps',               icp_score: 7, status: 'replied',  latest_event: 'Replied',     latest_icon: '💬', latest_at: new Date(Date.now() - 18*3600000).toISOString(), event_count: 3 },
    { id: 5, handle: 'recruiter_nyc',    platform: 'twitter', niche: 'recruiters',         icp_score: 7, status: 'sent',     latest_event: 'DM approved', latest_icon: '✉️', latest_at: new Date(Date.now() - 26*3600000).toISOString(), event_count: 2 },
  ]

  const DEMO_JOURNEYS = {
    // Stream examples — scanner caught their post live as it was published
    1: { id:1, handle:'futurestrader99', platform:'reddit', niche:'trading-coaches', icp_score:8, status:'replied', post_text:'Running a futures trading community for 2 years, 340 members but engagement is dying. People join, watch a few videos, then ghost.', post_url:'https://reddit.com/r/Daytrading/comments/example/', events:[
      { id:1, event:'Caught by Reddit stream', icon:'📡', detail:'Scanner caught their post in r/Daytrading within 4 min of publishing · ICP score 8 · signal: "engagement is dying"', created_at: new Date(Date.now()-5*3600000).toISOString() },
      { id:2, event:'Hermes commented publicly', icon:'💬', detail:'Hermes posted a helpful reply on the thread — adds credibility before any DM', created_at: new Date(Date.now()-4*3600000).toISOString() },
      { id:3, event:'DM approved', icon:'✅', detail:'Rep reviewed Hermes draft and approved for send', created_at: new Date(Date.now()-3*3600000).toISOString() },
      { id:4, event:'DM sent via Reddit', icon:'✉️', detail:'First touch sent — referenced their comment about member ghosting', created_at: new Date(Date.now()-3*3600000+600000).toISOString() },
      { id:5, event:'Prospect replied', icon:'💬', detail:'"This actually makes sense for where we\'re at — what does it look like?"', created_at: new Date(Date.now()-1*3600000).toISOString() },
    ]},
    4: { id:4, handle:'msp_founder_ohio', platform:'reddit', niche:'msps', icp_score:7, status:'replied', post_text:'Running an MSP with 12 techs. We do fine on renewals but I can\'t crack net new. Tried cold email — 0 replies in 3 months. Tried LinkedIn — got ghosted.', post_url:'', events:[
      { id:14, event:'Caught by Reddit stream', icon:'📡', detail:'Scanner caught their post in r/msp within 9 min of publishing · ICP score 7 · signal: "can\'t crack net new"', created_at: new Date(Date.now()-2*24*3600000).toISOString() },
      { id:15, event:'Queued for review', icon:'🔍', detail:'Score 7 — sent to rep inbox for manual review before DM', created_at: new Date(Date.now()-2*24*3600000+600000).toISOString() },
      { id:16, event:'DM approved', icon:'✅', detail:'Rep approved — customized Hermes draft to reference cold email frustration', created_at: new Date(Date.now()-2*24*3600000+7200000).toISOString() },
      { id:17, event:'DM sent via Reddit', icon:'✉️', detail:'First touch sent', created_at: new Date(Date.now()-1*24*3600000).toISOString() },
      { id:18, event:'Prospect replied', icon:'💬', detail:'"Honestly yeah, happy to hear what you\'re doing differently"', created_at: new Date(Date.now()-18*3600000).toISOString() },
    ]},
    // Scrape Badger examples — bulk scraped from Reddit, pushed in via webhook
    2: { id:2, handle:'riaowner_chicago', platform:'reddit', niche:'financial-advisors', icp_score:9, status:'sent', post_text:'Solo RIA, been at it 6 years. Great at managing portfolios but terrible at getting in front of new people. Referrals have dried up since COVID.', post_url:'', events:[
      { id:6, event:'Imported via Scrape Badger', icon:'🦡', detail:'Scrape Badger batch pulled this post from r/CFP · ICP score 9 · signal: "referrals have dried up"', created_at: new Date(Date.now()-8*3600000).toISOString() },
      { id:7, event:'Auto-approved', icon:'⚡', detail:'Score 9 — above auto-approve threshold, no rep review needed', created_at: new Date(Date.now()-8*3600000+300000).toISOString() },
      { id:8, event:'DM sent via Reddit', icon:'✉️', detail:'Hermes sent first touch — financial advisor angle, referenced the referral comment', created_at: new Date(Date.now()-6*3600000).toISOString() },
    ]},
    3: { id:3, handle:'wealthmgr_dallas', platform:'reddit', niche:'financial-advisors', icp_score:8, status:'booked', post_text:'I need to book more discovery calls. Running Google ads ($800/mo), posting on LinkedIn daily, and still averaging 1-2 new inquiries per week.', post_url:'', events:[
      { id:9,  event:'Imported via Scrape Badger', icon:'🦡', detail:'Scrape Badger batch pulled this post from r/FinancialPlanning · ICP score 8 · signal: "need more booked calls"', created_at: new Date(Date.now()-3*24*3600000).toISOString() },
      { id:10, event:'Auto-approved', icon:'⚡', detail:'Score 8+ — auto-queued for outreach', created_at: new Date(Date.now()-3*24*3600000+300000).toISOString() },
      { id:11, event:'DM sent via Reddit', icon:'✉️', detail:'Hermes first touch — led with the Google ads waste angle', created_at: new Date(Date.now()-2*24*3600000).toISOString() },
      { id:12, event:'Prospect replied', icon:'💬', detail:'"That\'s a good point — our landing page is probably killing the conversion"', created_at: new Date(Date.now()-1*24*3600000).toISOString() },
      { id:13, event:'Loom sent', icon:'▶️', detail:'Rep sent 3 min demo walkthrough via Loom link', created_at: new Date(Date.now()-20*3600000).toISOString() },
      { id:14, event:'Call booked', icon:'📅', detail:'Discovery call booked via Calendly — 30 min slot Thursday 2pm', created_at: new Date(Date.now()-12*3600000).toISOString() },
    ]},
    5: { id:5, handle:'recruiter_nyc', platform:'twitter', niche:'recruiters', icp_score:7, status:'sent', post_text:'Anybody else finding that LinkedIn outreach reply rates have completely tanked? Used to get 15-20% reply rate, now sitting at 3-4%. The platform is just too noisy.', post_url:'', events:[
      { id:19, event:'Imported via Scrape Badger', icon:'🦡', detail:'Scrape Badger pulled this post from X · ICP score 7 · signal: "LinkedIn reply rates tanked"', created_at: new Date(Date.now()-28*3600000).toISOString() },
      { id:20, event:'Queued for review', icon:'🔍', detail:'Score 7 — sent to rep inbox for review', created_at: new Date(Date.now()-27*3600000).toISOString() },
      { id:21, event:'DM approved', icon:'✅', detail:'Rep approved Hermes draft — recruiter niche angle', created_at: new Date(Date.now()-26*3600000).toISOString() },
      { id:22, event:'DM sent via X', icon:'✉️', detail:'First touch sent — referenced their tweet about reply rate drop', created_at: new Date(Date.now()-26*3600000+300000).toISOString() },
    ]},
  }

  useEffect(() => {
    setLoading(true)
    const params = new URLSearchParams()
    if (search)                          params.set('search', search)
    if (activeNiche && activeNiche !== 'all') params.set('niche', activeNiche)
    fetch(`/api/journey?${params}`)
      .then(r => r.ok ? r.json() : [])
      .then(d => {
        setProspects(Array.isArray(d) ? d : [])
        setLoading(false)
      })
      .catch(() => { setProspects([]); setLoading(false) })
  }, [search, activeNiche])

  function selectProspect(p) {
    setSelected(p)
    setReplyMode(false)
    setReplyText('')
    setJourney(null)
    fetch(`/api/journey/${p.id}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && d.events?.length) setJourney(d) })
      .catch(() => {})
  }

  function logReply() {
    if (!replyText.trim() || !selected) return
    setSaving(true)
    fetch(`/api/prospects/${selected.id}/log-reply`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ body: replyText, sender: 'prospect' }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(() => {
        setReplyText('')
        setReplyMode(false)
        setSaving(false)
        // Refresh journey
        fetch(`/api/journey/${selected.id}`)
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d) setJourney(d) })
      })
      .catch(() => setSaving(false))
  }

  function addEvent(event, icon, detail) {
    if (!selected) return
    fetch(`/api/journey/${selected.id}/add-event`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ event, icon, detail }),
    }).then(() => {
      fetch(`/api/journey/${selected.id}`)
        .then(r => r.ok ? r.json() : null)
        .then(d => { if (d) setJourney(d) })
    })
  }

  const events = journey?.events || journey?.journey || []

  return (
    <div className="content" style={{ display: 'flex', gap: 0, padding: 0, height: '100%' }}>

      {/* Left — prospect list */}
      <div style={{ width: 280, flexShrink: 0, borderRight: '1px solid var(--border)', overflowY: 'auto', padding: '16px 0' }}>
        <div style={{ padding: '0 16px 12px' }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search prospects…"
            style={{ width: '100%', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 10px', fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit' }}
          />
        </div>
        {loading && <div style={{ padding: '16px', fontSize: 13, color: 'var(--text-tertiary)' }}>Loading…</div>}
        {!loading && prospects.length === 0 && (
          <div style={{ padding: '16px', fontSize: 13, color: 'var(--text-tertiary)' }}>
            No prospects yet — run a scan to populate the journey.
          </div>
        )}
        {prospects.map(p => (
          <div
            key={p.id}
            onClick={() => selectProspect(p)}
            style={{
              padding: '10px 16px', cursor: 'pointer',
              background: selected?.id === p.id ? 'var(--surface-2)' : 'transparent',
              borderLeft: selected?.id === p.id ? '2px solid var(--teal)' : '2px solid transparent',
            }}
          >
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
              {p.name || p.handle}
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 4 }}>
              {p.handle} · {p.niche}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
              <span style={{ fontSize: 10, background: 'var(--surface-3)', borderRadius: 4, padding: '2px 6px', color: 'var(--text-secondary)' }}>
                {p.latest_icon} {p.latest_event || STATUS_LABEL[p.status] || p.status}
              </span>
              <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{timeAgo(p.latest_at || p.scraped_at)}</span>
            </div>
          </div>
        ))}
      </div>

      {/* Right — journey timeline */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 24 }}>
        {!selected && (
          <div style={{ color: 'var(--text-tertiary)', fontSize: 14, paddingTop: 40, textAlign: 'center' }}>
            Select a prospect to see their full journey.
          </div>
        )}

        {selected && (
          <>
            {/* Header */}
            <div style={{ marginBottom: 24 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                {selected.name || selected.handle}
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-secondary)', marginBottom: 12 }}>
                {selected.handle} · {selected.niche} · ICP {selected.icp_score}/10
              </div>
              {selected.post_text && (
                <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px', fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.6, maxWidth: 580, fontStyle: 'italic' }}>
                  "{selected.post_text?.slice(0, 280)}{selected.post_text?.length > 280 ? '…' : ''}"
                </div>
              )}
            </div>

            {/* Timeline */}
            <div style={{ position: 'relative', paddingLeft: 32, marginBottom: 24 }}>
              <div style={{ position: 'absolute', left: 11, top: 0, bottom: 0, width: 1, background: 'var(--border)' }} />
              {events.length === 0 && (
                <div style={{ fontSize: 13, color: 'var(--text-tertiary)' }}>No journey events yet.</div>
              )}
              {events.map((ev, i) => (
                <div key={ev.id || i} style={{ position: 'relative', marginBottom: 20 }}>
                  <div style={{
                    position: 'absolute', left: -32, top: 2,
                    width: 22, height: 22, borderRadius: '50%',
                    background: 'var(--surface)', border: '2px solid var(--teal)',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11,
                  }}>
                    {ev.icon}
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>{ev.event}</div>
                  {ev.detail && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>{ev.detail}</div>}
                  {ev.full_message && (
                    <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 12px', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.65, maxWidth: 540, fontStyle: 'italic', marginBottom: 4 }}>
                      "{ev.full_message}"
                    </div>
                  )}
                  <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{timeAgo(ev.created_at)}</div>
                </div>
              ))}
            </div>

            {/* Log reply panel */}
            {replyMode ? (
              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 10, padding: 16, maxWidth: 540, marginBottom: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 8 }}>Paste their reply</div>
                <textarea
                  value={replyText}
                  onChange={e => setReplyText(e.target.value)}
                  placeholder="Paste what they said on LinkedIn, Facebook, or wherever…"
                  rows={4}
                  style={{ width: '100%', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 8, padding: '8px 10px', fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit', resize: 'vertical' }}
                />
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button onClick={logReply} disabled={saving || !replyText.trim()}
                    style={{ background: 'var(--teal)', color: '#fff', border: 'none', borderRadius: 7, padding: '7px 16px', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit' }}>
                    {saving ? 'Saving…' : 'Log reply →'}
                  </button>
                  <button onClick={() => setReplyMode(false)}
                    style={{ background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border)', borderRadius: 7, padding: '7px 12px', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit' }}>
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                <button onClick={() => setReplyMode(true)}
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 14px', fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>
                  ↩️ Log reply
                </button>
                <button onClick={() => addEvent('Call booked', '📅', 'Discovery call booked manually')}
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 14px', fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>
                  📅 Log call booked
                </button>
                <button onClick={() => addEvent('Proposal sent', '📄', 'Proposal sent')}
                  style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 8, padding: '7px 14px', fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer', fontFamily: 'inherit' }}>
                  📄 Log proposal sent
                </button>
                <button onClick={() => addEvent('Closed won', '🏆', 'Deal closed — new client')}
                  style={{ background: 'rgba(29,158,117,0.1)', border: '1px solid rgba(29,158,117,0.3)', borderRadius: 8, padding: '7px 14px', fontSize: 12, color: 'var(--teal)', cursor: 'pointer', fontFamily: 'inherit' }}>
                  🏆 Mark closed won
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
