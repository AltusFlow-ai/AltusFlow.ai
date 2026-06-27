"""
scrapers/facebook.py
Scans Facebook Groups for signal posts using the Apify Facebook Groups Scraper.

Actor: apify/facebook-groups-scraper
Docs: https://apify.com/apify/facebook-groups-scraper

For each niche, scans the niche's FACEBOOK_GROUPS list for posts matching
SIGNAL_PHRASES. Returns posts with author, group name, post URL, and date.

Error handling mirrors linkedin.py — all failures log via error_logger,
this function never raises.
"""

import os
import json
import time
import urllib.request
import urllib.error

APIFY_TOKEN      = os.environ.get("APIFY_API_TOKEN", "")
ACTOR_ID         = "apify~facebook-groups-scraper"
POLL_INTERVAL    = 8     # FB scraper is slower than LinkedIn
MAX_POLL_SECONDS = 300   # 5-minute timeout per actor run
MAX_POSTS_PER_GROUP = int(os.environ.get("FB_POSTS_PER_GROUP", "50"))


def _build_search_url(group_name, query):
    """Facebook group search URL — Apify uses the group name to locate and scan."""
    return f"https://www.facebook.com/groups/{group_name.lower().replace(' ', '')}"


def run_apify_actor(group_name, signal_phrase, niche_slug, run_id=None):
    """
    Run the Apify Facebook Groups scraper for one group + signal phrase.
    Returns a list of prospect dicts, or [] on any failure.
    """
    from error_logger import log_pipeline_error, WARNING, CRITICAL

    if not APIFY_TOKEN:
        log_pipeline_error(
            run_id, "facebook_scraper",
            "APIFY_API_TOKEN is not set — Facebook search skipped.",
            CRITICAL,
            suggested_fix="Add APIFY_API_TOKEN to your .env file.",
        )
        return []

    start_url = f"https://api.apify.com/v2/acts/{ACTOR_ID}/runs?token={APIFY_TOKEN}"
    payload = json.dumps({
        "startUrls": [
            {"url": f"https://www.facebook.com/groups/{group_name}/"}
        ],
        "searchQuery": signal_phrase,
        "maxPosts":    MAX_POSTS_PER_GROUP,
        "proxyConfig": {"useApifyProxy": True, "apifyProxyGroups": ["RESIDENTIAL"]},
    }).encode()

    apify_run_id = None
    try:
        req = urllib.request.Request(
            start_url, data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            run_data = json.loads(r.read())
        apify_run_id = run_data["data"]["id"]
        print(f"[Facebook] [{niche_slug}] Actor started: {apify_run_id} | {group_name}")

    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:300]
        log_pipeline_error(
            run_id, "facebook_scraper",
            f"Failed to start Facebook actor for '{group_name}': HTTP {e.code} — {body}",
            CRITICAL,
            suggested_fix=(
                "APIFY_API_TOKEN may be invalid or quota exhausted. "
                "Check console.apify.com/account/usage."
                if e.code in (401, 403)
                else f"Apify API returned HTTP {e.code}."
            ),
        )
        return []
    except Exception as e:
        log_pipeline_error(
            run_id, "facebook_scraper",
            f"Failed to start Facebook actor for '{group_name}': {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []

    # ── Poll for completion ───────────────────────────────────────────────────
    max_polls = MAX_POLL_SECONDS // POLL_INTERVAL

    for attempt in range(max_polls):
        time.sleep(POLL_INTERVAL)
        try:
            status_url = f"https://api.apify.com/v2/actor-runs/{apify_run_id}?token={APIFY_TOKEN}"
            with urllib.request.urlopen(urllib.request.Request(status_url), timeout=15) as r:
                status_data = json.loads(r.read())

            actor_status = status_data["data"]["status"]
            if actor_status == "SUCCEEDED":
                break
            if actor_status in ("FAILED", "ABORTED", "TIMED-OUT"):
                debug_url = f"https://console.apify.com/view/runs/{apify_run_id}"
                log_pipeline_error(
                    run_id, "facebook_scraper",
                    f"Facebook actor {actor_status} for group '{group_name}'. Debug: {debug_url}",
                    CRITICAL,
                    suggested_fix=(
                        f"Check {debug_url}. Facebook groups require residential proxies. "
                        "Ensure proxyConfig includes RESIDENTIAL group."
                    ),
                )
                return []

        except Exception as e:
            log_pipeline_error(
                run_id, "facebook_scraper",
                f"Poll error for Facebook run {apify_run_id} (attempt {attempt+1}): "
                f"{type(e).__name__}: {e}",
                WARNING,
            )
            continue
    else:
        log_pipeline_error(
            run_id, "facebook_scraper",
            f"Facebook actor timed out after {MAX_POLL_SECONDS}s for group '{group_name}'.",
            CRITICAL,
            suggested_fix=(
                f"Increase FB_POSTS_PER_GROUP env var or MAX_POLL_SECONDS in scrapers/facebook.py. "
                f"Check run at console.apify.com/view/runs/{apify_run_id}."
            ),
        )
        return []

    # ── Fetch results ─────────────────────────────────────────────────────────
    try:
        dataset_id  = status_data["data"]["defaultDatasetId"]
        results_url = (
            f"https://api.apify.com/v2/datasets/{dataset_id}/items"
            f"?token={APIFY_TOKEN}&format=json"
        )
        with urllib.request.urlopen(urllib.request.Request(results_url), timeout=30) as r:
            items = json.loads(r.read())
    except Exception as e:
        log_pipeline_error(
            run_id, "facebook_scraper",
            f"Failed to fetch Facebook results for '{group_name}': {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []

    # ── Parse results ─────────────────────────────────────────────────────────
    from scrapers.niches import get_signal_phrases
    signal_phrases = get_signal_phrases(niche_slug)

    results = []
    for item in items:
        post_text = (
            item.get("text") or item.get("body") or
            item.get("message") or item.get("postText") or ""
        )
        if not post_text:
            continue

        # Filter to posts containing a signal phrase
        post_lower = post_text.lower()
        matched_phrase = None
        for phrase in signal_phrases:
            if phrase.lower() in post_lower:
                matched_phrase = phrase
                break
        if not matched_phrase and signal_phrase.lower() not in post_lower:
            continue

        author     = item.get("author", {}) or {}
        name       = author.get("name", "") or item.get("authorName", "")
        profile_id = author.get("id", "") or item.get("authorId", "")
        handle     = profile_id or name.lower().replace(" ", "_") or "unknown"
        post_url   = item.get("url") or item.get("postUrl") or ""
        post_date  = str(item.get("date") or item.get("timestamp") or "")

        if not name:
            continue

        results.append({
            "platform":      "facebook",
            "niche":         niche_slug,
            "niche_segment": niche_slug,
            "handle":        handle,
            "name":          name,
            "title":         "",
            "company":       "",
            "profile_url":   f"https://facebook.com/{profile_id}" if profile_id else "",
            "post_text":     post_text,
            "post_url":      post_url,
            "post_date":     post_date,
            "signal_phrase": matched_phrase or signal_phrase,
            "group_name":    group_name,
            "outreach_method": "direct",
        })

    print(f"[Facebook] [{niche_slug}] {len(results)} signal posts from '{group_name}'")
    return results


def run_niche_search(niche_slug, run_id=None):
    """
    Scan all Facebook groups for a single niche.
    Returns combined unique results from all groups.
    """
    from scrapers.niches import get_facebook_groups, get_signal_phrases
    from error_logger import log_pipeline_error, CRITICAL

    if not APIFY_TOKEN:
        log_pipeline_error(
            run_id, "facebook_scraper",
            "APIFY_API_TOKEN not set — Facebook search skipped.",
            CRITICAL,
            suggested_fix="Add APIFY_API_TOKEN to your .env file.",
        )
        return []

    groups          = get_facebook_groups(niche_slug)
    signal_phrases  = get_signal_phrases(niche_slug)
    all_results     = []
    seen_handles    = set()

    if not groups:
        print(f"[Facebook] [{niche_slug}] No groups configured — skipping.")
        return []

    # Use the first 3 signal phrases per group to keep Apify usage reasonable
    primary_phrases = signal_phrases[:3]

    for group in groups:
        for phrase in primary_phrases:
            results = run_apify_actor(group, phrase, niche_slug, run_id=run_id)
            for r in results:
                key = (r["handle"], r.get("post_url", ""))
                if key not in seen_handles:
                    seen_handles.add(key)
                    all_results.append(r)

    print(f"[Facebook] [{niche_slug}] Total unique: {len(all_results)}")
    return all_results


def run_all_searches(run_id=None, niche_slugs=None):
    """
    Scan all niches (or a subset) across their Facebook groups.
    Returns combined unique results across all niches.
    """
    from scrapers.niches import ALL_NICHES
    from error_logger import log_pipeline_error, log_zero_results_alert, CRITICAL

    if not APIFY_TOKEN:
        log_pipeline_error(
            run_id, "facebook_scraper",
            "APIFY_API_TOKEN not set — Facebook search skipped entirely.",
            CRITICAL,
            suggested_fix="Add APIFY_API_TOKEN to your .env file.",
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
            key = (r["handle"], r.get("post_url", ""))
            if key not in seen_handles:
                seen_handles.add(key)
                all_results.append(r)

    print(f"\n[Facebook] Total unique prospects across all niches: {len(all_results)}")

    if not all_results and APIFY_TOKEN:
        log_zero_results_alert(run_id, "Facebook")

    return all_results


if __name__ == "__main__":
    results = run_niche_search("altusflow-own", run_id=None)
    for r in results[:3]:
        print(f"\n{r['name']} | {r['group_name']}")
        print(f"Post: {r['post_text'][:120]}...")
        print(f"Signal: {r['signal_phrase']}")
