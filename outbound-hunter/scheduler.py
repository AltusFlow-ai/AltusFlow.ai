"""
scheduler.py
APScheduler-based background scheduler for Outbound Hunter.

Scan schedule (all times US/Eastern, configurable via env vars):
  SCAN_CRON_HOUR / SCAN_CRON_MINUTE   → primary scan   (default: 16:15 — market close for trading coaches)
  SCAN_CRON_HOUR_2 / SCAN_CRON_MINUTE_2 → evening scan (default: 20:00 — peak posting time for FA clients)
  DIGEST_CRON_HOUR / DIGEST_CRON_MINUTE → digest email (default: 17:00 — 45 min after primary scan)

Design decisions:
  - BackgroundScheduler with daemon=True — runs in a thread, no asyncio, dies with the process
  - CronTrigger — env vars control timing; both scan jobs call the same _run_pipeline()
  - Pause state persisted in scheduler_state DB row — survives app restarts
  - Concurrent-run guard via threading.Lock — second trigger during an active run is silently skipped
  - run_now() — manual trigger from /admin page, also guarded by the same lock
  - Every unhandled exception is caught and logged so the scheduler thread never dies silently
  - stop() uses wait=False so Flask can shut down without waiting for an in-flight scan
"""

import os
import threading
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from database import get_scheduler_state, set_scheduler_paused
from error_logger import log_pipeline_error, CRITICAL

logger = logging.getLogger(__name__)

SCAN_CRON_HOUR          = int(os.environ.get("SCAN_CRON_HOUR",   "16"))
SCAN_CRON_MINUTE        = int(os.environ.get("SCAN_CRON_MINUTE", "15"))
SCAN_CRON_HOUR_2        = int(os.environ.get("SCAN_CRON_HOUR_2",  "20"))
SCAN_CRON_MINUTE_2      = int(os.environ.get("SCAN_CRON_MINUTE_2", "0"))
DIGEST_CRON_HOUR        = int(os.environ.get("DIGEST_CRON_HOUR",   "17"))
DIGEST_CRON_MINUTE      = int(os.environ.get("DIGEST_CRON_MINUTE", "0"))
CALENDLY_POLL_MINUTES   = int(os.environ.get("CALENDLY_POLL_MINUTES", "15"))
DISCORD_POLL_MINUTES    = int(os.environ.get("DISCORD_POLL_MINUTES",  "5"))

_scheduler        = None
_run_lock         = threading.Lock()
_calendly_lock    = threading.Lock()
_is_running       = False  # flipped inside the lock; readable outside for status checks
_calendly_running = False


def _run_pipeline():
    """
    Actual job function — called both by the cron trigger and by run_now().
    Iterates over all active tenants and runs the full pipeline for each one.
    Never raises: any unhandled exception is logged and swallowed so the
    BackgroundScheduler thread stays alive.
    """
    global _is_running

    # ── Concurrent-run guard ──────────────────────────────────────────────────
    if not _run_lock.acquire(blocking=False):
        logger.info("Scan already in progress — skipping this trigger.")
        return

    try:
        _is_running = True

        # ── Pause check ───────────────────────────────────────────────────────
        # Read from the first active tenant's DB for global pause state.
        # Individual niche pauses are checked inside _run_niche_agent() in main.py.
        state = get_scheduler_state()
        if state and state.get("is_paused"):
            reason = state.get("paused_reason") or "no reason given"
            logger.info("Scheduler is paused (%s) — skipping run.", reason)
            return

        # ── Get active tenants ────────────────────────────────────────────────
        try:
            from master_db import get_active_tenants
            tenants = get_active_tenants()
        except Exception:
            # master_db not initialised yet (legacy single-tenant mode)
            tenants = []

        if not tenants:
            # Legacy single-tenant mode — no master DB, run once with env var config
            logger.info("No tenants in master DB — running in single-tenant mode.")
            _run_tenant_pipeline(None)
            return

        # ── Multi-tenant: run for each active tenant ──────────────────────────
        for tenant in tenants:
            slug = tenant["slug"]
            logger.info("Starting pipeline for tenant: %s", slug)
            _run_tenant_pipeline(slug)
            logger.info("Pipeline complete for tenant: %s", slug)

    except Exception as e:
        try:
            log_pipeline_error(
                None, "pipeline",
                f"Unhandled error in scheduled run: {type(e).__name__}: {e}",
                CRITICAL,
            )
        except Exception:
            pass
        logger.exception("Unhandled error in scheduled scan run.")

    finally:
        _is_running = False
        _run_lock.release()


def _run_tenant_pipeline(tenant_slug):
    """
    Run the full outbound pipeline for a single tenant.
    Sets the tenant slug on the current thread before calling main.main()
    so database.py routes all queries to the correct tenant DB.
    """
    try:
        from database import set_tenant_slug, init_db
        if tenant_slug:
            set_tenant_slug(tenant_slug)
            init_db()  # ensure schema exists (idempotent)
        import main as _main
        _main.main()
    except Exception as e:
        try:
            log_pipeline_error(
                None, "pipeline",
                f"Pipeline error for tenant '{tenant_slug}': {type(e).__name__}: {e}",
                CRITICAL,
            )
        except Exception:
            pass
        logger.exception("Pipeline error for tenant '%s'.", tenant_slug)


def _run_digest_job():
    """
    Daily digest email — sent after the primary scan completes (default 5:00 PM).
    Skipped silently if DIGEST_EMAIL_TO or SMTP/SendGrid credentials are not set.
    """
    try:
        import digest_mailer as _dm
        _dm.send_daily_digest()
    except Exception as e:
        logger.exception("Unhandled error in daily digest job: %s", e)


_discord_lock    = threading.Lock()
_discord_running = False


def _poll_discord_job():
    """
    Discord channel polling job — runs every 5 minutes.
    Skipped silently if DISCORD_BOT_TOKEN is not set.
    Uses its own lock to avoid blocking the main scan pipeline.
    """
    global _discord_running

    import os as _os
    if not _os.environ.get("DISCORD_BOT_TOKEN") and not _os.environ.get("DISCORD_USER_TOKEN"):
        return  # not configured — skip silently

    if not _discord_lock.acquire(blocking=False):
        logger.info("Discord poll already in progress — skipping.")
        return

    try:
        _discord_running = True
        from discord_watcher import run_all_polls
        results = run_all_polls()
        stored  = sum(r.get("stored", 0) for r in results)
        if stored:
            logger.info("Discord poll: %d new prospects from %d channels", stored, len(results))
    except Exception as e:
        logger.exception("Unhandled error in Discord poll job: %s", e)
    finally:
        _discord_running = False
        _discord_lock.release()


def _poll_calendly_job():
    """
    15-minute Calendly polling job.
    Skipped silently if CALENDLY_TOKEN is not set (token not configured yet).
    Uses a separate lock so it never blocks or delays the main scan pipeline.
    """
    global _calendly_running

    import os as _os
    if not _os.environ.get("CALENDLY_TOKEN"):
        return  # not configured — skip silently

    if not _calendly_lock.acquire(blocking=False):
        logger.info("Calendly poll already in progress — skipping this trigger.")
        return

    try:
        _calendly_running = True
        import calendly_watcher as _cw
        result = _cw.poll_new_bookings()
        if result["new_bookings"]:
            logger.info(
                "Calendly poll: %d new booking(s) processed.",
                result["new_bookings"],
            )
    except Exception as e:
        logger.exception("Unhandled error in Calendly poll job: %s", e)
    finally:
        _calendly_running = False
        _calendly_lock.release()


def _run_nightly_content():
    """
    Nightly content generation job — runs at 02:00.
    Generates 2 Reddit posts + 2 X threads based on top signals from the last 14 days.
    Each draft is saved with auto_generated=True and source_signal set.
    All exceptions per-item are caught and logged so the job always completes.
    """
    from value_post_generator import generate_targeted_post, generate_targeted_x_thread
    from database import create_value_post, _reader
    from sqlalchemy import text as _t

    REDDIT_DEMO = [
        {'signal': 'blown account day trading',  'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Just blew my 3rd account."},
        {'signal': 'revenge trading spiral',     'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Revenge traded a loss into a bigger loss."},
    ]
    X_DEMO = [
        {'signal': 'IV crush destroyed trade',  'pod': 'options',      'example': '"IV crush" destroyed my trade'},
        {'signal': 'failed prop firm eval',     'pod': 'futures',      'example': 'Failed my 3rd prop firm eval'},
    ]

    def _top_signal(src_platform):
        try:
            plat_filter = (
                "AND (platform='x' OR platform='twitter')"
                if src_platform == 'x'
                else "AND (platform='reddit' OR platform IS NULL)"
            )
            with _reader() as conn:
                row = conn.execute(_t(f"""
                    SELECT signal_phrase,
                           GROUP_CONCAT(DISTINCT subreddit) AS subs,
                           GROUP_CONCAT(DISTINCT pod_slug)  AS pods,
                           MIN(post_text) AS example,
                           COUNT(*) AS cnt
                    FROM prospects
                    WHERE signal_phrase IS NOT NULL AND signal_phrase != ''
                      AND scraped_at >= datetime('now', '-14 days')
                      {plat_filter}
                    GROUP BY signal_phrase
                    ORDER BY cnt DESC
                    LIMIT 1
                """)).fetchone()
            if row:
                return {
                    'signal':    row[0],
                    'subreddit': (row[1] or 'Daytrading').split(',')[0].strip(),
                    'pod':       (row[2] or 'daytrading').split(',')[0].strip(),
                    'example':   row[3] or '',
                }
        except Exception:
            pass
        return None

    import random
    count = 0

    # 2 Reddit posts
    for i in range(2):
        try:
            sig = _top_signal('reddit')
            if not sig:
                sig = random.choice(REDDIT_DEMO)
            result = generate_targeted_post(
                signal       = sig['signal'],
                subreddit    = sig.get('subreddit', 'Daytrading'),
                example_post = sig.get('example', ''),
            )
            if result:
                pid = create_value_post(
                    subreddit      = result['subreddit'],
                    post_type      = result['type'],
                    title          = result['title'],
                    body           = result['body'],
                    topic          = result.get('topic'),
                    signals        = result.get('signals', []),
                    post_count     = 0,
                    auto_generated = True,
                    source_signal  = sig['signal'],
                    platform       = 'reddit',
                    image_prompt   = result.get('image_prompt'),
                )
                count += 1
        except Exception as e:
            logger.error("[content] nightly reddit post %d failed: %s", i + 1, e)

    # 2 X threads
    for i in range(2):
        try:
            sig = _top_signal('x')
            if not sig:
                sig = random.choice(X_DEMO)
            niche  = sig.get('pod', 'daytrading').replace('-', ' ')
            result = generate_targeted_x_thread(
                signal       = sig['signal'],
                niche        = niche,
                example_post = sig.get('example', ''),
            )
            if result:
                body_text = '\n\n'.join(result.get('tweets', []))
                hook      = result.get('hook', sig['signal'])
                pid = create_value_post(
                    subreddit      = 'x',
                    post_type      = 'x_thread',
                    title          = hook[:200],
                    body           = body_text,
                    topic          = sig['signal'],
                    signals        = [sig['signal']],
                    post_count     = 0,
                    auto_generated = True,
                    source_signal  = sig['signal'],
                    platform       = 'x',
                    image_prompt   = result.get('image_prompt'),
                )
                count += 1
        except Exception as e:
            _alert_error(f"nightly_x_thread_{i+1}", e)

    logger.info("[content] nightly: %d drafted and sent to Telegram", count)


_perf_lock    = threading.Lock()
_comment_lock = threading.Lock()


def _run_performance_check():
    """Every 6 hours — update upvotes + comments on all posted content."""
    if not _perf_lock.acquire(blocking=False):
        return
    try:
        from performance_tracker import run_performance_check
        updated = run_performance_check()
        if updated:
            logger.info("[perf] updated %d posts", updated)
    except Exception as e:
        _alert_error("performance_check", e)
    finally:
        _perf_lock.release()


def _run_comment_monitor():
    """Every 2 hours — check for qualifying comments on posted Reddit content."""
    if not _comment_lock.acquire(blocking=False):
        return
    try:
        from comment_monitor import run_comment_monitor
        found = run_comment_monitor()
        if found:
            logger.info("[comments] %d new leads found", found)
    except Exception as e:
        _alert_error("comment_monitor", e)
    finally:
        _comment_lock.release()


def _run_scheduled_posts():
    """Every 15 min — post any approved content whose scheduled_for has passed."""
    try:
        from database import get_scheduled_value_posts, update_value_post
        from social_poster import post_content

        due = get_scheduled_value_posts()
        for p in due:
            pid = p["id"]
            try:
                result = post_content(p)
                if result.get('ok'):
                    url = result.get('url', '')
                    update_value_post(pid, status='posted', post_url=url, scheduled_for=None)
                    logger.info("[scheduler] posted scheduled post %d → %s", pid, url)
                    platform = (p.get('platform') or 'reddit').lower()
                    plat_lbl = f"r/{p.get('subreddit','')}" if platform == 'reddit' else '𝕏'
                    _tg_notify(f"✅ Scheduled post live on {plat_lbl}\n{url}")
                else:
                    err = result.get('error', 'unknown')
                    logger.warning("[scheduler] scheduled post %d failed: %s", pid, err)
                    update_value_post(pid, status='approved')
            except Exception as e:
                _alert_error(f"scheduled_post_{pid}", e)
    except Exception as e:
        _alert_error("scheduled_posts", e)


_warmup_lock = threading.Lock()


def _run_reddit_warmup():
    """Daily Reddit account warmup — generate one genuine comment per day."""
    if not _warmup_lock.acquire(blocking=False):
        return
    try:
        from reddit_warmer import run_daily_warmup
        queued = run_daily_warmup()
        if queued:
            logger.info('[warmup] comment queued for Telegram approval')
        else:
            logger.info('[warmup] no suitable post found today — skipped')
    except Exception as e:
        _alert_error("reddit_warmup", e)
    finally:
        _warmup_lock.release()


def _tg_notify(message: str):
    """Send a plain text message to the Telegram approval chat."""
    import os, json, urllib.request
    token   = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        return
    try:
        body = json.dumps({"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}).encode()
        req  = urllib.request.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=body, headers={"Content-Type": "application/json"}, method="POST",
        )
        urllib.request.urlopen(req, timeout=8)
    except Exception:
        pass


def _alert_error(job_name: str, error: Exception):
    """Send a job failure alert to Telegram."""
    msg = f"🚨 *AltusFlow job failed: {job_name}*\n\n`{type(error).__name__}: {str(error)[:300]}`"
    _tg_notify(msg)
    logger.error('[alert] %s failed: %s', job_name, error)


def start():
    """
    Start the BackgroundScheduler. Called once at Flask app startup.
    Safe to call multiple times — no-op if already running.
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler already running — start() is a no-op.")
        return

    _scheduler = BackgroundScheduler(daemon=True)
    _scheduler.add_job(
        _run_pipeline,
        trigger=CronTrigger(hour=SCAN_CRON_HOUR, minute=SCAN_CRON_MINUTE),
        id="daily_scan",
        name="Outbound Hunter scan (market close)",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
    _scheduler.add_job(
        _run_pipeline,
        trigger=CronTrigger(hour=SCAN_CRON_HOUR_2, minute=SCAN_CRON_MINUTE_2),
        id="daily_scan_evening",
        name="Outbound Hunter scan (evening — FA clients)",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
    _scheduler.add_job(
        _run_digest_job,
        trigger=CronTrigger(hour=DIGEST_CRON_HOUR, minute=DIGEST_CRON_MINUTE),
        id="daily_digest",
        name="Daily digest email",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
    _scheduler.add_job(
        _poll_calendly_job,
        trigger=IntervalTrigger(minutes=CALENDLY_POLL_MINUTES),
        id="calendly_poll",
        name="Calendly booking poll",
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
    )
    _scheduler.add_job(
        _poll_discord_job,
        trigger=IntervalTrigger(minutes=DISCORD_POLL_MINUTES),
        id="discord_poll",
        name="Discord channel poll",
        replace_existing=True,
        misfire_grace_time=60,
        coalesce=True,
    )
    _scheduler.add_job(
        _run_nightly_content,
        trigger=CronTrigger(hour=2, minute=0),
        id="nightly_content",
        name="Nightly content generation",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )
    _scheduler.add_job(
        _run_performance_check,
        trigger=IntervalTrigger(hours=6),
        id="perf_check",
        name="Post performance check",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
    _scheduler.add_job(
        _run_comment_monitor,
        trigger=IntervalTrigger(hours=2),
        id="comment_monitor",
        name="Comment lead monitor",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
    _scheduler.add_job(
        _run_scheduled_posts,
        trigger=IntervalTrigger(minutes=15),
        id="scheduled_posts",
        name="Post scheduled content",
        replace_existing=True,
        misfire_grace_time=120,
        coalesce=True,
    )
    _scheduler.add_job(
        _run_reddit_warmup,
        trigger=CronTrigger(hour=10, minute=30),  # 10:30 AM daily — mid-morning activity looks human
        id="reddit_warmup",
        name="Reddit account warmup",
        replace_existing=True,
        misfire_grace_time=600,
        coalesce=True,
    )
    _scheduler.start()
    logger.info(
        "Scheduler started. Scans at %02d:%02d and %02d:%02d. Digest at %02d:%02d. "
        "Calendly every %d min. Discord every %d min.",
        SCAN_CRON_HOUR, SCAN_CRON_MINUTE,
        SCAN_CRON_HOUR_2, SCAN_CRON_MINUTE_2,
        DIGEST_CRON_HOUR, DIGEST_CRON_MINUTE,
        CALENDLY_POLL_MINUTES, DISCORD_POLL_MINUTES,
    )


def stop():
    """
    Gracefully stop the scheduler. Called on Flask app teardown.
    wait=False: does not block for an in-flight run to complete.
    """
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler stopped.")


def run_now():
    """
    Trigger an immediate scan in a background thread.
    Respects the same concurrent-run guard as the cron trigger.
    Does NOT bypass the pause check — call resume() first if paused.

    Returns (started: bool, message: str).
    """
    if _is_running:
        return False, "A scan is already in progress. Try again when it finishes."

    state = get_scheduler_state()
    if state and state.get("is_paused"):
        reason = state.get("paused_reason") or "paused"
        return False, f"Scheduler is paused: {reason}. Resume it first from the admin page."

    t = threading.Thread(target=_run_pipeline, name="manual_scan", daemon=True)
    t.start()
    return True, "Scan started in the background."


def pause(reason="Manually paused by admin"):
    """
    Persist pause state to DB. The next cron trigger will read this and skip.
    Existing in-flight run is NOT interrupted — it finishes normally.
    """
    set_scheduler_paused(True, reason)
    logger.info("Scheduler paused: %s", reason)


def resume():
    """Clear pause state. The next cron trigger (or run_now) will proceed normally."""
    set_scheduler_paused(False, None)
    logger.info("Scheduler resumed.")


def get_status():
    """
    Return a dict consumed by the /admin page.

    Keys:
      is_paused       — bool, from DB (survives restarts)
      paused_reason   — str | None
      paused_at       — ISO timestamp | None
      is_running      — bool, current in-flight flag
      next_run        — str "YYYY-MM-DD HH:MM:SS TZ" | None
      cron_schedule   — human-readable "HH:MM daily"
      scheduler_alive — bool, APScheduler thread is up
    """
    state = get_scheduler_state() or {}

    next_run = None
    next_run_evening = None
    if _scheduler and _scheduler.running:
        job = _scheduler.get_job("daily_scan")
        if job and job.next_run_time:
            next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")
        job2 = _scheduler.get_job("daily_scan_evening")
        if job2 and job2.next_run_time:
            next_run_evening = job2.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")

    # Calendly poll next-run time
    next_calendly_run = None
    if _scheduler and _scheduler.running:
        cal_job = _scheduler.get_job("calendly_poll")
        if cal_job and cal_job.next_run_time:
            next_calendly_run = cal_job.next_run_time.strftime("%Y-%m-%d %H:%M:%S %Z")

    import os as _os
    return {
        "is_paused":          bool(state.get("is_paused")),
        "paused_reason":      state.get("paused_reason"),
        "paused_at":          state.get("paused_at"),
        "is_running":         _is_running,
        "next_run":           next_run,
        "next_run_evening":   next_run_evening,
        "cron_schedule":      f"{SCAN_CRON_HOUR:02d}:{SCAN_CRON_MINUTE:02d} daily",
        "cron_schedule_2":    f"{SCAN_CRON_HOUR_2:02d}:{SCAN_CRON_MINUTE_2:02d} daily",
        "scheduler_alive":    bool(_scheduler and _scheduler.running),
        "digest_schedule":    f"{DIGEST_CRON_HOUR:02d}:{DIGEST_CRON_MINUTE:02d} daily",
        "digest_enabled":     bool(_os.environ.get("DIGEST_EMAIL_TO")),
        "calendly_enabled":   bool(_os.environ.get("CALENDLY_TOKEN")),
        "calendly_running":   _calendly_running,
        "next_calendly_run":  next_calendly_run,
        "calendly_interval":  f"every {CALENDLY_POLL_MINUTES} min",
    }
