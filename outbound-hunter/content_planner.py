"""
content_planner.py — Weekly content calendar from structured data.

Takes raw text from the user (macro indicators, news events, Google Sheets paste)
and generates a 7-day content plan: platform, subreddit, topic, angle, hook.
Each day can be drafted with one click from the Plan tab.
"""

import csv
import json
import io
import logging
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)


def parse_sheet_input(raw: str) -> str:
    """
    Accept CSV or tab-separated or plain text. Returns a cleaned summary string.
    Handles Google Sheets paste (tab-separated), CSV file, or free-form notes.
    """
    raw = raw.strip()
    if not raw:
        return ""

    # Try CSV parsing
    try:
        reader = csv.reader(io.StringIO(raw))
        rows = [r for r in reader if any(c.strip() for c in r)]
        if len(rows) > 1 and len(rows[0]) > 1:
            lines = []
            headers = rows[0]
            for row in rows[1:]:
                parts = [f"{h}: {v}" for h, v in zip(headers, row) if v.strip()]
                if parts:
                    lines.append(" | ".join(parts))
            return "\n".join(lines)
    except Exception:
        pass

    # Try tab-separated (Google Sheets paste)
    if "\t" in raw:
        try:
            rows = [line.split("\t") for line in raw.splitlines() if line.strip()]
            if rows:
                headers = rows[0]
                lines = []
                for row in rows[1:]:
                    parts = [f"{h.strip()}: {v.strip()}" for h, v in zip(headers, row) if v.strip()]
                    if parts:
                        lines.append(" | ".join(parts))
                return "\n".join(lines)
        except Exception:
            pass

    # Plain text — return as-is
    return raw


def generate_weekly_plan(
    sheet_data: str,
    subreddits: list = None,
    niche: str = "daytrading",
    days: int = 7,
    client_id: str = None,
) -> dict | None:
    """
    Generate a day-by-day content plan from structured macro/market data.

    sheet_data: raw paste from Google Sheets, CSV, or plain text
    subreddits: target subreddits (default: Daytrading + Futures)
    niche: trading niche for tone/language
    days: how many days to plan (default 7)
    """
    from value_post_generator import _call_claude, _REDDIT_SYSTEM

    cleaned = parse_sheet_input(sheet_data)
    if not cleaned:
        return None

    subs = subreddits or ["Daytrading", "Futures"]
    subs_text = ", ".join(f"r/{s}" for s in subs)

    today = datetime.now(timezone.utc)
    day_labels = [
        (today + timedelta(days=i)).strftime("%A %b %-d")
        for i in range(days)
    ]
    days_list = "\n".join(f"- Day {i+1} ({label})" for i, label in enumerate(day_labels))

    # Pull top post context for reference if available
    top_post_ctx = ""
    try:
        from reddit_top_posts import get_top_post_context
        ctxs = [get_top_post_context(s, client_id=client_id, limit=3) for s in subs[:2]]
        top_post_ctx = "\n\n".join(c for c in ctxs if c)
    except Exception:
        pass

    top_post_section = (
        f"\n\nFor reference — what's currently winning engagement in these communities:\n{top_post_ctx}"
        if top_post_ctx else ""
    )

    prompt = f"""You are planning a {days}-day trading content calendar for {subs_text}.

The user provided this macro data / market context / indicator sheet:
---
{cleaned[:4000]}
---
{top_post_section}

Generate a {days}-day content plan. The days to cover:
{days_list}

For EACH day:
1. Pick the most relevant macro event, indicator, or theme from the data
2. Connect it to a specific pain or mistake {niche} traders make in that context
3. Design ONE post that gives the community genuine value about this

Requirements:
- Each day must have a DIFFERENT angle — no two days address the same pain
- Alternate platforms: mix Reddit posts and X threads across the week
- Be specific about which subreddit fits best for each Reddit post
- The hook MUST be specific and punchy — not generic like "market volatility tips"
- content_type must be "insight_digest", "resource_post", or "x_thread"

Return ONLY valid JSON, no markdown:
{{"plan": [
  {{
    "day_label": "Monday Jun 23",
    "platform": "reddit",
    "subreddit": "Daytrading",
    "topic": "Fed meeting day volatility",
    "angle": "Most traders don't realize FOMC days have a predictable 10:30 fade that destroys entries made at 9:35",
    "hook": "Fed day is the #1 account killer in r/Daytrading. Here's the pattern nobody talks about.",
    "content_type": "insight_digest"
  }},
  ...
]}}"""

    text = _call_claude(prompt, max_tokens=2500, system=_REDDIT_SYSTEM)
    if not text:
        return None

    try:
        clean = text.strip().lstrip("`").rstrip("`")
        if clean.startswith("json"):
            clean = clean[4:].strip()
        result = json.loads(clean)
        plan_items = result.get("plan", [])
        if not plan_items:
            return None

        plan = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "niche":        niche,
            "subreddits":   subs,
            "days":         days,
            "plan":         plan_items,
        }

        # Persist to DB
        try:
            from database import save_content_plan
            save_content_plan(
                plan_json   = json.dumps(plan),
                source_data = cleaned[:2000],
                niche       = niche,
                client_id   = client_id,
            )
        except Exception as e:
            log.warning(f"[content_planner] db save error: {e}")

        return plan

    except Exception as e:
        log.warning(f"[content_planner] parse error: {e} — raw: {text[:300]}")
        return None
