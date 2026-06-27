"""
app.py
Flask web UI for the AltusFlow Outbound Hunter.

Route map:
  GET  /                          Pending review — manual exceptions (confidence 4-8)
  GET  /batch-confirm             One-click confirm — auto-approved prospects (confidence 9-10)
  POST /batch-confirm             Confirm selected prospects -> HubSpot push
  GET  /approved                  Outreach queue — approved, awaiting send
  GET  /admin                     Scheduler controls + recent alerts + scan stats
  POST /admin/run-now             Manual scan trigger (scheduler.run_now())
  POST /admin/pause               Pause scheduled runs (persisted to DB)
  POST /admin/resume              Resume scheduled runs
  GET  /admin/pods                Pod factory overview — all pods + status
  GET  /admin/pods/<slug>         Single pod detail + run history
  POST /admin/pods/<slug>/pause   Pause a pod
  POST /admin/pods/<slug>/resume  Resume a paused pod
  POST /admin/pods/<slug>/reset   Reset circuit breaker + resume pod
  POST /admin/pods/<slug>/run-now Force immediate pod run
  GET  /admin/pods/<slug>/logs    Last 50 run reports for a pod (JSON)
  POST /approve/<pid>             Approve single prospect + HubSpot push
  POST /retry_hs/<pid>            Retry failed HubSpot push
  POST /skip/<pid>                Skip a pending prospect
  POST /mark_sent/<pid>           Mark approved prospect as sent
  POST /acknowledge/<nid>         Acknowledge one notification
  POST /acknowledge-all           Acknowledge all notifications
  GET  /export                    Download approved prospects as CSV
  GET  /health                    UptimeRobot-ready monitoring endpoint
  GET  /api/scan-status           Polling endpoint for live scan progress
  GET  /budget                    Marketing budget dashboard (spend, pipeline, ROI)
  POST /budget/allocate           Create/update a budget category allocation
  POST /budget/log                Log a manual transaction (spend or revenue)
  GET  /budget/export             Download all transactions as CSV
  GET  /connections               Platform connections manager
  POST /connections/<platform>    Save an encrypted API token for a platform
  POST /connections/<p>/disconnect Remove stored token and mark platform disconnected

Classification (per autonomous mandate):
  fully-automated   — scraping, scoring, routing, error logging
  one-click confirm — /batch-confirm (auto_approved queue)
  must-remain-manual — /approve (individual), LinkedIn/Twitter message send
"""

import os
try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file, g, flash
from flask_login import login_required, current_user
from database import (
    init_db, get_pending, get_approved, get_auto_approved, get_prospect,
    update_status, update_hs_result, mark_sent,
    export_approved_csv, get_stats, get_distinct_niches, get_niche_counts,
    get_health_data, get_scan_status,
    get_notifications, acknowledge_notification, acknowledge_all_notifications,
    get_unacknowledged_count,
    set_niche_paused, get_niche_pause_states, get_registry_stats,
    get_platform_stats, get_platform_health,
    set_tenant_slug,
)
from hubspot import push_prospect_atomic
from brief_generator import generate_and_save as _generate_brief
from auth import auth_bp, login_manager
from master_db import init_master_db
import scheduler
try:
    from api import api as api_bp
except Exception as _api_e:
    import logging as _log
    _log.getLogger(__name__).warning("api blueprint load failed: %s", _api_e)
    api_bp = None

ALERT_HOURS = int(os.environ.get("ALERT_HOURS", "26"))
PAGE_SIZE   = 50

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "altusflow-hunter-2025")


@app.template_filter("currency")
def currency_filter(value):
    """Format a number as $X,XXX.XX — used by budget.html."""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "$0.00"

# ── Auth setup ────────────────────────────────────────────────────────────────
login_manager.init_app(app)
app.register_blueprint(auth_bp)
if os.environ.get("NO_AUTH", "false").lower() == "true":
    from dummy_api import dummy_api
    app.register_blueprint(dummy_api)
if api_bp:
    app.register_blueprint(api_bp)
try:
    from jobs_api import jobs_bp
    app.register_blueprint(jobs_bp)
except Exception as _jobs_e:
    import logging as _log
    _log.getLogger(__name__).warning("jobs blueprint load failed: %s", _jobs_e)
try:
    from webhooks import webhooks_bp
    app.register_blueprint(webhooks_bp)
except Exception as _wh_e:
    import logging as _log
    _log.getLogger(__name__).warning("webhooks blueprint load failed: %s", _wh_e)
try:
    import live_call as _lc
    _lc.register(app)
except Exception as _lce:
    import logging as _log
    _log.getLogger(__name__).warning("live_call load failed: %s", _lce)
init_master_db()


def _load_keys_from_db():
    """On startup, pull any API keys stored in the DB into os.environ.
    This lets Railway run with only FLASK_SECRET + SECRET_KEY + DATABASE_URL set —
    everything else is configured via the Connections dashboard page.
    """
    try:
        from master_db import get_active_tenants, get_all_tenant_config
        from auth import decrypt_token
        tenants = get_active_tenants()
        if not tenants:
            return
        config = get_all_tenant_config(tenants[0]['id'])
        for key, enc_value in config.items():
            if enc_value and not os.environ.get(key):
                decrypted = decrypt_token(enc_value)
                if decrypted:
                    os.environ[key] = decrypted
    except Exception:
        pass


_load_keys_from_db()
init_db()  # create all tables before the scheduler/orchestrator start


_NO_AUTH = os.environ.get("NO_AUTH", "false").lower() == "true"

_DEV_USER_ROW = {
    "id": "dev-0", "email": "dev@local", "role": "admin",
    "tenant_id": 0, "tenant_slug": "", "company_name": "Dev", "plan": "pro",
}


@app.before_request
def _set_tenant_context():
    """
    Two jobs per request:
    1. Gate: redirect unauthenticated users to /login (except /login, /logout, /health).
    2. Wire: set the tenant slug on g + database layer so every DB call routes correctly.
    """
    from flask import request as _req
    from flask_login import current_user as _cu

    # NO_AUTH bypass — dev user injected via request_loader in auth.py, no session needed
    if _NO_AUTH:
        return

    # Public endpoints — no auth required
    public = {"auth.login", "auth.logout", "health", "static"}
    if _req.endpoint in public:
        return
    if not _cu.is_authenticated:
        return redirect(url_for("auth.login", next=_req.url))
    g.tenant_slug = _cu.tenant_slug
    set_tenant_slug(_cu.tenant_slug)

# Start the background scheduler when the app module loads.
# BackgroundScheduler(daemon=True) dies with the process — no cleanup needed for dev.
# For gunicorn with multiple workers, set SCHEDULER_ENABLED=true only on one worker
# (or use an external cron that POSTs to /admin/run-now).
if os.environ.get("SCHEDULER_ENABLED", "true").lower() != "false":
    scheduler.start()

# Start Telegram approval bot (no-op if TELEGRAM_BOT_TOKEN not set)
try:
    import telegram_approver as _tg
    _tg.init()
except Exception as _tg_err:
    import logging as _lg
    _lg.getLogger(__name__).warning("Telegram approver init failed: %s", _tg_err)

# ── Real-time Reddit stream ────────────────────────────────────────────────────
# Daemon thread — monitors subreddits 24/7 via PRAW stream.
# All prospects land in pending_review with a staged Hermes draft (one-click approve).
# Mod outreach goes to mod_outreach table — never mixed with prospects.
# Disable with STREAM_ENABLED=false in .env.
if os.environ.get("STREAM_ENABLED", "true").lower() != "false":
    try:
        from stream_watcher import start as _start_stream
        _start_stream()
    except Exception as _se:
        import logging as _slog
        _slog.getLogger(__name__).warning("stream_watcher start failed: %s", _se)

# ── Pod orchestrator (opt-in via USE_POD_ORCHESTRATOR=true) ──────────────────
_pod_orchestrator = None
if os.environ.get("USE_POD_ORCHESTRATOR", "false").lower() == "true":
    try:
        from orchestrator import init_orchestrator
        _pod_orchestrator = init_orchestrator()
    except Exception as _oe:
        import logging as _log
        _log.getLogger(__name__).warning("Orchestrator init failed: %s", _oe)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ctx():
    """Common template context available on every page."""
    return {
        "niches":        get_distinct_niches(),
        "niche_counts":  get_niche_counts(),
        "alert_count":   get_unacknowledged_count(),
        "tenant_name":   current_user.company_name if current_user.is_authenticated else "",
        "tenant_slug":   current_user.tenant_slug  if current_user.is_authenticated else "",
        "user_email":    current_user.email         if current_user.is_authenticated else "",
    }


# ── Digest views ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    niche    = request.args.get("niche") or None
    pending  = get_pending(niche=niche)
    stats    = get_stats()
    return render_template(
        "digest.html",
        prospects=pending, stats=stats, view="pending",
        active_niche=niche, **_ctx()
    )


@app.route("/batch-confirm")
def batch_confirm():
    """One-click confirm queue — auto-approved prospects (confidence 9-10)."""
    niche       = request.args.get("niche") or None
    prospects   = get_auto_approved(niche=niche)
    stats       = get_stats()
    return render_template(
        "digest.html",
        prospects=prospects, stats=stats, view="batch_confirm",
        active_niche=niche, **_ctx()
    )


@app.route("/batch-confirm", methods=["POST"])
def batch_confirm_post():
    """
    Approve a selected subset of auto_approved prospects and push to HubSpot.

    Body: { "ids": [1, 2, 3], "messages": {"1": "...", "2": "..."} }
    Returns: { "results": [{"id": 1, "ok": true, ...}, ...] }

    CONSTRAINT: This is a one-click confirm — never auto-executed without a human POST.
    """
    data     = request.get_json() or {}
    ids      = data.get("ids", [])
    messages = data.get("messages", {})
    results  = []

    for pid in ids:
        message  = messages.get(str(pid), "")
        prospect = get_prospect(pid)
        if not prospect:
            results.append({"id": pid, "ok": False, "error": "Prospect not found"})
            continue

        update_status(pid, "approved", drafted_message=message)

        hs = push_prospect_atomic(prospect)
        if hs["ok"]:
            update_hs_result(
                pid,
                contact_id=hs["contact_id"],
                deal_id=hs["deal_id"],
                status="pushed",
            )
            results.append({
                "id":         pid,
                "ok":         True,
                "contact_id": hs["contact_id"],
                "deal_id":    hs["deal_id"],
            })
        else:
            update_hs_result(
                pid,
                contact_id=hs.get("contact_id"),
                deal_id=hs.get("deal_id"),
                status="failed",
                error=hs.get("error"),
            )
            results.append({
                "id":    pid,
                "ok":    False,
                "error": hs.get("error"),
                "step":  hs.get("step"),
            })

    return jsonify({"results": results})


@app.route("/approved")
def approved():
    niche     = request.args.get("niche") or None
    prospects = get_approved(niche=niche)
    stats     = get_stats()
    return render_template(
        "digest.html",
        prospects=prospects, stats=stats, view="approved",
        active_niche=niche, **_ctx()
    )


# ── Admin page ────────────────────────────────────────────────────────────────

@app.route("/admin")
def admin():
    sched_status       = scheduler.get_status()
    notifications      = get_notifications(unacknowledged_only=False)[:20]
    stats              = get_stats()
    niche_pause_states = get_niche_pause_states()
    registry_stats     = get_registry_stats()
    platform_stats     = get_platform_stats(days=7)
    return render_template(
        "admin.html",
        sched=sched_status,
        notifications=notifications,
        stats=stats,
        niche_pause_states=niche_pause_states,
        registry_stats=registry_stats,
        platform_stats=platform_stats,
        **_ctx()
    )


@app.route("/admin/run-now", methods=["POST"])
def admin_run_now():
    ok, message = scheduler.run_now()
    return jsonify({"ok": ok, "message": message})


@app.route("/admin/pause", methods=["POST"])
def admin_pause():
    reason = (request.get_json() or {}).get("reason", "Manually paused by admin")
    scheduler.pause(reason)
    return jsonify({"ok": True})


@app.route("/admin/resume", methods=["POST"])
def admin_resume():
    scheduler.resume()
    return jsonify({"ok": True})


# ── Notification acknowledgement ──────────────────────────────────────────────

@app.route("/acknowledge/<int:nid>", methods=["POST"])
def acknowledge(nid):
    acknowledge_notification(nid)
    return jsonify({"ok": True})


@app.route("/acknowledge-all", methods=["POST"])
def acknowledge_all():
    acknowledge_all_notifications()
    return jsonify({"ok": True})


# ── Prospect actions ──────────────────────────────────────────────────────────

@app.route("/approve/<int:pid>", methods=["POST"])
def approve(pid):
    data    = request.get_json()
    message = data.get("message", "")

    update_status(pid, "approved", drafted_message=message)

    prospect = get_prospect(pid)
    if not prospect:
        return jsonify({"ok": False, "error": "Prospect not found"})

    # Feed approved message back to Hermes Golden History as a positive example
    if message:
        try:
            from hermes import update_hermes_context
            update_hermes_context(
                signal_phrase=prospect.get("signal_phrase") or prospect.get("niche") or "general",
                feedback={
                    "type":    "positive",
                    "note":    "Owner approved this message for outreach",
                    "message": message,
                },
            )
        except Exception:
            pass  # Never block approval flow due to training errors

    result = push_prospect_atomic(prospect)
    if result["ok"]:
        update_hs_result(
            pid,
            contact_id=result["contact_id"],
            deal_id=result["deal_id"],
            status="pushed",
        )
        return jsonify({
            "ok":         True,
            "contact_id": result["contact_id"],
            "deal_id":    result["deal_id"],
        })
    else:
        update_hs_result(
            pid,
            contact_id=result.get("contact_id"),
            deal_id=result.get("deal_id"),
            status="failed",
            error=result.get("error"),
        )
        return jsonify({
            "ok":    False,
            "error": result.get("error"),
            "step":  result.get("step"),
        })


@app.route("/retry_hs/<int:pid>", methods=["POST"])
def retry_hs(pid):
    prospect = get_prospect(pid)
    if not prospect:
        return jsonify({"ok": False, "error": "Prospect not found"})

    result = push_prospect_atomic(prospect)
    if result["ok"]:
        update_hs_result(
            pid,
            contact_id=result["contact_id"],
            deal_id=result["deal_id"],
            status="pushed",
        )
        return jsonify({"ok": True, "contact_id": result["contact_id"], "deal_id": result["deal_id"]})
    else:
        update_hs_result(
            pid,
            contact_id=result.get("contact_id"),
            deal_id=result.get("deal_id"),
            status="failed",
            error=result.get("error"),
        )
        return jsonify({"ok": False, "error": result.get("error"), "step": result.get("step")})


@app.route("/skip/<int:pid>", methods=["POST"])
def skip(pid):
    update_status(pid, "skipped")
    return jsonify({"ok": True})


@app.route("/mark_sent/<int:pid>", methods=["POST"])
def mark_sent_route(pid):
    data    = request.get_json()
    message = data.get("message", "")
    mark_sent(pid, message)
    return jsonify({"ok": True})


@app.route("/export")
def export():
    path = export_approved_csv()
    if path and os.path.exists(path):
        return send_file(path, as_attachment=True, download_name="altusflow_outreach_queue.csv")
    return "No approved prospects to export yet.", 404


# ── Monitoring endpoints ──────────────────────────────────────────────────────

@app.route("/health")
def health():
    """
    UptimeRobot-ready health endpoint.
    Returns 200 always so Railway deployments pass. Only flags alert:true
    when a scan has previously run but is now overdue (not on fresh installs).
    """
    try:
        clients = get_health_data()
        # "never" means fresh install — not an alert condition
        alert = any(
            c["hours_since_scan"] > ALERT_HOURS
            for c in clients
            if c.get("last_scan_status") != "never"
        )
        payload = {
            "status":    "degraded" if alert else "ok",
            "clients":   clients,
            "platforms": get_platform_health(),
            "alert":     alert,
        }
    except Exception:
        payload = {"status": "ok", "alert": False}
    return jsonify(payload), 200


@app.route("/api/scan-status")
def scan_status():
    """Polling endpoint. Pass ?run_id=N for a specific run, or omit for latest."""
    run_id = request.args.get("run_id", type=int)
    run    = get_scan_status(run_id)
    if not run:
        return jsonify({"status": "no_runs", "message": "No scans have been run yet."})
    return jsonify(run)


# ── Niche pause controls ──────────────────────────────────────────────────────

@app.route("/admin/niche/<slug>/pause", methods=["POST"])
def admin_niche_pause(slug):
    reason = (request.get_json() or {}).get("reason", "Paused from admin UI")
    set_niche_paused(slug, True, reason)
    return jsonify({"ok": True})


@app.route("/admin/niche/<slug>/resume", methods=["POST"])
def admin_niche_resume(slug):
    set_niche_paused(slug, False)
    return jsonify({"ok": True})


# ── Pre-call brief ─────────────────────────────────────────────────────────────

@app.route("/generate-brief/<int:pid>", methods=["POST"])
def generate_brief_route(pid):
    result = _generate_brief(pid)
    return jsonify(result)


# ── Budget ────────────────────────────────────────────────────────────────────

@app.route("/budget")
def budget_page():
    from budget import (
        get_budget_summary, get_platform_breakdown, get_all_budgets,
        get_transactions,
    )
    # Filters from query string
    platform   = request.args.get("platform") or None
    direction  = request.args.get("direction") or None
    date_from  = request.args.get("date_from") or None
    date_to    = request.args.get("date_to")   or None
    offset     = max(0, request.args.get("offset", 0, type=int))

    summary            = get_budget_summary()
    platform_breakdown = get_platform_breakdown()
    budgets            = get_all_budgets()
    transactions, total_count = get_transactions(
        platform=platform, direction=direction,
        date_from=date_from, date_to=date_to,
        limit=PAGE_SIZE, offset=offset,
    )

    # Distinct platform list for the filter dropdown
    from database import _get_engine
    from sqlalchemy import text as _text
    with _get_engine().connect() as conn:
        raw = conn.execute(_text(
            "SELECT DISTINCT platform FROM budget_transactions ORDER BY platform"
        )).fetchall()
    platforms = [r[0] for r in raw]

    return render_template(
        "budget.html",
        summary=summary,
        platform_breakdown=platform_breakdown,
        budgets=budgets,
        transactions=transactions,
        total_count=total_count,
        offset=offset,
        page_size=PAGE_SIZE,
        platforms=platforms,
        filters={
            "platform":  platform  or "",
            "direction": direction or "",
            "date_from": date_from or "",
            "date_to":   date_to   or "",
        },
        **_ctx(),
    )


@app.route("/budget/allocate", methods=["POST"])
def budget_allocate():
    from budget import get_or_create_budget, update_budget_allocation
    name      = (request.form.get("budget_name") or "").strip()
    btype     = request.form.get("budget_type") or "monthly"
    allocated = request.form.get("allocated") or "0"
    if name:
        b = get_or_create_budget(name, btype)
        if b:
            update_budget_allocation(b["id"], float(allocated))
    return redirect(url_for("budget_page"))


@app.route("/budget/log", methods=["POST"])
def budget_log():
    from budget import log_transaction
    platform    = (request.form.get("platform")    or "").strip()
    description = (request.form.get("description") or "").strip()
    amount_raw  = request.form.get("amount") or "0"
    direction   = request.form.get("direction", "out")
    budget_name = (request.form.get("budget_name") or "").strip() or None
    if platform and description:
        try:
            amount = float(amount_raw)
            if amount > 0:
                log_transaction(
                    platform=platform, description=description,
                    amount=amount, direction=direction,
                    budget_name=budget_name,
                )
        except ValueError:
            pass
    return redirect(url_for("budget_page") + "?saved=1")


@app.route("/budget/export")
def budget_export():
    from budget import export_transactions_csv
    path = export_transactions_csv()
    if path and os.path.exists(path):
        return send_file(path, as_attachment=True, download_name="altusflow_budget.csv")
    return "No transactions to export yet.", 404


# ── Platform connections ──────────────────────────────────────────────────────

_ALLOWED_PLATFORMS = {"hubspot", "meta_ads", "apify", "calendly", "linkedin"}


@app.route("/connections")
def connections_page():
    from budget import get_all_connections
    raw_conns = get_all_connections()
    connections = {}
    for p in _ALLOWED_PLATFORMS:
        row = raw_conns.get(p, {})
        connections[p] = {
            "status":        row.get("status", "disconnected"),
            "account_id":    row.get("account_id"),
            "account_name":  row.get("account_name"),
            "connected_at":  row.get("connected_at"),
            "last_sync_at":  row.get("last_sync_at"),
            "error_message": row.get("error_message"),
        }
    return render_template("connections.html", connections=connections, **_ctx())


@app.route("/connections/<platform>", methods=["POST"])
def save_connection_route(platform):
    if platform not in _ALLOWED_PLATFORMS:
        return "Unknown platform", 400
    from budget import save_connection
    from auth import encrypt_token
    token      = (request.form.get("token") or "").strip()
    account_id = (request.form.get("account_id") or "").strip() or None
    acct_name  = (request.form.get("account_name") or "").strip() or None
    if token:
        save_connection(
            platform=platform,
            token_encrypted=encrypt_token(token),
            account_id=account_id,
            account_name=acct_name,
        )
    return redirect(url_for("connections_page") + f"?connected={platform}")


@app.route("/connections/<platform>/disconnect", methods=["POST"])
def disconnect_platform(platform):
    if platform not in _ALLOWED_PLATFORMS:
        return "Unknown platform", 400
    from budget import disconnect_connection
    disconnect_connection(platform)
    return redirect(url_for("connections_page") + f"?disconnected={platform}")


# ── Pod factory admin routes ──────────────────────────────────────────────────

_ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "")


def _is_admin():
    """True if the current user is allowed to access /admin/pods routes."""
    if not current_user.is_authenticated:
        return False
    if _ADMIN_EMAIL and current_user.email == _ADMIN_EMAIL:
        return True
    # Fallback: if no ADMIN_EMAIL is set, any logged-in user can access
    return not bool(_ADMIN_EMAIL)


def _require_admin():
    """Return 403 response if the current user is not an admin."""
    if not _is_admin():
        return jsonify({"ok": False, "error": "Admin access required"}), 403
    return None


@app.route("/admin/pods")
@login_required
def admin_pods():
    """Pod factory overview — list all discovered pods with status."""
    guard = _require_admin()
    if guard:
        return guard
    from database import get_all_pod_statuses
    pods = get_all_pod_statuses()
    orch_status = _pod_orchestrator.get_status() if _pod_orchestrator else {}
    return render_template(
        "admin_pods.html",
        pods=pods,
        orch_status=orch_status,
        pod_mode=bool(_pod_orchestrator),
        **_ctx(),
    )


@app.route("/admin/pods/<slug>")
@login_required
def admin_pod_detail(slug):
    """Single pod detail + last 20 run history."""
    guard = _require_admin()
    if guard:
        return guard
    from database import get_pod_registry, get_pod_run_history
    pod     = get_pod_registry(slug)
    history = get_pod_run_history(slug, limit=20)
    if not pod:
        return f"Pod '{slug}' not found", 404
    return render_template(
        "admin_pods.html",
        pod=pod,
        history=history,
        detail_view=True,
        **_ctx(),
    )


@app.route("/admin/pods/<slug>/pause", methods=["POST"])
@login_required
def admin_pod_pause(slug):
    guard = _require_admin()
    if guard:
        return guard
    reason = (request.get_json() or {}).get("reason", "Paused via admin UI")
    if _pod_orchestrator:
        _pod_orchestrator.pause_pod(slug, reason)
    else:
        from database import set_pod_paused
        set_pod_paused(slug, True, reason)
    return jsonify({"ok": True})


@app.route("/admin/pods/<slug>/resume", methods=["POST"])
@login_required
def admin_pod_resume(slug):
    guard = _require_admin()
    if guard:
        return guard
    if _pod_orchestrator:
        _pod_orchestrator.resume_pod(slug)
    else:
        from database import set_pod_paused
        set_pod_paused(slug, False)
    return jsonify({"ok": True})


@app.route("/admin/pods/<slug>/reset", methods=["POST"])
@login_required
def admin_pod_reset(slug):
    """Reset circuit breaker and resume. Operator confirms root cause is fixed."""
    guard = _require_admin()
    if guard:
        return guard
    if _pod_orchestrator:
        _pod_orchestrator.reset_pod(slug)
    else:
        from database import set_pod_circuit_breaker, set_pod_paused
        set_pod_circuit_breaker(slug, open=False)
        set_pod_paused(slug, False)
    return jsonify({"ok": True, "message": f"Pod '{slug}' circuit breaker reset."})


@app.route("/admin/pods/<slug>/run-now", methods=["POST"])
@login_required
def admin_pod_run_now(slug):
    """Force an immediate run of the named pod in a background thread."""
    guard = _require_admin()
    if guard:
        return guard
    if not _pod_orchestrator:
        return jsonify({"ok": False, "error": "Pod orchestrator not enabled. Set USE_POD_ORCHESTRATOR=true."})
    result = _pod_orchestrator.run_pod_now(slug)
    return jsonify(result)


@app.route("/admin/pods/<slug>/cost-save-mode", methods=["POST"])
@login_required
def admin_pod_cost_save(slug):
    """Toggle Cost Save Mode for a single pod (Reddit-only scanning, no Apify charges)."""
    guard = _require_admin()
    if guard:
        return guard
    body    = request.get_json() or {}
    enabled = bool(body.get("enabled", True))
    from database import set_cost_save_mode
    set_cost_save_mode(slug, enabled)
    state = "enabled" if enabled else "disabled"
    return jsonify({"ok": True, "message": f"Cost Save Mode {state} for '{slug}'"})


@app.route("/admin/pods/cost-save-mode/global", methods=["POST"])
@login_required
def admin_pod_cost_save_global():
    """Toggle Cost Save Mode for ALL pods at once."""
    guard = _require_admin()
    if guard:
        return guard
    body    = request.get_json() or {}
    enabled = bool(body.get("enabled", True))
    from database import set_global_cost_save_mode
    set_global_cost_save_mode(enabled)
    state = "enabled" if enabled else "disabled"
    return jsonify({"ok": True, "message": f"Cost Save Mode {state} for all pods"})


@app.route("/admin/pods/<slug>/logs")
@login_required
def admin_pod_logs(slug):
    """Return last 50 run reports for a pod as JSON."""
    guard = _require_admin()
    if guard:
        return guard
    from database import get_pod_run_history
    history = get_pod_run_history(slug, limit=50)
    return jsonify({"pod": slug, "runs": history})


# ── Voice / Morgan inbound receptionist ──────────────────────────────────────
#
# Two webhook routes (public — Vapi POSTs here, no login cookie):
#   POST /webhooks/voice/inbound    — Vapi fires when AltusFlow number is called
#   POST /webhooks/voice/call-ended — Vapi fires when call ends (transcript + outcome)
#
# One settings page (login required):
#   GET  /settings/phone            — closer notification configuration
#   POST /settings/phone            — save closer settings
#   POST /settings/phone/test       — fire a test notification to closer

_gateway = None  # Lazy-loaded; returns None if VAPI_API_KEY is not set


def _get_gateway():
    global _gateway
    if not os.environ.get("VAPI_API_KEY"):
        import logging as _log
        _log.getLogger(__name__).info("Vapi not configured — voice disabled (set VAPI_API_KEY to enable)")
        return None
    if _gateway is None:
        try:
            from voice.VoiceGateway import VoiceGateway
            _gateway = VoiceGateway()
        except Exception as _ve:
            import logging as _log
            _log.getLogger(__name__).warning("VoiceGateway init failed: %s", _ve)
            return None
    return _gateway


@app.route("/webhooks/voice/inbound", methods=["POST"])
def webhook_voice_inbound():
    """
    Vapi calls this when someone dials the AltusFlow Twilio number.
    Must respond within 500ms with Morgan's assistant config.
    This route is intentionally unauthenticated — Vapi cannot send a session cookie.
    """
    try:
        payload       = request.get_json(force=True) or {}
        called_number = payload.get("call", {}).get("phoneNumberId", "")
        caller_number = payload.get("call", {}).get("customer", {}).get("number", "")
        user_id       = os.environ.get("CLIENT_ID", "ALT00")

        config = _get_gateway().handle_inbound_call(
            called_number=called_number,
            caller_number=caller_number,
            user_id=user_id,
        )
        return jsonify(config), 200
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("voice/inbound error: %s", e)
        # Return minimal Morgan config so Vapi still answers — never let the call go dead
        return jsonify({
            "assistant": {
                "firstMessage": "Thank you for calling AltusFlow. Please hold for a moment.",
                "model": {"provider": "anthropic", "model": "claude-sonnet-4-6"},
            }
        }), 200


@app.route("/webhooks/voice/call-ended", methods=["POST"])
def webhook_voice_call_ended():
    """
    Vapi calls this when a call ends. Stores transcript (PII hashed),
    updates HubSpot, logs cost, fires closer notification if booking made.
    Intentionally unauthenticated — Vapi cannot send a session cookie.
    """
    try:
        payload = request.get_json(force=True) or {}
        _get_gateway().handle_call_ended(payload)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("voice/call-ended error: %s", e)
    return jsonify({"ok": True}), 200


@app.route("/settings/phone", methods=["GET", "POST"])
@login_required
def settings_phone():
    """Closer notification settings — webhook URL, email, name, method."""
    saved = False
    if request.method == "POST":
        closer_webhook = request.form.get("closer_webhook_url", "").strip()
        closer_email   = request.form.get("closer_email", "").strip()
        closer_name    = request.form.get("closer_name", "").strip()
        notif_method   = request.form.get("notification_method", "webhook")

        # Persist to platform_connections table (reuse existing encrypted store)
        from budget import save_connection
        save_connection(
            platform="closer_notifications",
            token_encrypted=closer_webhook,   # webhook URL stored as "token"
            account_id=closer_email,
            account_name=closer_name or "Growth Specialist",
        )

        # Also update runtime env vars for this process so next call picks them up
        os.environ["CLOSER_WEBHOOK_URL"] = closer_webhook
        os.environ["CLOSER_EMAIL"]       = closer_email
        os.environ["CLOSER_NAME"]        = closer_name or "Growth Specialist"
        saved = True

    # Load current settings from env / connection store
    from budget import get_connection
    conn_row  = get_connection("closer_notifications") or {}
    settings  = {
        "closer_webhook_url":  os.environ.get("CLOSER_WEBHOOK_URL", "") or conn_row.get("token_encrypted", ""),
        "closer_email":        os.environ.get("CLOSER_EMAIL", "")        or conn_row.get("account_id", ""),
        "closer_name":         os.environ.get("CLOSER_NAME", "")         or conn_row.get("account_name", ""),
        "twilio_number":       os.environ.get("TWILIO_ALTUSFLOW_NUMBER", ""),
        "vapi_connected":      bool(os.environ.get("VAPI_API_KEY", "")),
    }

    from database import get_voice_calls
    recent_calls = get_voice_calls(limit=10, user_id=current_user.tenant_slug)

    return render_template(
        "settings_phone.html",
        settings=settings,
        saved=saved,
        recent_calls=recent_calls,
        **_ctx(),
    )


@app.route("/settings/phone/test", methods=["POST"])
@login_required
def settings_phone_test():
    """Send a test closer notification to confirm the webhook/email is working."""
    try:
        from voice.VoiceGateway import VoiceGateway
        gw = VoiceGateway()
        gw.notify_closer(
            call_id="test-notification",
            booking_data={"start_time": "Thursday June 26 at 2:00 PM"},
            prospect_context={
                "prospect_name": "Test Prospect",
                "summary":       "This is a test notification from AltusFlow Morgan receptionist.",
                "user_id":       current_user.tenant_slug,
            },
            is_escalation=False,
        )
        return jsonify({"ok": True, "message": "Test notification sent."})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# ── Pre-call brief (closer reads this before the discovery call) ───────────────

@app.route("/prep/<call_id>")
@login_required
def pre_call_brief(call_id):
    """
    Closer opens this URL from the notification to read context before the call.
    Shows Morgan's summary, signal post (if known), and prospect details.
    """
    from database import get_voice_calls
    calls = get_voice_calls(limit=200)
    call  = next((c for c in calls if str(c.get("call_id")) == str(call_id)), None)
    if not call:
        return "Call record not found", 404
    return render_template("settings_phone.html", brief_mode=True, call=call, **_ctx())


# ── React Dashboard (SPA catch-all) ──────────────────────────────────────────

@app.route("/dashboard")
@app.route("/dashboard/<path:path>")
def dashboard(path=None):
    """Serve the React SPA for all /dashboard/* routes."""
    import flask
    dash_path = os.path.join(app.static_folder, "dashboard", "index.html")
    if not os.path.exists(dash_path):
        return flask.abort(503, "Dashboard not built yet — run: cd dashboard && npm run build")
    return flask.send_file(dash_path)


# ── Boot ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    print("=" * 40)
    print("  AltusFlow Outbound Hunter UI")
    print("  http://localhost:5000")
    print("  /               - pending review")
    print("  /batch-confirm  - one-click confirm queue")
    print("  /approved       - outreach queue")
    print("  /admin          - scheduler + alerts")
    print("  /health         - monitoring endpoint")
    print("=" * 40)
    app.run(debug=True, port=5000)
