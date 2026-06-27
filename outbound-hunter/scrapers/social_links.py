"""
scrapers/social_links.py
LinkedIn + Facebook "jump link" mode — no Apify required.

Instead of scraping post content, generates direct deep-search URLs
pre-filtered to each signal phrase + last 24 hours. Each result is a
prospect card with an "Open on LinkedIn →" or "Open on Facebook →" button.
The user is already logged in their browser — one click and they're on the post.

This runs automatically when APIFY_API_TOKEN is NOT set.
When Apify IS configured, this is skipped in favour of the full scraper.

No API keys required. No rate limits. Completely free.
"""

import os
import urllib.parse
from datetime import datetime, timezone

LINKEDIN_ENABLED = os.environ.get("LINKEDIN_LINKS_ENABLED", "true").lower() != "false"
FACEBOOK_ENABLED = os.environ.get("FACEBOOK_LINKS_ENABLED", "true").lower() != "false"


# ── URL builders ──────────────────────────────────────────────────────────────

def _linkedin_search_url(phrase):
    """
    Deep-link to LinkedIn content search, filtered to past week.
    Opens the user's native LinkedIn feed search — no auth needed from our side.
    """
    params = urllib.parse.urlencode({
        "keywords": phrase,
        "datePosted": "past-week",
        "sortBy": "date_posted",
        "origin": "FACETED_SEARCH",
    })
    return f"https://www.linkedin.com/search/results/content/?{params}"


def _facebook_search_url(phrase, group_name=None):
    """
    Deep-link to Facebook post search. If a group name is provided, scopes
    to that group's search. Otherwise searches all of Facebook.
    """
    q = urllib.parse.quote_plus(phrase)
    if group_name:
        slug = group_name.lower().replace(" ", "").replace("-", "")
        return f"https://www.facebook.com/groups/{slug}/search/?q={q}"
    return f"https://www.facebook.com/search/posts/?q={q}"


# ── Prospect builder ──────────────────────────────────────────────────────────

def _make_prospect(platform, phrase, niche_slug, url, label, group_name=None):
    """Build a minimal prospect dict for a search-link result."""
    handle = f"search_{platform}_{urllib.parse.quote(phrase[:30], safe='')}"
    return {
        "handle":          handle,
        "name":            f"{label} — {phrase[:60]}",
        "platform":        platform,
        "niche":           niche_slug,
        "niche_segment":   niche_slug,
        "signal_phrase":   phrase,
        "post_text":       f'Signal phrase detected: "{phrase}". Click to open {label} search and find the post.',
        "profile_url":     url,
        "outreach_method": "open_in_browser",
        "platform_label":  label,
        "group_name":      group_name or "",
        "source":          f"{platform}_search_link",
        "scraped_at":      datetime.now(timezone.utc).isoformat(),
        "icp_score":       5,
        "icp_notes":       f"Search-link prospect — score pending manual review",
    }


# ── Main entry points ─────────────────────────────────────────────────────────

def run_linkedin_links(niche_slug, run_id=None):
    """
    Generate LinkedIn search jump links for every signal phrase in this niche.
    Returns a list of prospect dicts (one per phrase).
    Skipped if APIFY_API_TOKEN is set (full scraper takes over).
    """
    if os.environ.get("APIFY_API_TOKEN"):
        return []  # Full Apify scraper handles LinkedIn when token is present
    if not LINKEDIN_ENABLED:
        return []

    try:
        from scrapers.niches import get_niche
        niche = get_niche(niche_slug)
        if not niche:
            return []
        queries = getattr(niche, "LINKEDIN_QUERIES", [])
        if not queries:
            return []

        results = []
        for phrase in queries:
            url = _linkedin_search_url(phrase)
            results.append(_make_prospect("linkedin", phrase, niche_slug, url, "LinkedIn"))

        print(f"[{niche_slug}] LinkedIn links: {len(results)} search jump links generated")
        return results

    except Exception as e:
        import sys
        print(f"[{niche_slug}] LinkedIn links error: {e}", file=sys.stderr)
        return []


def run_facebook_links(niche_slug, run_id=None):
    """
    Generate Facebook group search jump links for every signal phrase + group combo.
    Returns a list of prospect dicts.
    Skipped if APIFY_API_TOKEN is set.
    """
    if os.environ.get("APIFY_API_TOKEN"):
        return []
    if not FACEBOOK_ENABLED:
        return []

    try:
        from scrapers.niches import get_niche
        niche = get_niche(niche_slug)
        if not niche:
            return []
        groups  = getattr(niche, "FACEBOOK_GROUPS", [])
        phrases = getattr(niche, "SIGNAL_PHRASES", [])
        if not groups or not phrases:
            return []

        results = []
        # One jump link per group × top 3 signal phrases (avoid flooding queue)
        for group in groups[:5]:
            for phrase in phrases[:3]:
                url = _facebook_search_url(phrase, group)
                results.append(_make_prospect(
                    "facebook", phrase, niche_slug, url, f"Facebook · {group}", group_name=group
                ))

        print(f"[{niche_slug}] Facebook links: {len(results)} search jump links generated")
        return results

    except Exception as e:
        import sys
        print(f"[{niche_slug}] Facebook links error: {e}", file=sys.stderr)
        return []
