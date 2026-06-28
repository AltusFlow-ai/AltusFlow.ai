import React, { useState, useEffect } from 'react'

// ── Integration catalog (mirrors integrations.py CATALOG) ────────────────────
const CATALOG = [
  {
    slug: 'webhook_outbound', name: 'Outbound Webhook', icon: '🔗',
    badge: 'Universal', badgeColor: '#1d9e75',
    desc: 'POST prospect events to any URL — works with Zapier, Make, n8n, or your own server.',
    fields: [
      { key: 'webhook_url', label: 'Webhook URL',     type: 'url',      placeholder: 'https://hooks.zapier.com/hooks/catch/...', required: true },
      { key: 'secret',      label: 'Signing Secret',  type: 'password', placeholder: 'Optional — requests signed with HMAC-SHA256' },
    ],
    eventFilter: true,
  },
  {
    slug: 'hubspot', name: 'HubSpot', icon: '🟠',
    badge: 'CRM', badgeColor: '#ff7a59',
    desc: 'Sync contacts to HubSpot CRM and auto-enroll in sequences (Sales Hub Pro required for sequences).',
    fields: [
      { key: 'api_key',     label: 'Private App Token', type: 'password', placeholder: 'pat-na1-...', required: true },
      { key: 'sequence_id', label: 'Sequence ID',       type: 'text',     placeholder: 'Optional — auto-enroll on approval' },
      { key: 'pipeline_id', label: 'Deal Pipeline ID',  type: 'text',     placeholder: 'Optional — create deals automatically' },
    ],
    eventFilter: false,
  },
  {
    slug: 'gmail', name: 'Gmail / SMTP', icon: '📧',
    badge: 'Email', badgeColor: '#4285f4',
    desc: 'Send email touches as part of your sequence using Gmail or any SMTP provider.',
    fields: [
      { key: 'smtp_user', label: 'Gmail Address', type: 'email',    placeholder: 'you@gmail.com',       required: true },
      { key: 'smtp_pass', label: 'App Password',  type: 'password', placeholder: 'xxxx xxxx xxxx xxxx', required: true },
      { key: 'from_name', label: 'From Name',     type: 'text',     placeholder: 'Your Name' },
      { key: 'smtp_host', label: 'SMTP Host',     type: 'text',     placeholder: 'smtp.gmail.com (default)' },
      { key: 'smtp_port', label: 'Port',          type: 'text',     placeholder: '587 (default)' },
    ],
    eventFilter: false,
  },
  {
    slug: 'calendly', name: 'Calendly', icon: '📅',
    badge: 'Calendar', badgeColor: '#006bff',
    desc: 'Auto-log bookings as "Call booked" journey events when prospects schedule via Calendly.',
    fields: [
      { key: 'signing_key', label: 'Webhook Signing Key', type: 'password', placeholder: 'From Calendly → Integrations → Webhooks', required: true },
      { key: 'event_type',  label: 'Event Type UUID',     type: 'text',     placeholder: 'Optional — filter to one meeting type' },
    ],
    eventFilter: false,
  },
  {
    slug: 'apollo', name: 'Apollo.io', icon: '🚀',
    badge: 'Email', badgeColor: '#3b5bdb',
    desc: 'Enroll approved prospects in an Apollo sequence automatically.',
    fields: [
      { key: 'api_key',     label: 'API Key',     type: 'password', placeholder: 'From Apollo → Settings → API Keys', required: true },
      { key: 'sequence_id', label: 'Sequence ID', type: 'text',     placeholder: 'Optional — default sequence' },
    ],
    eventFilter: false,
  },
  {
    slug: 'instantly', name: 'Instantly', icon: '⚡',
    badge: 'Email', badgeColor: '#f59f00',
    desc: 'Push prospects to an Instantly campaign when they reach "sent" status.',
    fields: [
      { key: 'api_key',     label: 'API Key',     type: 'password', placeholder: 'From Instantly → Settings → API', required: true },
      { key: 'campaign_id', label: 'Campaign ID', type: 'text',     placeholder: 'Target campaign ID' },
    ],
    eventFilter: false,
  },
  {
    slug: 'lemlist', name: 'Lemlist', icon: '🍋',
    badge: 'Email', badgeColor: '#fab005',
    desc: 'Add leads to a Lemlist campaign on approval.',
    fields: [
      { key: 'api_key',     label: 'API Key',     type: 'password', placeholder: 'From Lemlist → Settings → Integrations', required: true },
      { key: 'campaign_id', label: 'Campaign ID', type: 'text',     placeholder: 'Target campaign' },
    ],
    eventFilter: false,
  },
  {
    slug: 'gohighlevel', name: 'GoHighLevel', icon: '🏆',
    badge: 'CRM', badgeColor: '#7048e8',
    desc: 'Sync contacts and pipeline stages to a GHL sub-account.',
    fields: [
      { key: 'api_key',     label: 'API Key',      type: 'password', placeholder: 'Agency or location API key', required: true },
      { key: 'location_id', label: 'Location ID',  type: 'text',     placeholder: 'Sub-account location ID' },
      { key: 'pipeline_id', label: 'Pipeline ID',  type: 'text',     placeholder: 'Optional — create opportunities' },
    ],
    eventFilter: false,
  },
  {
    slug: 'slack', name: 'Slack', icon: '💬',
    badge: 'Notify', badgeColor: '#4a154b',
    desc: 'Post Slack notifications when prospects reply, book calls, or close won.',
    fields: [
      { key: 'webhook_url', label: 'Incoming Webhook URL', type: 'url', placeholder: 'https://hooks.slack.com/services/...', required: true },
    ],
    eventFilter: true,
  },
]

const ALL_EVENTS = [
  { key: 'prospect.approved', label: 'Approved' },
  { key: 'prospect.sent',     label: 'Message sent' },
  { key: 'prospect.replied',  label: 'Replied' },
  { key: 'prospect.booked',   label: 'Call booked' },
  { key: 'prospect.closed_won', label: 'Closed won' },
]

const TABS = ['Integrations', 'Account', 'Notifications', 'Team']

// ── Helpers ───────────────────────────────────────────────────────────────────

function TabBtn({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      background: 'none', border: 'none', padding: '10px 16px',
      fontSize: 13, fontWeight: active ? 600 : 400, cursor: 'pointer',
      color: active ? 'var(--text-primary)' : 'var(--text-tertiary)',
      borderBottom: active ? '2px solid var(--teal)' : '2px solid transparent',
      fontFamily: 'inherit',
    }}>{label}</button>
  )
}

function Toggle({ on, onChange }) {
  return (
    <div onClick={e => { e.stopPropagation(); onChange(!on) }}
      style={{
        width: 40, height: 22, borderRadius: 11, flexShrink: 0,
        background: on ? 'var(--teal)' : 'var(--surface-3)',
        cursor: 'pointer', position: 'relative', transition: 'background 0.2s',
      }}>
      <div style={{
        position: 'absolute', top: 3,
        left: on ? 21 : 3,
        width: 16, height: 16, borderRadius: '50%',
        background: '#fff', transition: 'left 0.2s',
      }} />
    </div>
  )
}

// ── Integrations tab ──────────────────────────────────────────────────────────

function IntegrationsTab() {
  const [rows,       setRows]       = useState({})  // slug → {enabled, config}
  const [expanded,   setExpanded]   = useState(null)
  const [dirty,      setDirty]      = useState({})  // slug → partial field edits
  const [saving,     setSaving]     = useState(null)
  const [testing,    setTesting]    = useState(null)
  const [testResult, setTestResult] = useState({})

  useEffect(() => {
    fetch('/api/integrations')
      .then(r => r.ok ? r.json() : [])
      .then(list => {
        const m = {}
        for (const item of (list || [])) m[item.slug] = { enabled: item.enabled, config: item.config || {} }
        setRows(m)
      })
      .catch(() => {})
  }, [])

  function toggle(slug) {
    const cur     = rows[slug] || { enabled: false, config: {} }
    const newVal  = !cur.enabled
    setRows(r => ({ ...r, [slug]: { ...cur, enabled: newVal } }))
    fetch(`/api/integrations/${slug}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: newVal, config: cur.config }),
    }).catch(() => {})
  }

  function save(slug) {
    setSaving(slug)
    const cur    = rows[slug] || { enabled: false, config: {} }
    const merged = { ...(cur.config || {}), ...(dirty[slug] || {}) }
    fetch(`/api/integrations/${slug}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled: cur.enabled, config: merged }),
    })
      .then(r => r.ok ? r.json() : null)
      .then(() => {
        setRows(r => ({ ...r, [slug]: { ...cur, config: merged } }))
        setDirty(d => { const n = { ...d }; delete n[slug]; return n })
        setSaving(null)
      })
      .catch(() => setSaving(null))
  }

  function test(slug) {
    setTesting(slug)
    setTestResult(r => ({ ...r, [slug]: null }))
    fetch(`/api/integrations/${slug}/test`, { method: 'POST' })
      .then(r => r.json())
      .then(d => { setTestResult(r => ({ ...r, [slug]: d.ok ? 'ok' : 'fail' })); setTesting(null) })
      .catch(() => { setTestResult(r => ({ ...r, [slug]: 'fail' })); setTesting(null) })
  }

  function setField(slug, key, value) {
    setDirty(d => ({ ...d, [slug]: { ...(d[slug] || {}), [key]: value } }))
  }

  function getField(slug, key) {
    return dirty[slug]?.[key] !== undefined
      ? dirty[slug][key]
      : (rows[slug]?.config?.[key] ?? '')
  }

  return (
    <div>
      <div style={{ marginBottom: 20 }}>
        <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>Integrations</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          Connect AltusFlow to any tool. Events fire automatically on prospect status changes — no Zapier required for native connectors.
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {CATALOG.map(intg => {
          const row        = rows[intg.slug] || { enabled: false, config: {} }
          const isExpanded = expanded === intg.slug
          const isDirty    = !!(dirty[intg.slug] && Object.keys(dirty[intg.slug]).length)
          const result     = testResult[intg.slug]
          const evList     = Array.isArray(getField(intg.slug, 'events'))
            ? getField(intg.slug, 'events')
            : ALL_EVENTS.map(e => e.key)

          return (
            <div key={intg.slug} style={{
              background: 'var(--surface)',
              border: `1px solid ${row.enabled ? 'rgba(29,158,117,0.35)' : 'var(--border)'}`,
              borderRadius: 10,
              transition: 'border-color 0.2s',
            }}>
              {/* Card header */}
              <div
                onClick={() => setExpanded(isExpanded ? null : intg.slug)}
                style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', cursor: 'pointer' }}
              >
                <span style={{ fontSize: 22, flexShrink: 0 }}>{intg.icon}</span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, flexWrap: 'wrap' }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{intg.name}</span>
                    <span style={{ fontSize: 10, borderRadius: 4, padding: '2px 6px', fontWeight: 600,
                      background: intg.badgeColor + '22', color: intg.badgeColor }}>
                      {intg.badge}
                    </span>
                    {row.enabled && (
                      <span style={{ fontSize: 10, borderRadius: 4, padding: '2px 6px',
                        background: 'rgba(29,158,117,0.13)', color: 'var(--teal)' }}>
                        ● Connected
                      </span>
                    )}
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2, lineHeight: 1.4 }}>
                    {intg.desc}
                  </div>
                </div>
                <Toggle on={row.enabled} onChange={() => toggle(intg.slug)} />
                <span style={{ color: 'var(--text-tertiary)', fontSize: 11, marginLeft: 2 }}>
                  {isExpanded ? '▲' : '▼'}
                </span>
              </div>

              {/* Expanded config */}
              {isExpanded && (
                <div style={{ borderTop: '1px solid var(--border)', padding: '16px 16px 14px' }}>
                  {intg.fields.map(f => (
                    <div key={f.key} style={{ marginBottom: 12 }}>
                      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>
                        {f.label}
                        {f.required && <span style={{ color: '#e55', marginLeft: 2 }}>*</span>}
                      </label>
                      <input
                        type={f.type === 'password' ? 'password' : 'text'}
                        value={getField(intg.slug, f.key)}
                        onChange={e => setField(intg.slug, f.key, e.target.value)}
                        placeholder={f.placeholder}
                        autoComplete="off"
                        style={{
                          width: '100%', boxSizing: 'border-box',
                          background: 'var(--surface-2)', border: '1px solid var(--border)',
                          borderRadius: 7, padding: '7px 10px',
                          fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit',
                        }}
                      />
                    </div>
                  ))}

                  {intg.eventFilter && (
                    <div style={{ marginBottom: 14 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', marginBottom: 7 }}>
                        Fire on these events
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px 14px' }}>
                        {ALL_EVENTS.map(ev => (
                          <label key={ev.key} style={{ display: 'flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--text-secondary)', cursor: 'pointer' }}>
                            <input
                              type="checkbox"
                              checked={evList.includes(ev.key)}
                              onChange={e => {
                                const next = e.target.checked
                                  ? [...evList, ev.key]
                                  : evList.filter(k => k !== ev.key)
                                setField(intg.slug, 'events', next)
                              }}
                            />
                            {ev.label}
                          </label>
                        ))}
                      </div>
                    </div>
                  )}

                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                    <button
                      onClick={() => save(intg.slug)}
                      disabled={saving === intg.slug || !isDirty}
                      style={{
                        background: isDirty ? 'var(--teal)' : 'var(--surface-2)',
                        color: isDirty ? '#fff' : 'var(--text-tertiary)',
                        border: 'none', borderRadius: 7, padding: '7px 18px',
                        fontSize: 12, fontWeight: 600, fontFamily: 'inherit',
                        cursor: isDirty ? 'pointer' : 'not-allowed',
                      }}
                    >
                      {saving === intg.slug ? 'Saving…' : 'Save'}
                    </button>
                    <button
                      onClick={() => test(intg.slug)}
                      disabled={testing === intg.slug}
                      style={{
                        background: 'transparent', color: 'var(--text-secondary)',
                        border: '1px solid var(--border)', borderRadius: 7,
                        padding: '7px 14px', fontSize: 12, cursor: 'pointer', fontFamily: 'inherit',
                      }}
                    >
                      {testing === intg.slug ? 'Testing…' : 'Send test'}
                    </button>
                    {result === 'ok'   && <span style={{ fontSize: 12, color: 'var(--teal)' }}>✓ Test delivered</span>}
                    {result === 'fail' && <span style={{ fontSize: 12, color: '#e55' }}>✗ Failed — check your URL or key</span>}
                  </div>
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Inbound webhook info */}
      <div style={{ marginTop: 24, background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '16px 18px' }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 6 }}>
          Inbound Webhook
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6, marginBottom: 10 }}>
          Any tool can push status updates back to AltusFlow. Set <code style={{ background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 4 }}>INBOUND_WEBHOOK_KEY</code> in your
          {' '}<code style={{ background: 'var(--surface-2)', padding: '1px 5px', borderRadius: 4 }}>.env</code> then send a POST to:
        </div>
        <div style={{ background: 'var(--surface-2)', borderRadius: 7, padding: '8px 12px', fontSize: 12, fontFamily: 'monospace', color: 'var(--text-secondary)', marginBottom: 8 }}>
          POST /api/webhooks/inbound/{'<YOUR_KEY>'}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
          Payload: <code style={{ background: 'var(--surface-2)', padding: '1px 4px', borderRadius: 3 }}>{`{ event, prospect_handle, platform, note }`}</code>
          {' — '}events: <code style={{ background: 'var(--surface-2)', padding: '1px 4px', borderRadius: 3 }}>prospect.replied</code> · <code style={{ background: 'var(--surface-2)', padding: '1px 4px', borderRadius: 3 }}>prospect.booked</code> · <code style={{ background: 'var(--surface-2)', padding: '1px 4px', borderRadius: 3 }}>prospect.closed_won</code>
        </div>
      </div>
    </div>
  )
}

// ── Account tab ───────────────────────────────────────────────────────────────

function AccountTab() {
  const [form,   setForm]   = useState({})
  const [saving, setSaving] = useState(false)
  const [saved,  setSaved]  = useState(false)

  useEffect(() => {
    fetch('/api/settings').then(r => r.ok ? r.json() : {}).then(d => setForm(d || {})).catch(() => {})
  }, [])

  function save() {
    setSaving(true)
    fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    }).then(() => { setSaving(false); setSaved(true); setTimeout(() => setSaved(false), 2000) })
      .catch(() => setSaving(false))
  }

  const field = (key, label, placeholder, type = 'text') => (
    <div style={{ marginBottom: 14 }}>
      <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>{label}</label>
      <input
        type={type} value={form[key] || ''} onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        style={{ width: '100%', boxSizing: 'border-box', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 7, padding: '7px 10px', fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit' }}
      />
    </div>
  )

  const CLIENT_NICHES = [
    { value: 'trading-coaches',    label: 'Trading Coach' },
    { value: 'financial-advisors', label: 'Financial Advisor' },
    { value: 'fitness-coaches',    label: 'Fitness Coach' },
    { value: 'recruiters',         label: 'Recruiter' },
    { value: 'real-estate',        label: 'Real Estate Investor' },
  ]

  const isAdmin = form.niche === 'altusflow'

  return (
    <div style={{ maxWidth: 520 }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 16 }}>Account</div>
      {field('business_name', 'Business Name',    'AltusFlow Agency')}
      {field('website',       'Website',          'https://altusflow.ai', 'url')}
      {field('calendly_url',  'Calendly URL',     'https://calendly.com/yourname/discovery', 'url')}
      {field('reply_email',   'Reply-from Email', 'hello@altusflow.ai',   'email')}
      <div style={{ marginBottom: 14 }}>
        <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Content Mode</label>
        <select
          value={form.niche || ''}
          onChange={e => setForm(f => ({ ...f, niche: e.target.value }))}
          style={{ width: '100%', boxSizing: 'border-box', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 7, padding: '7px 10px', fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit' }}
        >
          <option value=''>Select mode…</option>
          <option value='altusflow'>AltusFlow Admin — I'm finding coaches as clients</option>
          <option value='client'>Client Mode — I'm a coach posting to attract my own clients</option>
        </select>
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>Controls the voice and intent of all AI-generated content</div>
      </div>
      {isAdmin && (
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Target Niche <span style={{ color: 'var(--teal)' }}>— which type of coach are you targeting?</span></label>
          <select
            value={form.target_niche || ''}
            onChange={e => setForm(f => ({ ...f, target_niche: e.target.value }))}
            style={{ width: '100%', boxSizing: 'border-box', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 7, padding: '7px 10px', fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit' }}
          >
            <option value=''>Select target niche…</option>
            {CLIENT_NICHES.map(n => <option key={n.value} value={n.value}>{n.label}</option>)}
          </select>
          <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>Generated posts will speak to pain points specific to this type of coach</div>
        </div>
      )}
      {form.niche === 'client' && (
        <div style={{ marginBottom: 14 }}>
          <label style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)', display: 'block', marginBottom: 4 }}>Your Niche <span style={{ color: 'var(--teal)' }}>— what type of coach are you?</span></label>
          <select
            value={form.target_niche || ''}
            onChange={e => setForm(f => ({ ...f, target_niche: e.target.value }))}
            style={{ width: '100%', boxSizing: 'border-box', background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 7, padding: '7px 10px', fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit' }}
          >
            <option value=''>Select your niche…</option>
            {CLIENT_NICHES.map(n => <option key={n.value} value={n.value}>{n.label}</option>)}
          </select>
        </div>
      )}

      <button onClick={save} disabled={saving} style={{
        background: 'var(--teal)', color: '#fff', border: 'none', borderRadius: 7,
        padding: '8px 20px', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
      }}>
        {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save'}
      </button>
    </div>
  )
}

// ── Notifications tab ─────────────────────────────────────────────────────────

function NotificationsTab() {
  const [form,    setForm]    = useState({})
  const [saving,  setSaving]  = useState(false)
  const [saved,   setSaved]   = useState(false)
  const [saveErr, setSaveErr] = useState('')

  useEffect(() => {
    fetch('/api/settings/notifications').then(r => r.ok ? r.json() : {}).then(d => setForm(d || {})).catch(() => {})
  }, [])

  function save() {
    setSaving(true)
    setSaveErr('')
    fetch('/api/settings/notifications', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form),
    })
      .then(r => r.json())
      .then(d => {
        setSaving(false)
        if (d && d.ok) { setSaved(true); setTimeout(() => setSaved(false), 2000) }
        else setSaveErr(d?.error || 'Save failed — check Railway logs')
      })
      .catch(e => { setSaving(false); setSaveErr(String(e)) })
  }

  const tog = (key, label, desc) => (
    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, marginBottom: 16 }}>
      <Toggle on={!!form[key]} onChange={v => setForm(f => ({ ...f, [key]: v }))} />
      <div>
        <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{label}</div>
        {desc && <div style={{ fontSize: 12, color: 'var(--text-tertiary)', marginTop: 2 }}>{desc}</div>}
      </div>
    </div>
  )

  return (
    <div style={{ maxWidth: 520 }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 16 }}>Notifications</div>
      {tog('daily_digest',   'Daily digest email',     'Morning summary of yesterday\'s scans and pipeline movement')}
      {tog('reply_alert',    'Reply alerts',            'Email when a prospect replies to your outreach')}
      {tog('booked_alert',   'Call booked alerts',      'Instant alert when a prospect books a discovery call')}
      {tog('scan_complete',  'Scan complete summary',   'Summary email after each scan run')}
      {tog('weekly_report',  'Weekly performance report', 'Every Monday — open rates, replies, bookings')}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginTop: 4 }}>
        <button onClick={save} disabled={saving} style={{
          background: 'var(--teal)', color: '#fff', border: 'none', borderRadius: 7,
          padding: '8px 20px', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
        }}>
          {saving ? 'Saving…' : saved ? 'Saved ✓' : 'Save'}
        </button>
        {saveErr && <span style={{ fontSize: 11, color: 'var(--coral)' }}>{saveErr}</span>}
      </div>
    </div>
  )
}

// ── Team tab ──────────────────────────────────────────────────────────────────

function TeamTab() {
  const [members, setMembers] = useState([])
  const [email,   setEmail]   = useState('')
  const [sending, setSending] = useState(false)
  const [msg,     setMsg]     = useState('')

  useEffect(() => {
    fetch('/api/team').then(r => r.ok ? r.json() : []).then(d => setMembers(d || [])).catch(() => {})
  }, [])

  function invite() {
    if (!email.trim()) return
    setSending(true)
    fetch('/api/team/invite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email }),
    })
      .then(r => r.json())
      .then(d => {
        setSending(false)
        if (d.ok) { setMsg('Invite sent'); setEmail('') }
        else setMsg(d.error || 'Failed')
        setTimeout(() => setMsg(''), 3000)
      })
      .catch(() => { setSending(false); setMsg('Error') })
  }

  function remove(mid) {
    fetch(`/api/team/${mid}`, { method: 'DELETE' }).then(() => setMembers(m => m.filter(x => x.id !== mid)))
  }

  return (
    <div style={{ maxWidth: 520 }}>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 16 }}>Team</div>
      {members.length === 0 && (
        <div style={{ fontSize: 13, color: 'var(--text-tertiary)', marginBottom: 16 }}>No team members yet.</div>
      )}
      {members.map(m => (
        <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 12px', background: 'var(--surface-2)', borderRadius: 8, marginBottom: 6 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>{m.name || m.email}</div>
            {m.name && <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>{m.email}</div>}
          </div>
          <span style={{ fontSize: 10, background: 'var(--surface-3)', borderRadius: 4, padding: '2px 6px', color: 'var(--text-secondary)' }}>{m.role || 'Member'}</span>
          <button onClick={() => remove(m.id)} style={{ background: 'none', border: 'none', color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 14, padding: '2px 4px' }}>✕</button>
        </div>
      ))}
      <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
        <input
          type="email" value={email} onChange={e => setEmail(e.target.value)}
          placeholder="teammate@example.com"
          onKeyDown={e => e.key === 'Enter' && invite()}
          style={{ flex: 1, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 7, padding: '7px 10px', fontSize: 12, color: 'var(--text-primary)', fontFamily: 'inherit' }}
        />
        <button onClick={invite} disabled={sending || !email.trim()} style={{
          background: 'var(--teal)', color: '#fff', border: 'none', borderRadius: 7,
          padding: '7px 16px', fontSize: 12, fontWeight: 600, cursor: 'pointer', fontFamily: 'inherit',
        }}>
          {sending ? '…' : 'Invite'}
        </button>
      </div>
      {msg && <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 6 }}>{msg}</div>}
    </div>
  )
}

// ── Root ──────────────────────────────────────────────────────────────────────

export default function Settings() {
  const [tab, setTab] = useState('Integrations')

  return (
    <div className="content">
      {/* Tab bar */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 24, gap: 0 }}>
        {TABS.map(t => <TabBtn key={t} label={t} active={tab === t} onClick={() => setTab(t)} />)}
      </div>

      {tab === 'Integrations'  && <IntegrationsTab />}
      {tab === 'Account'       && <AccountTab />}
      {tab === 'Notifications' && <NotificationsTab />}
      {tab === 'Team'          && <TeamTab />}
    </div>
  )
}
