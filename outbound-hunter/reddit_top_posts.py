"""
reddit_top_posts.py — Pull top-performing posts from Reddit subreddits.

Uses Reddit's public JSON API (no API key needed for public subreddits).
Stores title, body, score, and comment count so the content engine can
match the format and topics that actually get engagement in each community.
"""

import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_UA = "AltusFlow/1.0 content-intelligence (+https://altusflow.ai)"

_DEFAULT_SUBS = {
    "daytrading":    ["Daytrading", "Scalping"],
    "futures":       ["Futures", "FuturesTrading"],
    "swing-trading": ["swingtrading", "StockMarket"],
    "crypto":        ["CryptoCurrency", "CryptoMarkets"],
    "options":       ["options", "thetagang"],
}


def fetch_top_posts(subreddit: str, period: str = "week", limit: int = 25) -> list[dict]:
    """
    Fetch top text posts from a public subreddit.
    period: 'day' | 'week' | 'month' | 'year' | 'all'
    Returns only self (text) posts — no link/image posts.
    """
    url = (
        f"https://www.reddit.com/r/{subreddit}/top.json"
        f"?t={period}&limit={limit}&raw_json=1"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())

        results = []
        for child in data.get("data", {}).get("children", []):
            p = child.get("data", {})
            # Text posts only — image/link posts don't tell us what content resonates
            if not p.get("is_self") or not p.get("selftext", "").strip():
                continue
            if p.get("selftext") in ("[deleted]", "[removed]"):
                continue
            results.append({
                "post_id":       p.get("id", ""),
                "subreddit":     p.get("subreddit", subreddit),
                "title":         p.get("title", ""),
                "body":          p.get("selftext", "")[:3000],
                "score":         int(p.get("score", 0)),
                "upvote_ratio":  float(p.get("upvote_ratio", 0)),
                "comment_count": int(p.get("num_comments", 0)),
                "post_url":      "https://reddit.com" + p.get("permalink", ""),
                "created_utc":   int(p.get("created_utc", 0)),
            })
        return results

    except urllib.error.HTTPError as e:
        log.warning(f"[top_posts] HTTP {e.code} fetching r/{subreddit}: {e.reason}")
        return []
    except Exception as e:
        log.warning(f"[top_posts] fetch error for r/{subreddit}: {e}")
        return []


def refresh_subreddit(subreddit: str, period: str = "week", client_id: str = None) -> int:
    """Fetch top posts and upsert them into the DB. Returns count saved."""
    posts = fetch_top_posts(subreddit, period=period)
    if not posts:
        return 0

    from database import save_top_post
    saved = 0
    now = datetime.now(timezone.utc).isoformat()
    for p in posts:
        try:
            save_top_post(
                client_id     = client_id,
                subreddit     = p["subreddit"],
                post_id       = p["post_id"],
                title         = p["title"],
                body          = p["body"],
                score         = p["score"],
                upvote_ratio  = p["upvote_ratio"],
                comment_count = p["comment_count"],
                post_url      = p["post_url"],
                time_period   = period,
                fetched_at    = now,
            )
            saved += 1
        except Exception as e:
            log.warning(f"[top_posts] save error for {p.get('post_id')}: {e}")

    log.info(f"[top_posts] {saved}/{len(posts)} saved from r/{subreddit} ({period})")
    return saved


def refresh_niche(niche_slug: str, period: str = "week", client_id: str = None) -> dict:
    """Refresh all subreddits for a niche. Returns {subreddit: count}."""
    subs = _DEFAULT_SUBS.get(niche_slug, [])
    results = {}
    for sub in subs:
        results[sub] = refresh_subreddit(sub, period=period, client_id=client_id)
    return results


def get_top_post_context(subreddit: str, client_id: str = None, limit: int = 5) -> str:
    """
    Return a formatted string of top posts for injection into generation prompts.
    Tells Claude what format and topics are winning in this community right now.
    """
    from database import get_top_posts
    posts = get_top_posts(subreddit=subreddit, client_id=client_id, limit=limit)
    if not posts:
        return ""

    lines = [
        f"Top-performing posts in r/{subreddit} this week — use these as FORMAT and TOPIC signals only, do NOT copy them:",
    ]
    for p in posts:
        eng = f"↑{p['score']} | {p['comment_count']} comments"
        lines.append(f'  [{eng}] "{p["title"]}"')

    return "\n".join(lines)
