"""
Monitor comments on our posted Reddit content.
Qualifies commenters as leads and sends reply opportunities to Telegram.
Called by scheduler every ~2 hours.
"""
import json, logging, os, urllib.request
from datetime import datetime, timezone

import database as db

log = logging.getLogger(__name__)

# Signals that indicate a commenter is a potential lead
_PAIN_SIGNALS = [
    "struggling", "hard time", "can't figure out", "confused",
    "looking for", "recommend", "any advice", "how do you",
    "what do you use", "anyone else", "help", "frustrated",
    "not working", "keep losing", "blowing up", "blown up",
    "lost money", "drawdown", "stop loss", "entry", "scanner",
    "setup", "strategy", "system", "backtesting", "paper trading",
    "trying to learn", "new to", "just started", "been trading",
]

_QUALIFY_PROMPT = """You are qualifying Reddit comments as potential sales leads.

Our product: AltusFlow — AI-powered outbound prospecting for financial service businesses.
Target: active traders or business owners who manage client money, run trading education,
or are serious retail traders looking to systematize.

Comment from u/{username} on r/{subreddit}:
\"\"\"{comment}\"\"\"

Score this commenter 0-100 (100 = hot lead):
- 80-100: Clear pain point + authority (runs a business, coaches, manages money)
- 60-79: Active trader with a real problem we can solve
- 40-59: Interested but vague
- 0-39: Not a prospect (spam, joke, irrelevant)

Respond JSON only:
{{
  "score": <int 0-100>,
  "signal_match": "<the specific pain point or signal you detected, 1 short phrase>",
  "reason": "<one sentence why this score>"
}}"""

_REPLY_PROMPT = """You are drafting a Reddit reply on behalf of a trading tools company.

Post we made: \"{post_title}\"
Commenter u/{username} said: \"{comment}\"
Their pain signal: {signal_match}

Write a short, human, non-salesy reply (2-4 sentences max).
- Lead with genuine empathy or insight about their specific situation
- Optionally mention what we help with IF it naturally fits — never force it
- Do NOT mention the company name in the reply
- Sound like a fellow trader helping out, not a marketer
- No bullet points, no headers, no em-dashes

Reply only — no preamble."""


def _fetch_comments(post_url: str, subreddit: str) -> list[dict]:
    """Fetch top-level comments from a Reddit post."""
    url = post_url.rstrip("/") + ".json?limit=50&sort=top"
    req = urllib.request.Request(url, headers={"User-Agent": "AltusFlow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        comments_listing = data[1]["data"]["children"]
        results = []
        for c in comments_listing:
            if c.get("kind") != "t1":
                continue
            cd = c["data"]
            results.append({
                "author":     cd.get("author", "[deleted]"),
                "body":       cd.get("body", ""),
                "score":      cd.get("score", 0),
                "permalink":  "https://www.reddit.com" + cd.get("permalink", ""),
            })
        return results
    except Exception as e:
        log.warning("comment_monitor: fetch failed for %s: %s", post_url, e)
        return []


def _fetch_author_info(username: str) -> dict:
    """Get basic account info for karma/age check."""
    if not username or username == "[deleted]":
        return {}
    url = f"https://www.reddit.com/user/{username}/about.json"
    req = urllib.request.Request(url, headers={"User-Agent": "AltusFlow/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read())
        d = data.get("data", {})
        created = d.get("created_utc", 0)
        age_days = max(0, int(
            (datetime.now(timezone.utc).timestamp() - created) / 86400
        )) if created else 0
        return {
            "karma":          d.get("comment_karma", 0) + d.get("link_karma", 0),
            "account_age_days": age_days,
        }
    except Exception:
        return {}


def _has_pain_signal(text: str) -> bool:
    lower = text.lower()
    return any(sig in lower for sig in _PAIN_SIGNALS)


def _qualify_and_reply(username: str, subreddit: str, comment: str,
                        post_title: str) -> dict | None:
    """Ask Claude to score the comment and draft a reply if worthy."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        return None

    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "system": "You are a lead qualification expert. Respond with JSON only.",
        "messages": [{"role": "user", "content": _QUALIFY_PROMPT.format(
            username=username, subreddit=subreddit, comment=comment[:600],
        )}],
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = json.loads(resp.read())
        text_out = raw["content"][0]["text"].strip()
        if text_out.startswith("```"):
            text_out = text_out.split("```")[1]
            if text_out.startswith("json"):
                text_out = text_out[4:]
        qual = json.loads(text_out)
        score = int(qual.get("score", 0))
        if score < 50:
            return {"score": score, "qualified": False}

        # Generate reply for qualified leads
        reply_payload = json.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "system": "You write brief, human Reddit replies for a trading tools company.",
            "messages": [{"role": "user", "content": _REPLY_PROMPT.format(
                post_title=post_title[:200],
                username=username,
                comment=comment[:400],
                signal_match=qual.get("signal_match", ""),
            )}],
        }).encode()

        req2 = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=reply_payload,
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=20) as resp2:
            raw2 = json.loads(resp2.read())
        reply_text = raw2["content"][0]["text"].strip()

        return {
            "score":        score,
            "signal_match": qual.get("signal_match", ""),
            "qualified":    True,
            "reply":        reply_text,
        }
    except Exception as e:
        log.warning("comment_monitor: qualify error: %s", e)
        return None


def run_comment_monitor(client_id: str = None) -> int:
    """
    Check all posted value_posts for new qualifying comments.
    Returns count of new leads found.
    """
    posts   = db.get_posted_value_posts(client_id)
    cid     = client_id or os.environ.get("CLIENT_ID", "default")
    new_leads = 0

    for post in posts:
        post_url = post.get("post_url", "")
        if not post_url or "reddit.com" not in post_url:
            continue
        post_id    = post["id"]
        subreddit  = post.get("subreddit", "")
        post_title = post.get("title", "")

        comments = _fetch_comments(post_url, subreddit)
        for c in comments:
            username = c["author"]
            body     = c["body"]

            if not username or username in ("[deleted]", "AutoModerator"):
                continue
            if len(body) < 15 or not _has_pain_signal(body):
                continue

            result = _qualify_and_reply(username, subreddit, body, post_title)
            if not result or not result.get("qualified"):
                continue

            author_info = _fetch_author_info(username)
            lead_id = db.save_comment_lead(
                client_id        = cid,
                value_post_id    = post_id,
                subreddit        = subreddit,
                post_url         = post_url,
                commenter        = username,
                comment_text     = body[:1000],
                comment_url      = c.get("permalink", ""),
                comment_score    = c.get("score", 0),
                account_age_days = author_info.get("account_age_days", 0),
                karma            = author_info.get("karma", 0),
                qualification_score = result["score"],
                signal_match     = result.get("signal_match", ""),
                suggested_reply  = result.get("reply", ""),
            )

            if lead_id:
                new_leads += 1
                log.info("comment_monitor: new lead #%d from u/%s on post %d",
                         lead_id, username, post_id)
                # Telegram disabled — review reply leads in the Reply Center

    return new_leads


def _notify_telegram(lead_id: int, post_title: str, subreddit: str,
                      post_url: str, username: str, comment: str,
                      suggested_reply: str, score: int):
    """Send comment lead to Telegram for reply approval."""
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id   = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not bot_token or not chat_id:
        return

    preview_comment = comment[:200] + ("…" if len(comment) > 200 else "")
    preview_reply   = suggested_reply[:300] + ("…" if len(suggested_reply) > 300 else "")

    text = (
        f"💬 *Reply opportunity* — lead score {score}/100\n\n"
        f"*Post:* {post_title[:100]}\n"
        f"*r/{subreddit}* · [View post]({post_url})\n\n"
        f"*u/{username}* said:\n_{preview_comment}_\n\n"
        f"*Suggested reply:*\n{preview_reply}"
    )

    keyboard = json.dumps({
        "inline_keyboard": [[
            {"text": "✅ Post Reply",   "callback_data": f"reply_approve:{lead_id}"},
            {"text": "✏️ Edit Reply",  "callback_data": f"reply_edit:{lead_id}"},
            {"text": "❌ Skip",         "callback_data": f"reply_deny:{lead_id}"},
        ]]
    })

    payload = json.dumps({
        "chat_id":              chat_id,
        "text":                 text,
        "parse_mode":           "Markdown",
        "reply_markup":         keyboard,
        "disable_web_page_preview": True,
    }).encode()

    try:
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        log.warning("comment_monitor: telegram notify failed: %s", e)
