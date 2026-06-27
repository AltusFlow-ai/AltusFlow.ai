import React, { useState } from 'react'

const TABS = ['Signal phrases', 'Best openers', 'Objections', 'Market intel', 'Call insights']

const SIGNAL_PHRASES = [
  { phrase: 'pipeline dried up',              niche: 'FA',  uses: 12, replies: 7, rate: '58%', trend: 'up' },
  { phrase: 'referrals stopped',              niche: 'FA',  uses: 9,  replies: 5, rate: '55%', trend: 'up' },
  { phrase: 'need more booked calls',         niche: 'FA',  uses: 8,  replies: 4, rate: '50%', trend: 'flat' },
  { phrase: "can't fix discipline alone",     niche: 'TC',  uses: 8,  replies: 5, rate: '62%', trend: 'up' },
  { phrase: 'blown account last month',       niche: 'TC',  uses: 6,  replies: 4, rate: '67%', trend: 'up' },
  { phrase: 'demo profitable but live losing',niche: 'TC',  uses: 7,  replies: 4, rate: '57%', trend: 'up' },
  { phrase: 'BD is brutal right now',         niche: 'RC',  uses: 6,  replies: 2, rate: '33%', trend: 'flat' },
  { phrase: 'deal flow slow',                 niche: 'CRE', uses: 4,  replies: 1, rate: '25%', trend: 'flat' },
  { phrase: 'cold email zero response',       niche: 'MSP', uses: 3,  replies: 0, rate: '0%',  trend: 'down' },
]

const OPENERS = [
  {
    text: '"Saw your post — 2 years trading alone and the psychology problem doesn\'t fix itself. Is the issue execution on individual trades, or is it more about sizing when you\'re already down?"',
    niche: 'TC', replies: 5, rate: '62%', why: 'References their exact situation, then asks a specific binary question that signals you understand the nuance. Low barrier to reply.',
  },
  {
    text: '"The demo-to-live gap on NQ is almost never a strategy problem — it\'s a psychology one. Are you cutting winners too early or letting losers run?"',
    niche: 'TC', replies: 4, rate: '57%', why: 'Names the exact mechanism (not the symptom), then gives them a binary that validates their experience.',
  },
  {
    text: '"Saw your post — referral slowdowns are hitting a lot of FAs right now. Are you finding that the people you\'d normally get referrals from are just quieter, or is it something else?"',
    niche: 'FA', replies: 7, rate: '58%', why: 'Opens with empathy + specific observation. Ends with an easy binary question — low friction to reply.',
  },
  {
    text: '"The ad → call funnel for FAs is almost always broken at the landing page, not the ad. Are you sending them to a generic website or a specific page?"',
    niche: 'FA', replies: 4, rate: '50%', why: 'Leads with a diagnosis (not a pitch). Makes them feel understood before any ask.',
  },
  {
    text: '"The retained vs contingency tension is at an all-time high right now. Are you finding clients pushing back on fees, or is it more about response time?"',
    niche: 'RC', replies: 2, rate: '33%', why: 'Validates their frustration with the market, not just their problem. Binary question keeps reply barrier low.',
  },
  {
    text: '"Cold outreach for MSPs almost never works until you get hyper-specific on the vertical. Are you targeting a specific type of business, or going broad?"',
    niche: 'MSP', replies: 0, rate: '0%', why: 'Too direct — still testing. May need a softer entry for MSP niche.',
  },
]

const OBJECTIONS = [
  {
    objection: '"I\'ve tried cold outreach before and it didn\'t work."',
    response: '"That\'s because most outreach is generic. We only message people who\'ve already publicly said they have the problem you solve — so the reply rate is 4–5× higher."',
    used: 6, resolved: 5,
  },
  {
    objection: '"I don\'t have time to manage another tool."',
    response: '"You don\'t manage it — Hermes does. You show up to approve messages that are already written and see a pipeline in HubSpot. Total time: 10 minutes a day."',
    used: 4, resolved: 3,
  },
  {
    objection: '"How is this different from a lead gen agency?"',
    response: '"Agencies charge $3–5k/mo for unqualified lists. We score every signal in real time and only surface people who are actively expressing the pain right now."',
    used: 3, resolved: 2,
  },
  {
    objection: '"I need to talk to my partner first."',
    response: '"Of course — I can send you a one-pager you can share. Or we can do a 20-minute call with both of you. Which is easier?"',
    used: 2, resolved: 1,
  },
]

const MARKET_INTEL = [
  { topic: 'FA referral drought', signals: 18, trend: 'up',   insight: 'Referral networks are quietly collapsing for solo and small RIAs. Best window to reach them is 6–8 weeks into the dry spell when panic sets in.' },
  { topic: 'TC demo-to-live crisis', signals: 21, trend: 'up', insight: 'r/Daytrading and r/Futures see 20–30 posts per week about traders who are profitable on paper but blow live accounts. Peak coaching intent window: within 72h of post.' },
  { topic: 'TC revenge trading pattern', signals: 14, trend: 'up', insight: 'Posts about "can\'t stop overtrading when down" signal the highest-value coaching clients — they already have a strategy and know it. They need the psychology fix, not more education.' },
  { topic: 'Trading coach churn', signals: 9,  trend: 'flat', insight: 'Members join for signals/education but leave for accountability. Pain is retention, not acquisition.' },
  { topic: 'NYC recruiter fee war', signals: 6, trend: 'up',  insight: 'Retained vs contingency pressure intensifying. Recruiters are open to any system that de-risks client relationships.' },
  { topic: 'MSP cold outreach fatigue', signals: 4, trend: 'down', insight: 'MSP decision-makers have been burned by bad cold email. Warm signal approach is novel — needs patience.' },
  { topic: 'CRE rate uncertainty', signals: 3, trend: 'flat', insight: 'CRE brokers waiting for rate clarity. Low urgency to change tools until market moves.' },
]

const CALL_INSIGHTS = [
  { insight: 'Calls where Hermes asks a binary question in the first 30 seconds book 2× more than open-ended starts.', source: '4 calls', type: 'technique' },
  { insight: 'Callers who mention Reddit in the opening are 3× more likely to book — they\'re already warm.', source: '3 calls', type: 'channel' },
  { insight: 'Average time to "yes, book it" from call start: 4 minutes 20 seconds.', source: '2 calls', type: 'timing' },
  { insight: '"Tell me more" responses (not ghosting, not objecting) should be treated as soft yeses — follow up same day.', source: '2 calls', type: 'technique' },
]

const NICHE_COLOR = { FA: '#1D9E75', TC: '#534AB7', RC: '#BA7517', CRE: '#378ADD', MSP: '#D85A30' }

export default function Learning() {
  const [tab, setTab] = useState('Signal phrases')

  return (
    <div className="content">
      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            fontSize: 11, padding: '5px 13px', borderRadius: 6, cursor: 'pointer',
            border: `1px solid ${tab === t ? 'var(--teal)' : 'var(--border)'}`,
            background: tab === t ? 'rgba(29,158,117,0.12)' : 'transparent',
            color: tab === t ? 'var(--teal)' : 'var(--text-secondary)', fontWeight: tab === t ? 700 : 400,
          }}>
            {t}
          </button>
        ))}
      </div>

      {/* Signal phrases */}
      {tab === 'Signal phrases' && (
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 60px 60px 60px 50px', gap: 0 }}>
            {['Phrase', 'Uses', 'Replies', 'Rate', 'Trend'].map(h => (
              <div key={h} style={{ padding: '8px 14px', fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', textTransform: 'uppercase', borderBottom: '1px solid var(--border)', background: 'var(--bg-primary)' }}>{h}</div>
            ))}
            {SIGNAL_PHRASES.map((s, i) => (
              <React.Fragment key={i}>
                <div style={{ padding: '10px 14px', fontSize: 12, borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 9, fontWeight: 700, color: NICHE_COLOR[s.niche], background: `${NICHE_COLOR[s.niche]}22`, borderRadius: 3, padding: '1px 5px' }}>{s.niche}</span>
                  "{s.phrase}"
                </div>
                <div style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>{s.uses}</div>
                <div style={{ padding: '10px 14px', fontSize: 12, color: 'var(--text-secondary)', borderBottom: '1px solid var(--border)' }}>{s.replies}</div>
                <div style={{ padding: '10px 14px', fontSize: 12, fontWeight: 700, color: parseFloat(s.rate) >= 50 ? 'var(--teal)' : parseFloat(s.rate) >= 25 ? '#BA7517' : 'var(--text-tertiary)', borderBottom: '1px solid var(--border)' }}>{s.rate}</div>
                <div style={{ padding: '10px 14px', fontSize: 14, borderBottom: '1px solid var(--border)' }}>
                  {s.trend === 'up' ? '↑' : s.trend === 'down' ? '↓' : '→'}
                </div>
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Best openers */}
      {tab === 'Best openers' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {OPENERS.map((o, i) => (
            <div key={i} className="card" style={{ padding: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
                <span style={{ fontSize: 9, fontWeight: 700, color: NICHE_COLOR[o.niche], background: `${NICHE_COLOR[o.niche]}22`, borderRadius: 3, padding: '1px 5px' }}>{o.niche}</span>
                <span style={{ fontSize: 11, fontWeight: 700, color: parseFloat(o.rate) >= 50 ? 'var(--teal)' : 'var(--text-tertiary)' }}>{o.rate} reply rate</span>
                <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>· {o.replies} replies from {Math.round(o.replies / (parseFloat(o.rate) / 100) || 0) || '?'} sends</span>
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-primary)', fontStyle: 'italic', lineHeight: 1.5, marginBottom: 10 }}>{o.text}</div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)', borderTop: '1px solid var(--border)', paddingTop: 8 }}>
                <strong style={{ color: 'var(--teal)' }}>Why it works: </strong>{o.why}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Objections */}
      {tab === 'Objections' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {OBJECTIONS.map((o, i) => (
            <div key={i} className="card" style={{ padding: 16 }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--coral, #D85A30)', marginBottom: 8 }}>❝ {o.objection}</div>
              <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5, marginBottom: 10, padding: '8px 12px', background: 'rgba(29,158,117,0.07)', borderRadius: 6, borderLeft: '3px solid var(--teal)' }}>
                {o.response}
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                Used {o.used}× · Resolved {o.resolved}× ({Math.round((o.resolved / o.used) * 100)}% resolution rate)
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Market intel */}
      {tab === 'Market intel' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {MARKET_INTEL.map((m, i) => (
            <div key={i} className="card" style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <div style={{ textAlign: 'center', flexShrink: 0 }}>
                <div style={{ fontSize: 20, fontWeight: 700, color: 'var(--teal)' }}>{m.signals}</div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', textTransform: 'uppercase' }}>signals</div>
                <div style={{ fontSize: 14, marginTop: 2 }}>{m.trend === 'up' ? '↑' : m.trend === 'down' ? '↓' : '→'}</div>
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13, marginBottom: 4 }}>{m.topic}</div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>{m.insight}</div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Call insights */}
      {tab === 'Call insights' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {CALL_INSIGHTS.map((c, i) => (
            <div key={i} className="card" style={{ padding: 14, display: 'flex', gap: 12, alignItems: 'flex-start' }}>
              <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--teal)', background: 'rgba(29,158,117,0.12)', borderRadius: 3, padding: '2px 6px', flexShrink: 0, marginTop: 2, textTransform: 'uppercase' }}>{c.type}</span>
              <div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)', lineHeight: 1.5 }}>{c.insight}</div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>Source: {c.source}</div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
