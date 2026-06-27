import React, { useState, useEffect, useCallback } from 'react'

function favicon(domain) {
  return `https://www.google.com/s2/favicons?domain=${domain}&sz=64`
}

// section: 'core' | 'signals' | 'crm' | 'voice' | 'scheduling'
// crm: true means this is a CRM option (only one active at a time via CRM_PROVIDER)
const PLATFORMS = [
  // ── Core ─────────────────────────────────────────────────────────────────
  {
    id: 'anthropic', section: 'core',
    name: 'Anthropic', sub: 'Claude AI — Hermes suggestions',
    logo: { type: 'img', src: favicon('anthropic.com'), bg: '#191919' },
    field: 'API Key', placeholder: 'sk-ant-api03-...',
    docsUrl: 'https://console.anthropic.com/settings/keys', required: true,
  },
  {
    id: 'scrapebadger', section: 'core',
    name: 'ScrapeBadger', sub: 'Omnichannel scraping — powers Market Pulse',
    logo: { type: 'img', src: '/scrapebadger.jpg', bg: '#F0F9FF' },
    field: 'API Key', placeholder: 'sb-live-...',
    docsUrl: null, required: false, badge: 'Market Pulse',
  },
  // ── Signal Sources ────────────────────────────────────────────────────────
  {
    id: 'reddit', section: 'signals',
    name: 'Reddit', sub: 'Organic signal scanning',
    logo: { type: 'img', src: favicon('reddit.com'), bg: '#FFF0EA' },
    fields: [
      { envVar: 'REDDIT_CLIENT_ID',     label: 'Client ID',     placeholder: 'aBcDeFgH...' },
      { envVar: 'REDDIT_CLIENT_SECRET', label: 'Client Secret', placeholder: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' },
    ],
    docsUrl: 'https://www.reddit.com/prefs/apps', required: true,
  },
  {
    id: 'twitter', section: 'signals',
    name: 'Twitter / X', sub: 'Twitter signal scanning',
    logo: { type: 'img', src: favicon('twitter.com'), bg: '#000' },
    field: 'Bearer Token', placeholder: 'AAAAAAAAAA...',
    docsUrl: 'https://developer.twitter.com/en/portal/dashboard', required: false,
  },
  {
    id: 'discord', section: 'signals',
    name: 'Discord', sub: 'Discord channel signal scanning — polls every 5 min',
    logo: { type: 'letter', letter: 'D', bg: '#5865F2', color: '#fff' },
    field: 'Bot Token', placeholder: 'MTxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://discord.com/developers/applications', required: false,
    badge: 'Channel Scanner',
  },
  // ── CRM — Pipeline Sync ──────────────────────────────────────────────────
  {
    id: 'hubspot', section: 'crm', crm: true,
    name: 'HubSpot', sub: 'Contacts, deals, pipeline sync',
    logo: { type: 'img', src: favicon('hubspot.com'), bg: '#FFF4F1' },
    field: 'Private App Token', placeholder: 'pat-na1-...',
    docsUrl: 'https://app.hubspot.com/private-apps', required: false,
  },
  {
    id: 'pipedrive', section: 'crm', crm: true,
    name: 'Pipedrive', sub: 'Persons, deals, notes sync',
    logo: { type: 'img', src: favicon('pipedrive.com'), bg: '#FFF8F0' },
    field: 'API Token', placeholder: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://www.pipedrive.com/en/blog/pipedrive-api', required: false,
  },
  {
    id: 'gohighlevel', section: 'crm', crm: true,
    name: 'GoHighLevel', sub: 'Contacts, opportunities, notes sync',
    logo: { type: 'img', src: favicon('gohighlevel.com'), bg: '#F0FFF4' },
    field: 'Private API Key', placeholder: 'eyJhbGci...',
    docsUrl: 'https://marketplace.gohighlevel.com/oauth/chooselocation', required: false,
  },
  {
    id: 'salesforce', section: 'crm', crm: true,
    name: 'Salesforce', sub: 'Contacts, opportunities, notes sync',
    logo: { type: 'img', src: favicon('salesforce.com'), bg: '#EAF5FF' },
    field: 'Client ID', placeholder: '3MVG9...',
    docsUrl: 'https://help.salesforce.com/s/articleView?id=sf.connected_app_create.htm', required: false,
  },
  // ── Hermes Voice ──────────────────────────────────────────────────────────
  {
    id: 'twilio', section: 'voice',
    name: 'Twilio', sub: 'Phone number — forwards calls, records + transcribes via Hermes',
    logo: { type: 'img', src: favicon('twilio.com'), bg: '#F9F0FF' },
    docsUrl: 'https://console.twilio.com', required: false, badge: 'Hermes Voice',
    fields: [
      { envVar: 'TWILIO_ACCOUNT_SID',  label: 'Account SID',      placeholder: 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' },
      { envVar: 'TWILIO_AUTH_TOKEN',   label: 'Auth Token',        placeholder: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx' },
      { envVar: 'TWILIO_PHONE_NUMBER', label: 'Twilio number',     placeholder: '+15555550100' },
      { envVar: 'MY_CELL_NUMBER',      label: 'Your cell (E.164)', placeholder: '+15555550199' },
    ],
  },
  {
    id: 'openai', section: 'voice',
    name: 'OpenAI', sub: 'Whisper transcription — converts call recordings to text',
    logo: { type: 'img', src: favicon('openai.com'), bg: '#1a1a1a' },
    field: 'API Key', placeholder: 'sk-...',
    docsUrl: 'https://platform.openai.com/api-keys', required: false, badge: 'Hermes Voice',
  },
  {
    id: 'deepgram', section: 'voice',
    name: 'Deepgram', sub: 'Live call transcription — real-time speech-to-text during active calls',
    logo: { type: 'img', src: favicon('deepgram.com'), bg: '#0D1117' },
    field: 'API Key', placeholder: 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
    docsUrl: 'https://console.deepgram.com/signup', required: false, badge: 'Hermes Voice',
  },
  {
    id: 'vapi', section: 'voice',
    name: 'Vapi', sub: 'Hermes voice — inbound calls, transcripts logged back to model',
    logo: { type: 'img', src: favicon('vapi.ai'), bg: '#F5F3FF' },
    field: 'API Key', placeholder: 'xxxxxxxx-xxxx-xxxx-xxxx-...',
    docsUrl: 'https://dashboard.vapi.ai', required: false, badge: 'Hermes Voice',
  },
  {
    id: 'bland', section: 'voice',
    name: 'Bland AI', sub: 'Hermes outbound calls — follow-up pipeline',
    logo: { type: 'img', src: favicon('bland.ai'), bg: '#F0FDF4' },
    field: 'API Key', placeholder: 'sk-...',
    docsUrl: 'https://app.bland.ai', required: false, badge: 'Hermes Voice',
  },
  // ── Scheduling ────────────────────────────────────────────────────────────
  {
    id: 'calendly', section: 'scheduling',
    name: 'Calendly', sub: 'Booking detection — auto pipeline advance + CRM stage sync',
    logo: { type: 'img', src: favicon('calendly.com'), bg: '#EEF4FF' },
    field: 'Personal Access Token', placeholder: 'eyJraWQ...',
    docsUrl: 'https://calendly.com/integrations/api_webhooks',
    required: false, locked: true, lockLabel: 'Unlocks after client 1',
  },
]

const SECTION_LABELS = {
  core:       'Core',
  signals:    'Signal Sources',
  crm:        'CRM — Pipeline Sync',
  voice:      'Hermes Voice',
  scheduling: 'Scheduling',
}

function PlatformLogo({ logo }) {
  if (logo.type === 'img') {
    return (
      <div className="connection-icon" style={{ background: logo.bg, overflow: 'hidden', padding: 4 }}>
        <img src={logo.src} alt="" style={{ width: 28, height: 28, objectFit: 'contain', borderRadius: 4 }} />
      </div>
    )
  }
  return (
    <div className="connection-icon" style={{ background: logo.bg, color: logo.color, fontWeight: 800, fontSize: 11 }}>
      {logo.letter}
    </div>
  )
}

function ConnectForm({ platform, onSave }) {
  const isMulti = Array.isArray(platform.fields)
  const [keyVal,  setKeyVal]  = useState('')
  const [multiVal, setMultiVal] = useState(() =>
    isMulti ? Object.fromEntries(platform.fields.map(f => [f.envVar, ''])) : {}
  )
  const [saving, setSaving] = useState(false)
  const [msg,    setMsg]    = useState('')

  async function handleSave() {
    setSaving(true)
    setMsg('')
    try {
      const body = isMulti
        ? { keys: Object.fromEntries(Object.entries(multiVal).filter(([, v]) => v.trim())) }
        : { key: keyVal.trim() }

      const r = await fetch(`/api/connections/${platform.id}/key`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      })
      const d = await r.json()
      if (d.ok) { onSave(); setKeyVal(''); setMultiVal(isMulti ? Object.fromEntries(platform.fields.map(f => [f.envVar, ''])) : {}) }
      else { setMsg(d.error || 'Save failed') }
    } catch {
      setMsg('Network error — is Flask running?')
    }
    setSaving(false)
  }

  const canSave = isMulti
    ? Object.values(multiVal).some(v => v.trim())
    : !!keyVal.trim()

  return (
    <div style={{ marginTop: 8, paddingTop: 8, borderTop: '1px solid var(--border)', width: '100%' }}>
      {platform.docsUrl && (
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginBottom: 6 }}>
          <a href={platform.docsUrl} target="_blank" rel="noreferrer"
            style={{ color: 'var(--accent)', textDecoration: 'none' }}>
            Get credentials ↗
          </a>
        </div>
      )}

      {isMulti ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
          {platform.fields.map(f => (
            <div key={f.envVar}>
              <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginBottom: 2 }}>{f.label}</div>
              <input
                type="password"
                value={multiVal[f.envVar] || ''}
                onChange={e => setMultiVal(v => ({ ...v, [f.envVar]: e.target.value }))}
                placeholder={f.placeholder}
                style={{
                  width: '100%', boxSizing: 'border-box', padding: '5px 8px', borderRadius: 5,
                  border: '1px solid var(--border)', background: 'var(--bg-primary)',
                  color: 'var(--text-primary)', fontSize: 11, fontFamily: 'monospace',
                }}
              />
            </div>
          ))}
        </div>
      ) : (
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            type="password"
            value={keyVal}
            onChange={e => setKeyVal(e.target.value)}
            placeholder={platform.placeholder}
            onKeyDown={e => e.key === 'Enter' && handleSave()}
            autoFocus
            style={{
              flex: 1, padding: '6px 8px', borderRadius: 6, minWidth: 0,
              border: '1px solid var(--border)', background: 'var(--bg-primary)',
              color: 'var(--text-primary)', fontSize: 11, fontFamily: 'monospace',
            }}
          />
        </div>
      )}

      <button
        onClick={handleSave}
        disabled={saving || !canSave}
        style={{
          marginTop: 8, width: '100%', padding: '6px 0', borderRadius: 6,
          fontWeight: 600, fontSize: 11,
          background: saving ? 'var(--border)' : 'var(--teal)',
          color: '#fff', border: 'none', cursor: saving || !canSave ? 'default' : 'pointer',
        }}
      >
        {saving ? 'Saving…' : 'Save'}
      </button>

      {msg && <div style={{ fontSize: 10, color: 'var(--coral)', marginTop: 4 }}>{msg}</div>}
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4 }}>
        Saved securely to database — active immediately, no restart needed.
      </div>
    </div>
  )
}

function WebhookUrlPanel() {
  const [copied, setCopied] = useState(false)
  const webhookUrl = `${window.location.origin}/api/webhooks/scrapebadger`

  const copy = async () => {
    await navigator.clipboard.writeText(webhookUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div style={{
      marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)', width: '100%',
    }}>
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', marginBottom: 6, letterSpacing: '0.06em' }}>
        WEBHOOK URL — paste this into Scrape Badger → Settings → Webhook
      </div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <div style={{
          flex: 1, background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 6, padding: '7px 10px',
          fontSize: 11, color: 'var(--text-secondary)', fontFamily: 'monospace',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {webhookUrl}
        </div>
        <button
          onClick={copy}
          style={{
            background: copied ? 'rgba(29,158,117,0.15)' : 'var(--teal)',
            color: copied ? 'var(--teal)' : '#000',
            border: copied ? '1px solid var(--teal)' : 'none',
            padding: '7px 14px', borderRadius: 6, fontSize: 11,
            fontWeight: 700, cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
          }}
        >
          {copied ? '✓ Copied!' : '📋 Copy URL'}
        </button>
      </div>
      <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 6, lineHeight: 1.5 }}>
        When Scrape Badger finds a lead, it POSTs to this URL automatically.
        Leads appear instantly in <strong style={{ color: 'var(--text-secondary)' }}>Reply Center → 🎯 Scrape Badger</strong> tab.
        Optional: set <code style={{ background: 'var(--bg)', padding: '1px 4px', borderRadius: 3 }}>SCRAPEBADGER_WEBHOOK_SECRET</code> in .env to verify incoming requests.
      </div>
    </div>
  )
}

// ── Discord Channel Manager ───────────────────────────────────────────────────
function DiscordChannelManager({ channels, onRefresh }) {
  const [channelId,   setChannelId]   = useState('')
  const [guildName,   setGuildName]   = useState('')
  const [channelName, setChannelName] = useState('')
  const [podSlug,     setPodSlug]     = useState('daytrading')
  const [adding,      setAdding]      = useState(false)
  const [msg,         setMsg]         = useState('')
  const [testing,     setTesting]     = useState(false)
  const [testResult,  setTestResult]  = useState(null)

  const POD_OPTIONS = [
    { value: 'daytrading',    label: 'Day Trading'   },
    { value: 'futures',       label: 'Futures'       },
    { value: 'swing-trading', label: 'Swing Trading' },
    { value: 'crypto',        label: 'Crypto'        },
    { value: 'options',       label: 'Options'       },
  ]

  const addChannel = async () => {
    if (!channelId.trim()) return
    setAdding(true); setMsg('')
    try {
      const r = await fetch('/api/discord/channels', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ channel_id: channelId.trim(), guild_name: guildName.trim() || null, channel_name: channelName.trim() || null, pod_slug: podSlug }),
      })
      const d = await r.json()
      if (d.ok) { setMsg('✓ Channel added'); setChannelId(''); setGuildName(''); setChannelName(''); onRefresh() }
      else setMsg(d.error || 'Add failed')
    } catch { setMsg('Network error') }
    setAdding(false)
  }

  const removeChannel = async (cid) => {
    try {
      await fetch(`/api/discord/channels/${cid}`, { method: 'DELETE' })
      onRefresh()
    } catch {}
  }

  const testConnection = async () => {
    setTesting(true); setTestResult(null)
    try {
      const r = await fetch('/api/discord/validate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
      const d = await r.json()
      setTestResult(d)
    } catch { setTestResult({ ok: false, error: 'Network error' }) }
    setTesting(false)
  }

  return (
    <div style={{ width: '100%', marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
      {/* Test connection */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
        <button
          onClick={testConnection}
          disabled={testing}
          style={{
            background: 'rgba(88,101,242,0.12)', color: '#5865F2',
            border: '1px solid rgba(88,101,242,0.35)',
            padding: '5px 12px', borderRadius: 5, fontSize: 11, fontWeight: 600,
            cursor: testing ? 'wait' : 'pointer',
          }}
        >
          {testing ? '⏳ Testing…' : '🔗 Test bot connection'}
        </button>
        {testResult && (
          <span style={{ fontSize: 11, color: testResult.ok ? 'var(--teal)' : 'var(--coral)', fontWeight: 600 }}>
            {testResult.ok ? `✓ Connected as ${testResult.username || 'bot'}` : `✗ ${testResult.error}`}
          </span>
        )}
      </div>

      {/* Channel list */}
      {channels.length > 0 && (
        <div style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', gap: 6 }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 4 }}>
            WATCHED CHANNELS ({channels.length})
          </div>
          {channels.map(ch => (
            <div key={ch.channel_id} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              background: 'var(--bg)', border: '1px solid var(--border)',
              borderRadius: 6, padding: '6px 10px',
            }}>
              <span style={{ fontSize: 12, color: '#5865F2', fontWeight: 700 }}>#</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {ch.channel_name || ch.channel_id}
                </div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>
                  {ch.guild_name && `${ch.guild_name} · `}{ch.pod_slug} pod · {ch.enabled ? 'watching' : 'paused'}
                </div>
              </div>
              <button
                onClick={() => removeChannel(ch.channel_id)}
                style={{ background: 'transparent', border: 'none', color: 'var(--text-tertiary)', fontSize: 14, cursor: 'pointer', padding: '2px 6px', borderRadius: 4 }}
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Add channel form */}
      <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', marginBottom: 6 }}>
        ADD CHANNEL
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
        <input
          value={channelId}
          onChange={e => setChannelId(e.target.value)}
          placeholder="Channel ID (right-click channel → Copy ID)"
          style={{ width: '100%', boxSizing: 'border-box', padding: '6px 8px', borderRadius: 5, border: '1px solid var(--border)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 11, fontFamily: 'monospace' }}
        />
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            value={guildName}
            onChange={e => setGuildName(e.target.value)}
            placeholder="Server name (optional)"
            style={{ flex: 1, padding: '6px 8px', borderRadius: 5, border: '1px solid var(--border)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 11 }}
          />
          <input
            value={channelName}
            onChange={e => setChannelName(e.target.value)}
            placeholder="#channel-name (optional)"
            style={{ flex: 1, padding: '6px 8px', borderRadius: 5, border: '1px solid var(--border)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 11 }}
          />
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <select
            value={podSlug}
            onChange={e => setPodSlug(e.target.value)}
            style={{ padding: '6px 8px', borderRadius: 5, border: '1px solid var(--border)', background: 'var(--bg-primary)', color: 'var(--text-primary)', fontSize: 11, cursor: 'pointer' }}
          >
            {POD_OPTIONS.map(o => <option key={o.value} value={o.value}>{o.label} pod</option>)}
          </select>
          <button
            onClick={addChannel}
            disabled={adding || !channelId.trim()}
            style={{
              flex: 1, padding: '7px 0', borderRadius: 5, fontWeight: 600, fontSize: 11,
              background: adding ? 'var(--border)' : '#5865F2',
              color: '#fff', border: 'none',
              cursor: adding || !channelId.trim() ? 'default' : 'pointer',
            }}
          >
            {adding ? 'Adding…' : '+ Add channel'}
          </button>
        </div>
        {msg && (
          <div style={{ fontSize: 10, color: msg.startsWith('✓') ? 'var(--teal)' : 'var(--coral)', marginTop: 2 }}>
            {msg}
          </div>
        )}
        <div style={{ fontSize: 10, color: 'var(--text-tertiary)', lineHeight: 1.5 }}>
          Enable Developer Mode in Discord settings to copy Channel IDs. Bot must be in the server.
        </div>
      </div>
    </div>
  )
}

function ConnectionCard({ platform, connected, activeCrm, onSave, onDisconnect, discordChannels, onDiscordRefresh }) {
  const [open, setOpen] = useState(platform.id === 'scrapebadger')
  const isActive = platform.crm && activeCrm === platform.id

  async function handleDisconnect() {
    try {
      await fetch(`/api/connections/${platform.id}/disconnect`, { method: 'POST' })
      onDisconnect(platform.id)
    } catch {}
  }

  const isLocked = !connected && platform.locked

  return (
    <div className={`connection-card${isLocked ? ' locked' : ''}`}
      style={{
        flexWrap: 'wrap',
        borderLeft: `3px solid ${isActive ? '#534AB7' : connected ? 'var(--teal)' : isLocked ? 'var(--border)' : 'var(--border)'}`,
        alignItems: open ? 'flex-start' : 'center',
        background: isActive ? 'rgba(83,74,183,0.04)' : undefined,
      }}
    >
      <PlatformLogo logo={platform.logo} />

      <div className="connection-info">
        <div style={{ display: 'flex', alignItems: 'center', gap: 5, flexWrap: 'wrap' }}>
          <span className="connection-name">{platform.name}</span>
          {isActive && (
            <span style={{ fontSize: 9, fontWeight: 700, color: '#534AB7', background: 'rgba(83,74,183,0.15)', borderRadius: 3, padding: '1px 5px' }}>
              ACTIVE CRM
            </span>
          )}
          {platform.required && (
            <span style={{ fontSize: 9, fontWeight: 700, color: 'var(--coral)', background: 'rgba(216,90,48,0.12)', borderRadius: 3, padding: '1px 4px' }}>
              REQUIRED
            </span>
          )}
          {platform.badge && (
            <span style={{
              fontSize: 9, fontWeight: 600, borderRadius: 3, padding: '1px 4px',
              color:      platform.badge === 'Hermes Voice' ? 'var(--teal)' : '#7C3AED',
              background: platform.badge === 'Hermes Voice' ? 'rgba(29,158,117,0.15)' : 'rgba(124,58,237,0.12)',
            }}>
              {platform.badge}
            </span>
          )}
          {platform.badge === 'Market Pulse' && (
            <span style={{ fontSize: 9, fontWeight: 600, borderRadius: 3, padding: '1px 4px', color: '#7C3AED', background: 'rgba(124,58,237,0.12)' }}>
              {platform.badge}
            </span>
          )}
        </div>
        <div className={`connection-status ${connected ? 'connected' : 'disconnected'}`}>
          {isActive
            ? 'Active CRM · pipeline sync enabled'
            : connected
            ? platform.crm ? 'Key saved · active CRM set in Settings' : 'Connected · key active'
            : isLocked
            ? platform.lockLabel
            : 'Not connected'}
        </div>

        {open && !connected && !isLocked && (
          <ConnectForm platform={platform} onSave={() => { onSave(platform.id); setOpen(false) }} />
        )}

        {/* Scrape Badger — show webhook URL so they can paste it into SB settings */}
        {platform.id === 'scrapebadger' && open && (
          <WebhookUrlPanel />
        )}

        {/* Discord — show channel manager when connected */}
        {platform.id === 'discord' && connected && (
          <DiscordChannelManager
            channels={discordChannels || []}
            onRefresh={onDiscordRefresh || (() => {})}
          />
        )}
      </div>

      {isLocked ? (
        <div className="lock-icon">🔒</div>
      ) : connected ? (
        <button
          onClick={handleDisconnect}
          style={{ fontSize: 10, padding: '3px 8px', borderRadius: 5, border: '1px solid var(--border)', background: 'transparent', color: 'var(--text-tertiary)', cursor: 'pointer', flexShrink: 0 }}
        >
          Disconnect
        </button>
      ) : (
        <button
          className="btn btn-sm"
          onClick={() => setOpen(o => !o)}
          style={{ flexShrink: 0 }}
        >
          {open ? 'Cancel' : 'Connect'}
        </button>
      )}

      {!open && (
        <div className={`health-dot ${isActive ? '' : connected ? 'green' : isLocked ? '' : 'amber'}`}
          style={
            isActive     ? { background: '#534AB7' } :
            !connected && !isLocked ? { background: 'var(--amber)' } : {}
          }
        />
      )}
    </div>
  )
}

export default function Connections() {
  const [status, setStatus] = useState({
    reddit: false, twitter: false, discord: false,
    hubspot: false, pipedrive: false, gohighlevel: false, salesforce: false,
    anthropic: false, scrapebadger: false,
    twilio: false, openai: false, deepgram: false,
    vapi: false, bland: false, calendly: false,
    crm_provider: 'none',
  })
  const [discordChannels, setDiscordChannels] = useState([])
  const [showDiscordMgr, setShowDiscordMgr] = useState(false)

  useEffect(() => {
    fetch('/api/connections')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d && typeof d === 'object') setStatus(d) })
      .catch(() => {})
  }, [])

  const loadDiscordChannels = () => {
    fetch('/api/discord/channels')
      .then(r => r.ok ? r.json() : [])
      .then(d => { if (Array.isArray(d)) setDiscordChannels(d) })
      .catch(() => {})
  }

  useEffect(() => {
    if (status.discord) loadDiscordChannels()
  }, [status.discord])

  function handleSave(id)       { setStatus(s => ({ ...s, [id]: true  })) }
  function handleDisconnect(id) { setStatus(s => ({ ...s, [id]: false })) }

  const activeCrm      = status.crm_provider || 'none'
  const connectedCount = PLATFORMS.filter(p => !!status[p.id]).length
  const allRequired    = PLATFORMS.filter(p => p.required).every(p => status[p.id])

  // Group platforms by section
  const sections = ['core', 'signals', 'crm', 'voice', 'scheduling']

  return (
    <div className="content">
      <div className="demo-label">
        🔌 CONNECTIONS — {connectedCount}/{PLATFORMS.length} connected
        {allRequired
          ? <span style={{ color: 'var(--teal)', marginLeft: 8 }}>✓ Core stack ready</span>
          : <span style={{ color: 'var(--amber)', marginLeft: 8 }}>⚠ Connect required integrations</span>
        }
      </div>

      {sections.map(section => {
        const items = PLATFORMS.filter(p => p.section === section)
        if (!items.length) return null
        return (
          <div key={section} style={{ marginBottom: 32 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '.08em', textTransform: 'uppercase' }}>
                {SECTION_LABELS[section]}
              </div>
              {section === 'crm' && (
                <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                  · active: <span style={{ color: activeCrm === 'none' ? 'var(--amber)' : '#534AB7', fontWeight: 600 }}>
                    {activeCrm === 'none' ? 'none — connect a CRM below' : activeCrm}
                  </span>
                </div>
              )}
              <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            </div>
            <div className="connections-grid">
              {items.map(p => (
                <ConnectionCard
                  key={p.id}
                  platform={p}
                  connected={!!status[p.id]}
                  activeCrm={activeCrm}
                  onSave={handleSave}
                  onDisconnect={handleDisconnect}
                  discordChannels={p.id === 'discord' ? discordChannels : undefined}
                  onDiscordRefresh={p.id === 'discord' ? loadDiscordChannels : undefined}
                />
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}
