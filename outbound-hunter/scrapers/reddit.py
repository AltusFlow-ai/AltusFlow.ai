"""
scrapers/reddit.py
Scans Reddit for signal posts using the ScrapeBadger API.

Replaces PRAW and the now-deprecated unauthenticated .json endpoints.
ScrapeBadger handles Reddit auth, rate limiting, and session management.

Setup:
  1. Sign up at scrapebadger.com and get your API key
  2. Add to Railway env vars: SCRAPEBADGER_API_KEY=your_key

Cost: 2 credits per search or subreddit fetch.

DM sending: set REDDIT_USERNAME + REDDIT_PASSWORD + REDDIT_CLIENT_ID +
REDDIT_CLIENT_SECRET if you want to send DMs directly. Without them,
outreach_method falls back to 'find_linkedin'.
"""

import os
import time

import requests

# ── Env vars ───────────────────────────────────────────────────────────────────
# SCRAPEBADGER_API_KEY is read dynamically (see _get_api_key) so that keys
# saved via the Settings dashboard are picked up by background scan threads.
REDDIT_USER_AGENT    = os.environ.get("REDDIT_USER_AGENT", "AltusFlowHunter/1.0")


def _get_reddit_creds() -> dict:
    """Read Reddit OAuth creds fresh each call: env first, then tenant_settings DB."""
    client_id     = os.environ.get("REDDIT_CLIENT_ID", "")
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "")
    username      = os.environ.get("REDDIT_USERNAME", "")
    password      = os.environ.get("REDDIT_PASSWORD", "")
    if client_id and client_secret and username and password:
        return {"client_id": client_id, "client_secret": client_secret,
                "username": username, "password": password}
    try:
        from database import get_settings
        s = get_settings()
        return {
            "client_id":     s.get("reddit_client_id", "")     or "",
            "client_secret": s.get("reddit_client_secret", "") or "",
            "username":      s.get("reddit_username", "")      or "",
            "password":      s.get("reddit_password", "")      or "",
        }
    except Exception:
        return {"client_id": "", "client_secret": "", "username": "", "password": ""}


# Module-level aliases kept for backward compatibility — do not use directly.
REDDIT_CLIENT_ID     = ""
REDDIT_CLIENT_SECRET = ""
REDDIT_USERNAME      = ""
REDDIT_PASSWORD      = ""


def _get_api_key() -> str:
    """Read ScrapeBadger key fresh each call: env var first, then tenant_settings DB."""
    key = os.environ.get("SCRAPEBADGER_API_KEY", "")
    if key:
        return key
    try:
        from database import get_settings
        return get_settings().get("scrapebadger_key", "") or ""
    except Exception:
        return ""


# Module-level alias kept for any external callers that reference it directly.
# Always call _get_api_key() internally so background threads see the live value.
SCRAPEBADGER_API_KEY = ""  # resolved dynamically — do not use directly

SCRAPEBADGER_BASE = "https://api.scrapebadger.com/v1/reddit"

# ── ICP boost constants ────────────────────────────────────────────────────────
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

MAX_POSTS_PER_SEARCH = int(os.environ.get("REDDIT_POSTS_PER_SEARCH", "50"))
_RATE_FLOOR = 1.0  # seconds between requests

# ── Error logger (optional dep) ────────────────────────────────────────────────
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
    s.headers.update({
        "Authorization": f"Bearer {_get_api_key()}",
        "User-Agent": REDDIT_USER_AGENT,
    })
    return s


# ── Legacy compatibility stub ──────────────────────────────────────────────────

def get_reddit_client():
    """Kept for backward compatibility — returns a truthy sentinel."""
    return _session() if _get_api_key() else None


# ── DM sending (optional — requires PRAW + full Reddit credentials) ────────────

def _can_send_dms() -> bool:
    c = _get_reddit_creds()
    return bool(c["client_id"] and c["client_secret"] and c["username"] and c["password"])


def send_reddit_dm(username: str, subject: str, body: str) -> dict:
    if not _can_send_dms():
        return {
            "ok": False,
            "error": "Reddit DM sending requires REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD — paste them in Settings → Connections.",
        }
    try:
        c = _get_reddit_creds()
        import praw
        reddit = praw.Reddit(
            client_id=c["client_id"],
            client_secret=c["client_secret"],
            username=c["username"],
            password=c["password"],
            user_agent=REDDIT_USER_AGENT,
        )
        reddit.redditor(username).message(subject=subject, message=body)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


# ── ScrapeBadger API helpers ───────────────────────────────────────────────────

def _sb_get(session: requests.Session, endpoint: str, params: dict = None,
            run_id=None, context: str = "") -> dict | None:
    """
    GET a ScrapeBadger Reddit endpoint with retry on 429.
    Endpoint is relative to SCRAPEBADGER_BASE, e.g. '/search/posts'.
    """
    if not _get_api_key():
        _log_error(
            run_id, "reddit_scraper",
            "SCRAPEBADGER_API_KEY not set — Reddit scraping skipped. "
            "Add it to Railway env vars or paste it in Settings → Connections.",
            _CRIT,
        )
        return None

    url = SCRAPEBADGER_BASE + endpoint

    for attempt in range(3):
        try:
            r = session.get(url, params=params, timeout=20)
            time.sleep(_RATE_FLOOR)

            if r.status_code == 200:
                data = r.json()
                import logging as _l2
                _l2.getLogger(__name__).info("[reddit] ScrapeBadger %s → 200, posts=%d",
                    context, len(data.get('posts', [])))
                return data

            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 65))
                _log_error(
                    run_id, "reddit_scraper",
                    f"429 on {context} — waiting {wait}s (attempt {attempt + 1}/3)",
                    _WARN,
                )
                time.sleep(wait)
                continue

            if r.status_code == 401:
                _log_error(
                    run_id, "reddit_scraper",
                    f"ScrapeBadger 401 on {context} — API key invalid or expired. "
                    "Check SCRAPEBADGER_API_KEY in Railway. Body: " + r.text[:200],
                    _CRIT,
                )
                return None

            _log_error(
                run_id, "reddit_scraper",
                f"ScrapeBadger HTTP {r.status_code} on {context} — body: {r.text[:200]}",
                _WARN,
            )
            return None

        except requests.RequestException as e:
            _log_error(run_id, "reddit_scraper", f"Request error on {context}: {e}", _WARN)
            time.sleep(5)

    return None


def _extract_posts(data: dict) -> list:
    """Pull post list from a ScrapeBadger response."""
    if not data:
        return []
    return data.get("posts", [])


# ── Signal matching & prospect building ───────────────────────────────────────

def _matches_signal(post: dict, signal_phrases: list) -> str | None:
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
        notes.append(f"Reddit upvotes: {score} (community validated pain)")

    if subreddit_name.lower() in {s.lower() for s in PROFESSIONAL_SUBREDDITS}:
        boost += PROFESSIONAL_SUB_BONUS
        notes.append(f"Professional subreddit: r/{subreddit_name}")

    text = ((post.get("title") or "") + " " + (post.get("selftext") or "")).lower()
    if any(p in text for p in ["recommend", "recommendation", "suggestions", "who do you use", "what do you use"]):
        boost += RECOMMENDATION_BONUS
        notes.append("Post asks for recommendations (+2)")

    return boost, notes


def _post_to_prospect(post: dict, niche_slug: str, matched_phrase: str) -> dict:
    """Convert a ScrapeBadger post dict to a standard prospect dict."""
    username  = post.get("author") or "deleted"
    title     = post.get("title") or ""
    selftext  = post.get("selftext") or ""
    post_text = title + ("\n\n" + selftext if selftext else "")
    subreddit = post.get("subreddit") or ""
    post_id   = post.get("id") or ""

    # ScrapeBadger returns url field; for self posts it's the Reddit URL
    post_url = post.get("url") or f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/"

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
        "post_url":            post_url,
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
    Scan one subreddit via ScrapeBadger:
      1. Search for each signal phrase within the subreddit.
      2. Fetch new posts and filter locally to catch anything search missed.
    """
    results  = []
    seen_ids = set()

    # ── Signal phrase search (restricted to this subreddit) ───────────────────
    for phrase in signal_phrases:
        data = _sb_get(
            session,
            "/search/posts",
            params={
                "q":     f"{phrase} subreddit:{subreddit_name}",
                "sort":  "new",
                "limit": MAX_POSTS_PER_SEARCH,
            },
            run_id=run_id,
            context=f"r/{subreddit_name} search '{phrase}'",
        )
        for post in _extract_posts(data):
            pid    = post.get("id")
            author = post.get("author")
            if not pid or pid in seen_ids or not author or author in ("deleted", "[deleted]"):
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

    # ── New posts sweep — catch anything search missed ────────────────────────
    data = _sb_get(
        session,
        f"/subreddits/{subreddit_name}/posts",
        params={"sort": "new", "limit": MAX_POSTS_PER_SEARCH},
        run_id=run_id,
        context=f"r/{subreddit_name} new posts",
    )
    for post in _extract_posts(data):
        pid    = post.get("id")
        author = post.get("author")
        if not pid or pid in seen_ids or not author or author in ("deleted", "[deleted]"):
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


# ── Public entry points (same signatures as original) ─────────────────────────

def run_niche_search(niche_slug: str, run_id=None) -> list:
    """Scan all subreddits for a single niche."""
    import logging as _logging
    _lg = _logging.getLogger(__name__)

    from scrapers.niches import get_reddit_subreddits, get_signal_phrases

    key = _get_api_key()
    _lg.info("[reddit] run_niche_search niche=%r key_found=%s", niche_slug, bool(key))

    if not key:
        _log_error(
            run_id, "reddit_scraper",
            "SCRAPEBADGER_API_KEY not configured — Reddit scan skipped. "
            "Add it to Railway env vars or paste it in Settings → Connections.",
            _CRIT,
        )
        return []

    subreddits     = get_reddit_subreddits(niche_slug)
    signal_phrases = get_signal_phrases(niche_slug)

    _lg.info("[reddit] niche=%r subreddits=%r phrases=%r", niche_slug, subreddits, signal_phrases[:3])

    if not subreddits:
        _lg.warning("[reddit] niche=%r has no subreddits configured", niche_slug)
        return []

    _lg.info("[reddit] scanning %d subreddits for %s via ScrapeBadger...", len(subreddits), niche_slug)
    session     = _session()
    all_results = []
    seen_keys   = set()

    for subreddit in subreddits:
        posts = scan_subreddit(session, subreddit, signal_phrases, niche_slug, run_id=run_id)
        _lg.info("[reddit] r/%s → %d signal posts", subreddit, len(posts))
        for p in posts:
            key = (p["handle"], p["post_url"])
            if key not in seen_keys:
                seen_keys.add(key)
                all_results.append(p)

    _lg.info("[reddit] niche=%r total unique=%d", niche_slug, len(all_results))
    return all_results


def run_all_searches(run_id=None, niche_slugs=None) -> list:
    """Scan all niches across their subreddits."""
    from scrapers.niches import ALL_NICHES

    niches = ALL_NICHES if not niche_slugs else [
        n for n in ALL_NICHES if n.NICHE_SLUG in niche_slugs
    ]

    all_results = []
    seen_keys   = set()

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
