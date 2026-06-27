"""
scrapers/twitter.py
Searches X/Twitter for prospects posting signal phrases.

Signal phrases are organized by niche — each prospect is tagged with the
niche of the phrase that matched it. The niche flows through to the DB
and is used to filter the batch-confirm and digest views.

Error handling:
  - 401 / 403  → CRITICAL  (token invalid or permission revoked)
  - 429        → WARNING   (rate limit, self-healing on next run)
  - 5xx        → CRITICAL  (API outage)
  - Network    → CRITICAL
  - No token   → CRITICAL  (misconfiguration)
"""

import os
import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta

BEARER_TOKEN = os.environ.get("TWITTER_BEARER_TOKEN", "")

# ── Signal phrase library ─────────────────────────────────────────────────────
# Organized by niche. Each prospect is tagged with the niche of its matching phrase.
# Add new niches here as AltusFlow expands to new verticals.

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

# Suggested fixes by HTTP status code
_STATUS_FIX = {
    401: (
        "TWITTER_BEARER_TOKEN is invalid or expired. "
        "Regenerate at developer.twitter.com > Your App > Keys and Tokens."
    ),
    403: (
        "This app does not have permission to use Twitter API v2 search. "
        "Verify app permissions and your plan tier at developer.twitter.com."
    ),
    429: (
        "Twitter rate limit hit. The scraper will automatically recover on the next run. "
        "No action needed unless this recurs daily — if so, reduce max_per_phrase."
    ),
    503: (
        "Twitter API is experiencing an outage. "
        "Check https://api.twitterstat.us — resolves automatically."
    ),
}


def _bearer_header():
    return {"Authorization": f"Bearer {BEARER_TOKEN}"}


def _parse_bio(description):
    """Extract (title, company) from a Twitter bio string."""
    bio = description.lower()
    if "|" in description:
        parts = description.split("|")
        return parts[0].strip(), (parts[1].strip() if len(parts) > 1 else "")
    if " at " in bio:
        idx = bio.index(" at ")
        return description[:idx].strip(), description[idx + 4:idx + 44].strip()
    if " @ " in description:
        idx = description.index(" @ ")
        return description[:idx].strip(), description[idx + 3:idx + 43].strip()
    return "", ""


def search_recent(query, niche, max_results=20, run_id=None):
    """
    Search recent tweets for one signal phrase.
    Returns a list of prospect dicts tagged with niche, or [] on any failure.
    Failures are logged via error_logger — this function never raises.
    """
    from error_logger import log_pipeline_error, WARNING, CRITICAL

    if not BEARER_TOKEN:
        log_pipeline_error(
            run_id, "twitter_scraper",
            "TWITTER_BEARER_TOKEN is not set — Twitter search skipped entirely.",
            CRITICAL,
            suggested_fix=(
                "Add TWITTER_BEARER_TOKEN to your .env file. "
                "Get a Bearer Token at developer.twitter.com > Your App > Keys and Tokens."
            ),
        )
        return []

    full_query = f"{query} -is:retweet -is:reply lang:en"
    params = urllib.parse.urlencode({
        "query":        full_query,
        "max_results":  min(max_results, 100),
        "tweet.fields": "created_at,author_id,public_metrics,entities",
        "user.fields":  "name,username,description,public_metrics,location",
        "expansions":   "author_id",
        "start_time":   (datetime.utcnow() - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    url = f"https://api.twitter.com/2/tweets/search/recent?{params}"

    try:
        req = urllib.request.Request(url, headers=_bearer_header())
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())

    except urllib.error.HTTPError as e:
        body     = e.read().decode(errors="replace")[:300]
        severity = CRITICAL if e.code in (401, 403) else WARNING
        fix      = _STATUS_FIX.get(
            e.code,
            f"Twitter API returned HTTP {e.code}. Check developer.twitter.com for details."
        )
        log_pipeline_error(
            run_id, "twitter_scraper",
            f"HTTP {e.code} on query '{query[:60]}': {body}",
            severity, suggested_fix=fix,
        )
        return []

    except urllib.error.URLError as e:
        log_pipeline_error(
            run_id, "twitter_scraper",
            f"Network error on query '{query[:60]}': {e.reason}",
            CRITICAL,
            suggested_fix="Check internet connectivity and DNS resolution from the server.",
        )
        return []

    except Exception as e:
        log_pipeline_error(
            run_id, "twitter_scraper",
            f"Unexpected error on query '{query[:60]}': {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []

    tweets = data.get("data", [])
    users  = {u["id"]: u for u in data.get("includes", {}).get("users", [])}

    results = []
    for tweet in tweets:
        user        = users.get(tweet.get("author_id"), {})
        description = user.get("description", "")
        handle      = user.get("username", "")
        title, company = _parse_bio(description)

        results.append({
            "platform":     "twitter",
            "niche":        niche,
            "handle":       f"@{handle}",
            "name":         user.get("name", ""),
            "title":        title,
            "company":      company,
            "profile_url":  f"https://twitter.com/{handle}",
            "post_text":    tweet.get("text", ""),
            "post_url":     f"https://twitter.com/{handle}/status/{tweet['id']}",
            "post_date":    tweet.get("created_at", ""),
            "signal_phrase": query,
        })

    return results


def run_all_searches(max_per_phrase=10, run_id=None):
    """
    Run every signal phrase across all niches.
    Returns combined unique results, each tagged with niche.
    If total results are zero after all searches, fires a critical alert.
    """
    from error_logger import log_pipeline_error, log_zero_results_alert, CRITICAL

    # Early exit with one notification — avoids per-phrase duplicate alerts
    if not BEARER_TOKEN:
        log_pipeline_error(
            run_id, "twitter_scraper",
            "TWITTER_BEARER_TOKEN not set — Twitter search skipped entirely.",
            CRITICAL,
            suggested_fix=(
                "Add TWITTER_BEARER_TOKEN to your .env file. "
                "Get a Bearer Token at developer.twitter.com > Your App > Keys and Tokens."
            ),
        )
        return []

    all_results    = []
    seen_handles   = set()
    phrase_count   = sum(len(v) for v in SIGNAL_PHRASES_BY_NICHE.values())
    phrases_failed = 0

    for niche, phrases in SIGNAL_PHRASES_BY_NICHE.items():
        for phrase in phrases:
            print(f"[Twitter] [{niche}] Searching: {phrase}")
            results = search_recent(phrase, niche=niche, max_results=max_per_phrase, run_id=run_id)

            if not results and BEARER_TOKEN:
                phrases_failed += 1

            for r in results:
                if r["handle"] not in seen_handles:
                    seen_handles.add(r["handle"])
                    all_results.append(r)

    print(
        f"[Twitter] Total unique prospects: {len(all_results)} "
        f"({phrases_failed}/{phrase_count} phrase searches returned 0 results)"
    )

    if not all_results and BEARER_TOKEN:
        log_zero_results_alert(run_id, "Twitter")

    return all_results


def run_niche_search(niche_slug: str, run_id=None, max_per_phrase: int = 10) -> list[dict]:
    """
    Search X for a single niche — mirrors reddit.py's run_niche_search() signature
    so main.py can call it the same way.
    """
    phrases = SIGNAL_PHRASES_BY_NICHE.get(niche_slug, [])
    if not phrases:
        print(f"[Twitter] [{niche_slug}] No X signal phrases configured — skipping.")
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


if __name__ == "__main__":
    results = run_all_searches(max_per_phrase=5)
    for r in results[:3]:
        print(f"\n{r['name']} ({r['handle']}) [{r['niche']}]")
        print(f"Post: {r['post_text'][:100]}...")
        print(f"URL:  {r['post_url']}")
