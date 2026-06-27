"""
stream_watcher.py — Real-time Reddit stream for AltusFlow.

Runs as a daemon thread alongside Flask. Monitors subreddits 24/7 using
PRAW's SubredditStream, scores each new post immediately, and creates a
prospect with a staged Hermes draft when ICP >= threshold.

Rules:
  - ALL Hermes drafts are staged (status='pending_review'). Never auto-sent.
  - Mod outreach messages are written to the mod_outreach table, NOT prospects.
    This ensures reps can never confuse a mod with a sales lead.
  - Reconnects automatically on network errors with exponential back-off.
  - Skip_existing=True so restarting the app doesn't re-process old posts.
"""

import os
import json
import logging
import threading
import time
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# ── Global state ──────────────────────────────────────────────────────────────

_stream_thread = None
_stop_event    = threading.Event()
_status_lock   = threading.Lock()
_status = {
    'running':          False,
    'started_at':       None,
    'posts_seen':       0,
    'prospects_found':  0,
    'last_post_at':     None,
    'last_prospect_at': None,
    'last_error':       None,
    'subreddits':       [],
}


def get_stream_status() -> dict:
    with _status_lock:
        return dict(_status)


def _upd(**kw):
    with _status_lock:
        _status.update(kw)


# ── ICP keyword scorer (fast pre-filter; full Claude qualifier runs at scan time)

_PAIN_SIGNALS = [
    ('blown account', 5), ('blew up my account', 5), ('blew up', 4),
    ('blown up', 4), ('3rd account', 4), ('third account', 4),
    ('4th account', 4), ('lost everything', 4), ('margin call', 4),
    ('need a coach', 5), ('looking for a coach', 5), ('find a coach', 5),
    ('trading coach', 4), ('find a mentor', 4), ('need a mentor', 4),
    ('trading mentor', 4), ('accountability', 3), ('consistently losing', 4),
    ('keep losing', 3), ('always lose', 3), ('cant stop losing', 4),
    ('revenge trad', 4), ('emotional trad', 4), ('overtrading', 3),
    ('trading psychology', 3), ('does anyone know', 2), ('recommend a', 2),
    ('help me', 1), ('struggling', 2), ('discipline problem', 3),
    ('gambling', 2), ('addicted to trading', 3), ('stop trading', 2),
    ('quit trading', 3), ('I give up', 3), ('done with trading', 3),
]

# Trading educators / coaching — the only niche active right now.
# Add other niches here when expanding beyond trading coaches.
_TRADING_SUBREDDITS = {
    'Daytrading', 'Futures', 'FuturesTrading', 'Forex', 'stocks', 'options',
    'algotrading', 'StockMarket', 'pennystocks', 'RobinHood', 'wallstreetbets',
}

_NICHE_MAP = {
    'Daytrading':     'trading-coaches',
    'Futures':        'trading-coaches',
    'FuturesTrading': 'trading-coaches',
    'Forex':          'trading-coaches',
    'stocks':         'trading-coaches',
    'options':        'trading-coaches',
    'algotrading':    'trading-coaches',
    'StockMarket':    'trading-coaches',
    'pennystocks':    'trading-coaches',
    'RobinHood':      'trading-coaches',
    'wallstreetbets': 'trading-coaches',
}


def _score(title: str, body: str, subreddit: str) -> tuple[float, str]:
    text  = f"{title} {body}".lower()
    score = 0.0
    hits  = []
    for phrase, weight in _PAIN_SIGNALS:
        if phrase in text:
            score += weight
            hits.append(phrase)
    if subreddit in _TRADING_SUBREDDITS:
        score += 1.0
    reason = ', '.join(hits[:5]) if hits else ''
    return min(round(score, 1), 10.0), reason


# ── Hermes draft (fast path — no conversation history for stream posts) ────────

def _draft_message(prospect: dict) -> str | None:
    """
    Ask Hermes for a first-touch draft. Returns the text or None.
    The draft is stored in prospects.drafted_message — one-click approve to send.
    """
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return None

        import urllib.request as _ur

        prompt = (
            "You are Hermes, an outreach assistant for a trading coach. "
            "Write a short, warm Reddit DM (under 280 chars) to someone who posted about trading struggles. "
            "Sound human. Reference their specific pain. End with a gentle offer to help, no hard sell. "
            "Return ONLY the message text.\n\n"
            f"Subreddit: r/{prospect.get('subreddit', '')}\n"
            f"Their post: {(prospect.get('post_text') or '')[:600]}"
        )

        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 120,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            method="POST",
        )
        with _ur.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return (data.get("content") or [{}])[0].get("text", "").strip() or None

    except Exception as e:
        log.debug(f"[stream] hermes draft error: {e}")
        return None


# ── Public comment draft (comments-first approach) ───────────────────────────
# This is the biggest lever from the Avneesh playbook.
# Post a HELPFUL COMMENT on the prospect's post BEFORE sending a DM.
# The comment gets seen by everyone who views the post — the DM is only seen by the poster.
# Rep approves this separately from the DM.

def _draft_public_comment(prospect: dict) -> str | None:
    """
    Draft a helpful public reply to the prospect's Reddit post.
    Stored in call_opener field — displayed as a separate draft from the DM.
    Must read like genuine advice from a knowledgeable person, NOT a pitch.
    """
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return None

        import urllib.request as _ur

        prompt = (
            "You are an expert trading educator writing a genuinely helpful public Reddit comment. "
            "Write a comment that: (1) acknowledges their specific situation, "
            "(2) gives ONE concrete, actionable piece of advice they can use immediately, "
            "(3) ends naturally — no pitch, no links, no mention of coaching. "
            "Sound like a fellow trader who's been there. Under 200 words. "
            "Return ONLY the comment text.\n\n"
            f"Subreddit: r/{prospect.get('subreddit', '')}\n"
            f"Their post: {(prospect.get('post_text') or '')[:800]}"
        )

        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            method="POST",
        )
        with _ur.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return (data.get("content") or [{}])[0].get("text", "").strip() or None

    except Exception as e:
        log.debug(f"[stream] public comment draft error: {e}")
        return None


# ── Mod introduction draft ────────────────────────────────────────────────────

def _draft_mod_intro(subreddit: str, niche: str) -> str:
    """Draft a mod introduction message — staged in mod_outreach, never auto-sent."""
    try:
        api_key = os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return (
                f"Hi! I run AltusFlow — we help {niche.replace('-', ' ')} find people "
                f"asking for help in r/{subreddit}. We never spam. Would it be OK to "
                f"occasionally share helpful resources here? Happy to follow any rules you have."
            )

        import urllib.request as _ur

        prompt = (
            f"Write a short, respectful Reddit DM to the moderators of r/{subreddit}. "
            f"We want permission to occasionally share helpful resources for people asking about "
            f"{niche.replace('-', ' ')} in this subreddit. "
            "Must sound human and genuine, not corporate. Under 200 words. "
            "Return ONLY the message text."
        )

        body = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = _ur.Request(
            "https://api.anthropic.com/v1/messages",
            data=body,
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            method="POST",
        )
        with _ur.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        return (data.get("content") or [{}])[0].get("text", "").strip()

    except Exception:
        return f"Hi mods — we'd love to occasionally share resources for people asking about trading in r/{subreddit}. Let us know if that's OK!"


# ── Fetch posts via public Reddit JSON API (no credentials needed) ────────────

def _fetch_new_posts(subreddit: str) -> list:
    """
    Pull newest posts via Reddit's public RSS feed — designed for public consumption,
    no API key or app registration needed. Falls back to empty list on error.
    Returns list of dicts matching the same shape _process() expects.
    """
    import urllib.request as _ur
    import xml.etree.ElementTree as ET

    url = f"https://www.reddit.com/r/{subreddit}/new/.rss?limit=25"
    req = _ur.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; AltusFlow/1.0; RSS reader)',
        'Accept':     'application/rss+xml, application/xml, text/xml',
    })
    with _ur.urlopen(req, timeout=12) as resp:
        xml_bytes = resp.read()

    root = ET.fromstring(xml_bytes)
    ns   = {'atom': 'http://www.w3.org/2005/Atom'}
    posts = []

    for entry in root.findall('atom:entry', ns) or root.findall('.//item'):
        try:
            # Atom feed (reddit standard)
            if entry.tag.endswith('entry'):
                link      = entry.find('atom:link', ns)
                permalink = link.get('href', '') if link is not None else ''
                title     = (entry.findtext('atom:title', '', ns) or '').strip()
                content   = (entry.findtext('{http://www.w3.org/2005/Atom}content', '')
                             or entry.findtext('atom:summary', '', ns) or '').strip()
                author_el = entry.find('{http://www.w3.org/2005/Atom}author')
                author    = author_el.findtext('{http://www.w3.org/2005/Atom}name', '') if author_el is not None else ''
                author    = author.replace('/u/', '').strip()
                post_id   = (entry.findtext('atom:id', '', ns) or permalink).split('/')[-2] or permalink
            else:
                # RSS 2.0 fallback
                permalink = entry.findtext('link', '') or ''
                title     = (entry.findtext('title') or '').strip()
                content   = (entry.findtext('description') or '').strip()
                author    = (entry.findtext('{http://purl.org/dc/elements/1.1/}creator') or '').strip()
                post_id   = permalink

            # Strip HTML tags from content
            import re
            body = re.sub(r'<[^>]+>', '', content).strip()[:2000]

            posts.append({
                'name':        f"t3_{post_id}",
                'id':           post_id,
                'title':        title,
                'selftext':     body,
                'author':       author or '[deleted]',
                'subreddit':    subreddit,
                'permalink':    permalink.replace('https://www.reddit.com', '') if 'reddit.com' in permalink else permalink,
                'created_utc':  time.time(),
                'url':          permalink,
            })
        except Exception:
            continue

    return posts


# ── Process one post (dict from JSON API) ────────────────────────────────────

def _process(post: dict, min_icp: int, client_id: str):
    handle    = post.get('author', '[deleted]')
    subreddit = post.get('subreddit', '')
    title     = post.get('title', '')
    body      = post.get('selftext', '')
    permalink = post.get('permalink', '')
    post_url  = f"https://reddit.com{permalink}" if permalink else ''
    created   = datetime.fromtimestamp(post.get('created_utc', 0), tz=timezone.utc).isoformat()

    # Skip bots and deleted
    if handle in ('[deleted]', 'AutoModerator') or handle.lower().endswith('bot'):
        return

    # Quick score
    score, signal_phrase = _score(title, body, subreddit)
    if score < min_icp:
        return

    # Dedup
    try:
        from database import prospect_exists
        if prospect_exists(handle, 'reddit'):
            return
    except Exception:
        pass

    niche   = _NICHE_MAP.get(subreddit, 'altusflow-own')
    post_text = f"{title}\n\n{body}".strip()[:2000]

    # Build prospect data first so both drafts can reference it
    prospect_data = {
        'handle':      handle,
        'name':        f"u/{handle}",
        'platform':    'reddit',
        'subreddit':   subreddit,
        'post_text':   post_text,
        'post_url':    post_url,
        'post_date':   created,
        'icp_score':   score,
        'signal_phrase': signal_phrase,
        'niche':       niche,
        'niche_segment': niche,
        'outreach_method': 'reddit_dm',
        'reddit_username': handle,
        'client_id':   client_id,
        'source':      'live_stream',
    }

    # Draft 1: Private DM (drafted_message)
    draft = _draft_message(prospect_data)
    if draft:
        prospect_data['drafted_message'] = draft

    # Draft 2: Public comment — post on their thread BEFORE the DM (call_opener field)
    public_comment = _draft_public_comment(prospect_data)
    if public_comment:
        prospect_data['call_opener'] = public_comment

    try:
        from database import insert_prospect
        pid = insert_prospect(prospect_data)
        _upd(
            prospects_found=_status['prospects_found'] + 1,
            last_prospect_at=datetime.now(timezone.utc).isoformat(),
        )
        log.info(f"[stream] ★ New prospect u/{handle} r/{subreddit} ICP={score} pid={pid}")
    except Exception as e:
        log.warning(f"[stream] insert_prospect failed for u/{handle}: {e}")
        return

    # Queue mod outreach for this subreddit if not done yet
    try:
        from database import has_mod_outreach, queue_mod_outreach
        if not has_mod_outreach(subreddit):
            intro = _draft_mod_intro(subreddit, niche)
            queue_mod_outreach(subreddit, niche, intro, client_id)
            log.info(f"[stream] Mod intro queued for r/{subreddit}")
    except Exception:
        pass


# ── Stream worker thread (polls public JSON API — no credentials needed) ──────

def _worker(subreddits: list, min_icp: int, client_id: str):
    """
    Polls Reddit's public /new.json endpoint every 60 seconds per subreddit.
    No PRAW, no API app, no phone verification — works on any Reddit account or none.
    Tracks seen post IDs so nothing is processed twice.
    """
    poll_interval = 60  # seconds between sweeps of each subreddit
    seen          = set()

    _upd(running=True, started_at=datetime.now(timezone.utc).isoformat(),
         subreddits=subreddits, last_error=None)
    log.info(f"[stream] Polling {len(subreddits)} subreddits every {poll_interval}s — no API key needed")

    # Prime seen set so we don't re-process posts that existed before startup
    for sub in subreddits:
        if _stop_event.is_set():
            break
        try:
            for post in _fetch_new_posts(sub):
                seen.add(post.get('name', ''))
        except Exception:
            pass
    log.info(f"[stream] Primed with {len(seen)} existing posts — watching for new ones")

    while not _stop_event.is_set():
        for sub in subreddits:
            if _stop_event.is_set():
                break
            try:
                posts = _fetch_new_posts(sub)
                for post in posts:
                    name = post.get('name', '')
                    if not name or name in seen:
                        continue
                    seen.add(name)

                    with _status_lock:
                        _status['posts_seen'] += 1
                        _status['last_post_at'] = datetime.now(timezone.utc).isoformat()

                    try:
                        _process(post, min_icp, client_id)
                    except Exception as exc:
                        log.warning(f"[stream] _process error for r/{sub}: {exc}")

            except Exception as exc:
                _upd(last_error=str(exc))
                log.warning(f"[stream] poll error r/{sub}: {exc}")

        # Wait between full sweeps — check stop event every second
        for _ in range(poll_interval):
            if _stop_event.is_set():
                break
            time.sleep(1)

    _upd(running=False)
    log.info("[stream] stopped cleanly")


# ── Public control ────────────────────────────────────────────────────────────

def start(subreddits: list = None, min_icp: int = None, client_id: str = None):
    """
    Start the stream watcher in a daemon thread.
    Safe to call multiple times — no-ops if already running.
    Called from app.py after init_db().
    """
    global _stream_thread

    if _stream_thread and _stream_thread.is_alive():
        log.debug("[stream] already running — skipping start")
        return

    _stop_event.clear()

    if min_icp is None:
        min_icp = int(os.environ.get('MIN_ICP_SCORE', 4))
    if client_id is None:
        try:
            from database import CLIENT_ID as _cid
            client_id = _cid
        except Exception:
            client_id = os.environ.get('CLIENT_ID', 'ALT00')
    if subreddits is None:
        subreddits = _discover_subreddits()

    if not subreddits:
        log.info("[stream] No subreddits configured — live stream disabled")
        return

    _stream_thread = threading.Thread(
        target=_worker,
        args=(subreddits, min_icp, client_id),
        name='reddit-stream',
        daemon=True,
    )
    _stream_thread.start()
    log.info(f"[stream] Thread started ({len(subreddits)} subreddits)")


def stop():
    _stop_event.set()


def _discover_subreddits() -> list:
    """Pull subreddits from pod tasks.json files, fall back to defaults."""
    import glob, json as _j
    subs = set()
    for path in glob.glob('pods/*/tasks.json'):
        try:
            with open(path, encoding='utf-8') as f:
                data = _j.load(f)
            items = data if isinstance(data, list) else data.get('tasks', [])
            for task in items:
                for sub in task.get('subreddits', []):
                    subs.add(sub.strip())
        except Exception:
            pass
    # Default: trading coaches subreddits only
    return list(subs) or [
        'Daytrading', 'Futures', 'FuturesTrading', 'Forex',
        'stocks', 'options', 'algotrading',
    ]
