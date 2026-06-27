"""
market_pulse.py
Aggregates market insights from Reddit and Twitter into a single intelligence view.

Groups pain points by BOTH topic and source so the dashboard can surface:
  "Reddit users complain about X, while Twitter users are asking about Y."

Call get_market_pulse() for the /api/market-pulse widget endpoint.
"""

import os
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


def get_market_pulse(pod_slug: str = None, source: str = None) -> dict:
    """
    Return current market intelligence for the MarketPulseWidget.

    source: 'reddit' | 'twitter' | None (both combined)

    Return shape:
    {
        pain_points:         [{topic, count, sources, avg_intent, severity, cross_channel}]
        daily_hook:          str    # Claude-written cross-source outreach opener
        competitor_mentions: [{name, mentions, sources}]
        by_source: {
            reddit:  {count, pain_points}
            twitter: {count, pain_points}
        }
        total_signals: int
        updated_at:    str
    }
    """
    try:
        from database import get_market_pulse_data
        rows = get_market_pulse_data(pod_slug=pod_slug, source=source)
    except Exception as exc:
        logger.error("get_market_pulse DB error: %s", exc)
        rows = []

    if not rows:
        return _empty_pulse()

    topic_map      = defaultdict(lambda: {"count": 0, "sources": set(), "intent_scores": []})
    competitor_map = defaultdict(lambda: {"count": 0, "sources": set()})
    by_source      = {
        "reddit":  {"count": 0, "pain_points": []},
        "twitter": {"count": 0, "pain_points": []},
    }

    for row in rows:
        src   = (row.get("source") or row.get("platform") or "reddit").lower()
        pain  = (row.get("primary_pain_point") or "").strip()
        score = float(row.get("intent_score") or 0)

        try:
            raw         = row.get("competitor_mentions") or "[]"
            competitors = json.loads(raw) if isinstance(raw, str) else (raw or [])
        except Exception:
            competitors = []

        if pain:
            topic_map[pain]["count"] += 1
            topic_map[pain]["sources"].add(src)
            topic_map[pain]["intent_scores"].append(score)

        for comp in competitors:
            if comp and isinstance(comp, str):
                competitor_map[comp]["count"] += 1
                competitor_map[comp]["sources"].add(src)

        bucket = by_source.get(src) or by_source["reddit"]
        bucket["count"] += 1
        if pain and pain not in bucket["pain_points"]:
            bucket["pain_points"].append(pain)

    # Ranked pain points
    pain_points = []
    for topic, data in sorted(topic_map.items(), key=lambda x: -x[1]["count"]):
        scores    = data["intent_scores"]
        avg_score = sum(scores) / len(scores) if scores else 0
        pain_points.append({
            "topic":        topic,
            "count":        data["count"],
            "sources":      sorted(data["sources"]),
            "avg_intent":   round(avg_score, 2),
            "severity":     _severity(data["count"], avg_score),
            "cross_channel": len(data["sources"]) > 1,
        })

    competitors_list = [
        {"name": c, "mentions": d["count"], "sources": sorted(d["sources"])}
        for c, d in sorted(competitor_map.items(), key=lambda x: -x[1]["count"])
    ][:8]

    # Cross-source hook
    reddit_top  = by_source["reddit"]["pain_points"]
    twitter_top = by_source["twitter"]["pain_points"]
    daily_hook  = _generate_cross_source_hook(
        reddit_pain  = reddit_top[0]  if reddit_top  else None,
        twitter_pain = twitter_top[0] if twitter_top else None,
        top_pain     = pain_points[0]["topic"] if pain_points else None,
    )

    return {
        "pain_points":         pain_points[:10],
        "daily_hook":          daily_hook,
        "competitor_mentions": competitors_list,
        "by_source": {
            k: {**v, "pain_points": v["pain_points"][:5]}
            for k, v in by_source.items()
        },
        "total_signals": len(rows),
        "updated_at":    datetime.now(timezone.utc).isoformat(),
    }


def _generate_cross_source_hook(
    reddit_pain: str | None,
    twitter_pain: str | None,
    top_pain: str | None,
) -> str:
    """
    Use Claude Haiku to write a combined-source outreach opener.
    Falls back to a template if no API key is set.
    """
    if not ANTHROPIC_API_KEY:
        return _template_hook(reddit_pain, twitter_pain, top_pain)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        signals = []
        if reddit_pain:
            signals.append(f'Reddit signal: "{reddit_pain}"')
        if twitter_pain:
            signals.append(f'Twitter signal: "{twitter_pain}"')
        if top_pain and top_pain not in (reddit_pain or "", twitter_pain or ""):
            signals.append(f'Top combined pain: "{top_pain}"')

        if not signals:
            return _template_hook(reddit_pain, twitter_pain, top_pain)

        prompt = (
            "You are an expert cold outreach copywriter.\n"
            "Based on these real market signals from Reddit and Twitter:\n"
            + "\n".join(signals)
            + "\n\nWrite ONE outreach hook (2 sentences, under 250 characters) that:\n"
            "- Acknowledges a pain point seen across BOTH platforms\n"
            "- Sounds like a real person noticing a trend, not a salesperson\n"
            "- Ends with a soft open question\n"
            "Return only the hook text — no quotes, no labels."
        )

        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=120,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.content[0].text.strip()

    except Exception as exc:
        logger.warning("_generate_cross_source_hook failed: %s", exc)
        return _template_hook(reddit_pain, twitter_pain, top_pain)


def _template_hook(reddit_pain, twitter_pain, top_pain) -> str:
    if reddit_pain and twitter_pain:
        return (
            f'Seeing this on both Reddit and Twitter — a lot of people dealing with '
            f'"{reddit_pain}". Are you running into the same thing?'
        )
    pain = reddit_pain or twitter_pain or top_pain or "the same challenges"
    return f'Noticing a lot of chatter around "{pain}" lately. Are you dealing with this too?'


def _severity(count: int, avg_intent: float) -> str:
    if count >= 5 or avg_intent >= 0.8:
        return "high"
    if count >= 2 or avg_intent >= 0.5:
        return "medium"
    return "low"


def _empty_pulse() -> dict:
    return {
        "pain_points":         [],
        "daily_hook":          "Run your first pod scan to start seeing market signals here.",
        "competitor_mentions": [],
        "by_source": {
            "reddit":  {"count": 0, "pain_points": []},
            "twitter": {"count": 0, "pain_points": []},
        },
        "total_signals": 0,
        "updated_at":    datetime.now(timezone.utc).isoformat(),
    }
