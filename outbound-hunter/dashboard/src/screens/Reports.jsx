import React, { useState } from 'react'

// ── Data ─────────────────────────────────────────────────────────────────────

const DAILY = [
  {
    id: 1, label: 'Today — Jun 21', status: 'in_progress',
    metrics: { prospects_found: 6, messages_sent: 4, replies: 1, reply_rate: '25%', calls: 0, new_pipeline: 0 },
    highlights: [
      'Signal phrase "pipeline dried up" fired 3× on r/FinancialAdvisors',
      '1 reply received — FA in Chicago, high intent',
      'Best send window so far today: 8–9am',
    ],
  },
  {
    id: 2, label: 'Yesterday — Jun 20', status: 'ready',
    metrics: { prospects_found: 9, messages_sent: 7, replies: 3, reply_rate: '43%', calls: 1, new_pipeline: 1 },
    highlights: [
      'Highest single-day reply rate this month',
      'David R. booked via Hermes call — moved to pipeline',
      'Twitter signals up 2× vs Reddit for recruiters',
    ],
  },
  {
    id: 3, label: 'Jun 19', status: 'ready',
    metrics: { prospects_found: 11, messages_sent: 8, replies: 2, reply_rate: '25%', calls: 2, new_pipeline: 0 },
    highlights: [
      '2 Hermes calls — 1 booked callback, 1 voicemail',
      'MSP niche: 0 replies — signal phrases need refinement',
      'Sarah K. demo booked for Thursday',
    ],
  },
  {
    id: 4, label: 'Jun 18', status: 'ready',
    metrics: { prospects_found: 8, messages_sent: 5, replies: 1, reply_rate: '20%', calls: 1, new_pipeline: 1 },
    highlights: [
      'First pipeline deal created — FA Dallas',
      'Auto-approval threshold working well at 8.5+',
      'Calendly link in follow-up increased booking rate',
    ],
  },
  {
    id: 5, label: 'Jun 17', status: 'ready',
    metrics: { prospects_found: 7, messages_sent: 4, replies: 2, reply_rate: '50%', calls: 0, new_pipeline: 0 },
    highlights: [
      '50% reply rate — best opener was the landing page diagnostic',
      'Both replies came from Reddit, not Twitter',
      'ICP score calibration: raised floor to 7.5',
    ],
  },
]

const WEEKLY = [
  {
    id: 1, label: 'This week (Jun 16–21)', status: 'in_progress',
    metrics: { prospects_found: 41, messages_sent: 28, replies: 9, reply_rate: '32%', calls: 4, new_pipeline: 2 },
    highlights: [
      'Best week since launch — reply rate up 7pts vs last week',
      'Hermes calls converting at 50% to booked or callback',
      'FA niche driving 70% of all qualified prospects',
      'Tuesday morning remains the highest-performing send window',
    ],
  },
  {
    id: 2, label: 'Jun 9–15', status: 'ready',
    metrics: { prospects_found: 33, messages_sent: 22, replies: 5, reply_rate: '23%', calls: 1, new_pipeline: 0 },
    highlights: [
      'Reply rate dipped — openers revised mid-week, recovered by Friday',
      'First Hermes call logged — Marcus T. callback pending',
      'CRE niche underperforming — low urgency signals, consider pause',
    ],
  },
  {
    id: 3, label: 'Jun 2–8', status: 'ready',
    metrics: { prospects_found: 29, messages_sent: 18, replies: 4, reply_rate: '22%', calls: 0, new_pipeline: 0 },
    highlights: [
      'Steady baseline — system running autonomously without intervention',
      'Reddit r/FinancialAdvisors producing best signal density',
      'ScrapeBadger pulling Twitter signals — 3 new prospects added',
    ],
  },
  {
    id: 4, label: 'May 26–Jun 1', status: 'ready',
    metrics: { prospects_found: 22, messages_sent: 14, replies: 3, reply_rate: '21%', calls: 0, new_pipeline: 0 },
    highlights: [
      'Launch week — first real outreach sent',
      'ICP scoring calibration in progress — threshold set at 7.0',
      '3 replies in week 1 — strong early signal',
    ],
  },
]

const MONTHLY = [
  {
    id: 1, label: 'June 2026', status: 'in_progress', generated: null,
    metrics: { prospects_found: 94, messages_sent: 61, replies: 18, reply_rate: '29.5%', calls_booked: 4, deals_in_pipeline: 2, revenue_influenced: '$0' },
    highlights: [
      'Best performing signal phrase: "pipeline dried up" — 4/6 replied',
      'Financial advisors converting 2× faster than recruiters',
      'Tuesday 9–11am messages get highest open rate',
      'Hermes calls added mid-month — 2 deals attributed',
    ],
  },
  {
    id: 2, label: 'May 2026', status: 'ready', generated: '2026-06-01', pages: 8,
    metrics: { prospects_found: 71, messages_sent: 44, replies: 11, reply_rate: '25%', calls_booked: 2, deals_in_pipeline: 1, revenue_influenced: '$0' },
    highlights: [
      'First reply within 3h of launch — fastest ever',
      'Trading coaches had lowest ICP scores — consider tighter filters',
      'Reddit r/FinancialAdvisors = 60% of qualified prospects',
    ],
  },
  {
    id: 3, label: 'April 2026', status: 'ready', generated: '2026-05-01', pages: 7,
    metrics: { prospects_found: 38, messages_sent: 22, replies: 5, reply_rate: '22.7%', calls_booked: 1, deals_in_pipeline: 0, revenue_influenced: '$0' },
    highlights: [
      'System launched mid-month — half a month of data',
      'Calibrating ICP threshold — moved from 7.0 to 7.5 cutoff',
      'First booked discovery call: FA in Dallas',
    ],
  },
]

// ── Shared ────────────────────────────────────────────────────────────────────

const STATUS_STYLE = {
  ready:       { color: 'var(--teal)',  bg: 'rgba(29,158,117,0.12)',  label: '✓ Ready' },
  in_progress: { color: '#BA7517',      bg: 'rgba(186,117,23,0.12)', label: '◐ In progress' },
}

function MetricRow({ label, value }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', padding: '5px 0', borderBottom: '1px solid var(--border)', fontSize: 12 }}>
      <span style={{ color: 'var(--text-tertiary)' }}>{label}</span>
      <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{value}</span>
    </div>
  )
}

function ReportList({ reports, active, onSelect, footerNote }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
      {reports.map(r => {
        const s = STATUS_STYLE[r.status]
        const isActive = active?.id === r.id
        return (
          <div key={r.id} onClick={() => onSelect(r)} style={{
            padding: '10px 14px', borderRadius: 8, cursor: 'pointer',
            background: isActive ? 'var(--bg-secondary)' : 'transparent',
            border: `1px solid ${isActive ? 'var(--teal)' : 'var(--border)'}`,
          }}>
            <div style={{ fontWeight: 600, fontSize: 12, color: 'var(--text-primary)' }}>{r.label}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 3 }}>
              <span style={{ fontSize: 9, fontWeight: 700, color: s.color, background: s.bg, borderRadius: 4, padding: '1px 5px' }}>{s.label}</span>
              {r.pages && <span style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{r.pages}pp</span>}
            </div>
          </div>
        )
      })}
      {footerNote && (
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', padding: '4px 4px', lineHeight: 1.5 }}>{footerNote}</div>
      )}
    </div>
  )
}

function ReportDetail({ report, timeframe }) {
  const m = report.metrics
  const isMonthly = timeframe === 'monthly'
  return (
    <div className="card" style={{ padding: 18 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
        <div>
          <div style={{ fontWeight: 700, fontSize: 14 }}>{report.label}</div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 2 }}>
            {report.status === 'in_progress'
              ? `${timeframe === 'daily' ? 'Day' : timeframe === 'weekly' ? 'Week' : 'Month'} in progress — updates live`
              : report.generated ? `Generated ${report.generated}${report.pages ? ` · ${report.pages} pages` : ''}` : 'Complete'}
          </div>
        </div>
        {report.status === 'ready' && (
          <button className="btn btn-primary" style={{ fontSize: 11 }}>⬇ Download PDF</button>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>Metrics</div>
          <MetricRow label="Prospects found"    value={m.prospects_found} />
          <MetricRow label="Messages sent"      value={m.messages_sent} />
          <MetricRow label="Replies"            value={m.replies} />
          <MetricRow label="Reply rate"         value={m.reply_rate} />
          {isMonthly ? (
            <>
              <MetricRow label="Calls booked"       value={m.calls_booked} />
              <MetricRow label="Deals in pipeline"  value={m.deals_in_pipeline} />
              <MetricRow label="Revenue influenced" value={m.revenue_influenced} />
            </>
          ) : (
            <>
              <MetricRow label="Calls (Hermes)"   value={m.calls} />
              <MetricRow label="New pipeline"     value={m.new_pipeline} />
            </>
          )}
        </div>

        <div>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>Insights</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {report.highlights.map((h, i) => (
              <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', padding: '7px 10px', background: 'var(--bg-primary)', borderRadius: 6, borderLeft: '3px solid var(--teal)', lineHeight: 1.4 }}>
                {h}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Main ──────────────────────────────────────────────────────────────────────

const TABS = ['Daily', 'Weekly', 'Monthly']

export default function Reports() {
  const [tab,    setTab]    = useState('Daily')
  const [active, setActive] = useState({ Daily: DAILY[0], Weekly: WEEKLY[0], Monthly: MONTHLY[0] })

  const lists      = { Daily: DAILY, Weekly: WEEKLY, Monthly: MONTHLY }
  const footerNotes = {
    Daily:   'Daily snapshots generated at midnight.',
    Weekly:  'Weekly reports close every Sunday at midnight.',
    Monthly: 'Monthly PDFs auto-generated on the 1st.',
  }

  return (
    <div className="content">
      <div className="demo-label">📄 REPORTS — Daily · Weekly · Monthly snapshots</div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 14 }}>
        {TABS.map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '6px 18px', borderRadius: 7, fontSize: 12, fontWeight: 600, cursor: 'pointer',
            border: `1px solid ${tab === t ? 'var(--teal)' : 'var(--border)'}`,
            background: tab === t ? 'rgba(29,158,117,0.12)' : 'transparent',
            color: tab === t ? 'var(--teal)' : 'var(--text-secondary)',
          }}>
            {t}
          </button>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '210px 1fr', gap: 12 }}>
        <ReportList
          reports={lists[tab]}
          active={active[tab]}
          onSelect={r => setActive(a => ({ ...a, [tab]: r }))}
          footerNote={footerNotes[tab]}
        />
        {active[tab] && <ReportDetail report={active[tab]} timeframe={tab.toLowerCase()} />}
      </div>
    </div>
  )
}
