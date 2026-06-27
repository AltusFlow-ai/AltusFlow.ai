"""
digest_mailer.py
Daily summary email sent at 6:30 AM after the 6:00 AM scan completes.

Supports:
  - SMTP (Gmail, Outlook, any provider) via SMTP_HOST/SMTP_PORT/SMTP_USER/SMTP_PASS
  - SendGrid via SENDGRID_API_KEY

Silent skip if neither is configured — no errors, no crashes.

Env vars:
  DIGEST_EMAIL_TO      — recipient address (required for any email to send)
  SMTP_HOST            — e.g. smtp.gmail.com
  SMTP_PORT            — e.g. 587
  SMTP_USER            — sender email
  SMTP_PASS            — app password (not your login password for Gmail)
  SENDGRID_API_KEY     — alternative to SMTP

Usage (called by scheduler.py daily at 6:30 AM):
  from digest_mailer import send_daily_digest
  send_daily_digest()
"""

import os
import logging

logger = logging.getLogger(__name__)

_DIGEST_TO   = os.environ.get("DIGEST_EMAIL_TO", "")
_SMTP_HOST   = os.environ.get("SMTP_HOST", "")
_SMTP_PORT   = int(os.environ.get("SMTP_PORT", "587"))
_SMTP_USER   = os.environ.get("SMTP_USER", "")
_SMTP_PASS   = os.environ.get("SMTP_PASS", "")
_SENDGRID_KEY = os.environ.get("SENDGRID_API_KEY", "")


def _is_configured() -> bool:
    if not _DIGEST_TO:
        return False
    return bool(_SMTP_HOST and _SMTP_USER and _SMTP_PASS) or bool(_SENDGRID_KEY)


def _build_subject_and_body(stats: dict, top_prospect: dict | None) -> tuple[str, str, str]:
    """Return (subject, plain_text, html)."""
    found      = stats.get("total", 0)
    qualified  = stats.get("pending", 0) + stats.get("auto_approved", 0)
    auto_app   = stats.get("auto_approved", 0)
    pending    = stats.get("pending", 0)
    app_url    = os.environ.get("SITE_URL", "http://localhost:5000")

    subject = f"AltusFlow Hunter — Daily Digest"

    plain = f"""Today's scan results:
- Qualified (score 4+):   {qualified}
- Auto-approved (9+):     {auto_app}
- Pending your review:    {pending}

Open batch confirm: {app_url}/batch-confirm
"""

    if top_prospect:
        name      = top_prospect.get("name") or top_prospect.get("handle") or "Unknown"
        platform  = top_prospect.get("platform", "reddit")
        subreddit = top_prospect.get("subreddit") or top_prospect.get("group_name", "")
        score     = top_prospect.get("icp_score", "?")
        post      = (top_prospect.get("post_text") or "")[:100]
        plain += f"""
Top prospect today:
  Name:     {name}
  Platform: {platform}{f" — r/{subreddit}" if subreddit else ""}
  Score:    {score}/10
  Post:     "{post}..."
"""

    html = f"""<html><body style="font-family:system-ui,sans-serif;background:#0a0a0a;color:#e4e4e4;padding:32px">
<div style="max-width:560px;margin:0 auto">
  <h2 style="color:#1D9E75;margin-bottom:24px">AltusFlow Hunter — Daily Digest</h2>

  <table style="width:100%;border-collapse:collapse;margin-bottom:24px">
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #222;color:#aaa">Qualified (score 4+)</td>
      <td style="padding:10px 0;border-bottom:1px solid #222;text-align:right;font-weight:600">{qualified}</td>
    </tr>
    <tr>
      <td style="padding:10px 0;border-bottom:1px solid #222;color:#aaa">Auto-approved (9+)</td>
      <td style="padding:10px 0;border-bottom:1px solid #222;text-align:right;font-weight:600;color:#1D9E75">{auto_app}</td>
    </tr>
    <tr>
      <td style="padding:10px 0;color:#aaa">Pending your review</td>
      <td style="padding:10px 0;text-align:right;font-weight:600;color:#EF9F27">{pending}</td>
    </tr>
  </table>

  <a href="{app_url}/batch-confirm"
     style="display:inline-block;background:#1D9E75;color:#fff;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:600;margin-bottom:24px">
    Open batch confirm →
  </a>
"""

    if top_prospect:
        name      = top_prospect.get("name") or top_prospect.get("handle") or "Unknown"
        platform  = top_prospect.get("platform", "reddit")
        subreddit = top_prospect.get("subreddit") or top_prospect.get("group_name", "")
        score     = top_prospect.get("icp_score", "?")
        post      = (top_prospect.get("post_text") or "")[:120]
        html += f"""
  <div style="background:#111;border:1px solid #222;border-radius:8px;padding:20px;margin-top:8px">
    <p style="color:#888;font-size:12px;text-transform:uppercase;letter-spacing:.06em;margin-bottom:12px">Top Prospect Today</p>
    <p style="font-weight:600;color:#fff;margin-bottom:4px">{name}</p>
    <p style="color:#666;font-size:13px;margin-bottom:12px">{platform}{f" · r/{subreddit}" if subreddit else ""} · ICP {score}/10</p>
    <p style="font-size:13px;color:#aaa;font-style:italic">"{post}..."</p>
  </div>
"""

    html += "</div></body></html>"

    return subject, plain, html


def _send_smtp(to: str, subject: str, plain: str, html: str) -> bool:
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = _SMTP_USER
    msg["To"]      = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html,  "html"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=15) as s:
            s.ehlo()
            s.starttls()
            s.login(_SMTP_USER, _SMTP_PASS)
            s.sendmail(_SMTP_USER, [to], msg.as_string())
        return True
    except Exception as e:
        logger.error("SMTP digest send failed: %s", e)
        return False


def _send_sendgrid(to: str, subject: str, plain: str, html: str) -> bool:
    import urllib.request, urllib.error, json as _json
    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from":             {"email": _SMTP_USER or "noreply@altusflow.ai"},
        "subject":          subject,
        "content":          [
            {"type": "text/plain", "value": plain},
            {"type": "text/html",  "value": html},
        ],
    }
    data = _json.dumps(payload).encode()
    req  = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={
            "Authorization": f"Bearer {_SENDGRID_KEY}",
            "Content-Type":  "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status in (200, 202)
    except Exception as e:
        logger.error("SendGrid digest send failed: %s", e)
        return False


def send_daily_digest() -> bool:
    """
    Send daily digest email. Returns True if sent, False if skipped or failed.
    Never raises — always safe to call from the scheduler.
    """
    if not _is_configured():
        return False

    try:
        from database import get_stats, get_pending, get_auto_approved

        stats = get_stats()

        # Pick the top prospect (highest ICP score from pending + auto_approved)
        candidates = list(get_auto_approved()) + list(get_pending())
        candidates.sort(key=lambda p: p.get("icp_score", 0), reverse=True)
        top = candidates[0] if candidates else None

        subject, plain, html = _build_subject_and_body(stats, top)

        if _SENDGRID_KEY:
            sent = _send_sendgrid(_DIGEST_TO, subject, plain, html)
        else:
            sent = _send_smtp(_DIGEST_TO, subject, plain, html)

        if sent:
            logger.info("Daily digest sent to %s", _DIGEST_TO)
        return sent

    except Exception as e:
        logger.error("digest_mailer.send_daily_digest failed: %s", e)
        return False
