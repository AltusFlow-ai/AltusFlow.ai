"""
scrapers/linkedin.py
Searches LinkedIn for prospects posting signal phrases via Apify.

Signal phrases are organized by niche — each prospect is tagged with the
niche of the phrase that matched it. The niche flows through to the DB
and is used to filter the batch-confirm and digest views.

Apify actor used: apify/linkedin-post-search-scraper
Free tier: 5 actor runs/month — batch your queries wisely.

Error handling:
  - Actor start failure       → CRITICAL (token or API error)
  - Actor FAILED / ABORTED    → CRITICAL (with direct Apify debug URL)
  - Actor TIMED-OUT           → CRITICAL (with fix suggestion)
  - Transient poll error      → WARNING  (retried on next poll cycle)
  - Results fetch failure     → CRITICAL
  - No token                  → CRITICAL (misconfiguration)
  - Zero total results        → CRITICAL alert after all queries complete
"""

import os
import json
import time
import urllib.request
import urllib.error

APIFY_TOKEN      = os.environ.get("APIFY_API_TOKEN", "")
ACTOR_ID         = "apify~linkedin-post-search-scraper"
POLL_INTERVAL    = 5    # seconds between status polls
MAX_POLL_SECONDS = 180  # 3-minute timeout per actor run


def _build_queries_by_niche(niche_slugs=None):
    """
    Build {niche_slug: [queries]} from the niche libraries.
    If niche_slugs is None, includes all registered niches.
    """
    from scrapers.niches import ALL_NICHES, get_linkedin_queries
    niches = ALL_NICHES if not niche_slugs else [
        n for n in ALL_NICHES if n.NICHE_SLUG in niche_slugs
    ]
    return {n.NICHE_SLUG: get_linkedin_queries(n.NICHE_SLUG) for n in niches}


def run_apify_actor(query, niche, max_results=20, run_id=None):
    """
    Run the Apify LinkedIn scraper for one search query.
    Returns a list of prospect dicts tagged with niche, or [] on any failure.
    All failures are logged via error_logger — this function never raises.
    """
    from error_logger import log_pipeline_error, WARNING, CRITICAL

    if not APIFY_TOKEN:
        log_pipeline_error(
            run_id, "linkedin_scraper",
            "APIFY_API_TOKEN is not set — LinkedIn search skipped entirely.",
            CRITICAL,
            suggested_fix=(
                "Add APIFY_API_TOKEN to your .env file. "
                "Get a token at console.apify.com > Settings > Integrations."
            ),
        )
        return []

    # ── Start the actor run ───────────────────────────────────────────────────
    start_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}"
    payload   = json.dumps({
        "searchQuery": query,
        "maxResults":  max_results,
        "proxyConfig": {"useApifyProxy": True},
    }).encode()

    apify_run_id = None
    try:
        req = urllib.request.Request(
            start_url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            run_data     = json.loads(r.read())
        apify_run_id = run_data["data"]["id"]
        print(f"[LinkedIn] [{niche}] Actor run started: {apify_run_id}")

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        fix  = (
            "APIFY_API_TOKEN is invalid or your monthly quota is exhausted. "
            "Check at console.apify.com/account/usage."
            if e.code in (401, 403)
            else f"Apify API returned HTTP {e.code}. Check https://status.apify.com."
        )
        log_pipeline_error(
            run_id, "linkedin_scraper",
            f"Failed to start Apify actor for '{query[:60]}': HTTP {e.code} — {body}",
            CRITICAL, suggested_fix=fix,
        )
        return []

    except Exception as e:
        log_pipeline_error(
            run_id, "linkedin_scraper",
            f"Failed to start Apify actor for '{query[:60]}': {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []

    # ── Poll for completion ───────────────────────────────────────────────────
    max_polls   = MAX_POLL_SECONDS // POLL_INTERVAL
    status_data = None

    for attempt in range(max_polls):
        time.sleep(POLL_INTERVAL)
        try:
            status_url = f"https://api.apify.com/v2/actor-runs/{apify_run_id}?token={APIFY_TOKEN}"
            req = urllib.request.Request(status_url)
            with urllib.request.urlopen(req, timeout=15) as r:
                status_data = json.loads(r.read())

            actor_status = status_data["data"]["status"]

            if actor_status == "SUCCEEDED":
                break

            if actor_status in ("FAILED", "ABORTED", "TIMED-OUT"):
                debug_url = f"https://console.apify.com/view/runs/{apify_run_id}"
                log_pipeline_error(
                    run_id, "linkedin_scraper",
                    f"Apify actor {actor_status} for query '{query[:60]}'. Debug: {debug_url}",
                    CRITICAL,
                    suggested_fix=(
                        f"Open {debug_url} to see the actor error log. "
                        "Common causes: query too specific (no LinkedIn results), "
                        "Apify proxy error, or monthly run quota reached."
                    ),
                )
                return []

        except Exception as e:
            log_pipeline_error(
                run_id, "linkedin_scraper",
                f"Status poll error for Apify run {apify_run_id} "
                f"(attempt {attempt + 1}/{max_polls}): {type(e).__name__}: {e}",
                WARNING,
            )
            continue
    else:
        # for/else: loop completed max_polls iterations without a SUCCEEDED break
        log_pipeline_error(
            run_id, "linkedin_scraper",
            f"Apify actor timed out after {MAX_POLL_SECONDS}s for query '{query[:60]}'.",
            CRITICAL,
            suggested_fix=(
                f"Increase MAX_POLL_SECONDS in scrapers/linkedin.py (currently {MAX_POLL_SECONDS}s), "
                "or reduce max_results per query to speed up actor runs. "
                f"Check run status at console.apify.com/view/runs/{apify_run_id}."
            ),
        )
        return []

    # Guard: status_data could be None if every poll attempt raised an exception
    if status_data is None:
        log_pipeline_error(
            run_id, "linkedin_scraper",
            f"No valid status data received for Apify run {apify_run_id} after polling.",
            CRITICAL,
        )
        return []

    # ── Fetch results ─────────────────────────────────────────────────────────
    try:
        dataset_id  = status_data["data"]["defaultDatasetId"]
        results_url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={APIFY_TOKEN}&format=json"
        )
        req = urllib.request.Request(results_url)
        with urllib.request.urlopen(req, timeout=30) as r:
            items = json.loads(r.read())
    except Exception as e:
        log_pipeline_error(
            run_id, "linkedin_scraper",
            f"Failed to fetch Apify results for query '{query[:60]}': {type(e).__name__}: {e}",
            CRITICAL,
            suggested_fix=(
                "The actor run succeeded but results could not be fetched. "
                f"Try fetching manually at console.apify.com/view/runs/{apify_run_id}."
            ),
        )
        return []

    results = []
    for item in items:
        author    = item.get("author", {})
        name      = author.get("name", "")
        handle    = author.get("publicIdentifier", "")
        title     = author.get("headline", "")
        company   = (
            author.get("company", {}).get("name", "")
            if isinstance(author.get("company"), dict)
            else ""
        )
        post_text = item.get("text", "") or item.get("commentary", "")
        post_url  = item.get("postUrl", f"https://linkedin.com/in/{handle}")
        post_date = str(item.get("postedAt", "") or item.get("date", ""))

        if not post_text or not handle:
            continue

        results.append({
            "platform":     "linkedin",
            "niche":        niche,
            "handle":       handle,
            "name":         name,
            "title":        title,
            "company":      company,
            "profile_url":  f"https://linkedin.com/in/{handle}",
            "post_text":    post_text,
            "post_url":     post_url,
            "post_date":    post_date,
            "signal_phrase": query,
        })

    print(f"[LinkedIn] [{niche}] {len(results)} results for '{query}'")
    return results


def run_all_searches(max_per_query=10, run_id=None, niche_slugs=None):
    """
    Run all LinkedIn queries across all niches (or a specific subset).
    Returns combined unique results, each tagged with niche_segment.
    If total results are zero after all queries, fires a critical alert.

    Args:
        niche_slugs: list of niche slugs to scan, or None for all niches.
    """
    from error_logger import log_pipeline_error, log_zero_results_alert, CRITICAL

    if not APIFY_TOKEN:
        log_pipeline_error(
            run_id, "linkedin_scraper",
            "APIFY_API_TOKEN not set — LinkedIn search skipped entirely.",
            CRITICAL,
            suggested_fix=(
                "Add APIFY_API_TOKEN to your .env file. "
                "Get a token at console.apify.com > Settings > Integrations."
            ),
        )
        return []

    queries_by_niche = _build_queries_by_niche(niche_slugs)
    all_results      = []
    seen_handles     = set()

    for niche_slug, queries in queries_by_niche.items():
        for query in queries:
            print(f"\n[LinkedIn] [{niche_slug}] Searching: {query}")
            results = run_apify_actor(
                query, niche=niche_slug, max_results=max_per_query, run_id=run_id
            )
            for r in results:
                r["niche_segment"] = niche_slug  # canonical field for 5-niche system
                if r["handle"] and r["handle"] not in seen_handles:
                    seen_handles.add(r["handle"])
                    all_results.append(r)

    print(f"\n[LinkedIn] Total unique prospects: {len(all_results)}")

    if not all_results and APIFY_TOKEN:
        log_zero_results_alert(run_id, "LinkedIn")

    return all_results


def run_niche_search(niche_slug, max_per_query=10, run_id=None):
    """Convenience wrapper — run LinkedIn for a single niche only."""
    return run_all_searches(
        max_per_query=max_per_query, run_id=run_id, niche_slugs=[niche_slug]
    )


if __name__ == "__main__":
    results = run_all_searches(max_per_query=5)
    for r in results[:3]:
        print(f"\n{r['name']} | {r['title']} | {r['company']} [{r['niche']}]")
        print(f"Post: {r['post_text'][:120]}...")
        print(f"URL:  {r['profile_url']}")
