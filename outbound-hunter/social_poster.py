"""
social_poster.py — Post approved content to Reddit and X.

Reddit: OAuth2 password flow (no browser required).
X:      OAuth 1.0a via Twitter API v2 (free basic tier).

Required env vars:
  Reddit: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
  X:      X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET
"""

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

log = logging.getLogger(__name__)


_KARMA_MIN   = 100   # minimum combined karma before posting
_AGE_MIN     = 30    # minimum account age in days before posting


def check_reddit_account_health() -> dict:
    """
    Check karma + account age for the configured Reddit account.
    Returns:
      { ok, username, karma, age_days, warnings: list[str], blocked: bool }
    blocked=True means the account is too new/low-karma to post safely.
    """
    username = os.environ.get('REDDIT_USERNAME', '')
    if not username:
        return {'ok': False, 'blocked': True, 'warnings': ['REDDIT_USERNAME not set'], 'karma': 0, 'age_days': 0}

    url = f'https://www.reddit.com/user/{username}/about.json'
    req = urllib.request.Request(url, headers={'User-Agent': 'AltusFlow/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        d = data.get('data', {})
        karma    = (d.get('comment_karma') or 0) + (d.get('link_karma') or 0)
        created  = d.get('created_utc', 0)
        age_days = int((time.time() - created) / 86400) if created else 0
        is_suspended = d.get('is_suspended', False)

        warnings = []
        if is_suspended:
            warnings.append('Account is suspended')
        if karma < _KARMA_MIN:
            warnings.append(f'Low karma: {karma} (min {_KARMA_MIN} recommended)')
        if age_days < _AGE_MIN:
            warnings.append(f'Account too new: {age_days} days old (min {_AGE_MIN} recommended)')

        blocked = is_suspended or (karma < _KARMA_MIN and age_days < _AGE_MIN)
        return {
            'ok':        not is_suspended,
            'username':  username,
            'karma':     karma,
            'age_days':  age_days,
            'warnings':  warnings,
            'blocked':   blocked,
        }
    except Exception as e:
        log.warning(f'[poster] account health check error: {e}')
        return {'ok': True, 'blocked': False, 'warnings': [f'Could not check: {e}'], 'karma': 0, 'age_days': 0}


def _reddit_access_token() -> str | None:
    client_id     = os.environ.get('REDDIT_CLIENT_ID', '')
    client_secret = os.environ.get('REDDIT_CLIENT_SECRET', '')
    username      = os.environ.get('REDDIT_USERNAME', '')
    password      = os.environ.get('REDDIT_PASSWORD', '')

    if not all([client_id, client_secret, username, password]):
        return None

    creds = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    req   = urllib.request.Request(
        'https://www.reddit.com/api/v1/access_token',
        data    = urllib.parse.urlencode({
            'grant_type': 'password',
            'username':   username,
            'password':   password,
        }).encode(),
        headers = {
            'Authorization': f'Basic {creds}',
            'User-Agent':    'AltusFlow/1.0 (content automation)',
        },
        method  = 'POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        return data.get('access_token')
    except Exception as e:
        log.warning(f"[poster] Reddit auth error: {e}")
        return None


def post_to_reddit(title: str, body: str, subreddit: str) -> dict:
    """
    Submit a self (text) post to a subreddit.
    Returns { ok, url, post_id } or { ok: False, error }.
    """
    token = _reddit_access_token()
    if not token:
        return {'ok': False, 'error': 'Reddit credentials missing or auth failed'}

    req = urllib.request.Request(
        'https://oauth.reddit.com/api/submit',
        data    = urllib.parse.urlencode({
            'kind':     'self',
            'sr':       subreddit,
            'title':    title[:300],
            'text':     body,
            'resubmit': True,
            'nsfw':     False,
        }).encode(),
        headers = {
            'Authorization': f'Bearer {token}',
            'User-Agent':    'AltusFlow/1.0 (content automation)',
            'Content-Type':  'application/x-www-form-urlencoded',
        },
        method  = 'POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            result = json.loads(r.read())

        json_data = result.get('json', {})
        errors    = json_data.get('errors', [])
        if errors:
            return {'ok': False, 'error': str(errors)}

        data = json_data.get('data', {})
        url  = data.get('url', '')
        return {'ok': True, 'url': url, 'post_id': data.get('id', '')}

    except urllib.error.HTTPError as e:
        err = e.read().decode(errors='replace')
        return {'ok': False, 'error': f'Reddit HTTP {e.code}: {err[:200]}'}
    except Exception as e:
        return {'ok': False, 'error': f'Reddit error: {e}'}


def _x_oauth_header(method: str, url: str, api_key: str, api_secret: str,
                    access_token: str, access_secret: str) -> str:
    ts    = str(int(time.time()))
    nonce = secrets.token_hex(16)
    oauth = {
        'oauth_consumer_key':     api_key,
        'oauth_nonce':            nonce,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp':        ts,
        'oauth_token':            access_token,
        'oauth_version':          '1.0',
    }
    sorted_params = '&'.join(
        f"{urllib.parse.quote(k, '')}={urllib.parse.quote(str(v), '')}"
        for k, v in sorted(oauth.items())
    )
    base = f"{method}&{urllib.parse.quote(url, '')}&{urllib.parse.quote(sorted_params, '')}"
    key  = f"{urllib.parse.quote(api_secret, '')}&{urllib.parse.quote(access_secret, '')}"
    sig  = base64.b64encode(hmac.new(key.encode(), base.encode(), hashlib.sha1).digest()).decode()
    oauth['oauth_signature'] = sig
    return 'OAuth ' + ', '.join(
        f'{k}="{urllib.parse.quote(str(v), "")}"' for k, v in sorted(oauth.items())
    )


def _post_single_tweet(text: str, reply_to_id: str = None,
                       api_key: str = '', api_secret: str = '',
                       access_token: str = '', access_secret: str = '') -> dict:
    url     = 'https://api.twitter.com/2/tweets'
    payload = {'text': text[:280]}
    if reply_to_id:
        payload['reply'] = {'in_reply_to_tweet_id': reply_to_id}

    body   = json.dumps(payload).encode()
    header = _x_oauth_header('POST', url, api_key, api_secret, access_token, access_secret)
    req    = urllib.request.Request(url, data=body, headers={
        'Authorization': header,
        'Content-Type':  'application/json',
    }, method='POST')

    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def post_to_x(tweets: list) -> dict:
    """
    Post a thread of tweets to X. First tweet is standalone, rest reply in chain.
    Returns { ok, url, thread_id } or { ok: False, error }.
    """
    api_key       = os.environ.get('X_API_KEY', '')
    api_secret    = os.environ.get('X_API_SECRET', '')
    access_token  = os.environ.get('X_ACCESS_TOKEN', '')
    access_secret = os.environ.get('X_ACCESS_SECRET', '')

    if not all([api_key, api_secret, access_token, access_secret]):
        return {'ok': False, 'error': 'X credentials missing'}

    creds = dict(api_key=api_key, api_secret=api_secret,
                 access_token=access_token, access_secret=access_secret)

    try:
        first_id = None
        for i, tweet in enumerate(tweets):
            if not tweet.strip():
                continue
            result   = _post_single_tweet(tweet.strip(), reply_to_id=first_id if i > 0 else None, **creds)
            tweet_id = result.get('data', {}).get('id')
            if i == 0:
                first_id = tweet_id
            time.sleep(1)  # rate-limit buffer between tweets in thread

        thread_url = f"https://x.com/i/web/status/{first_id}" if first_id else ''
        return {'ok': True, 'url': thread_url, 'thread_id': first_id}

    except urllib.error.HTTPError as e:
        err = e.read().decode(errors='replace')
        return {'ok': False, 'error': f'X HTTP {e.code}: {err[:200]}'}
    except Exception as e:
        return {'ok': False, 'error': f'X error: {e}'}


def post_reddit_reply(comment_url: str, reply_text: str) -> dict:
    """
    Reply to a specific Reddit comment. comment_url is the full permalink URL.
    Returns { ok, url } or { ok: False, error }.
    """
    if not comment_url or not reply_text:
        return {'ok': False, 'error': 'Missing comment_url or reply_text'}

    token = _reddit_access_token()
    if not token:
        return {'ok': False, 'error': 'Reddit credentials missing or auth failed'}

    # Extract comment fullname from URL — format: /r/sub/comments/postid/title/commentid/
    parts = [p for p in comment_url.split('/') if p]
    comment_id = None
    for i, p in enumerate(parts):
        if p == 'comments' and i + 3 < len(parts):
            comment_id = parts[i + 3]
    if not comment_id:
        return {'ok': False, 'error': 'Could not parse comment ID from URL'}

    fullname = f"t1_{comment_id}"
    req = urllib.request.Request(
        'https://oauth.reddit.com/api/comment',
        data    = urllib.parse.urlencode({
            'thing_id': fullname,
            'text':     reply_text,
        }).encode(),
        headers = {
            'Authorization': f'Bearer {token}',
            'User-Agent':    'AltusFlow/1.0 (content automation)',
            'Content-Type':  'application/x-www-form-urlencoded',
        },
        method  = 'POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            result = json.loads(r.read())
        errors = result.get('json', {}).get('errors', [])
        if errors:
            return {'ok': False, 'error': str(errors)}
        data   = result.get('json', {}).get('data', {}).get('things', [{}])[0].get('data', {})
        url    = f"https://www.reddit.com{data.get('permalink', '')}" if data.get('permalink') else ''
        return {'ok': True, 'url': url}
    except Exception as e:
        return {'ok': False, 'error': f'Reddit reply error: {e}'}


def post_content(post_data: dict) -> dict:
    """
    Route to the correct platform and post.
    post_data keys: platform, title, body, subreddit, tweets (for X)
    """
    platform = (post_data.get('platform') or 'reddit').lower()

    if platform == 'x':
        tweets = post_data.get('tweets') or []
        if not tweets and post_data.get('body'):
            tweets = [t.strip() for t in post_data['body'].split('\n\n') if t.strip()]
        return post_to_x(tweets)
    else:
        return post_to_reddit(
            title     = post_data.get('title', ''),
            body      = post_data.get('body', ''),
            subreddit = post_data.get('subreddit', 'Daytrading'),
        )
