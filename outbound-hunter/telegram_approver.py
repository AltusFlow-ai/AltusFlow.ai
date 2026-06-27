"""
telegram_approver.py — Hands-off content approval via Telegram.

Flow:
  1. Post is generated → send_for_review(post_id, post_data) is called
  2. Bot sends full preview to your Telegram with [✅ Approve] [❌ Deny] [✏️ Edit] buttons
  3. Tap Approve → posts to Reddit/X automatically, confirms with URL
  4. Tap Deny → removes from queue
  5. Tap Edit → reply with feedback text → AI rewrites → re-sends for review

Setup:
  TELEGRAM_BOT_TOKEN  — from @BotFather on Telegram
  TELEGRAM_CHAT_ID    — your personal chat ID (send /start to @userinfobot to get it)

Runs as a polling thread (no public webhook URL needed).
No asyncio — uses threading.Thread per the project's no-async rule.
"""

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

log = logging.getLogger(__name__)

# Peak posting windows per platform (hour, minute) in UTC
# Reddit trading subs peak:   13:30 (8:30 EST), 17:00 (12:00 EST), 21:15 (4:15 EST)
# X peaks:                    13:00 (8:00 EST), 17:30 (12:30 EST), 22:30 (5:30 EST)
_PEAK_WINDOWS_UTC = {
    'reddit': [(13, 30), (17, 0), (21, 15)],
    'x':      [(13, 0),  (17, 30), (22, 30)],
}
_MAX_SCHEDULE_DELAY_HOURS = 8  # if peak is further than this, post now


def _next_peak_window(platform: str) -> datetime | None:
    """Return the next upcoming peak UTC datetime for this platform, or None."""
    windows = _PEAK_WINDOWS_UTC.get(platform.lower(), _PEAK_WINDOWS_UTC['reddit'])
    now = datetime.now(timezone.utc)
    candidates = []
    for h, m in windows:
        candidate = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)
    candidates.sort()
    return candidates[0] if candidates else None

# post_id (str) → post_data dict for pending approvals
_pending: dict[str, dict] = {}
# post_id → original message_id so we can edit it on approve/deny
_msg_ids: dict[str, int] = {}
# chat_id → post_id awaiting edit text (post rewrite)
_awaiting_edit: dict[str, str] = {}
# chat_id → lead_id (str) awaiting reply-edit feedback
_awaiting_reply_edit: dict[str, str] = {}
_lock = threading.Lock()


class _Bot:
    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = str(chat_id)
        self._base   = f"https://api.telegram.org/bot{token}"
        self._offset = 0
        self._stop   = threading.Event()

    def _call(self, method: str, **params) -> dict:
        url  = f"{self._base}/{method}"
        body = json.dumps(params).encode()
        req  = urllib.request.Request(
            url, data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())

    def _get_updates(self) -> list:
        try:
            result = self._call(
                'getUpdates',
                offset=self._offset,
                timeout=25,
                allowed_updates=['message', 'callback_query'],
            )
            return result.get('result', [])
        except Exception as e:
            log.warning(f"[telegram] getUpdates error: {e}")
            return []

    def send_for_review(self, post_id: int | str, post_data: dict):
        """Send a post preview with Approve / Deny / Edit buttons."""
        pid = str(post_id)
        with _lock:
            _pending[pid] = post_data

        platform = (post_data.get('platform') or 'reddit').lower()

        if platform == 'x':
            tweets   = post_data.get('tweets') or []
            preview  = '\n\n'.join(tweets)[:800]
            plat_lbl = '𝕏 X Thread'
        else:
            title    = post_data.get('title', '')
            body     = post_data.get('body', '')
            preview  = f"*{title}*\n\n{body[:700]}"
            plat_lbl = f"🟠 Reddit r/{post_data.get('subreddit', '')}"

        signal = post_data.get('signal') or post_data.get('source_signal') or post_data.get('topic', '')

        text = (
            f"📋 *New post ready for review*\n\n"
            f"*Platform:* {plat_lbl}\n"
            f"*Signal:* _{signal}_\n\n"
            f"─────────────────\n"
            f"{preview}"
            f"{'…' if len(preview) >= 700 else ''}"
        )

        keyboard = {'inline_keyboard': [[
            {'text': '✅ Approve',  'callback_data': f'approve:{pid}'},
            {'text': '❌ Deny',     'callback_data': f'deny:{pid}'},
            {'text': '✏️ Edit',    'callback_data': f'edit:{pid}'},
        ]]}

        try:
            result = self._call(
                'sendMessage',
                chat_id      = self.chat_id,
                text         = text[:4096],
                parse_mode   = 'Markdown',
                reply_markup = keyboard,
            )
            msg_id = result.get('result', {}).get('message_id')
            if msg_id:
                with _lock:
                    _msg_ids[pid] = msg_id
        except Exception as e:
            log.warning(f"[telegram] send_for_review error: {e}")

    def _edit_msg(self, message_id: int, text: str, remove_buttons: bool = True):
        params = dict(
            chat_id    = self.chat_id,
            message_id = message_id,
            text       = text[:4096],
            parse_mode = 'Markdown',
        )
        if remove_buttons:
            params['reply_markup'] = {'inline_keyboard': []}
        try:
            self._call('editMessageText', **params)
        except Exception:
            pass

    def _send(self, text: str, reply_to: int = None):
        params = dict(chat_id=self.chat_id, text=text[:4096], parse_mode='Markdown')
        if reply_to:
            params['reply_to_message_id'] = reply_to
        try:
            self._call('sendMessage', **params)
        except Exception as e:
            log.warning(f"[telegram] send error: {e}")

    def _handle_callback(self, cb: dict):
        data    = cb.get('data', '')
        cb_id   = cb['id']
        msg_id  = cb['message']['message_id']

        try:
            self._call('answerCallbackQuery', callback_query_id=cb_id)
        except Exception:
            pass

        if ':' not in data:
            return
        action, pid = data.split(':', 1)

        # Warmup comment approvals
        if action == 'warmup_approve':
            self._do_warmup_approve(pid, msg_id)
            return
        if action == 'warmup_deny':
            self._edit_msg(msg_id, "⏭️ *Skipped* — no comment posted today.")
            try:
                from reddit_warmer import _update_warmup_status
                _update_warmup_status(pid, 'skipped')
            except Exception:
                pass
            return

        # Reply-to-comment approvals (lead pipeline)
        if action == 'reply_approve':
            self._do_reply_approve(pid, msg_id)
            return
        if action == 'reply_deny':
            self._do_reply_deny(pid, msg_id)
            return
        if action == 'reply_edit':
            with _lock:
                _awaiting_reply_edit[self.chat_id] = pid
            self._send(
                f"✏️ *What should I change in the reply?*\n\n"
                f"Type your feedback and I'll rewrite it.\n\n"
                f"Examples:\n"
                f"• _Make it shorter_\n"
                f"• _Lead with a question instead_\n"
                f"• _Don't mention the product at all_\n"
                f"• _More empathy, less advice_",
                reply_to=msg_id,
            )
            return
        # Rules check overrides
        if action == 'approve_anyway':
            with _lock:
                post = _pending.get(pid)
            self._do_approve(pid, post, msg_id, skip_rules=True)
            return
        if action == 'cancel_post':
            self._do_deny(pid, msg_id)
            return

        with _lock:
            post = _pending.get(pid)

        if action == 'approve':
            self._do_approve(pid, post, msg_id)
        elif action == 'deny':
            self._do_deny(pid, msg_id)
        elif action == 'edit':
            with _lock:
                _awaiting_edit[self.chat_id] = pid
            self._send(
                f"✏️ *What should I change?*\n\n"
                f"Type your feedback and I'll rewrite it.\n\n"
                f"Examples:\n"
                f"• _Make the hook more direct_\n"
                f"• _Cut it by 30%_\n"
                f"• _Change tone — less formal_\n"
                f"• _Add a specific number to the open_",
                reply_to=msg_id,
            )

    def _do_approve(self, pid: str, post: dict, msg_id: int, skip_rules: bool = False):
        if not post:
            self._send("⚠️ Post data not found — may have already been processed.")
            return

        platform  = (post.get('platform') or 'reddit').lower()
        subreddit = post.get('subreddit', '')

        # Account health gate (Reddit only)
        if platform == 'reddit' and not skip_rules:
            try:
                from social_poster import check_reddit_account_health
                health = check_reddit_account_health()
                if health.get('blocked'):
                    warn_lines = '\n'.join(f'• {w}' for w in health.get('warnings', []))
                    self._edit_msg(msg_id, (
                        f"⚠️ *Reddit account health warning*\n\n"
                        f"u/{health.get('username', '?')} · "
                        f"{health.get('karma', 0)} karma · "
                        f"{health.get('age_days', 0)} days old\n\n"
                        f"{warn_lines}\n\n"
                        f"Posting now risks shadowban. Post anyway?"
                    ), remove_buttons=False)
                    keyboard = {'inline_keyboard': [[
                        {'text': '⚠️ Post Anyway', 'callback_data': f'approve_anyway:{pid}'},
                        {'text': '❌ Cancel',       'callback_data': f'cancel_post:{pid}'},
                    ]]}
                    try:
                        self._call('editMessageReplyMarkup',
                                   chat_id=self.chat_id, message_id=msg_id,
                                   reply_markup=keyboard)
                    except Exception:
                        pass
                    return
                elif health.get('warnings'):
                    # Soft warning — non-blocking, just inform
                    warn_txt = ' · '.join(health['warnings'])
                    self._send(f"⚠️ Account note: {warn_txt}")
            except Exception as e:
                log.warning(f"[telegram] account health check error: {e}")

        # Posting frequency limit (Reddit only)
        if platform == 'reddit' and subreddit and not skip_rules:
            try:
                import os as _os
                max_per_week = int(_os.environ.get('REDDIT_MAX_POSTS_PER_WEEK', '3'))
                from database import count_recent_posts_to_subreddit
                recent_count = count_recent_posts_to_subreddit(
                    _os.environ.get('CLIENT_ID', 'default'), subreddit, days=7
                )
                if recent_count >= max_per_week:
                    self._edit_msg(msg_id, (
                        f"⚠️ *Frequency limit hit for r/{subreddit}*\n\n"
                        f"{recent_count} posts in the last 7 days "
                        f"(limit: {max_per_week}). Posting more risks shadowban.\n\n"
                        f"Post anyway or wait until next week?"
                    ), remove_buttons=False)
                    keyboard = {'inline_keyboard': [[
                        {'text': '⚠️ Post Anyway', 'callback_data': f'approve_anyway:{pid}'},
                        {'text': '❌ Wait',         'callback_data': f'cancel_post:{pid}'},
                    ]]}
                    try:
                        self._call('editMessageReplyMarkup',
                                   chat_id=self.chat_id, message_id=msg_id,
                                   reply_markup=keyboard)
                    except Exception:
                        pass
                    return
            except Exception as e:
                log.warning(f'[telegram] frequency check error: {e}')

        # Subreddit rules check (Reddit only, skip if already confirmed)
        if platform == 'reddit' and subreddit and not skip_rules:
            try:
                from subreddit_rules import check_post_compliance
                compliance = check_post_compliance(
                    subreddit,
                    post.get('title', ''),
                    post.get('body', ''),
                )
                violations = compliance.get('violations', [])
                if violations and not compliance.get('error'):
                    vlist = '\n'.join(f"• {v}" for v in violations[:5])
                    self._edit_msg(msg_id, (
                        f"⚠️ *Rules check flagged issues for r/{subreddit}:*\n{vlist}\n\n"
                        f"Post anyway or cancel?"
                    ), remove_buttons=False)
                    keyboard = {'inline_keyboard': [[
                        {'text': '⚠️ Post Anyway', 'callback_data': f'approve_anyway:{pid}'},
                        {'text': '❌ Cancel',       'callback_data': f'cancel_post:{pid}'},
                    ]]}
                    try:
                        self._call('editMessageReplyMarkup',
                                   chat_id=self.chat_id, message_id=msg_id,
                                   reply_markup=keyboard)
                    except Exception:
                        pass
                    return
            except Exception as e:
                log.warning(f"[telegram] rules check error: {e}")

        # Posting time optimizer
        next_window = _next_peak_window(platform)
        now         = datetime.now(timezone.utc)
        if next_window:
            hours_until = (next_window - now).total_seconds() / 3600
            if 0.25 < hours_until <= _MAX_SCHEDULE_DELAY_HOURS:
                # Schedule it — don't post now
                sched_iso = next_window.isoformat()
                # Format for display in user's local context (EST = UTC-5)
                est = next_window - timedelta(hours=5)
                hour = est.hour % 12 or 12  # 12-hour clock, no leading zero
                ampm = "AM" if est.hour < 12 else "PM"
                sched_label = f"{hour}:{est.minute:02d} {ampm} EST"
                try:
                    from database import update_value_post
                    update_value_post(int(pid), status='approved', scheduled_for=sched_iso)
                except Exception:
                    pass
                self._edit_msg(msg_id, (
                    f"🕐 *Scheduled for {sched_label}* (peak window)\n\n"
                    f"Post will go live automatically. Check Results tab after."
                ))
                log.info(f"[telegram] post {pid} scheduled for {sched_iso}")
                with _lock:
                    _pending.pop(pid, None)
                    _msg_ids.pop(pid, None)
                return

        self._edit_msg(msg_id, "⏳ *Posting…*", remove_buttons=True)

        try:
            from social_poster import post_content
            result = post_content(post)
        except Exception as e:
            result = {'ok': False, 'error': str(e)}

        if result.get('ok'):
            url = result.get('url', '')
            self._edit_msg(msg_id, f"✅ *Posted!*\n{url}")
            try:
                from database import update_value_post
                update_value_post(int(pid), status='posted', post_url=url)
            except Exception:
                pass
            log.info(f"[telegram] post {pid} approved and posted: {url}")
        else:
            err = result.get('error', 'unknown error')
            self._edit_msg(msg_id, f"⚠️ *Posting failed*\n{err}\n\nPost kept in Queue — try again from dashboard.")
            log.warning(f"[telegram] post {pid} approve failed: {err}")

        with _lock:
            _pending.pop(pid, None)
            _msg_ids.pop(pid, None)

    def _do_warmup_approve(self, post_id: str, msg_id: int):
        self._edit_msg(msg_id, "⏳ *Posting comment…*", remove_buttons=True)
        try:
            from reddit_warmer import post_warmup_comment
            result = post_warmup_comment(post_id)
            if result.get('ok'):
                self._edit_msg(msg_id, "✅ *Comment posted!* Account warmup done for today.")
                log.info('[telegram] warmup comment %s posted', post_id)
            else:
                self._edit_msg(msg_id, f"⚠️ *Comment failed:* {result.get('error', 'unknown')}")
        except Exception as e:
            self._edit_msg(msg_id, f"⚠️ *Error:* {e}")

    def _do_reply_approve(self, lead_id_str: str, msg_id: int):
        """Post the AI-drafted reply to a qualifying comment."""
        try:
            lead_id = int(lead_id_str)
            from database import get_comment_leads, update_comment_lead
            leads = get_comment_leads()
            lead  = next((l for l in leads if l['id'] == lead_id), None)
            if not lead:
                self._edit_msg(msg_id, "⚠️ Lead not found.")
                return

            self._edit_msg(msg_id, "⏳ *Posting reply…*", remove_buttons=True)

            # Post reply via Reddit API
            from social_poster import post_reddit_reply
            result = post_reddit_reply(
                comment_url=lead.get('comment_url', ''),
                reply_text=lead.get('suggested_reply', ''),
            )
            if result.get('ok'):
                update_comment_lead(lead_id, reply_status='posted',
                                    reply_posted_at=datetime.now(timezone.utc).isoformat())
                self._edit_msg(msg_id, f"✅ *Reply posted!*\n{result.get('url', '')}")
            else:
                update_comment_lead(lead_id, reply_status='failed')
                self._edit_msg(msg_id, f"⚠️ *Reply failed:* {result.get('error', 'unknown')}")
        except Exception as e:
            log.warning(f"[telegram] reply_approve error: {e}")
            self._edit_msg(msg_id, f"⚠️ Error posting reply: {e}")

    def _do_reply_deny(self, lead_id_str: str, msg_id: int):
        try:
            from database import update_comment_lead
            update_comment_lead(int(lead_id_str), reply_status='skipped')
        except Exception:
            pass
        self._edit_msg(msg_id, "⏭️ *Skipped* — lead saved, reply not sent.")

    def _do_reply_rewrite(self, lead_id_str: str, feedback: str):
        """Rewrite suggested reply based on feedback, then re-send for approval."""
        import os, json, urllib.request as _req

        self._send("⏳ *Rewriting reply…*")

        try:
            from database import get_comment_leads, update_comment_lead
            leads = get_comment_leads()
            lead  = next((l for l in leads if l['id'] == int(lead_id_str)), None)
            if not lead:
                self._send("⚠️ Couldn't find the original lead — it may have expired.")
                return

            api_key = os.environ.get("ANTHROPIC_API_KEY", "")
            if not api_key:
                self._send("⚠️ ANTHROPIC_API_KEY not set — can't rewrite.")
                return

            prompt = (
                f"Original reply:\n\"{lead.get('suggested_reply', '')}\"\n\n"
                f"User feedback: \"{feedback}\"\n\n"
                f"Rewrite the reply incorporating this feedback. "
                f"Keep it short (2-4 sentences), human, non-salesy. "
                f"No bullet points or headers. Reply text only — no preamble."
            )
            payload = json.dumps({
                "model": "claude-haiku-4-5-20251001",
                "max_tokens": 200,
                "system": "You write brief, human Reddit replies. Return the reply text only.",
                "messages": [{"role": "user", "content": prompt}],
            }).encode()

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
            new_reply = raw["content"][0]["text"].strip()

            # Save updated reply to DB
            update_comment_lead(int(lead_id_str), suggested_reply=new_reply)

            # Re-send preview with approval buttons
            preview_comment = (lead.get('comment_text') or '')[:200]
            preview_reply   = new_reply[:300] + ("…" if len(new_reply) > 300 else "")
            score = lead.get('qualification_score', 0)

            text = (
                f"✏️ *Reply rewritten* — lead score {score}/100\n\n"
                f"*Post:* {(lead.get('post_url') or '')[:80]}\n"
                f"*u/{lead.get('commenter', '')}* said:\n_{preview_comment}_\n\n"
                f"*New reply:*\n{preview_reply}"
            )
            keyboard = json.dumps({
                "inline_keyboard": [[
                    {"text": "✅ Post Reply",  "callback_data": f"reply_approve:{lead_id_str}"},
                    {"text": "✏️ Edit Reply", "callback_data": f"reply_edit:{lead_id_str}"},
                    {"text": "❌ Skip",        "callback_data": f"reply_deny:{lead_id_str}"},
                ]]
            })
            payload2 = json.dumps({
                "chat_id":                  self.chat_id,
                "text":                     text[:4096],
                "parse_mode":               "Markdown",
                "reply_markup":             keyboard,
                "disable_web_page_preview": True,
            }).encode()
            req2 = _req.Request(
                f"{self._base}/sendMessage",
                data=payload2,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            _req.urlopen(req2, timeout=10)

        except Exception as e:
            log.warning(f"[telegram] reply rewrite error: {e}")
            self._send(f"⚠️ Rewrite failed: {e}\n\nType your feedback again to retry.")
            # Restore awaiting state so they can retry
            with _lock:
                _awaiting_reply_edit[self.chat_id] = lead_id_str

    def _do_deny(self, pid: str, msg_id: int):
        try:
            from database import update_value_post
            update_value_post(int(pid), status='rejected')
        except Exception:
            pass
        with _lock:
            _pending.pop(pid, None)
            _msg_ids.pop(pid, None)
        self._edit_msg(msg_id, "❌ *Denied* — post removed from queue.")
        log.info(f"[telegram] post {pid} denied")

    def _handle_message(self, msg: dict):
        """Handle free-text feedback for both post rewrites and reply edits."""
        text    = (msg.get('text') or '').strip()
        chat_id = str(msg.get('chat', {}).get('id', ''))
        msg_id  = msg.get('message_id')

        if not text or text.startswith('/') or chat_id != self.chat_id:
            return

        # Check reply-edit first (takes priority if both somehow set)
        with _lock:
            lead_id_str = _awaiting_reply_edit.pop(chat_id, None)

        if lead_id_str:
            self._do_reply_rewrite(lead_id_str, text)
            return

        with _lock:
            pid = _awaiting_edit.pop(chat_id, None)

        if not pid:
            return

        with _lock:
            original = _pending.get(pid)

        if not original:
            self._send("⚠️ Couldn't find the original post — it may have expired.")
            return

        self._send("⏳ *Rewriting…*")

        try:
            from value_post_generator import rewrite_with_feedback
            rewritten = rewrite_with_feedback(original, text)
        except Exception as e:
            rewritten = None
            log.warning(f"[telegram] rewrite error: {e}")

        if rewritten:
            with _lock:
                _pending[pid] = rewritten
                _msg_ids.pop(pid, None)
            self.send_for_review(pid, rewritten)
        else:
            self._send("⚠️ Rewrite failed — try again or approve/deny the original.")
            with _lock:
                _awaiting_edit[chat_id] = pid  # restore so they can try again

    def _handle_update(self, update: dict):
        try:
            if 'callback_query' in update:
                self._handle_callback(update['callback_query'])
            elif 'message' in update:
                self._handle_message(update['message'])
        except Exception as e:
            log.warning(f"[telegram] handle_update error: {e}")

    def poll(self):
        """Long-polling loop — runs in a daemon thread."""
        log.info("[telegram] bot polling started")
        while not self._stop.is_set():
            updates = self._get_updates()
            for u in updates:
                self._offset = u['update_id'] + 1
                self._handle_update(u)
            if not updates:
                time.sleep(1)

    def stop(self):
        self._stop.set()


# ── Module-level singleton ────────────────────────────────────────────────────

_bot: _Bot | None = None
_poll_thread: threading.Thread | None = None


def init():
    """
    Initialize and start the Telegram bot polling thread.
    Called once at Flask app startup (from app.py or main.py).
    No-op if TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID are not set.
    """
    global _bot, _poll_thread

    token   = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')

    if not token or not chat_id:
        log.info("[telegram] not configured — set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID to enable")
        return

    if _bot is not None:
        return  # already running

    _bot         = _Bot(token, chat_id)
    _poll_thread = threading.Thread(target=_bot.poll, name="telegram-approver", daemon=True)
    _poll_thread.start()
    log.info("[telegram] approver started for chat_id=%s", chat_id)


def send_for_review(post_id: int | str, post_data: dict):
    """
    Send a generated post to Telegram for approval.
    Silently no-ops if the bot isn't configured.
    """
    if _bot:
        _bot.send_for_review(post_id, post_data)
    else:
        log.debug("[telegram] send_for_review called but bot not configured")


def stop():
    if _bot:
        _bot.stop()
