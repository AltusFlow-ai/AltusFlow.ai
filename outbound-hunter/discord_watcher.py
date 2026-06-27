"""
discord_watcher.py — Discord community signal listener.

Uses Discord's HTTP REST API to poll configured channels for new messages.
No asyncio, no discord.py library — synchronous urllib.request calls to match
the existing Flask/threading architecture.

Signal detection: matches each message against the niche SIGNAL_PHRASES list
for the channel's registered pod_slug. Matching messages are upserted into
the prospects table with source='discord' and platform='discord'.

Poll cadence: runs every 5 minutes via APScheduler (existing scheduler).
Channel config lives in discord_channels DB table (add via API or settings UI).

Authorization:
  - Set DISCORD_BOT_TOKEN in .env for a proper Bot application (recommended)
  - OR set DISCORD_USER_TOKEN for a personal account (rate limited, ToS risk)
  Bot token format: "Bot <token>"
  User token format: just the raw token (no "Bot " prefix)
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

_DISCORD_API  = "https://discord.com/api/v10"
_MAX_MESSAGES = 100  # Discord API max per request


def _get_auth_header() -> str | None:
    bot_token  = os.environ.get("DISCORD_BOT_TOKEN", "").strip()
    user_token = os.environ.get("DISCORD_USER_TOKEN", "").strip()
    if bot_token:
        return f"Bot {bot_token}"
    if user_token:
        return user_token
    return None


def _discord_get(path: str) -> dict | list | None:
    """Make an authenticated GET to the Discord REST API."""
    auth = _get_auth_header()
    if not auth:
        log.warning("[discord] No DISCORD_BOT_TOKEN or DISCORD_USER_TOKEN in environment")
        return None
    try:
        req = urllib.request.Request(
            f"{_DISCORD_API}{path}",
            headers={"Authorization": auth, "User-Agent": "AltusFlow/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 429:
            log.warning(f"[discord] Rate limited on {path} — back off")
        elif e.code == 403:
            log.warning(f"[discord] No access to {path} — check bot permissions (VIEW_CHANNEL, READ_MESSAGE_HISTORY)")
        else:
            log.warning(f"[discord] HTTP {e.code} on {path}: {e.reason}")
        return None
    except Exception as e:
        log.warning(f"[discord] Request error on {path}: {e}")
        return None


def fetch_channel_messages(channel_id: str, after_id: str = None) -> list:
    """
    Fetch up to 100 messages from a Discord channel.
    Returns newest-first (Discord default) list of message dicts.
    Only includes: id, content, author.username, timestamp.
    """
    path = f"/channels/{channel_id}/messages?limit={_MAX_MESSAGES}"
    if after_id:
        path += f"&after={after_id}"
    msgs = _discord_get(path)
    if not isinstance(msgs, list):
        return []
    return msgs


def get_channel_info(channel_id: str) -> dict | None:
    """Fetch channel metadata (name, guild_id) to validate a new channel."""
    return _discord_get(f"/channels/{channel_id}")


def detect_signals_in_messages(messages: list, pod_slug: str) -> list:
    """
    Filter messages for pain signal phrases from the pod's niche module.
    Returns list of dicts with: message_id, author, content, matched_signal, timestamp.
    """
    try:
        from scrapers.niches import get_niche
        niche = get_niche(pod_slug)
        signal_phrases = getattr(niche, 'SIGNAL_PHRASES', []) if niche else []
    except Exception:
        signal_phrases = []

    if not signal_phrases:
        return []

    matched = []
    for msg in messages:
        content = (msg.get("content") or "").lower()
        if len(content) < 15:
            continue
        for phrase in signal_phrases:
            if phrase.lower() in content:
                author = msg.get("author") or {}
                matched.append({
                    "message_id":    msg.get("id"),
                    "author":        author.get("username") or author.get("global_name") or "unknown",
                    "author_id":     author.get("id"),
                    "content":       msg.get("content", "")[:1000],
                    "matched_signal": phrase,
                    "timestamp":     msg.get("timestamp"),
                })
                break  # One match per message is enough
    return matched


def store_discord_prospects(matches: list, channel_id: str, channel_name: str,
                             guild_name: str, pod_slug: str) -> int:
    """
    Upsert matched Discord messages as prospects.
    Uses same prospects table — platform='discord', source='discord'.
    Returns count of new prospects stored.
    """
    if not matches:
        return 0

    try:
        from database import store_prospect, prospect_exists, CLIENT_ID
    except Exception as e:
        log.warning(f"[discord] DB import error: {e}")
        return 0

    stored = 0
    for m in matches:
        handle = m["author"]
        if not handle or handle == "unknown":
            continue
        if prospect_exists(handle, "discord"):
            continue
        try:
            store_prospect({
                "handle":        handle,
                "platform":      "discord",
                "post_text":     m["content"],
                "signal_phrase": m["matched_signal"],
                "source":        "discord",
                "niche_segment": pod_slug,
                "subreddit":     f"{guild_name}#{channel_name}",
                "group_name":    guild_name,
                "client_id":     CLIENT_ID,
                "icp_score":     5,
                "status":        "new",
                "post_url":      f"https://discord.com/channels/{channel_id}/{m['message_id']}",
                "scraped_at":    m.get("timestamp") or datetime.now(timezone.utc).isoformat(),
            })
            stored += 1
        except Exception as e:
            log.warning(f"[discord] store error for {handle}: {e}")

    return stored


def poll_channel(channel_config: dict) -> dict:
    """
    Run one polling cycle for a single Discord channel.
    Returns status dict with counts.
    """
    channel_id   = channel_config.get("channel_id")
    channel_name = channel_config.get("channel_name") or channel_id
    guild_name   = channel_config.get("guild_name") or "Unknown Server"
    pod_slug     = channel_config.get("pod_slug") or "daytrading"
    last_id      = channel_config.get("last_message_id")

    msgs = fetch_channel_messages(channel_id, after_id=last_id)
    if not msgs:
        return {"channel_id": channel_id, "fetched": 0, "matched": 0, "stored": 0}

    newest_id = max(m["id"] for m in msgs)

    matches = detect_signals_in_messages(msgs, pod_slug)
    stored  = store_discord_prospects(matches, channel_id, channel_name, guild_name, pod_slug)

    # Advance the cursor
    try:
        from database import update_discord_last_id
        update_discord_last_id(channel_id, newest_id)
    except Exception as e:
        log.warning(f"[discord] cursor update error: {e}")

    log.info(f"[discord] #{channel_name} — fetched {len(msgs)}, matched {len(matches)}, stored {stored}")
    return {
        "channel_id":   channel_id,
        "channel_name": channel_name,
        "fetched":      len(msgs),
        "matched":      len(matches),
        "stored":       stored,
    }


def run_all_polls() -> list:
    """
    Poll all enabled Discord channels. Called by APScheduler every 5 minutes.
    Returns list of per-channel status dicts.
    """
    try:
        from database import get_discord_channels
        channels = get_discord_channels(enabled_only=True)
    except Exception as e:
        log.warning(f"[discord] failed to load channels: {e}")
        return []

    if not channels:
        return []

    if not _get_auth_header():
        log.warning("[discord] No bot token — skipping polls")
        return []

    results = []
    for ch in channels:
        try:
            result = poll_channel(ch)
            results.append(result)
        except Exception as e:
            log.warning(f"[discord] poll error for {ch.get('channel_id')}: {e}")
            results.append({"channel_id": ch.get("channel_id"), "error": str(e)})

    total_stored = sum(r.get("stored", 0) for r in results)
    log.info(f"[discord] Poll complete — {len(channels)} channels, {total_stored} new prospects")
    return results


def validate_connection(bot_token: str = None) -> dict:
    """
    Test that a Discord bot token is valid by fetching the bot's own user info.
    Returns {"ok": bool, "username": str | None, "error": str | None}.
    """
    token = bot_token or os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        return {"ok": False, "error": "No DISCORD_BOT_TOKEN provided"}
    try:
        req = urllib.request.Request(
            f"{_DISCORD_API}/users/@me",
            headers={"Authorization": f"Bot {token}", "User-Agent": "AltusFlow/1.0"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return {"ok": True, "username": data.get("username"), "error": None}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}: invalid token or missing intents"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


if __name__ == "__main__":
    import argparse
    from dotenv import load_dotenv
    load_dotenv()

    parser = argparse.ArgumentParser(description="AltusFlow Discord watcher")
    parser.add_argument("command", nargs="?", default="poll",
                        choices=["poll", "validate", "test-channel"])
    parser.add_argument("--channel", help="Channel ID to test")
    args = parser.parse_args()

    if args.command == "validate":
        result = validate_connection()
        print(json.dumps(result, indent=2))
    elif args.command == "test-channel" and args.channel:
        info = get_channel_info(args.channel)
        print(json.dumps(info or {"error": "Not found"}, indent=2))
    else:
        results = run_all_polls()
        print(json.dumps(results, indent=2))
