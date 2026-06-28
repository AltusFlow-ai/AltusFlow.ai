"""
scrapers/twitter.py
Searches X/Twitter for prospects posting signal phrases via ScrapeBadger API.

Replaces the official X API bearer token (paid, $100+/month) with ScrapeBadger
which covers Twitter at a fraction of the cost using the same SCRAPEBADGER_API_KEY
already used for Reddit.

Setup: SCRAPEBADGER_API_KEY in Railway env vars (same key as Reddit — no extra signup).
"""

import os
import time

import requests

SCRAPEBADGER_API_KEY  = os.environ.get("SCRAPEBADGER_API_KEY", "")
SCRAPEBADGER_TWITTER  = "https://scrapebadger.com/v1/twitter/tweets/advanced_search"

_RATE_FLOOR = 1.5  # seconds between requests

# ── Error logger ───────────────────────────────────────────────────────────────
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

# ── Signal phrase library (unchanged) ─────────────────────────────────────────
SIGNAL_PHRASES_BY_NICHE = {
    "financial-advisors": [
        '"pipeline dried up" financial advisor',
        '"struggling to find clients" advisor',
        '"lead gen" financial advisor',
        '"how do you get new clients" financial',
        '"ads not converting" financial services',
        '"need more booked calls" advisor',
        '"how do you grow a brokerage"',
        '"marketing for financial advisors"',
        '"qualified clients" financial advisor',
        '"not enough referrals" advisor',
        '"AUM growth" struggling',
        '"prospecting" financial advisor hard',
        '"cold outreach" financial advisor',
        '"social media" financial advisor clients',
    ],
    "trading-coaches": [
        '"growing our trading community"',
        '"looking to add members" trading',
        '"how do I grow my trading course"',
        '"trading students" struggling to find',
        '"marketing my trading" course',
        '"trading mentor" how to get clients',
        '"Discord trading" how to grow',
        '"trading community" need more members',
        '"trading course" not selling',
        '"promote my trading" group',
    ],
    "business-coaches": [
        '"pipeline dried up" coach',
        '"struggling to find coaching clients"',
        '"how do coaches get clients"',
        '"fill my coaching calendar"',
        '"need more clients" business coach',
        '"marketing for coaches" what works',
        '"cold outreach" coaching clients',
        '"lead gen" business coach',
        '"grow my coaching practice"',
        '"coaching clients" hard to find',
        '"ads for coaches" not working',
        '"client acquisition" coach struggling',
    ],
    "commercial-real-estate": [
        '"deal flow is slow" commercial real estate',
        '"pipeline dried up" CRE',
        '"struggling to find buyers" commercial',
        '"qualified leads" commercial real estate',
        '"prospecting" commercial real estate broker',
        '"how do CRE brokers" get clients',
        '"cold calling" commercial real estate not working',
        '"lead gen" commercial real estate',
        '"tenant rep" finding prospects',
        '"industrial deals" pipeline slow',
    ],
    "msps": [
        '"looking for MSP" recommendations',
        '"managed IT" recommendations',
        '"evaluating MSPs" help',
        '"need managed services" provider',
        '"IT provider" not happy looking',
        '"outsource IT" looking for provider',
        '"MSP" recommendations small business',
        '"managed services" who do you use',
        '"IT support" looking for better provider',
        '"switching MSPs" recommendations',
    ],
    "recruiters": [
        '"pipeline dried up" recruiting',
        '"struggling to find candidates"',
        '"lead gen" recruiting',
        '"sourcing candidates" hard',
        '"InMail" response rate dropping',
        '"LinkedIn recruiting" not working',
        '"how do recruiters" find candidates',
        '"passive candidates" hard to reach',
        '"cold outreach" recruiting not converting',
        '"talent acquisition" pipeline slow',
        '"executive search" prospecting',
    ],
    "daytrading": [
        '"blown my account" day trading',
        '"can\'t find consistency" trading',
        '"revenge trading" losing money',
        '"prop firm" failed "day trading"',
        '"overtrading" losing',
        '"FOMO" entry regret trading',
        '"day trading" not profitable help',
        '"losing streak" trading account',
        '"trading psychology" struggling',
        '"blown account" trader need help',
    ],
    "futures": [
        '"keep getting stopped out" futures',
        '"NQ" eating my account',
        '"can\'t pass prop firm eval" futures',
        '"failed prop firm challenge"',
        '"ES" losing money futures',
        '"prop firm" drawdown rule hit',
        '"futures trading" not profitable',
        '"MES NQ" blown account',
        '"emini" losing consistency',
        '"prop firm eval" failing again',
    ],
    "swing-trading": [
        '"keep buying breakouts that fail" swing',
        '"how do you screen for swing trades"',
        '"getting shaken out before the move"',
        '"swing trading" not profitable',
        '"swing trade" stop loss too tight',
        '"holding overnight" anxious trading',
        '"swing trading" losing money help',
        '"breakout failed" swing trading',
        '"position sizing" swing trading confused',
        '"swing trade" FOMO entry regret',
    ],
    "crypto": [
        '"got liquidated" crypto',
        '"panic sold the bottom" crypto',
        '"FOMO into a pump" crypto',
        '"bag holding" altcoin down',
        '"wrecked by altcoins" portfolio',
        '"crypto" losing money need help',
        '"altcoin" portfolio down 90',
        '"leveraged" liquidated crypto',
        '"crypto trading" not profitable',
        '"DCA" still losing crypto',
    ],
    "options": [
        '"IV crush" destroyed my trade',
        '"theta decay" killing my account',
        '"0DTE" blew up account options',
        '"assignment risk" confused options',
        '"options trading" losing money',
        '"selling puts" assignment nightmare',
        '"Greeks" confused options trading',
        '"IV" options strategy losing',
        '"options" not profitable help',
        '"covered calls" not working portfolio',
    ],
}


# ── HTTP helper ────────────────────────────────────────────────────────────────

def _sb_search(query: str, count: int = 50, run_id=None) -> list:
    """
    Search X/Twitter via ScrapeBadger advanced tweet search.
    Returns list of raw tweet dicts.
    """
    if not SCRAPEBADGER_API_KEY:
        _log_error(
            run_id, "twitter_scraper",
            "SCRAPEBADGER_API_KEY not set — Twitter search skipped. "
            "Add it to Railway env vars.",
            _CRIT,
        )
        return []

    headers = {"x-api-key": SCRAPEBADGER_API_KEY}
    params  = {
        "query":      f"{query} lang:en",
        "query_type": "Latest",
        "count":      min(count, 100),
    }

    for attempt in range(3):
        try:
            r = requests.get(SCRAPEBADGER_TWITTER, headers=headers, params=params, timeout=20)
            time.sleep(_RATE_FLOOR)

            if r.status_code == 200:
                return r.json().get("data", [])

            if r.status_code == 429:
                wait = int(r.headers.get("Retry-After", 65))
                _log_error(run_id, "twitter_scraper",
                           f"429 rate limit — waiting {wait}s (attempt {attempt + 1}/3)", _WARN)
                time.sleep(wait)
                continue

            if r.status_code == 401:
                _log_error(run_id, "twitter_scraper",
                           "ScrapeBadger API key invalid (401). Check SCRAPEBADGER_API_KEY in Railway.", _CRIT)
                return []

            if r.status_code == 402:
                _log_error(run_id, "twitter_scraper",
                           "ScrapeBadger credits exhausted (402). Top up at scrapebadger.com.", _CRIT)
                return []

            _log_error(run_id, "twitter_scraper",
                       f"HTTP {r.status_code} on query '{query[:60]}'", _WARN)
            return []

        except requests.RequestException as e:
            _log_error(run_id, "twitter_scraper", f"Network error: {e}", _CRIT)
            time.sleep(5)

    return []


def _tweet_to_prospect(tweet: dict, niche: str, signal_phrase: str) -> dict:
    """Convert a ScrapeBadger tweet dict to a standard prospect dict."""
    username    = tweet.get("username") or ""
    handle      = f"@{username}" if username and not username.startswith("@") else username
    display_name = tweet.get("user_name") or username
    text        = tweet.get("full_text") or tweet.get("text") or ""
    tweet_id    = tweet.get("id") or ""

    return {
        "platform":        "twitter",
        "niche":           niche,
        "niche_segment":   niche,
        "handle":          handle,
        "name":            display_name,
        "title":           "",
        "company":         "",
        "profile_url":     f"https://x.com/{username}",
        "post_text":       text,
        "post_url":        f"https://x.com/{username}/status/{tweet_id}",
        "post_date":       tweet.get("created_at", ""),
        "signal_phrase":   signal_phrase,
        "upvote_score":    tweet.get("favorite_count", 0) or 0,
        "outreach_method": "twitter_dm",
    }


# ── Public entry points ────────────────────────────────────────────────────────

def search_recent(query: str, niche: str, max_results: int = 20, run_id=None) -> list:
    """Search X for one signal phrase. Same signature as original."""
    tweets  = _sb_search(query, count=max_results, run_id=run_id)
    results = []
    for tweet in tweets:
        username = tweet.get("username") or ""
        if not username or username in ("deleted", ""):
            continue
        results.append(_tweet_to_prospect(tweet, niche, query))
    return results


def run_niche_search(niche_slug: str, run_id=None, max_per_phrase: int = 20) -> list:
    """Search X for a single niche. Same signature as original."""
    phrases = SIGNAL_PHRASES_BY_NICHE.get(niche_slug, [])
    if not phrases:
        print(f"[Twitter] [{niche_slug}] No signal phrases configured — skipping.")
        return []

    all_results  = []
    seen_handles = set()

    for phrase in phrases:
        print(f"[Twitter] [{niche_slug}] Searching: {phrase}")
        results = search_recent(phrase, niche=niche_slug, max_results=max_per_phrase, run_id=run_id)
        for r in results:
            if r["handle"] not in seen_handles:
                seen_handles.add(r["handle"])
                r.setdefault("niche_segment", niche_slug)
                all_results.append(r)

    print(f"[Twitter] [{niche_slug}] {len(all_results)} unique prospects found")
    return all_results


def run_all_searches(max_per_phrase: int = 20, run_id=None) -> list:
    """Run every signal phrase across all niches. Same signature as original."""
    if not SCRAPEBADGER_API_KEY:
        _log_error(
            run_id, "twitter_scraper",
            "SCRAPEBADGER_API_KEY not set — Twitter search skipped entirely. "
            "Add it to Railway env vars.",
            _CRIT,
        )
        return []

    all_results  = []
    seen_handles = set()

    for niche, phrases in SIGNAL_PHRASES_BY_NICHE.items():
        for phrase in phrases:
            print(f"[Twitter] [{niche}] Searching: {phrase}")
            results = search_recent(phrase, niche=niche, max_results=max_per_phrase, run_id=run_id)
            for r in results:
                if r["handle"] not in seen_handles:
                    seen_handles.add(r["handle"])
                    all_results.append(r)

    print(f"[Twitter] Total unique prospects: {len(all_results)}")

    try:
        from error_logger import log_zero_results_alert
        if not all_results and SCRAPEBADGER_API_KEY:
            log_zero_results_alert(run_id, "Twitter")
    except Exception:
        pass

    return all_results


if __name__ == "__main__":
    results = run_all_searches(max_per_phrase=5)
    for r in results[:3]:
        print(f"\n{r['name']} ({r['handle']}) [{r['niche']}]")
        print(f"Post: {r['post_text'][:100]}...")
        print(f"URL:  {r['post_url']}")
