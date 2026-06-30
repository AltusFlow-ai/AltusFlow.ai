"""
scrapers/reddit.py
Scans Reddit for signal posts using Reddit's free public JSON API.

No API key required — uses reddit.com/.json endpoints which are publicly
accessible. Rate limit: ~60 req/min; _RATE_FLOOR adds a 1s delay between
calls to stay well within limits.

DM sending: set REDDIT_USERNAME + REDDIT_PASSWORD + REDDIT_CLIENT_ID +
REDDIT_CLIENT_SECRET if you want to send DMs directly. Without them,
outreach_method falls back to 'find_linkedin'.
"""

import os
import time

import requests

REDDIT_USER_AGENT = os.environ.get("REDDIT_USER_AGENT", "AltusFlowHunter/1.0")


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


REDDIT_PUBLIC_BASE  = "https://www.reddit.com"
SCRAPEBADGER_BASE   = "https://scrapebadger.com/v1/reddit"

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

MAX_POSTS_PER_SEARCH = int(os.environ.get("REDDIT_POSTS_PER_SEARCH", "25"))
_RATE_FLOOR = 1.0  # seconds between requests


# ── HTTP session ───────────────────────────────────────────────────────────────

def _get_api_key() -> str:
    """Read ScrapeBadger key fresh each call — env first, then tenant DB."""
    key = os.environ.get("SCRAPEBADGER_API_KEY", "")
    if key:
        return key
    try:
        from database import get_settings
        return get_settings().get("scrapebadger_key", "") or ""
    except Exception:
        return ""


def _session(use_scrapebadger: bool = False) -> requests.Session:
    s = requests.Session()
    headers = {"User-Agent": REDDIT_USER_AGENT}
    if use_scrapebadger:
        headers["Authorization"] = f"Bearer {_get_api_key()}"
    s.headers.update(headers)
    return s


# ── Legacy compatibility stub ──────────────────────────────────────────────────

def get_reddit_client():
    """Kept for backward compatibility — returns a truthy sentinel."""
    return _session(use_scrapebadger=bool(_get_api_key()))


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


# ── HTTP helpers (ScrapeBadger + Reddit public fallback) ───────────────────────

_MAX_RETRIES  = 2
_MAX_WAIT     = 8   # cap retry-after / backoff so a run can never silently hang for minutes
_REQ_TIMEOUT  = 10  # seconds


def _sb_get(session: requests.Session, endpoint: str, params: dict = None,
            run_id=None, context: str = "") -> list:
    """GET a ScrapeBadger endpoint; returns list of post dicts."""
    url = SCRAPEBADGER_BASE + endpoint

    for attempt in range(_MAX_RETRIES):
        try:
            r = session.get(url, params=params, timeout=_REQ_TIMEOUT)
            time.sleep(_RATE_FLOOR)
            print(f"[SB] {context} → HTTP {r.status_code} | body[:200]: {r.text[:200]}")

            if r.status_code == 200:
                data = r.json()
                posts = (
                    data.get("posts")
                    or data.get("items")
                    or data.get("results")
                    or data.get("data")
                    or []
                )
                if isinstance(posts, dict):
                    posts = posts.get("children", [])
                    posts = [p.get("data", p) for p in posts]
                return posts

            if r.status_code == 429:
                wait = min(int(r.headers.get("Retry-After", _MAX_WAIT)), _MAX_WAIT)
                print(f"[SB] 429 on {context} — waiting {wait}s (attempt {attempt+1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue

            if r.status_code in (401, 403):
                print(f"[SB] {r.status_code} on {context} — auth failed, check SCRAPEBADGER_API_KEY")
                return []

            return []

        except requests.RequestException as e:
            print(f"[SB] request error on {context}: {e}")
            time.sleep(2)

    return []


def _reddit_get(session: requests.Session, url: str, params: dict = None,
                run_id=None, context: str = "") -> list:
    """GET a Reddit public JSON endpoint; returns list of post dicts."""
    for attempt in range(_MAX_RETRIES):
        try:
            r = session.get(url, params=params, timeout=_REQ_TIMEOUT)
            time.sleep(_RATE_FLOOR)

            if r.status_code == 200:
                data = r.json()
                posts = _extract_reddit_posts(data)
                print(f"[reddit][public] {context} → 200, posts={len(posts)}")
                return posts

            if r.status_code == 429:
                wait = min(int(r.headers.get("Retry-After", _MAX_WAIT)), _MAX_WAIT)
                print(f"[reddit][public] 429 on {context} — waiting {wait}s (attempt {attempt+1}/{_MAX_RETRIES})")
                time.sleep(wait)
                continue

            print(f"[reddit][public] HTTP {r.status_code} on {context} — body[:200]: {r.text[:200]}")
            return []

        except requests.RequestException as e:
            print(f"[reddit][public] request error on {context}: {e}")
            time.sleep(2)

    return []


def _extract_reddit_posts(data) -> list:
    """Pull post list from a Reddit public JSON response."""
    if not data:
        return []
    if isinstance(data, dict) and "data" in data:
        children = data["data"].get("children", [])
        return [c["data"] for c in children if isinstance(c.get("data"), dict)]
    return []


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
    """Convert a Reddit JSON post dict to a standard prospect dict."""
    username  = post.get("author") or "deleted"
    title     = post.get("title") or ""
    selftext  = post.get("selftext") or ""
    post_text = title + ("\n\n" + selftext if selftext else "")
    subreddit = post.get("subreddit") or ""
    post_id   = post.get("id") or ""
    permalink = post.get("permalink") or ""

    # Build canonical Reddit URL from permalink, fallback to constructed URL
    if permalink:
        post_url = f"https://www.reddit.com{permalink}"
    else:
        post_url = f"https://www.reddit.com/r/{subreddit}/comments/{post_id}/"

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

def _fetch_new_posts(session, subreddit_name: str, use_sb: bool, run_id=None) -> list:
    """Fetch newest posts for a subreddit — called once, not once per phrase."""
    if use_sb:
        return _sb_get(
            session, f"/subreddits/{subreddit_name}/posts",
            params={"sort": "new", "limit": MAX_POSTS_PER_SEARCH},
            run_id=run_id, context=f"r/{subreddit_name} new posts",
        )
    return _reddit_get(
        session,
        f"{REDDIT_PUBLIC_BASE}/r/{subreddit_name}/new.json",
        params={"limit": MAX_POSTS_PER_SEARCH},
        run_id=run_id, context=f"r/{subreddit_name} new posts",
    )


def _fetch_search(session, subreddit_name: str, phrase: str, use_sb: bool, run_id=None) -> list:
    """Search a subreddit for one phrase."""
    if use_sb:
        return _sb_get(
            session, "/search/posts",
            params={"q": f"{phrase} subreddit:{subreddit_name}", "sort": "new", "limit": MAX_POSTS_PER_SEARCH},
            run_id=run_id, context=f"r/{subreddit_name} search '{phrase}'",
        )
    return _reddit_get(
        session,
        f"{REDDIT_PUBLIC_BASE}/r/{subreddit_name}/search.json",
        params={"q": phrase, "restrict_sr": "1", "sort": "new", "limit": MAX_POSTS_PER_SEARCH},
        run_id=run_id, context=f"r/{subreddit_name} search '{phrase}'",
    )


def scan_subreddit(session, subreddit_name: str, signal_phrases: list,
                   niche_slug: str, run_id=None) -> list:
    """
    Scan one subreddit — uses ScrapeBadger if key is set, otherwise Reddit public API.
    New-posts sweep happens once; phrase search happens once per phrase.
    """
    use_sb   = bool(_get_api_key())
    results  = []
    seen_ids = set()

    def _process(post):
        pid    = post.get("id")
        author = post.get("author")
        if not pid or pid in seen_ids or not author or author in ("deleted", "[deleted]", "AutoModerator"):
            return
        matched = _matches_signal(post, signal_phrases)
        if not matched:
            return
        seen_ids.add(pid)
        p = _post_to_prospect(post, niche_slug, matched)
        boost, boost_notes = _reddit_icp_boost(post, subreddit_name, signal_phrases)
        p["_reddit_icp_boost"]   = boost
        p["_reddit_boost_notes"] = boost_notes
        results.append(p)

    for post in _fetch_new_posts(session, subreddit_name, use_sb, run_id):
        _process(post)

    for phrase in signal_phrases:
        for post in _fetch_search(session, subreddit_name, phrase, use_sb, run_id):
            _process(post)

    print(f"[Reddit] [{niche_slug}] r/{subreddit_name}: {len(results)} signal posts ({'SB' if use_sb else 'public'})")
    return results


# ── Public entry points (same signatures as original) ─────────────────────────

def run_niche_search(niche_slug: str, run_id=None) -> list:
    """Scan all subreddits for a single niche."""
    from scrapers.niches import get_reddit_subreddits, get_signal_phrases

    subreddits     = get_reddit_subreddits(niche_slug)
    signal_phrases = get_signal_phrases(niche_slug)

    if not subreddits:
        print(f"[reddit] niche={niche_slug!r} has no subreddits configured")
        return []

    use_sb = bool(_get_api_key())
    print(f"[reddit] {niche_slug}: scanning {len(subreddits)} subreddits x {len(signal_phrases)} "
          f"phrases via {'ScrapeBadger' if use_sb else 'Reddit public API'}...")
    session = _session(use_scrapebadger=use_sb)
    all_results = []
    seen_keys   = set()

    for subreddit in subreddits:
        posts = scan_subreddit(session, subreddit, signal_phrases, niche_slug, run_id=run_id)
        for p in posts:
            key = (p["handle"], p["post_url"])
            if key not in seen_keys:
                seen_keys.add(key)
                all_results.append(p)

    print(f"[reddit] {niche_slug}: total unique={len(all_results)}")
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
