"""
scrapers/reddit.py
Scans Reddit for signal posts and sends DMs via the official Reddit API (PRAW).

Cost: Free. Rate limit: 60 requests/minute.

Setup:
  1. Register a script app at reddit.com/prefs/apps
  2. Add to .env:
       REDDIT_CLIENT_ID=your_client_id
       REDDIT_CLIENT_SECRET=your_client_secret
       REDDIT_USERNAME=your_reddit_username      ← required for DM sending
       REDDIT_PASSWORD=your_reddit_password      ← required for DM sending
       REDDIT_USER_AGENT=AltusFlowHunter/1.0

Install:
  pip install praw

Outreach method:
  - When REDDIT_USERNAME + REDDIT_PASSWORD are set: outreach_method = 'reddit_dm'
    DMs are sent directly via PRAW. Reviewer approves, then clicks "Send DM".
  - When only client credentials are set (read-only): outreach_method = 'find_linkedin'
    LinkedIn search URL pre-filled; reviewer reaches out manually.

Reddit rate limits for DMs:
  - Reddit enforces anti-spam limits; new accounts may be shadowbanned if they DM too fast.
  - Keep volume to ≤ 10 DMs/day until the account is established (90+ days old, karma > 100).
"""

import os
import time

REDDIT_CLIENT_ID     = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME      = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD      = os.environ.get("REDDIT_PASSWORD", "")
REDDIT_USER_AGENT    = os.environ.get("REDDIT_USER_AGENT", "AltusFlowHunter/1.0")

# ICP score boosts specific to Reddit signals
UPVOTE_BOOST_THRESHOLD  = 10   # +1 if post score >= this
PROFESSIONAL_SUB_BONUS  = 1    # +1 if subreddit is in a professional list
RECOMMENDATION_BONUS    = 2    # +2 if post explicitly asks for recommendations

PROFESSIONAL_SUBREDDITS = {
    # Financial advisors / RIAs
    'CFP', 'financialplanning', 'personalfinance', 'financialindependence',
    'investing', 'FinancialAdvisors', 'wealthmanagement',
    # Trading coaches
    'Daytrading', 'StockMarket', 'options', 'Forex', 'algotrading', 'trading', 'Bogleheads',
    # Other niches
    'msp', 'sysadmin', 'ITManagers', 'humanresources', 'recruiting', 'jobs',
    'CommercialRealEstate', 'realestateinvesting',
    'Entrepreneur', 'AskEntrepreneurs', 'Business', 'startups', 'smallbusiness',
    'agency', 'freelance',
}

MAX_POSTS_PER_SEARCH = int(os.environ.get("REDDIT_POSTS_PER_SEARCH", "25"))
MAX_HOT_POSTS        = int(os.environ.get("REDDIT_HOT_POSTS", "50"))


def _can_send_dms():
    """True when username+password are configured (required for sending DMs via PRAW)."""
    return bool(REDDIT_USERNAME and REDDIT_PASSWORD)


def get_reddit_client():
    """
    Return an authenticated PRAW Reddit instance, or None if no credentials are set.

    Mode 1 — client + password (preferred, supports DMs):
        Set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD.
    Mode 2 — client credentials only (read-only, no DMs):
        Set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET; leave USERNAME/PASSWORD unset.
    Mode 3 — username/password only (legacy):
        Leave REDDIT_CLIENT_ID empty; set REDDIT_USERNAME + REDDIT_PASSWORD.
        PRAW requires placeholder strings for client_id/client_secret in this mode.
    """
    try:
        import praw
    except ImportError:
        return None

    client_id = REDDIT_CLIENT_ID.strip()

    if client_id and REDDIT_CLIENT_SECRET:
        try:
            if REDDIT_USERNAME and REDDIT_PASSWORD:
                # Mode 1: full auth (supports scanning + DMs)
                return praw.Reddit(
                    client_id=client_id,
                    client_secret=REDDIT_CLIENT_SECRET,
                    username=REDDIT_USERNAME,
                    password=REDDIT_PASSWORD,
                    user_agent=REDDIT_USER_AGENT,
                )
            else:
                # Mode 2: read-only (scanning only)
                return praw.Reddit(
                    client_id=client_id,
                    client_secret=REDDIT_CLIENT_SECRET,
                    user_agent=REDDIT_USER_AGENT,
                )
        except Exception:
            return None
    else:
        # Mode 3: username/password only
        if not REDDIT_USERNAME or not REDDIT_PASSWORD:
            return None
        try:
            return praw.Reddit(
                client_id="placeholder",
                client_secret="placeholder",
                username=REDDIT_USERNAME,
                password=REDDIT_PASSWORD,
                user_agent=REDDIT_USER_AGENT,
            )
        except Exception:
            return None


def send_reddit_dm(username: str, subject: str, body: str) -> dict:
    """
    Send a Reddit DM to a user via PRAW.

    Requires REDDIT_USERNAME + REDDIT_PASSWORD to be set (Mode 1 or 3).
    Returns {"ok": True} on success or {"ok": False, "error": "..."} on failure.

    Callers should gate on _can_send_dms() before calling this.
    """
    if not _can_send_dms():
        return {
            "ok": False,
            "error": "Reddit DM sending requires REDDIT_USERNAME and REDDIT_PASSWORD in .env",
        }

    reddit = get_reddit_client()
    if not reddit:
        return {"ok": False, "error": "Could not authenticate Reddit client"}

    try:
        reddit.redditor(username).message(subject=subject, message=body)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _reddit_icp_boost(submission, subreddit_name, signal_phrases):
    """
    Calculate Reddit-specific ICP score adjustments.
    Returns (boost: int, notes: list[str])
    """
    boost = 0
    notes = []

    score = getattr(submission, 'score', 0) or 0
    if score >= UPVOTE_BOOST_THRESHOLD:
        boost += 1
        notes.append(f"Reddit upvotes: {score} (others validated this pain)")

    if subreddit_name.lower() in {s.lower() for s in PROFESSIONAL_SUBREDDITS}:
        boost += PROFESSIONAL_SUB_BONUS
        notes.append(f"Professional subreddit: r/{subreddit_name}")

    text = (getattr(submission, 'selftext', '') or '') + (submission.title or '')
    text_lower = text.lower()
    rec_phrases = ['recommend', 'recommendation', 'suggestions', 'who do you use', 'what do you use']
    if any(p in text_lower for p in rec_phrases):
        boost += RECOMMENDATION_BONUS
        notes.append("Post explicitly asks for recommendations (+2)")

    return boost, notes


def _post_to_prospect(submission, niche_slug, signal_phrase, matched_phrase=None):
    """Convert a PRAW Submission to a prospect dict."""
    username   = str(submission.author) if submission.author else "deleted"
    post_text  = (submission.title or '') + ('\n\n' + submission.selftext if submission.selftext else '')
    subreddit  = submission.subreddit.display_name

    # Pre-fill LinkedIn search URL for the reviewer
    linkedin_search = (
        f"https://www.linkedin.com/search/results/people/?keywords={username}"
    )

    method = "reddit_dm" if _can_send_dms() else "find_linkedin"

    return {
        "platform":          "reddit",
        "niche":             niche_slug,
        "niche_segment":     niche_slug,
        "handle":            username,
        "reddit_username":   username,
        "name":              username,
        "title":             "",
        "company":           "",
        "profile_url":       f"https://reddit.com/user/{username}",
        "post_text":         post_text.strip(),
        "post_url":          f"https://reddit.com{submission.permalink}",
        "post_date":         str(submission.created_utc),
        "signal_phrase":     matched_phrase or signal_phrase,
        "subreddit":         subreddit,
        "upvote_score":      getattr(submission, 'score', 0) or 0,
        "outreach_method":   method,
        "linkedin_search_url": linkedin_search,
        "group_name":        f"r/{subreddit}",
    }


def _matches_signal(submission, signal_phrases):
    """Return the first matching signal phrase found in title+body, or None."""
    text = (
        (submission.title or '') + ' ' + (submission.selftext or '')
    ).lower()
    for phrase in signal_phrases:
        if phrase.lower() in text:
            return phrase
    return None


def _reddit_request(fn, run_id, context, max_retries=3):
    """
    Call fn() and return its result. On a 429 / RateLimitExceeded, waits
    the time Reddit requests (or 60s fallback) then retries up to max_retries.
    Returns None on permanent failure.
    """
    from error_logger import log_pipeline_error, WARNING
    for attempt in range(max_retries):
        try:
            return fn()
        except Exception as e:
            err_str = str(e).lower()
            is_rate_limit = (
                '429' in err_str
                or 'ratelimit' in err_str
                or 'rate limit' in err_str
                or 'too many requests' in err_str
            )
            if is_rate_limit:
                # Try to honour Reddit's Retry-After header value
                wait = 60
                try:
                    import re as _re
                    m = _re.search(r'(\d+)\s*second', err_str)
                    if m:
                        wait = int(m.group(1)) + 5
                except Exception:
                    pass
                log_pipeline_error(
                    run_id, "reddit_scraper",
                    f"429 rate limit on {context} — waiting {wait}s then retrying (attempt {attempt + 1}/{max_retries}).",
                    WARNING,
                )
                time.sleep(wait)
            else:
                log_pipeline_error(run_id, "reddit_scraper", f"Error on {context}: {type(e).__name__}: {e}", WARNING)
                return None
    return None


def scan_subreddit(reddit, subreddit_name, signal_phrases, niche_slug, run_id=None):
    """
    Scan one subreddit:
      1. Search for each signal phrase
      2. Also check hot + new posts and filter for signal phrases

    Returns list of prospect dicts (before dedup).
    """
    from error_logger import log_pipeline_error, WARNING

    results = []
    seen_ids = set()

    try:
        sub = reddit.subreddit(subreddit_name)

        # ── Signal phrase search ──────────────────────────────────────────────
        for phrase in signal_phrases:
            def _do_search(p=phrase):
                return list(sub.search(p, limit=MAX_POSTS_PER_SEARCH, sort="new"))

            posts = _reddit_request(_do_search, run_id, f"r/{subreddit_name} search '{phrase}'")
            if posts:
                for post in posts:
                    if post.id in seen_ids:
                        continue
                    seen_ids.add(post.id)
                    matched = _matches_signal(post, signal_phrases)
                    if not matched:
                        continue
                    p = _post_to_prospect(post, niche_slug, phrase, matched)
                    boost, boost_notes = _reddit_icp_boost(post, subreddit_name, signal_phrases)
                    p['_reddit_icp_boost'] = boost
                    p['_reddit_boost_notes'] = boost_notes
                    results.append(p)
            time.sleep(5)  # 5s between phrase searches

        # ── Hot + New posts filtered for signal phrases ───────────────────────
        for feed_name in ('hot', 'new'):
            def _do_feed(fn=feed_name):
                feed = sub.hot(limit=MAX_HOT_POSTS) if fn == 'hot' else sub.new(limit=MAX_HOT_POSTS)
                return list(feed)

            posts = _reddit_request(_do_feed, run_id, f"r/{subreddit_name} {feed_name}")
            if posts:
                for post in posts:
                    if post.id in seen_ids:
                        continue
                    matched = _matches_signal(post, signal_phrases)
                    if not matched:
                        continue
                    seen_ids.add(post.id)
                    p = _post_to_prospect(post, niche_slug, matched, matched)
                    boost, boost_notes = _reddit_icp_boost(post, subreddit_name, signal_phrases)
                    p['_reddit_icp_boost'] = boost
                    p['_reddit_boost_notes'] = boost_notes
                    results.append(p)
            time.sleep(5)  # 5s between hot/new feed requests

    except Exception as e:
        log_pipeline_error(
            run_id, "reddit_scraper",
            f"Failed to access r/{subreddit_name}: {type(e).__name__}: {e}",
            WARNING,
            suggested_fix=(
                "Subreddit may be private or banned. "
                "Remove it from the niche library or check reddit.com/r/{subreddit_name}."
            ),
        )

    print(f"[Reddit] [{niche_slug}] r/{subreddit_name}: {len(results)} signal posts")
    return results


def run_niche_search(niche_slug, run_id=None):
    """
    Scan all subreddits for a single niche.
    Returns combined unique results.
    """
    from scrapers.niches import get_reddit_subreddits, get_signal_phrases
    from error_logger import log_pipeline_error, CRITICAL

    reddit = get_reddit_client()
    if not reddit:
        log_pipeline_error(
            run_id, "reddit_scraper",
            "Reddit credentials not configured — scraper skipped.",
            CRITICAL,
            suggested_fix=(
                "Mode 1 (preferred): set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in .env "
                "(register a script app at reddit.com/prefs/apps). "
                "Mode 2 (fallback): leave REDDIT_CLIENT_ID empty and set "
                "REDDIT_USERNAME + REDDIT_PASSWORD instead."
            ),
        )
        return []

    subreddits     = get_reddit_subreddits(niche_slug)
    signal_phrases = get_signal_phrases(niche_slug)
    all_results    = []
    seen_handles   = set()

    if not subreddits:
        print(f"[Reddit] [{niche_slug}] No subreddits configured — skipping.")
        return []

    print(f"\n[Reddit] [{niche_slug}] Scanning {len(subreddits)} subreddits...")

    for i, subreddit in enumerate(subreddits):
        posts = scan_subreddit(reddit, subreddit, signal_phrases, niche_slug, run_id=run_id)
        for p in posts:
            key = (p["handle"], p["post_url"])
            if key not in seen_handles:
                seen_handles.add(key)
                all_results.append(p)
        if i < len(subreddits) - 1:
            time.sleep(8)  # 8s between subreddits to avoid rate limits

    print(f"[Reddit] [{niche_slug}] Total unique: {len(all_results)}")
    return all_results


def run_all_searches(run_id=None, niche_slugs=None):
    """
    Scan all niches (or a subset) across their subreddits.
    Returns combined unique results.
    """
    from scrapers.niches import ALL_NICHES
    from error_logger import log_pipeline_error, log_zero_results_alert, CRITICAL

    reddit = get_reddit_client()
    if not reddit:
        log_pipeline_error(
            run_id, "reddit_scraper",
            "Reddit credentials not configured — all Reddit scanning skipped.",
            CRITICAL,
            suggested_fix=(
                "Mode 1 (preferred): set REDDIT_CLIENT_ID + REDDIT_CLIENT_SECRET in .env "
                "(register a script app at reddit.com/prefs/apps). "
                "Mode 2 (fallback): leave REDDIT_CLIENT_ID empty and set "
                "REDDIT_USERNAME + REDDIT_PASSWORD instead."
            ),
        )
        return []

    niches = ALL_NICHES if not niche_slugs else [
        n for n in ALL_NICHES if n.NICHE_SLUG in niche_slugs
    ]
    all_results  = []
    seen_handles = set()

    for niche in niches:
        results = run_niche_search(niche.NICHE_SLUG, run_id=run_id)
        for r in results:
            key = (r["handle"], r["post_url"])
            if key not in seen_handles:
                seen_handles.add(key)
                all_results.append(r)

    print(f"\n[Reddit] Total unique prospects across all niches: {len(all_results)}")

    if not all_results and (REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET):
        log_zero_results_alert(run_id, "Reddit")

    return all_results


if __name__ == "__main__":
    results = run_niche_search("altusflow-own")
    for r in results[:3]:
        print(f"\nu/{r['handle']} | r/{r['subreddit']} | upvotes: {r['upvote_score']}")
        print(f"Post: {r['post_text'][:120]}...")
        print(f"LinkedIn: {r['linkedin_search_url']}")
