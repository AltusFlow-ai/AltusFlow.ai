import React, { useState, useEffect, useCallback } from 'react'

const TAGS = [
  { key: 'all',            label: 'All' },
  { key: 'warm_lead',      label: 'Warm lead' },
  { key: 'past_client',    label: 'Past client' },
  { key: 'referral',       label: 'Referral source' },
  { key: 'intro',          label: 'Intro' },
  { key: 'colleague',      label: 'Colleague' },
]

const TAG_COLORS = {
  warm_lead:   { color: '#534AB7', bg: 'rgba(83,74,183,0.12)',  border: 'rgba(83,74,183,0.3)' },
  past_client: { color: '#1D9E75', bg: 'rgba(29,158,117,0.12)', border: 'rgba(29,158,117,0.3)' },
  referral:    { color: '#BA7517', bg: 'rgba(186,117,23,0.12)', border: 'rgba(186,117,23,0.3)' },
  intro:       { color: '#888',    bg: 'rgba(120,120,120,0.1)', border: 'rgba(120,120,120,0.25)' },
  colleague:   { color: '#378ADD', bg: 'rgba(55,138,221,0.12)', border: 'rgba(55,138,221,0.3)' },
}

function initials(name) {
  return name.split(' ').filter(Boolean).slice(0, 2).map(w => w[0].toUpperCase()).join('')
}

function TagPill({ tag }) {
  const c = TAG_COLORS[tag] || TAG_COLORS.intro
  const label = TAGS.find(t => t.key === tag)?.label || tag
  return (
    <span style={{
      fontSize: 10, fontWeight: 700,
      color: c.color, background: c.bg, border: `1px solid ${c.border}`,
      padding: '2px 7px', borderRadius: 20, whiteSpace: 'nowrap',
    }}>
      {label}
    </span>
  )
}

function ContactCard({ contact, onUpdate, onDelete }) {
  const [expanded, setExpanded] = useState(false)
  const [notes,    setNotes]    = useState(contact.notes || '')
  const [saving,   setSaving]   = useState(false)

  const save = async () => {
    setSaving(true)
    try {
      await fetch(`/api/contacts/${contact.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ notes }),
      })
      onUpdate({ ...contact, notes })
    } catch {}
    setSaving(false)
  }

  const emailAction = contact.email
    ? () => window.open(`mailto:${contact.email}`)
    : null

  const tags = Array.isArray(contact.tags) ? contact.tags : (contact.tags ? [contact.tags] : [])
  const ini = initials(contact.name || '?')

  return (
    <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>

      {/* Row */}
      <div
        onClick={() => setExpanded(e => !e)}
        style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 16px', cursor: 'pointer', borderBottom: expanded ? '1px solid var(--border)' : 'none' }}
      >
        {/* Avatar */}
        <div style={{
          width: 36, height: 36, borderRadius: 8, flexShrink: 0,
          background: 'linear-gradient(135deg, #534AB7, #1D9E75)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 13, fontWeight: 700, color: '#fff',
        }}>
          {ini}
        </div>

        {/* Name + company */}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)' }}>{contact.name}</span>
            {tags.map(t => <TagPill key={t} tag={t} />)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-tertiary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {[contact.role, contact.company].filter(Boolean).join(' · ')}
            {contact.how_you_know && (
              <span style={{ marginLeft: 8, opacity: 0.7 }}>via {contact.how_you_know}</span>
            )}
          </div>
        </div>

        {/* Last contact + toggle */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexShrink: 0 }}>
          {contact.last_contact && (
            <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
              {new Date(contact.last_contact).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
            </span>
          )}
          <span style={{ color: 'var(--text-tertiary)', fontSize: 12 }}>{expanded ? '▲' : '▼'}</span>
        </div>
      </div>

      {/* Expanded */}
      {expanded && (
        <div style={{ padding: '16px 16px', display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Contact details */}
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {contact.email && (
              <div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700, letterSpacing: '0.05em', marginBottom: 3 }}>EMAIL</div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{contact.email}</div>
              </div>
            )}
            {contact.phone && (
              <div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700, letterSpacing: '0.05em', marginBottom: 3 }}>PHONE</div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{contact.phone}</div>
              </div>
            )}
            {contact.how_you_know && (
              <div>
                <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700, letterSpacing: '0.05em', marginBottom: 3 }}>HOW YOU KNOW THEM</div>
                <div style={{ fontSize: 12, color: 'var(--text-primary)' }}>{contact.how_you_know}</div>
              </div>
            )}
          </div>

          {/* Notes */}
          <div>
            <div style={{ fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700, letterSpacing: '0.05em', marginBottom: 5 }}>NOTES</div>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              rows={2}
              placeholder="What's relevant — what they need, mutual connections, last conversation…"
              style={{
                width: '100%', background: 'var(--bg)', border: '1px solid var(--border)',
                borderRadius: 6, padding: '8px 10px', color: 'var(--text-primary)',
                fontSize: 12, lineHeight: 1.6, resize: 'vertical', boxSizing: 'border-box', fontFamily: 'inherit',
              }}
            />
          </div>

          {/* Actions */}
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <button
              onClick={save}
              disabled={saving}
              style={{ background: 'var(--bg)', color: 'var(--text-secondary)', border: '1px solid var(--border)', padding: '6px 14px', borderRadius: 6, fontSize: 11, cursor: 'pointer', opacity: saving ? 0.5 : 1 }}
            >
              {saving ? 'Saving…' : 'Save'}
            </button>
            {emailAction && (
              <button
                onClick={emailAction}
                style={{ background: 'transparent', color: 'var(--teal)', border: '1px solid rgba(29,158,117,0.35)', padding: '6px 14px', borderRadius: 6, fontSize: 11, fontWeight: 600, cursor: 'pointer' }}
              >
                ✉ Email
              </button>
            )}
            <button
              onClick={() => onDelete(contact.id)}
              style={{ marginLeft: 'auto', background: 'transparent', color: 'var(--text-tertiary)', border: 'none', fontSize: 11, cursor: 'pointer', opacity: 0.6 }}
            >
              Remove
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

export default function Contacts() {
  const [contacts,   setContacts]   = useState([])
  const [loading,    setLoading]    = useState(true)
  const [tagFilter,  setTagFilter]  = useState('all')
  const [search,     setSearch]     = useState('')
  const [showForm,   setShowForm]   = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    name: '', company: '', role: '', email: '',
    phone: '', how_you_know: '', tags: 'warm_lead', notes: '',
  })

  const DEMO = [
    { id: 1, name: 'Marcus Webb',    company: 'Apex Traders',       role: 'Head of education', email: 'marcus@apextraders.co', phone: '', how_you_know: 'Mutual connection — Jordan',    tags: ['warm_lead'],   notes: 'Has 800 students. Interested in group coaching tools. Follow up after Q2.', last_contact: '2026-06-10' },
    { id: 2, name: 'Tara Nguyen',    company: '',                    role: 'Retail trader',      email: 'tara.n@gmail.com',       phone: '', how_you_know: 'Past client — upgraded to pro', tags: ['past_client'], notes: 'Closed 3 months ago. Happy customer. Asked about referral program.', last_contact: '2026-05-28' },
    { id: 3, name: 'Chris Salinas',  company: 'Funded Next',        role: 'Partnership manager',email: '', phone: '(312) 555-0190', how_you_know: 'Met at TraderMeet Chicago', tags: ['intro'],       notes: 'Can make intros to prop firm founders. Meet quarterly.', last_contact: '2026-04-15' },
    { id: 4, name: 'Jordan Fisk',    company: '',                    role: 'Trading coach',      email: 'jordan@fisktrading.com', phone: '', how_you_know: 'Referred 2 clients',           tags: ['referral'],    notes: 'Best referral source. Focuses on swing traders — complementary niche.', last_contact: '2026-06-18' },
    { id: 5, name: 'Priya Mehta',    company: 'Trader Niche Media', role: 'Content strategist', email: 'priya@traderniche.com',  phone: '', how_you_know: 'LinkedIn DM',                  tags: ['colleague'],   notes: 'Co-working on Reddit content strategy. Good to loop in on Attract posts.', last_contact: '2026-06-01' },
  ]

  const load = useCallback(async () => {
    try {
      const r = await fetch('/api/contacts')
      if (r.ok) {
        const d = await r.json()
        if (Array.isArray(d) && d.length > 0) { setContacts(d); setLoading(false); return }
      }
    } catch {}
    setContacts(DEMO)
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  const addContact = async () => {
    if (!form.name.trim()) return
    setSubmitting(true)
    try {
      await fetch('/api/contacts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, tags: [form.tags] }),
      })
      setForm({ name: '', company: '', role: '', email: '', phone: '', how_you_know: '', tags: 'warm_lead', notes: '' })
      setShowForm(false)
      await load()
    } catch {}
    setSubmitting(false)
  }

  const onUpdate = (updated) => setContacts(prev => prev.map(c => c.id === updated.id ? updated : c))
  const onDelete = async (id) => {
    try { await fetch(`/api/contacts/${id}`, { method: 'DELETE' }) } catch {}
    setContacts(prev => prev.filter(c => c.id !== id))
  }

  const counts = {}
  contacts.forEach(c => {
    const tags = Array.isArray(c.tags) ? c.tags : (c.tags ? [c.tags] : [])
    tags.forEach(t => { counts[t] = (counts[t] || 0) + 1 })
  })

  const filtered = contacts.filter(c => {
    const tags = Array.isArray(c.tags) ? c.tags : (c.tags ? [c.tags] : [])
    const matchTag = tagFilter === 'all' || tags.includes(tagFilter)
    const q = search.toLowerCase()
    const matchSearch = !q || [c.name, c.company, c.role, c.how_you_know].some(f => f?.toLowerCase().includes(q))
    return matchTag && matchSearch
  })

  const stats = [
    { label: 'Total',           val: contacts.length },
    { label: 'Warm leads',      val: counts.warm_lead   || 0 },
    { label: 'Past clients',    val: counts.past_client || 0 },
    { label: 'Referral sources',val: counts.referral    || 0 },
  ]

  return (
    <div style={{ maxWidth: 860, margin: '0 auto' }}>

      {/* Stats */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
        {stats.map(s => (
          <div key={s.label} style={{ flex: 1, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 10, padding: '12px 16px' }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: 'var(--text-primary)', lineHeight: 1 }}>{s.val}</div>
            <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4, fontWeight: 600, letterSpacing: '0.04em' }}>{s.label.toUpperCase()}</div>
          </div>
        ))}
      </div>

      {/* Filters + search + add */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 14, flexWrap: 'wrap', alignItems: 'center' }}>
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Search contacts…"
          style={{ flex: 1, minWidth: 180, background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 12px', color: 'var(--text-primary)', fontSize: 12 }}
        />
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap' }}>
          {TAGS.map(t => {
            const count = t.key === 'all' ? contacts.length : (counts[t.key] || 0)
            const active = tagFilter === t.key
            const c = TAG_COLORS[t.key]
            return (
              <button
                key={t.key}
                onClick={() => setTagFilter(t.key)}
                style={{
                  background: active ? (c ? c.bg : 'rgba(83,74,183,0.12)') : 'transparent',
                  color:      active ? (c ? c.color : '#534AB7')            : 'var(--text-tertiary)',
                  border:     active ? `1px solid ${c ? c.border : 'rgba(83,74,183,0.3)'}` : '1px solid transparent',
                  padding: '4px 11px', borderRadius: 20, fontSize: 11,
                  fontWeight: active ? 700 : 400, cursor: 'pointer',
                }}
              >
                {t.label}
                {count > 0 && (
                  <span style={{ marginLeft: 5, fontSize: 9, fontWeight: 700, background: 'rgba(0,0,0,0.15)', padding: '1px 5px', borderRadius: 8 }}>
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
          + Add contact
        </button>
      </div>

      {/* Add form */}
      {showForm && (
        <div style={{ background: 'var(--card)', border: '1px solid var(--teal)', borderRadius: 10, padding: 20, marginBottom: 20, display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Add contact</div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input value={form.name}    onChange={e => setForm(f => ({ ...f, name:    e.target.value }))} placeholder="Full name *" style={{ flex: 2, minWidth: 160, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12 }} />
            <input value={form.company} onChange={e => setForm(f => ({ ...f, company: e.target.value }))} placeholder="Company"     style={{ flex: 2, minWidth: 140, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12 }} />
            <input value={form.role}    onChange={e => setForm(f => ({ ...f, role:    e.target.value }))} placeholder="Role"        style={{ flex: 1, minWidth: 120, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12 }} />
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input value={form.email} onChange={e => setForm(f => ({ ...f, email: e.target.value }))} placeholder="Email" type="email" style={{ flex: 1, minWidth: 180, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12 }} />
            <input value={form.phone} onChange={e => setForm(f => ({ ...f, phone: e.target.value }))} placeholder="Phone"          style={{ flex: 1, minWidth: 140, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12 }} />
          </div>

          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
            <input
              value={form.how_you_know}
              onChange={e => setForm(f => ({ ...f, how_you_know: e.target.value }))}
              placeholder='How you know them — e.g. "Referred by Jordan", "Met at TraderMeet"'
              style={{ flex: 2, minWidth: 200, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12 }}
            />
            <select
              value={form.tags}
              onChange={e => setForm(f => ({ ...f, tags: e.target.value }))}
              style={{ flex: 1, minWidth: 150, background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12, cursor: 'pointer' }}
            >
              {TAGS.filter(t => t.key !== 'all').map(t => <option key={t.key} value={t.key}>{t.label}</option>)}
            </select>
          </div>

          <textarea
            value={form.notes}
            onChange={e => setForm(f => ({ ...f, notes: e.target.value }))}
            rows={2}
            placeholder="Notes — what they need, context, anything useful"
            style={{ background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 6, padding: '7px 10px', color: 'var(--text-primary)', fontSize: 12, lineHeight: 1.6, resize: 'vertical', fontFamily: 'inherit' }}
          />

          <div style={{ display: 'flex', gap: 8 }}>
            <button
              onClick={addContact}
              disabled={submitting || !form.name.trim()}
              style={{ background: 'var(--teal)', color: '#000', border: 'none', padding: '7px 18px', borderRadius: 6, fontSize: 12, fontWeight: 700, cursor: submitting || !form.name.trim() ? 'not-allowed' : 'pointer', opacity: !form.name.trim() ? 0.5 : 1 }}
            >
              {submitting ? 'Adding…' : 'Add contact'}
            </button>
            <button onClick={() => setShowForm(false)} style={{ background: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border)', padding: '7px 14px', borderRadius: 6, fontSize: 12, cursor: 'pointer' }}>
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
          {search || tagFilter !== 'all'
            ? 'No contacts match that filter.'
            : <>No contacts yet.<br /><span style={{ fontSize: 12 }}>Add warm leads, past clients, referral sources, or anyone you want to keep track of.</span></>}
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.map(c => <ContactCard key={c.id} contact={c} onUpdate={onUpdate} onDelete={onDelete} />)}
        </div>
      )}
    </div>
  )
}
