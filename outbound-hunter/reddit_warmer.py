"""
reddit_warmer.py — Keep Reddit accounts warm with genuine daily comments.

Strategy:
  - Once per day, pick a recent post in the target subreddit that asks a question
    or describes a problem the account can genuinely help with.
  - Generate a helpful, non-promotional comment via Claude.
  - Send to Telegram for approval before posting.
  - Never comment more than once per day per subreddit to avoid pattern detection.

This keeps the account looking human: active commenter, not just a broadcaster.
"""

import json
import logging
import os
import urllib.request
from datetime import datetime, timezone

log = logging.getLogger(__name__)

# Subreddits to rotate through (one comment per day total, not per sub)
_TARGET_SUBS = ['Daytrading', 'Futures', 'swingtrading', 'options', 'Scalping']

_COMMENT_PROMPT = """You are a helpful, experienced trader commenting on Reddit.

Post in r/{subreddit}:
TITLE: {title}
BODY: {body}

Write a SHORT, genuine, helpful comment (2-4 sentences max).
Rules:
- Add real value — answer the question, share a relevant observation, or validate their experience
- Sound like a fellow trader, not a coach or marketer
- NEVER mention any service, tool, or company
- NEVER use bullet points or headers
- NEVER be promotional in any way
- If the post has no clear question, respond with a relatable observation
- No em-dashes, no "delve", no AI-sounding phrases

Comment text only — no preamble, no quotes around it."""


def _fetch_candidate_posts(subreddit: str, limit: int = 25) -> list[dict]:
    """Fetch recent posts from a subreddit, return ones worth commenting on."""
    url = f'https://www.reddit.com/r/{subreddit}/new.json?limit={limit}'
    req = urllib.request.Request(url, headers={'User-Agent': 'AltusFlow/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        posts = []
        for item in data.get('data', {}).get('children', []):
            p = item.get('data', {})
            # Only comment on text posts with some engagement but not viral
            if (p.get('is_self')
                    and 1 <= p.get('score', 0) <= 500
                    and p.get('num_comments', 0) < 50
                    and not p.get('locked')
                    and not p.get('stickied')
                    and len(p.get('selftext', '')) > 30):
                posts.append({
                    'id':        p['id'],
                    'title':     p.get('title', ''),
                    'body':      p.get('selftext', '')[:800],
                    'url':       'https://www.reddit.com' + p.get('permalink', ''),
                    'score':     p.get('score', 0),
                    'comments':  p.get('num_comments', 0),
                    'subreddit': subreddit,
                })
        return posts
    except Exception as e:
        log.warning('reddit_warmer: fetch_candidate_posts error: %s', e)
        return []


def _already_commented(post_id: str) -> bool:
    """Check DB to avoid double-commenting on the same post."""
    try:
        from database import _reader
        from sqlalchemy import text
        with _reader() as conn:
            row = conn.execute(text(
                "SELECT 1 FROM warmup_comments WHERE post_id=:pid LIMIT 1"
            ), {"pid": post_id}).fetchone()
        return row is not None
    except Exception:
        return False


def _save_warmup_comment(post_id: str, subreddit: str, comment_text: str,
                          post_url: str, status: str = 'pending'):
    """Record warmup comment in DB."""
    try:
        from database import _writer
        from sqlalchemy import text
        with _writer() as conn:
            conn.execute(text("""
                INSERT OR IGNORE INTO warmup_comments
                (post_id, subreddit, comment_text, post_url, status, created_at)
                VALUES (:pid, :sub, :ct, :url, :status, datetime('now'))
            """), {"pid": post_id, "sub": subreddit, "ct": comment_text,
                   "url": post_url, "status": status})
    except Exception as e:
        log.warning('reddit_warmer: save error: %s', e)


def _update_warmup_status(post_id: str, status: str):
    try:
        from database import _writer
        from sqlalchemy import text
        with _writer() as conn:
            conn.execute(text(
                "UPDATE warmup_comments SET status=:s WHERE post_id=:pid"
            ), {"s": status, "pid": post_id})
    except Exception as e:
        log.warning('reddit_warmer: update status error: %s', e)


def _generate_comment(subreddit: str, title: str, body: str) -> str | None:
    """Use Claude Haiku to write the comment."""
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None
    prompt = _COMMENT_PROMPT.format(subreddit=subreddit, title=title[:200], body=body[:600])
    payload = json.dumps({
        'model':      'claude-haiku-4-5-20251001',
        'max_tokens': 150,
        'system':     'You write brief, genuine Reddit comments. Return the comment text only.',
        'messages':   [{'role': 'user', 'content': prompt}],
    }).encode()
    try:
        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data    = payload,
            headers = {
                'x-api-key':         api_key,
                'anthropic-version': '2023-06-01',
                'content-type':      'application/json',
            },
            method  = 'POST',
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read())
        return raw['content'][0]['text'].strip()
    except Exception as e:
        log.warning('reddit_warmer: comment gen error: %s', e)
        return None




def post_warmup_comment(post_id: str) -> dict:
    """
    Called by Telegram approver when user taps [✅ Post Comment].
    Fetches comment text from DB and posts it to Reddit.
    """
    try:
        from database import _reader
        from sqlalchemy import text as _t
        with _reader() as conn:
            row = conn.execute(_t(
                'SELECT subreddit, comment_text, post_url FROM warmup_comments WHERE post_id=:pid'
            ), {'pid': post_id}).fetchone()
        if not row:
            return {'ok': False, 'error': 'Warmup comment not found'}
        subreddit, comment_text, post_url = row[0], row[1], row[2]
    except Exception as e:
        return {'ok': False, 'error': str(e)}

    # Extract post fullname from URL
    parts = [p for p in post_url.split('/') if p]
    raw_post_id = None
    for i, p in enumerate(parts):
        if p == 'comments' and i + 1 < len(parts):
            raw_post_id = parts[i + 1]
    if not raw_post_id:
        return {'ok': False, 'error': 'Could not parse post ID from URL'}

    from social_poster import _reddit_access_token
    import urllib.parse
    token = _reddit_access_token()
    if not token:
        return {'ok': False, 'error': 'Reddit auth failed'}

    req = urllib.request.Request(
        'https://oauth.reddit.com/api/comment',
        data    = urllib.parse.urlencode({
            'thing_id': f't3_{raw_post_id}',
            'text':     comment_text,
        }).encode(),
        headers = {
            'Authorization': f'Bearer {token}',
            'User-Agent':    'AltusFlow/1.0',
            'Content-Type':  'application/x-www-form-urlencoded',
        },
        method  = 'POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
        errors = result.get('json', {}).get('errors', [])
        if errors:
            _update_warmup_status(post_id, 'failed')
            return {'ok': False, 'error': str(errors)}
        _update_warmup_status(post_id, 'posted')
        return {'ok': True}
    except Exception as e:
        _update_warmup_status(post_id, 'failed')
        return {'ok': False, 'error': str(e)}


def run_daily_warmup() -> bool:
    """
    Pick one good post across target subreddits, generate a comment, send to Telegram.
    Returns True if a comment was queued.
    Called by scheduler once per day.
    """
    import random
    import time as _time

    random.shuffle(_TARGET_SUBS)

    for subreddit in _TARGET_SUBS:
        posts = _fetch_candidate_posts(subreddit)
        random.shuffle(posts)

        for post in posts[:10]:
            pid = post['id']
            if _already_commented(pid):
                continue

            comment = _generate_comment(subreddit, post['title'], post['body'])
            if not comment:
                continue

            _save_warmup_comment(pid, subreddit, comment, post['url'], 'pending')
            log.info('reddit_warmer: queued comment on %s in r/%s', pid, subreddit)
            return True

        _time.sleep(1)  # be polite between subreddit fetches

    log.info('reddit_warmer: no suitable posts found today')
    return False
