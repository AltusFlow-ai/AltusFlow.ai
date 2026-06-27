"""
Track Reddit post performance at 24h and 48h after posting.
Called by scheduler every 6 hours.
Fetches upvotes + comments via Reddit public JSON API.
"""
import json, logging, urllib.request
from datetime import datetime, timezone, timedelta

import database as db

log = logging.getLogger(__name__)


def _reddit_post_stats(post_url: str) -> dict | None:
    """
    Fetch current upvote + comment counts for a Reddit post URL.
    Returns {"upvotes": int, "comments": int} or None on failure.
    """
    if not post_url or "reddit.com" not in post_url:
        return None
    # Append .json to get machine-readable data
    url = post_url.rstrip("/") + ".json?limit=1"
    req = urllib.request.Request(url, headers={"User-Agent": "AltusFlow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        post = data[0]["data"]["children"][0]["data"]
        return {
            "upvotes":  post.get("score", 0),
            "comments": post.get("num_comments", 0),
        }
    except Exception as e:
        log.warning("perf_tracker: failed to fetch %s: %s", post_url, e)
        return None


def _x_post_stats(post_url: str) -> dict | None:
    """
    X (Twitter) public engagement counts are gated behind API v2 Basic tier.
    Return None gracefully — env vars gate this at call site.
    """
    import os
    bearer = os.environ.get("X_BEARER_TOKEN", "")
    if not bearer or not post_url:
        return None
    # Extract tweet ID from URL
    parts = post_url.rstrip("/").split("/")
    tweet_id = parts[-1] if parts else None
    if not tweet_id or not tweet_id.isdigit():
        return None
    url = f"https://api.twitter.com/2/tweets/{tweet_id}?tweet.fields=public_metrics"
    req = urllib.request.Request(
        url, headers={"Authorization": f"Bearer {bearer}"}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read())
        m = data.get("data", {}).get("public_metrics", {})
        return {
            "upvotes":  m.get("like_count", 0),
            "comments": m.get("reply_count", 0),
        }
    except Exception as e:
        log.warning("perf_tracker: X fetch failed %s: %s", post_url, e)
        return None


def run_performance_check(client_id: str = None) -> int:
    """
    Called by scheduler. Returns number of posts updated.
    Checks all posted posts that haven't been fully checked yet (perf_checked < 2).
    """
    posts = db.get_posted_value_posts(client_id)
    updated = 0
    now = datetime.now(timezone.utc)

    for p in posts:
        post_url   = p.get("post_url", "")
        posted_at  = p.get("posted_at", "")
        post_id    = p.get("id")
        perf_done  = int(p.get("perf_checked") or 0)
        platform   = (p.get("platform") or "reddit").lower()

        if perf_done >= 2 or not posted_at:
            continue

        try:
            pt = datetime.fromisoformat(posted_at.replace("Z", "+00:00"))
            if pt.tzinfo is None:
                pt = pt.replace(tzinfo=timezone.utc)
        except Exception:
            continue

        age_hours = (now - pt).total_seconds() / 3600
        # Only check if at least 20 min old (Reddit vote fuzzing settles)
        if age_hours < 0.33:
            continue

        stats = None
        if "reddit.com" in (post_url or ""):
            stats = _reddit_post_stats(post_url)
        elif "twitter.com" in (post_url or "") or "x.com" in (post_url or ""):
            stats = _x_post_stats(post_url)

        if stats:
            new_perf = min(perf_done + 1, 2) if age_hours >= 24 else perf_done
            db.update_value_post(
                post_id,
                upvotes=stats["upvotes"],
                comments=stats["comments"],
                perf_checked=new_perf,
            )
            updated += 1
            log.info(
                "perf_tracker: post %d → %d upvotes, %d comments",
                post_id, stats["upvotes"], stats["comments"],
            )

    return updated
