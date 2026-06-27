"""
Fetch, cache, and check subreddit rules before posting.
Cache TTL: 24 hours per subreddit.
"""
import json, time, urllib.request
from datetime import datetime, timezone

_cache: dict[str, dict] = {}
_CACHE_TTL = 86400  # 24 hours


def _fetch_rules(subreddit: str) -> list[dict]:
    """Pull rules from Reddit public JSON endpoint."""
    url = f"https://www.reddit.com/r/{subreddit}/about/rules.json"
    req = urllib.request.Request(url, headers={"User-Agent": "AltusFlow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data.get("rules", [])
    except Exception:
        return []


def get_rules(subreddit: str) -> list[dict]:
    """Return cached or freshly fetched rules for a subreddit."""
    entry = _cache.get(subreddit)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["rules"]
    rules = _fetch_rules(subreddit)
    _cache[subreddit] = {"rules": rules, "ts": time.time()}
    return rules


def summarize_rules(subreddit: str) -> str:
    """Human-readable summary of a subreddit's rules for use in Claude prompt."""
    rules = get_rules(subreddit)
    if not rules:
        return f"No rules found for r/{subreddit} (or private/unavailable)."
    lines = []
    for i, r in enumerate(rules[:10], 1):
        short = r.get("short_name", "")
        desc  = r.get("description", "").strip().replace("\n", " ")[:200]
        lines.append(f"{i}. {short}" + (f": {desc}" if desc else ""))
    return "\n".join(lines)


def check_post_compliance(subreddit: str, title: str, body: str,
                           client_id: str = None) -> dict:
    """
    Check whether a post is likely compliant with subreddit rules.
    Uses Claude to cross-check. Returns:
      {ok: bool, violations: list[str], warnings: list[str], rules_summary: str}
    """
    import urllib.request as _req
    import os

    rules_text = summarize_rules(subreddit)
    if not rules_text or "No rules found" in rules_text:
        return {"ok": True, "violations": [], "warnings": [],
                "rules_summary": rules_text}

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return {"ok": True, "violations": [], "warnings": [],
                "rules_summary": rules_text, "skipped": True}

    prompt = f"""Subreddit r/{subreddit} rules:
{rules_text}

Post to check:
TITLE: {title[:300]}
BODY (first 800 chars): {body[:800]}

Respond with a JSON object only — no prose:
{{
  "ok": true or false,
  "violations": ["list of specific rule violations as short strings"],
  "warnings": ["list of minor concerns as short strings"]
}}

Be practical: flag clear violations only, not vague style concerns."""

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 400,
        "system": "You are a subreddit compliance checker. Reply with JSON only.",
        "messages": [{"role": "user", "content": prompt}],
    }).encode()

    try:
        req = _req.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with _req.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read())
        text_out = raw["content"][0]["text"].strip()
        # strip markdown fences if present
        if text_out.startswith("```"):
            text_out = text_out.split("```")[1]
            if text_out.startswith("json"):
                text_out = text_out[4:]
        result = json.loads(text_out)
        result["rules_summary"] = rules_text
        return result
    except Exception as e:
        return {"ok": True, "violations": [], "warnings": [str(e)],
                "rules_summary": rules_text, "error": True}
