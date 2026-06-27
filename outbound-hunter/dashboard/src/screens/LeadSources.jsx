/**
 * LeadSources.jsx — Content & Lead Source Intelligence
 *
 * Shows all four lead channels side by side with performance metrics,
 * value post stats, and comment funnel. Makes it obvious which source
 * is generating the most pipeline.
 */
import React, { useState, useEffect } from 'react'

// ── Source config ─────────────────────────────────────────────────────────────
const SOURCES = [
  {
    key:   'scrapebadger',
    label: 'Scrape Badger',
    icon:  '🎯',
    color: '#D85A30',
    bg:    'rgba(216,90,48,0.10)',
    border:'rgba(216,90,48,0.30)',
    desc:  'High-intent Reddit + X finds',
  },
  {
    key:   'post_comment',
    label: 'Post Comments',
    icon:  '💬',
    color: '#534AB7',
    bg:    'rgba(83,74,183,0.10)',
    border:'rgba(83,74,183,0.30)',
    desc:  'Warm inbound from value posts',
  },
  {
    key:   'cold_stream',
    label: 'Stream',
    icon:  '🔍',
    color: '#1D9E75',
    bg:    'rgba(29,158,117,0.10)',
    border:'rgba(29,158,117,0.30)',
    desc:  'Live pain signal monitoring',
  },
  {
    key:   'creator',
    label: 'Creators',
    icon:  '🤝',
    color: '#BA7517',
    bg:    'rgba(186,117,23,0.10)',
    border:'rgba(186,117,23,0.30)',
    desc:  'Influencer collab pipeline',
  },
]

// ── Demo data ─────────────────────────────────────────────────────────────────
const DEMO_SOURCE_STATS = [
  { source: 'scrapebadger', leads: 34, replies: 11, calls: 4, closed: 1, reply_rate: 32, avg_intent: 81 },
  { source: 'post_comment', leads: 18, replies: 9,  calls: 3, closed: 1, reply_rate: 50, avg_intent: 74 },
  { source: 'cold_stream',  leads: 52, replies: 8,  calls: 2, closed: 0, reply_rate: 15, avg_intent: 58 },
  { source: 'creator',      leads: 5,  replies: 3,  calls: 2, closed: 0, reply_rate: 60, avg_intent: 70 },
]

const DEMO_VALUE_POSTS = [
  {
    id: 1, title: 'What I\'m seeing in r/Daytrading this week — patterns worth knowing about',
    subreddit: 'Daytrading', status: 'posted', upvotes: 847, comments: 64,
    commenters_found: 12, posted_at: new Date(Date.now() - 4*24*3600000).toISOString(),
  },
  {
    id: 2, title: 'The 7 signs you\'re not ready to trade live yet (save this)',
    subreddit: 'Futures', status: 'posted', upvotes: 312, comments: 28,
    commenters_found: 5, posted_at: new Date(Date.now() - 8*24*3600000).toISOString(),
  },
  {
    id: 3, title: 'What I\'m seeing in r/Daytrading — the psychology patterns',
    subreddit: 'Daytrading', status: 'approved', upvotes: 0, comments: 0,
    commenters_found: 0, posted_at: null,
  },
  {
    id: 4, title: 'Why most traders fail in year 1 (and what actually fixes it)',
    subreddit: 'Daytrading', status: 'draft', upvotes: 0, comments: 0,
    commenters_found: 0, posted_at: null,
  },
]

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmt(n) { return (n || 0).toLocaleString() }

function StatCard({ label, value, sub, color }) {
  return (
    <div style={{
      background: 'var(--card)', border: '1px solid var(--border)',
      borderRadius: 10, padding: '16px 20px', flex: 1, minWidth: 140,
    }}>
      <div style={{ fontSize: 22, fontWeight: 700, color: color || 'var(--text-primary)', lineHeight: 1 }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginTop: 5 }}>{label}</div>
      {sub && <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 2 }}>{sub}</div>}
    </div>
  )
}

function Bar({ pct, color }) {
  return (
    <div style={{ height: 6, background: 'var(--border)', borderRadius: 3, flex: 1 }}>
      <div style={{
        height: '100%', width: `${Math.min(pct, 100)}%`,
        background: color, borderRadius: 3, transition: 'width 0.6s ease',
      }} />
    </div>
  )
}

function StatusPill({ status }) {
  const cfg = {
    posted:   { bg: 'rgba(29,158,117,0.12)', color: '#1D9E75',  label: 'Posted'   },
    approved: { bg: 'rgba(83,74,183,0.12)',  color: '#8B82D4',  label: 'Approved' },
    draft:    { bg: 'rgba(186,117,23,0.10)', color: '#BA7517',  label: 'Draft'    },
  }[status] || { bg: 'var(--bg)', color: 'var(--text-tertiary)', label: status }
  return (
    <span style={{
      fontSize: 9, fontWeight: 700, padding: '2px 7px', borderRadius: 10,
      background: cfg.bg, color: cfg.color, letterSpacing: '0.04em',
    }}>
      {cfg.label.toUpperCase()}
    </span>
  )
}

function formatDate(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// ── Main ──────────────────────────────────────────────────────────────────────
export default function LeadSources() {
  const [sourceStats, setSourceStats] = useState(DEMO_SOURCE_STATS)
  const [posts,       setPosts]       = useState(DEMO_VALUE_POSTS)
  const [loading,     setLoading]     = useState(false)

  useEffect(() => {
    // Try loading real data; fall back to demo on failure
    Promise.all([
      fetch('/api/lead-sources/stats').then(r => r.ok ? r.json() : null).catch(() => null),
      fetch('/api/value-posts').then(r => r.ok ? r.json() : null).catch(() => null),
    ]).then(([stats, postsData]) => {
      if (Array.isArray(stats) && stats.length > 0) setSourceStats(stats)
      if (Array.isArray(postsData) && postsData.length > 0) setPosts(postsData)
    })
  }, [])

  const totalLeads   = sourceStats.reduce((a, s) => a + (s.leads || 0), 0)
  const totalReplies = sourceStats.reduce((a, s) => a + (s.replies || 0), 0)
  const totalCalls   = sourceStats.reduce((a, s) => a + (s.calls || 0), 0)
  const totalClosed  = sourceStats.reduce((a, s) => a + (s.closed || 0), 0)
  const overallReplyRate = totalLeads > 0 ? Math.round((totalReplies / totalLeads) * 100) : 0
  const bestSource   = [...sourceStats].sort((a, b) => (b.reply_rate || 0) - (a.reply_rate || 0))[0]

  const postedPosts  = posts.filter(p => p.status === 'posted')
  const totalUpvotes = postedPosts.reduce((a, p) => a + (p.upvotes || 0), 0)
  const totalComments = postedPosts.reduce((a, p) => a + (p.comments || 0), 0)
  const totalCommenters = postedPosts.reduce((a, p) => a + (p.commenters_found || 0), 0)

  const maxLeads = Math.max(...sourceStats.map(s => s.leads || 0), 1)

  return (
    <div style={{ maxWidth: 960, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: 24 }}>

      {/* ── Hero stats ── */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <StatCard label="Total leads"    value={fmt(totalLeads)}          sub="all sources · 30 days" color="var(--text-primary)" />
        <StatCard label="Replies"         value={fmt(totalReplies)}        sub={`${overallReplyRate}% reply rate`} color="#534AB7" />
        <StatCard label="Calls booked"   value={fmt(totalCalls)}          sub="from outreach" color="var(--teal)" />
        <StatCard label="Closed"          value={fmt(totalClosed)}         sub="paying clients" color="#D85A30" />
        <StatCard label="Best channel"   value={bestSource ? SOURCES.find(s => s.key === bestSource.source)?.icon + ' ' + SOURCES.find(s => s.key === bestSource.source)?.label : '—'} sub={bestSource ? `${bestSource.reply_rate}% reply rate` : ''} color="#BA7517" />
      </div>

      {/* ── Lead source breakdown ── */}
      <div style={{
        background: 'var(--card)', border: '1px solid var(--border)',
        borderRadius: 12, padding: 24,
      }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          Lead Sources — channel breakdown
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 20 }}>
          Compare volume, reply rate, and conversion across all four channels
        </div>

        {/* Column headers */}
        <div style={{
          display: 'grid',
          gridTemplateColumns: '200px 1fr 80px 80px 80px 80px',
          gap: 16, marginBottom: 8, padding: '4px 16px',
        }}>
          {['Channel', 'Volume (leads)', 'Reply %', 'Calls', 'Closed', 'Avg Intent'].map((h, i) => (
            <div key={h} style={{
              fontSize: 9, color: 'var(--text-tertiary)', fontWeight: 700,
              letterSpacing: '0.06em', textAlign: i >= 2 ? 'center' : 'left',
            }}>
              {h.toUpperCase()}
            </div>
          ))}
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          {SOURCES.map(src => {
            const stat = sourceStats.find(s => s.source === src.key) || {}
            const replyRate = stat.reply_rate || 0
            const pct = Math.round(((stat.leads || 0) / maxLeads) * 100)
            return (
              <div key={src.key} style={{
                display: 'grid',
                gridTemplateColumns: '200px 1fr 80px 80px 80px 80px',
                alignItems: 'center', gap: 16,
                padding: '14px 16px', borderRadius: 10,
                background: src.bg, border: `1px solid ${src.border}`,
              }}>
                {/* Source label */}
                <div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 2 }}>
                    <span style={{ fontSize: 16 }}>{src.icon}</span>
                    <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>{src.label}</span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-tertiary)' }}>{src.desc}</div>
                </div>

                {/* Volume bar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <Bar pct={pct} color={src.color} />
                  <span style={{ fontSize: 11, color: src.color, fontWeight: 700, flexShrink: 0, width: 24, textAlign: 'right' }}>
                    {stat.leads || 0}
                  </span>
                </div>

                {/* Reply rate */}
                <div style={{ textAlign: 'center' }}>
                  <div style={{
                    fontSize: 16, fontWeight: 700,
                    color: replyRate >= 40 ? '#1D9E75' : replyRate >= 20 ? '#BA7517' : 'var(--text-secondary)',
                  }}>{replyRate}%</div>
                </div>

                {/* Calls */}
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: 'var(--text-primary)' }}>{stat.calls || 0}</div>
                </div>

                {/* Closed */}
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: (stat.closed || 0) > 0 ? 'var(--teal)' : 'var(--text-secondary)' }}>{stat.closed || 0}</div>
                </div>

                {/* Avg intent */}
                <div style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: src.color }}>{stat.avg_intent || '—'}{stat.avg_intent ? '%' : ''}</div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Value posts section ── */}
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, overflow: 'hidden' }}>
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', flexWrap: 'wrap', gap: 12 }}>
            <div>
              <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
                ✨ Value Posts — content performance
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>
                Posts you've published in trading subreddits — upvotes, comment volume, and prospects pulled in
              </div>
            </div>
            {/* Content stats pills */}
            <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
              {[
                { label: 'Posts live',  val: postedPosts.length,  color: '#1D9E75' },
                { label: 'Upvotes',     val: fmt(totalUpvotes),   color: '#534AB7' },
                { label: 'Comments',    val: fmt(totalComments),  color: '#BA7517' },
                { label: 'Prospects in',val: fmt(totalCommenters),color: '#D85A30' },
              ].map(p => (
                <div key={p.label} style={{
                  background: 'var(--bg)', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '8px 14px', textAlign: 'center',
                }}>
                  <div style={{ fontSize: 16, fontWeight: 700, color: p.color }}>{p.val}</div>
                  <div style={{ fontSize: 9, color: 'var(--text-tertiary)', marginTop: 2 }}>{p.label.toUpperCase()}</div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div style={{ padding: '0 24px 20px' }}>
          {/* Table header */}
          <div style={{
            display: 'grid', gridTemplateColumns: '1fr 100px 70px 70px 80px 90px',
            gap: 12, padding: '12px 0 8px',
            borderBottom: '1px solid var(--border)',
          }}>
            {['Post title', 'Subreddit', 'Upvotes', 'Comments', 'Prospects', 'Posted'].map((h, i) => (
              <div key={h} style={{ fontSize: 9, fontWeight: 700, color: 'var(--text-tertiary)', letterSpacing: '0.06em', textAlign: i >= 2 ? 'center' : 'left' }}>
                {h.toUpperCase()}
              </div>
            ))}
          </div>

          {posts.map((p, i) => (
            <div
              key={p.id}
              style={{
                display: 'grid', gridTemplateColumns: '1fr 100px 70px 70px 80px 90px',
                gap: 12, padding: '12px 0',
                borderBottom: i < posts.length - 1 ? '1px solid var(--border)' : 'none',
                alignItems: 'center',
              }}
            >
              <div>
                <div style={{
                  fontSize: 12, fontWeight: 600, color: 'var(--text-primary)',
                  overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                  marginBottom: 4,
                }}>
                  {p.title}
                </div>
                <StatusPill status={p.status} />
              </div>
              <div style={{ fontSize: 11, color: 'var(--text-secondary)' }}>r/{p.subreddit}</div>
              <div style={{ textAlign: 'center', fontSize: 13, fontWeight: 700, color: (p.upvotes || 0) > 200 ? '#534AB7' : 'var(--text-secondary)' }}>
                {p.upvotes > 0 ? fmt(p.upvotes) : '—'}
              </div>
              <div style={{ textAlign: 'center', fontSize: 13, fontWeight: 700, color: (p.comments || 0) > 0 ? '#BA7517' : 'var(--text-secondary)' }}>
                {p.comments > 0 ? fmt(p.comments) : '—'}
              </div>
              <div style={{ textAlign: 'center' }}>
                {(p.commenters_found || 0) > 0 ? (
                  <span style={{
                    fontSize: 12, fontWeight: 700, color: '#D85A30',
                    background: 'rgba(216,90,48,0.10)', border: '1px solid rgba(216,90,48,0.25)',
                    padding: '2px 8px', borderRadius: 6,
                  }}>
                    +{p.commenters_found}
                  </span>
                ) : (
                  <span style={{ fontSize: 11, color: 'var(--text-tertiary)' }}>—</span>
                )}
              </div>
              <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-tertiary)' }}>
                {formatDate(p.posted_at)}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Comment funnel ── */}
      <div style={{ background: 'var(--card)', border: '1px solid var(--border)', borderRadius: 12, padding: 24 }}>
        <div style={{ fontSize: 14, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 4 }}>
          💬 Comment Funnel — post → prospect → client
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-tertiary)', marginBottom: 20 }}>
          How value post engagement converts compared to cold outreach
        </div>

        <div style={{ display: 'flex', gap: 0, alignItems: 'stretch' }}>
          {[
            { label: 'Posts published', val: postedPosts.length, color: '#534AB7', pct: 100 },
            { label: 'Comments received', val: fmt(totalComments), color: '#BA7517', pct: 80 },
            { label: 'Prospects pulled in', val: fmt(totalCommenters), color: '#D85A30', pct: 55 },
            { label: 'Replied to DM', val: fmt(sourceStats.find(s => s.source === 'post_comment')?.replies || 9), color: '#1D9E75', pct: 35 },
            { label: 'Call booked', val: fmt(sourceStats.find(s => s.source === 'post_comment')?.calls || 3), color: '#1D9E75', pct: 18 },
          ].map((step, i, arr) => (
            <React.Fragment key={step.label}>
              <div style={{
                flex: 1, background: `${step.color}18`,
                border: `1px solid ${step.color}40`,
                borderRadius: 10, padding: '16px 12px', textAlign: 'center',
              }}>
                <div style={{ fontSize: 22, fontWeight: 800, color: step.color }}>{step.val}</div>
                <div style={{ fontSize: 10, color: 'var(--text-tertiary)', marginTop: 4, lineHeight: 1.4 }}>{step.label}</div>
              </div>
              {i < arr.length - 1 && (
                <div style={{ display: 'flex', alignItems: 'center', padding: '0 4px', color: 'var(--text-tertiary)', fontSize: 16 }}>›</div>
              )}
            </React.Fragment>
          ))}
        </div>

        <div style={{
          marginTop: 16, padding: '10px 14px', borderRadius: 8,
          background: 'rgba(29,158,117,0.08)', border: '1px solid rgba(29,158,117,0.2)',
          fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6,
        }}>
          💡 <strong style={{ color: 'var(--teal)' }}>Post comment leads convert at 50% reply rate</strong> vs 15% for cold stream —
          because they already engaged with your content before you ever DM'd them.
          One high-upvote post can generate more qualified prospects than a week of cold outreach.
        </div>
      </div>

    </div>
  )
}
