"""
scrapers/reddit.py
Scans Reddit for signal posts using Reddit's public JSON API.

No API key or app registration required — uses publicly accessible
JSON endpoints that Reddit exposes for every subreddit and search.

Rate limit: 2 seconds between requests (unauthenticated limit).
Set REDDIT_USER_AGENT in env to identify your bot (required by Reddit ToS).

DM sending: still requires PRAW + full credentials. Without them,
outreach_method falls back to 'find_linkedin' so reviewers reach
prospects manually. Scanning works with zero credentials.
"""

import os
import time

import requests

# ── Env vars ───────────────────────────────────────────────────────────────────
REDDIT_USER_AGENT    = os.environ.get(
    "REDDIT_USER_AGENT",
    "AltusFlowHunter/1.0 (outbound lead research tool)",
)
REDDIT_CLIENT_ID     = os.environ.get("REDDIT_CLIENT_ID", "")
REDDIT_CLIENT_SECRET = os.environ.get("REDDIT_CLIENT_SECRET", "")
REDDIT_USERNAME      = os.environ.get("REDDIT_USERNAME", "")
REDDIT_PASSWORD      = os.environ.get("REDDIT_PASSWORD", "")

# ── ICP boost constants (unchanged) ───────────────────────────────────────────
UPVOTE_BOOST_THRESHOLD = 10
PROFESSIONAL_SUB_BONUS = 1
RECOMMENDATION_BONUS   = 2

PROFESSIONAL_SUBREDDITS = {
    'CFP', 'financialplanning', 'personalfinance', 'financialindependence',
    'investing', 'FinancialAdvisors', 'wealthmanagement',
    'Daytrading', 'StockMarket', 'options', 'Forex', 'algotrading', 'trading', 'Bogleheads',
    'msp', 'sysadmin', 'ITManagers', 'humanresources', 'recruiting', 'jobs',
    'CommercialRealEstate', 'realestateinvesting',
    'Entrepreneur', 'AskEntrepreneurs', 'Business', 'startups', 'smallbusiness',
    'agency', 'freelance',
}

MAX_POSTS_PER_SEARCH = int(os.environ.get("REDDIT_POSTS_PER_SEARCH", "25"))
_RATE_FLOOR = 2.0  # seconds between requests

# ── Error logger (optional dep — fails gracefully if missing) ──────────────────
try:
    from error_logger import log_pipeline_error, WARNING, CRITICAL
    _log_error = log_pipeline_error
    _WARN = WARNING
    _CRIT = CRITICAL
except Exception:
    def _log_error(run_id, source, msg, sev=None, **kw):
        print(f"[{source}] {msg}")
    _WARN = "warning"
    _CRIT = "critical"


# ── HTTP session ───────────────────────────────────────────────────────────────

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": REDDIT_USER_AGENT})
    return s


# ── DM sending (optional — requires PRAW + full credentials) ──────────────────

def _can_send_dms() -> bool:
    return bool(
        REDDIT_USERNAME and REDDIT_PASSWORD
        and REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET
    )


def send_reddit_dm(username: str, subject: str, body: str) -> dict:
    """
    Send a Reddit DM via PRAW. Requires full credentials in env.
    Falls back gracefully when credentials aren't set.
    """
    if not _can_send_dms():
        return {
            "ok": False,
            "error": (
                "Reddit DM sending requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, "
                "REDDIT_USERNAME, and REDDIT_PASSWORD in env."
            ),
        }
    try:
        import praw
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_CLIENT_SECRET,
            username=REDDIT_USERNAME,
            password=REDDIT_PASSWORD,
            user_agent=REDDIT_USER_AGENT,
        )
        reddit.redditor(username).message(subject=subject, message=body)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ── Legacy compatibility stub ──────────────────────────────────────────────────

def get_reddit_client():
    """
    Kept for backward compatibility with code that checks 'if not reddit'.
    Scanning no longer requires a PRAW client — returns a truthy sentinel.
    """
    return _session()


# ── JSON API helpers ───────────────────────────────────────────────────────────

def _json_get(session: requests.Session, url: str, params: dict = None,
              run_id=None, context: str = "") -> dict | None:
    """
    GET a Reddit JSON endpoint with rate-aware retries.
    Sleeps _RATE_FLOOR seconds after every successful request.
    """
    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=15)
            if r.status_code == 200:
                time.sleep(_RATE_FLOOR)
                return r.json()
            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 65))
                _log_error(
                    run_id, "reddit_scraper",
                    f"429 on {context} — waiting {wait}s (attempt {attempt + 1}/3)",
                    _WARN,
                )
                time.sleep(wait)
                continue
            # Non-retryable error (403 private sub, 404, etc.)
            _log_error(
                run_id, "reddit_scraper",
                f"HTTP {r.status_code} on {context} — skipping",
                _WARN,
            )
            return None
        except requests.RequestException as e:
            _log_error(run_id, "reddit_scraper", f"Request error on {context}: {e}", _WARN)
            time.sleep(5)
    return None


def _extract_posts(json_data: dict) -> list:
    """Pull post dicts from a Reddit JSON listing response."""
    try:
        return [
            child["data"]
            for child in json_data["data"]["children"]
            if child.get("kind") == "t3"
        ]
    except (KeyError, TypeError):
        return []


# ── Signal matching & prospect building ───────────────────────────────────────

def _matches_signal(post: dict, signal_phrases: list) -> str | None:
    """Return the first matching signal phrase found in title+body, or None."""
    text = (
        (post.get("title") or "") + " " + (post.get("selftext") or "")
    ).lower()
    for phrase in signal_phrases:
        if phrase.lower() in text:
            return phrase
    return None


def _reddit_icp_boost(post: dict, subreddit_name: str, signal_phrases: list) -> tuple:
    boost = 0
    notes = []

    score = post.get("score", 0) or 0
    if score >= UPVOTE_BOOST_THRESHOLD:
        boost += 1
        notes.append(f"Reddit upvotes: {score} (pain validated by community)")

    if subreddit_name.lower() in {s.lower() for s in PROFESSIONAL_SUBREDDITS}:
        boost += PROFESSIONAL_SUB_BONUS
        notes.append(f"Professional subreddit: r/{subreddit_name}")

    text = ((post.get("title") or "") + " " + (post.get("selftext") or "")).lower()
    rec_phrases = ["recommend", "recommendation", "suggestions", "who do you use", "what do you use"]
    if any(p in text for p in rec_phrases):
        boost += RECOMMENDATION_BONUS
        notes.append("Post explicitly asks for recommendations (+2)")

    return boost, notes


def _post_to_prospect(post: dict, niche_slug: str, matched_phrase: str) -> dict:
    """Convert a Reddit JSON post dict to a standard prospect dict."""
    username  = post.get("author") or "deleted"
    title     = post.get("title") or ""
    selftext  = post.get("selftext") or ""
    post_text = title + ("\n\n" + selftext if selftext else "")
    subreddit = post.get("subreddit") or ""
    permalink = post.get("permalink") or ""

    method = "reddit_dm" if _can_send_dms() else "find_linkedin"

    return {
        "platform":            "reddit",
        "niche":               niche_slug,
        "niche_segment":       niche_slug,
        "handle":              username,
        "reddit_username":     username,
        "name":                username,
        "title":               "",
        "company":             "",
        "profile_url":         f"https://reddit.com/user/{username}",
        "post_text":           post_text.strip(),
        "post_url":            f"https://reddit.com{permalink}",
        "post_date":           str(post.get("created_utc", "")),
        "signal_phrase":       matched_phrase,
        "subreddit":           subreddit,
        "upvote_score":        post.get("score", 0) or 0,
        "outreach_method":     method,
        "linkedin_search_url": f"https://www.linkedin.com/search/results/people/?keywords={username}",
        "group_name":          f"r/{subreddit}",
    }


# ── Core scanner ──────────────────────────────────────────────────────────────

def scan_subreddit(session, subreddit_name: str, signal_phrases: list,
                   niche_slug: str, run_id=None) -> list:
    """
    Scan one subreddit via Reddit's public JSON API.
      1. Search for each signal phrase (restrict_sr=1 keeps it within the sub).
      2. Scan new posts and filter locally for signal matches.
    """
    results  = []
    seen_ids = set()

    # ── Signal phrase search ──────────────────────────────────────────────────
    for phrase in signal_phrases:
        data = _json_get(
            session,
            f"https://www.reddit.com/r/{subreddit_name}/search.json",
            params={"q": phrase, "sort": "new", "restrict_sr": "1", "limit": MAX_POSTS_PER_SEARCH},
            run_id=run_id,
            context=f"r/{subreddit_name} search '{phrase}'",
        )
        if not data:
            continue
        for post in _extract_posts(data):
            pid = post.get("id")
            if not pid or pid in seen_ids:
                continue
            author = post.get("author")
            if not author or author in ("deleted", "[deleted]"):
                continue
            matched = _matches_signal(post, signal_phrases)
            if not matched:
                continue
            seen_ids.add(pid)
            p = _post_to_prospect(post, niche_slug, matched)
            boost, boost_notes = _reddit_icp_boost(post, subreddit_name, signal_phrases)
            p["_reddit_icp_boost"]   = boost
            p["_reddit_boost_notes"] = boost_notes
            results.append(p)

    # ── New posts — catch anything the search missed ───────────────────────────
    data = _json_get(
        session,
        f"https://www.reddit.com/r/{subreddit_name}/new.json",
        params={"limit": MAX_POSTS_PER_SEARCH},
        run_id=run_id,
        context=f"r/{subreddit_name} new",
    )
    if data:
        for post in _extract_posts(data):
            pid = post.get("id")
            if not pid or pid in seen_ids:
                continue
            author = post.get("author")
            if not author or author in ("deleted", "[deleted]"):
                continue
            matched = _matches_signal(post, signal_phrases)
            if not matched:
                continue
            seen_ids.add(pid)
            p = _post_to_prospect(post, niche_slug, matched)
            boost, boost_notes = _reddit_icp_boost(post, subreddit_name, signal_phrases)
            p["_reddit_icp_boost"]   = boost
            p["_reddit_boost_notes"] = boost_notes
            results.append(p)

    print(f"[Reddit] [{niche_slug}] r/{subreddit_name}: {len(results)} signal posts")
    return results


# ── Public entry points (same signatures as before) ───────────────────────────

def run_niche_search(niche_slug: str, run_id=None) -> list:
    """Scan all subreddits for a single niche. Drop-in replacement for PRAW version."""
    from scrapers.niches import get_reddit_subreddits, get_signal_phrases

    subreddits     = get_reddit_subreddits(niche_slug)
    signal_phrases = get_signal_phrases(niche_slug)

    if not subreddits:
        print(f"[Reddit] [{niche_slug}] No subreddits configured — skipping.")
        return []

    print(f"\n[Reddit] [{niche_slug}] Scanning {len(subreddits)} subreddits (public JSON API, no key needed)...")
    session     = _session()
    all_results = []
    seen_keys   = set()

    for subreddit in subreddits:
        posts = scan_subreddit(session, subreddit, signal_phrases, niche_slug, run_id=run_id)
        for p in posts:
            key = (p["handle"], p["post_url"])
            if key not in seen_keys:
                seen_keys.add(key)
                all_results.append(p)

    print(f"[Reddit] [{niche_slug}] Total unique: {len(all_results)}")
    return all_results


def run_all_searches(run_id=None, niche_slugs=None) -> list:
    """Scan all niches across their subreddits. Drop-in replacement for PRAW version."""
    from scrapers.niches import ALL_NICHES

    niches = ALL_NICHES if not niche_slugs else [
        n for n in ALL_NICHES if n.NICHE_SLUG in niche_slugs
    ]

    all_results  = []
    seen_keys    = set()

    for niche in niches:
        results = run_niche_search(niche.NICHE_SLUG, run_id=run_id)
        for r in results:
            key = (r["handle"], r["post_url"])
            if key not in seen_keys:
                seen_keys.add(key)
                all_results.append(r)

    print(f"\n[Reddit] Total unique prospects across all niches: {len(all_results)}")

    try:
        from error_logger import log_zero_results_alert
        if not all_results:
            log_zero_results_alert(run_id, "Reddit")
    except Exception:
        pass

    return all_results


if __name__ == "__main__":
    results = run_niche_search("financial-advisors")
    for r in results[:3]:
        print(f"\nu/{r['handle']} | r/{r['subreddit']} | upvotes: {r['upvote_score']}")
        print(f"Signal: {r['signal_phrase']}")
        print(f"Post: {r['post_text'][:120]}...")
