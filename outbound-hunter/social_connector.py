"""
social_connector.py
Polymorphic omnichannel lead fetcher.

Factory pattern: fetch_leads(source, query, pod_id) dispatches to the right
actor — Reddit or Twitter/X — via ScrapeBadger when configured, falling back
to the native scrapers (PRAW / Twitter API v2) if not.

Both paths output the same normalised schema so qualify.py, drafter.py, and
database.insert_prospect() need zero changes.

Normalised output schema
------------------------
{
    "lead_text":    str,   # post body or tweet text
    "user_handle":  str,   # "u/username" or "@handle"
    "url":          str,   # permalink to the post / tweet
    "timestamp":    str,   # ISO-8601 UTC string
    "source":       str,   # "reddit" | "twitter"
    # downstream-compatible fields (map 1:1 to prospects table)
    "platform":     str,   # same as source
    "handle":       str,
    "name":         str,
    "profile_url":  str,
    "post_text":    str,
    "post_url":     str,
    "post_date":    str,
    "signal_phrase": str,
    "niche":        str,
    "niche_segment": str,
    "outreach_method": str,
    "upvote_score": int,
}
"""

import os
import json
import logging
import urllib.request
import urllib.parse
import urllib.error

logger = logging.getLogger(__name__)

SCRAPEBADGER_API_KEY  = os.environ.get("SCRAPEBADGER_API_KEY", "")
SCRAPEBADGER_BASE_URL = os.environ.get("SCRAPEBADGER_BASE_URL", "https://api.scrapebadger.io/v1")


class SocialConnector:
    """
    Omnichannel lead fetcher with a factory pattern.

    Usage:
        connector = SocialConnector()
        leads = connector.fetch_leads(
            source   = "twitter",
            query    = '"pipeline dried up" financial advisor',
            pod_id   = "financial-advisors",
        )
        # leads → list of normalised dicts, ready for qualify.py
    """

    def fetch_leads(self, source: str, query: str, pod_id: str = "") -> list[dict]:
        """
        Fetch and normalise leads from the given source.
        Returns [] on any failure — never raises.

        source: 'reddit' | 'twitter'
        query:  signal phrase or search string
        pod_id: niche slug used to tag each lead
        """
        source = source.lower().strip()
        try:
            if source == "reddit":
                raw = self._fetch_reddit(query)
            elif source in ("twitter", "x"):
                raw   = self._fetch_twitter(query)
                source = "twitter"
            else:
                logger.warning("SocialConnector: unknown source '%s'", source)
                return []
        except Exception as exc:
            logger.error("SocialConnector.fetch_leads(%s) failed: %s", source, exc)
            return []

        return [
            n for item in raw
            if item
            for n in [self._normalize(item, source, query, pod_id)]
            if n
        ]

    # ── Reddit ────────────────────────────────────────────────────────────────

    def _fetch_reddit(self, query: str) -> list[dict]:
        """ScrapeBadger first, PRAW fallback."""
        if SCRAPEBADGER_API_KEY:
            results = self._scrapebadger("reddit/search", {"query": query, "limit": 25})
            if results is not None:
                return results
        return self._praw_fallback(query)

    def _praw_fallback(self, query: str) -> list[dict]:
        try:
            from scrapers.reddit import get_reddit_client, _matches_signal, _post_to_prospect
            reddit = get_reddit_client()
            if not reddit:
                return []
            out = []
            for sub in reddit.subreddit("all").search(query, limit=20, sort="new"):
                matched = _matches_signal(sub, [query])
                if matched:
                    out.append(_post_to_prospect(sub, "", query, matched))
            return out
        except Exception as exc:
            logger.warning("PRAW fallback failed: %s", exc)
            return []

    # ── Twitter / X ───────────────────────────────────────────────────────────

    def _fetch_twitter(self, query: str) -> list[dict]:
        """ScrapeBadger first, Twitter API v2 fallback."""
        if SCRAPEBADGER_API_KEY:
            results = self._scrapebadger("twitter/search", {"query": query, "limit": 20})
            if results is not None:
                return results
        return self._twitter_api_fallback(query)

    def _twitter_api_fallback(self, query: str) -> list[dict]:
        try:
            from scrapers.twitter import search_recent
            return search_recent(query, niche="", max_results=20)
        except Exception as exc:
            logger.warning("Twitter API fallback failed: %s", exc)
            return []

    # ── ScrapeBadger ──────────────────────────────────────────────────────────

    def _scrapebadger(self, endpoint: str, payload: dict) -> list[dict] | None:
        """
        POST to ScrapeBadger and return the items list.
        Returns None (not []) so callers know to try the native fallback.
        """
        url  = f"{SCRAPEBADGER_BASE_URL.rstrip('/')}/{endpoint}"
        body = json.dumps(payload).encode()
        req  = urllib.request.Request(
            url,
            data=body,
            headers={
                "Authorization": f"Bearer {SCRAPEBADGER_API_KEY}",
                "Content-Type":  "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            return data.get("items") or data.get("results") or []
        except urllib.error.HTTPError as exc:
            logger.warning("ScrapeBadger /%s → HTTP %s", endpoint, exc.code)
            return None
        except Exception as exc:
            logger.warning("ScrapeBadger /%s → %s", endpoint, exc)
            return None

    # ── Normaliser ────────────────────────────────────────────────────────────

    def _normalize(self, item: dict, source: str, signal_phrase: str, niche: str) -> dict:
        if source == "reddit":
            return self._normalize_reddit(item, signal_phrase, niche)
        return self._normalize_twitter(item, signal_phrase, niche)

    def _normalize_reddit(self, item: dict, signal_phrase: str, niche: str) -> dict:
        """
        Handles both ScrapeBadger shape and PRAW-converted shape.
        ScrapeBadger: {text, author, url, created_utc, title, subreddit}
        PRAW-converted: {post_text, handle, post_url, post_date, subreddit, ...}
        """
        handle    = item.get("handle") or item.get("author") or "unknown"
        handle    = str(handle).replace("u/", "")
        lead_text = item.get("post_text") or item.get("text") or item.get("selftext") or ""
        title     = item.get("title", "")
        if title and title not in lead_text:
            lead_text = f"{title}\n\n{lead_text}".strip()
        url       = item.get("post_url") or item.get("url") or ""
        ts        = str(item.get("post_date") or item.get("created_utc") or "")
        subreddit = item.get("subreddit", "")

        return {
            "lead_text":          lead_text,
            "user_handle":        f"u/{handle}",
            "url":                url,
            "timestamp":          ts,
            "source":             "reddit",
            "platform":           "reddit",
            "handle":             f"u/{handle}",
            "reddit_username":    handle,
            "name":               handle,
            "title":              "",
            "company":            "",
            "profile_url":        item.get("profile_url") or f"https://reddit.com/user/{handle}",
            "post_text":          lead_text,
            "post_url":           url,
            "post_date":          ts,
            "signal_phrase":      signal_phrase,
            "niche":              niche,
            "niche_segment":      niche,
            "group_name":         f"r/{subreddit}" if subreddit else "",
            "subreddit":          subreddit,
            "outreach_method":    "find_linkedin",
            "linkedin_search_url": f"https://www.linkedin.com/search/results/people/?keywords={handle}",
            "upvote_score":       int(item.get("upvote_score") or item.get("score") or 0),
        }

    def _normalize_twitter(self, item: dict, signal_phrase: str, niche: str) -> dict:
        """
        Handles both ScrapeBadger shape and native twitter.py shape.
        ScrapeBadger: {text, username, name, url, created_at, user_bio}
        Native:       {handle, name, post_text, post_url, post_date, platform}
        """
        handle    = str(item.get("handle") or item.get("username") or "unknown").lstrip("@")
        lead_text = item.get("post_text") or item.get("text") or ""
        url       = item.get("post_url") or item.get("url") or f"https://twitter.com/{handle}"
        ts        = str(item.get("post_date") or item.get("created_at") or "")
        name      = item.get("name") or handle

        return {
            "lead_text":       lead_text,
            "user_handle":     f"@{handle}",
            "url":             url,
            "timestamp":       ts,
            "source":          "twitter",
            "platform":        "twitter",
            "handle":          f"@{handle}",
            "name":            name,
            "title":           item.get("title", ""),
            "company":         item.get("company", ""),
            "profile_url":     item.get("profile_url") or f"https://twitter.com/{handle}",
            "post_text":       lead_text,
            "post_url":        url,
            "post_date":       ts,
            "signal_phrase":   signal_phrase,
            "niche":           niche,
            "niche_segment":   niche,
            "outreach_method": "direct",
            "upvote_score":    0,
        }


# ── Convenience function ───────────────────────────────────────────────────────

_connector = SocialConnector()


def fetch_leads(source: str, query: str, pod_id: str = "") -> list[dict]:
    """Module-level shortcut: fetch_leads('twitter', '"pipeline dried up"', 'financial-advisors')"""
    return _connector.fetch_leads(source, query, pod_id)
