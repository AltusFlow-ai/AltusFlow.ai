"""
error_logger.py
Structured error capture and notification dispatch for the Outbound Hunter pipeline.

Every pipeline failure writes a JSON entry to scan_runs.error_log.
Critical failures additionally write to the notifications table and optionally
POST to ALERT_WEBHOOK_URL (Slack incoming webhook, Make.com, Zapier, any HTTP endpoint).

Severity levels:
  critical — scraper completely failed, HubSpot push failed, zero results >24h,
             high-value lead found. Always surfaces in UI badge.
  warning  — partial failure (some phrases failed, others ok). Batched in digest footnote.
  info     — no new prospects after dedup. Silent, logged only.

Usage:
    from error_logger import log_pipeline_error, CRITICAL, WARNING

    try:
        results = run_twitter()
    except Exception as e:
        log_pipeline_error(run_id, "twitter_scraper", str(e), CRITICAL)
        results = []
"""

import os
import json
import urllib.request
from datetime import datetime, timezone

CRITICAL = "critical"
WARNING  = "warning"
INFO     = "info"

ALERT_WEBHOOK_URL = os.environ.get("ALERT_WEBHOOK_URL", "")

# Default suggested fixes keyed by pipeline step name.
# These appear in the UI notification modal and any webhook payloads.
SUGGESTED_FIXES = {
    "twitter_scraper":  (
        "Verify TWITTER_BEARER_TOKEN is set and not expired. "
        "Check rate limits and quota at developer.twitter.com."
    ),
    "linkedin_scraper": (
        "Verify APIFY_API_TOKEN is valid. Free tier = 5 actor runs/month. "
        "Check quota at console.apify.com/account/usage."
    ),
    "hubspot_push": (
        "Verify HUBSPOT_TOKEN is a valid Private App token with "
        "contacts, deals, and notes write scope. "
        "Check token at HubSpot > Settings > Integrations > Private Apps."
    ),
    "zero_results": (
        "Check that scraper API tokens are valid and returning results. "
        "Consider widening signal phrase library if this persists across multiple runs."
    ),
    "database": (
        "Verify DATABASE_URL env var is set correctly. "
        "For PostgreSQL, check server is reachable and credentials are valid."
    ),
    "drafter": (
        "Verify ANTHROPIC_API_KEY is set and has quota remaining. "
        "Check usage at console.anthropic.com."
    ),
    "auto_router": (
        "Verify ANTHROPIC_API_KEY is set and has quota remaining. "
        "Affected prospects have been kept as 'pending' — no data was lost."
    ),
    "qualify": (
        "Internal scoring error. Likely a missing key in prospect data. "
        "Check qualify.py and the scraper output schema."
    ),
}


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_pipeline_error(run_id, step, message, severity=WARNING, suggested_fix=None):
    """
    Log a structured pipeline error.

    Always appends a JSON entry to scan_runs.error_log.
    If severity == CRITICAL: also writes to notifications table and fires webhook.

    Args:
        run_id:        scan_runs.id for the current pipeline run (None is safe)
        step:          pipeline step key, e.g. "twitter_scraper", "hubspot_push"
        message:       error message string
        severity:      CRITICAL | WARNING | INFO
        suggested_fix: override the default suggested fix for this step
    """
    # Deferred import to avoid any module-load circularity
    from database import append_scan_error, log_notification

    fix = suggested_fix or SUGGESTED_FIXES.get(step, "Check application logs for details.")

    entry = {
        "step":          step,
        "severity":      severity,
        "message":       str(message),
        "suggested_fix": fix,
        "timestamp":     _now(),
    }

    # Always append to scan_run error log (best-effort — never crashes pipeline)
    if run_id is not None:
        try:
            append_scan_error(run_id, entry)
        except Exception:
            pass

    # Critical: write to notifications table + fire optional webhook
    if severity == CRITICAL:
        try:
            log_notification(
                notif_type=step,
                severity=severity,
                title=f"[{step.upper().replace('_', ' ')}] {str(message)[:100]}",
                body=_format_markdown(entry),
                suggested_fix=fix,
                run_id=run_id,
            )
        except Exception:
            pass

        if ALERT_WEBHOOK_URL:
            _fire_webhook(entry)


def _format_markdown(entry):
    """Render a structured error entry as Markdown for the UI notification modal."""
    emoji = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(entry["severity"], "⚪")
    return "\n".join([
        f"## {emoji} Pipeline Error — `{entry['step']}`",
        "",
        f"**Severity:** `{entry['severity'].upper()}`  ",
        f"**Time:** {entry['timestamp']}",
        "",
        "**Error:**",
        "```",
        entry["message"],
        "```",
        "",
        "**Suggested fix:**",
        entry["suggested_fix"],
    ])


def _fire_webhook(entry):
    """
    POST a critical error payload to ALERT_WEBHOOK_URL.
    Payload format is Slack-compatible (attachments API).
    Works with Make.com, Zapier, and any HTTP endpoint that accepts JSON.
    Never raises — webhook failure must not interrupt the pipeline.
    """
    if not ALERT_WEBHOOK_URL:
        return
    payload = json.dumps({
        "text": f":rotating_light: *AltusFlow Critical Error* — `{entry['step']}`",
        "attachments": [{
            "color":  "danger",
            "fields": [
                {"title": "Step",          "value": entry["step"],          "short": True},
                {"title": "Severity",      "value": entry["severity"],      "short": True},
                {"title": "Error",         "value": entry["message"][:500], "short": False},
                {"title": "Suggested fix", "value": entry["suggested_fix"], "short": False},
                {"title": "Time",          "value": entry["timestamp"],     "short": True},
            ],
            "footer": "AltusFlow Outbound Hunter",
        }],
    }).encode()
    try:
        req = urllib.request.Request(
            ALERT_WEBHOOK_URL,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=5)
    except Exception:
        pass


# ── Convenience wrappers ──────────────────────────────────────────────────────

def log_zero_results_alert(run_id, platform, hours_since_last=None):
    """
    Critical alert: scraper returned zero results.
    Fires when a platform scan produces nothing after deduplication.
    """
    msg = f"Zero prospects found on {platform}"
    if hours_since_last is not None:
        msg += f" — last successful result was {hours_since_last:.0f}h ago"
    log_pipeline_error(run_id, "zero_results", msg, CRITICAL)


def log_hs_failure(run_id, prospect_name, error_detail):
    """
    Critical alert: HubSpot atomic push failed for a specific prospect.
    Called from app.py /approve and /retry_hs routes.
    """
    log_pipeline_error(
        run_id,
        "hubspot_push",
        f"HubSpot push failed for {prospect_name}: {str(error_detail)[:200]}",
        CRITICAL,
    )


def log_high_value_lead(run_id, prospect):
    """
    Exception-only notification for high-value leads (icp_score > 8).
    These are auto-approved but the founder is alerted immediately
    rather than waiting for their next UI visit.
    """
    from database import log_notification

    name  = prospect.get("name") or prospect.get("handle") or "Unknown"
    score = prospect.get("icp_score", 0)
    conf  = prospect.get("confidence_score", "—")
    niche = prospect.get("niche") or "Unknown"
    plat  = prospect.get("platform", "—")

    body = "\n".join([
        "## High-Value Lead Found",
        "",
        f"**Name:** {name}",
        f"**Platform:** {plat}",
        f"**Niche:** {niche}",
        f"**ICP Score:** {score}/10",
        f"**AI Confidence:** {conf}/10",
        f"**Signal phrase:** {prospect.get('signal_phrase', '—')}",
        "",
        "This prospect was auto-approved and is waiting in the Batch Confirm queue.",
        "Review the drafted message before confirming.",
    ])

    try:
        log_notification(
            notif_type="high_value_lead",
            severity=CRITICAL,
            title=f"High-value lead: {name} (ICP {score}/10, Confidence {conf}/10)",
            body=body,
            suggested_fix="Review and batch-confirm from the Batch Confirm page.",
            run_id=run_id,
        )
    except Exception:
        pass

    if ALERT_WEBHOOK_URL:
        _fire_webhook({
            "step":          "high_value_lead",
            "severity":      CRITICAL,
            "message":       f"{name} | ICP {score}/10 | Confidence {conf}/10 | Niche: {niche}",
            "suggested_fix": "Review in batch confirm queue.",
            "timestamp":     _now(),
        })
