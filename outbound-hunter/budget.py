"""
budget.py
Marketing budget and spend tracking for AltusFlow Outbound Hunter.

Tracks money OUT (Meta Ads spend, Apify compute, AltusFlow subscription) and
money IN (HubSpot deal closures, pipeline value) so clients see their outbound ROI.

All DB functions are tenant-aware: database._get_engine() routes to the correct
per-tenant SQLite file automatically via the threading.local slug set by
app.py's before_request hook or scheduler.py's _run_tenant_pipeline().
"""

import csv
import os
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone

from sqlalchemy import text
from database import _get_engine


def _now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _current_month():
    return datetime.now(timezone.utc).strftime("%Y-%m")


@contextmanager
def _writer():
    with _get_engine().begin() as conn:
        yield conn


@contextmanager
def _reader():
    with _get_engine().connect() as conn:
        yield conn


def _rows(result):
    return [dict(r._mapping) for r in result.fetchall()]


def _row(result):
    r = result.fetchone()
    return dict(r._mapping) if r else None


# ── Budget categories ─────────────────────────────────────────────────────────

def get_or_create_budget(name, budget_type="monthly"):
    """Return the budget row for `name`, creating it if it doesn't exist."""
    with _reader() as conn:
        existing = _row(conn.execute(
            text("SELECT * FROM marketing_budget WHERE budget_name = :n"),
            {"n": name}
        ))
    if existing:
        return existing
    with _writer() as conn:
        conn.execute(
            text("INSERT OR IGNORE INTO marketing_budget (budget_name, budget_type) VALUES (:n, :t)"),
            {"n": name, "t": budget_type}
        )
    with _reader() as conn:
        return _row(conn.execute(
            text("SELECT * FROM marketing_budget WHERE budget_name = :n"),
            {"n": name}
        ))


def get_all_budgets():
    """Return all active budget categories with their current spent totals."""
    with _reader() as conn:
        return _rows(conn.execute(text("""
            SELECT
                b.*,
                COALESCE(SUM(CASE WHEN t.direction='out' AND t.status != 'void' THEN t.amount ELSE 0 END), 0) AS spent
            FROM marketing_budget b
            LEFT JOIN budget_transactions t ON t.budget_id = b.id
            WHERE b.status = 'active'
            GROUP BY b.id
            ORDER BY b.total_allocated DESC, b.budget_name
        """)))


def update_budget_allocation(budget_id, allocated):
    """Set the total_allocated amount for a budget category."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE marketing_budget SET total_allocated = :a WHERE id = :id"),
            {"a": float(allocated), "id": budget_id}
        )


# ── Transactions ──────────────────────────────────────────────────────────────

def log_transaction(platform, description, amount, direction="out",
                    budget_name=None, transaction_type="spend",
                    reference_id=None, reference_type=None,
                    meta_campaign_id=None, meta_ad_id=None,
                    apify_run_id=None, prospect_id=None,
                    receipt_url=None, notes=None):
    """
    Append an immutable transaction to the ledger.
      direction='out'  spend (Meta Ads, Apify, AltusFlow sub)
      direction='in'   revenue/pipeline (HubSpot deal closed, contract signed)
    """
    budget_id = None
    if budget_name:
        b = get_or_create_budget(budget_name)
        budget_id = b["id"] if b else None

    with _writer() as conn:
        conn.execute(text("""
            INSERT INTO budget_transactions (
                budget_id, transaction_type, platform, description,
                amount, direction, transaction_date,
                reference_id, reference_type,
                meta_campaign_id, meta_ad_id, apify_run_id,
                prospect_id, receipt_url, notes
            ) VALUES (
                :bid, :ttype, :platform, :desc,
                :amount, :direction, :tdate,
                :ref_id, :ref_type,
                :meta_camp, :meta_ad, :apify_run,
                :prospect_id, :receipt_url, :notes
            )
        """), {
            "bid":        budget_id,
            "ttype":      transaction_type,
            "platform":   platform,
            "desc":       description,
            "amount":     float(amount),
            "direction":  direction,
            "tdate":      _now(),
            "ref_id":     reference_id,
            "ref_type":   reference_type,
            "meta_camp":  meta_campaign_id,
            "meta_ad":    meta_ad_id,
            "apify_run":  apify_run_id,
            "prospect_id": prospect_id,
            "receipt_url": receipt_url,
            "notes":       notes,
        })


def get_transactions(platform=None, direction=None, date_from=None, date_to=None,
                     limit=50, offset=0):
    """Return (rows, total_count) with optional filters. Rows ordered newest-first."""
    filters = []
    params  = {"limit": limit, "offset": offset}

    if platform:
        filters.append("platform = :platform")
        params["platform"] = platform
    if direction:
        filters.append("direction = :direction")
        params["direction"] = direction
    if date_from:
        filters.append("transaction_date >= :date_from")
        params["date_from"] = date_from
    if date_to:
        filters.append("transaction_date <= :date_to")
        params["date_to"] = date_to + " 23:59:59"

    where       = ("WHERE " + " AND ".join(filters)) if filters else ""
    count_params = {k: v for k, v in params.items() if k not in ("limit", "offset")}

    with _reader() as conn:
        rows  = _rows(conn.execute(text(f"""
            SELECT * FROM budget_transactions {where}
            ORDER BY transaction_date DESC
            LIMIT :limit OFFSET :offset
        """), params))
        total = _row(conn.execute(
            text(f"SELECT COUNT(*) AS cnt FROM budget_transactions {where}"),
            count_params
        ))

    return rows, (total["cnt"] if total else 0)


# ── Summary & analytics ───────────────────────────────────────────────────────

def get_budget_summary(year_month=None):
    """
    Headline figures for the given month (default: current month).
    Returns: allocated, spent, remaining, pipeline, roi, month_label.
    """
    ym = year_month or _current_month()

    with _reader() as conn:
        alloc = _row(conn.execute(text(
            "SELECT COALESCE(SUM(total_allocated), 0) AS total FROM marketing_budget WHERE status = 'active'"
        )))
        month_tx = _row(conn.execute(text("""
            SELECT
                COALESCE(SUM(CASE WHEN direction='out' THEN amount ELSE 0 END), 0) AS spent,
                COALESCE(SUM(CASE WHEN direction='in'  THEN amount ELSE 0 END), 0) AS pipeline
            FROM budget_transactions
            WHERE strftime('%Y-%m', transaction_date) = :ym
              AND status != 'void'
        """), {"ym": ym}))

    allocated = alloc["total"]    if alloc    else 0.0
    spent     = month_tx["spent"] if month_tx else 0.0
    pipeline  = month_tx["pipeline"] if month_tx else 0.0
    remaining = max(0.0, allocated - spent)
    roi       = round(pipeline / spent, 2) if spent > 0 else 0.0

    try:
        month_label = datetime.strptime(ym, "%Y-%m").strftime("%B %Y")
    except ValueError:
        month_label = ym

    return {
        "year_month":  ym,
        "month_label": month_label,
        "allocated":   allocated,
        "spent":       spent,
        "remaining":   remaining,
        "pipeline":    pipeline,
        "roi":         roi,
    }


def get_platform_breakdown(year_month=None):
    """
    Per-platform OUT spend for the given month with percentage of total.
    Used to render the horizontal bar chart on the budget page.
    """
    ym = year_month or _current_month()

    with _reader() as conn:
        rows = _rows(conn.execute(text("""
            SELECT
                platform,
                COALESCE(SUM(amount), 0) AS spent,
                COUNT(*)                  AS tx_count
            FROM budget_transactions
            WHERE strftime('%Y-%m', transaction_date) = :ym
              AND direction = 'out'
              AND status   != 'void'
            GROUP BY platform
            ORDER BY spent DESC
        """), {"ym": ym}))

    total = sum(r["spent"] for r in rows)
    for r in rows:
        r["pct"] = round(r["spent"] / total * 100) if total > 0 else 0

    return rows


def get_roi_summary():
    """All-time totals: total spend, total pipeline value, ROI multiplier."""
    with _reader() as conn:
        totals = _row(conn.execute(text("""
            SELECT
                COALESCE(SUM(CASE WHEN direction='out' THEN amount ELSE 0 END), 0) AS total_spend,
                COALESCE(SUM(CASE WHEN direction='in'  THEN amount ELSE 0 END), 0) AS total_pipeline,
                COUNT(CASE WHEN direction='in' THEN 1 END)                          AS deals_in
            FROM budget_transactions
            WHERE status != 'void'
        """)))

    spend    = totals["total_spend"]    if totals else 0.0
    pipeline = totals["total_pipeline"] if totals else 0.0
    roi      = round(pipeline / spend, 2) if spend > 0 else 0.0

    return {
        "spend":    spend,
        "pipeline": pipeline,
        "roi":      roi,
        "deals_in": totals["deals_in"] if totals else 0,
    }


# ── Platform connections ──────────────────────────────────────────────────────

def get_all_connections():
    """Return {platform_slug: row_dict} for all stored connection records."""
    with _reader() as conn:
        rows = _rows(conn.execute(text(
            "SELECT * FROM platform_connections ORDER BY platform"
        )))
    return {r["platform"]: r for r in rows}


def save_connection(platform, token_encrypted, account_id=None, account_name=None):
    """Upsert a platform connection with an already-encrypted token."""
    now = _now()
    with _writer() as conn:
        conn.execute(text("""
            INSERT INTO platform_connections
                (platform, status, token_encrypted, account_id, account_name, connected_at)
            VALUES
                (:p, 'connected', :tok, :acct_id, :acct_name, :now)
            ON CONFLICT(platform) DO UPDATE SET
                status          = 'connected',
                token_encrypted = excluded.token_encrypted,
                account_id      = excluded.account_id,
                account_name    = excluded.account_name,
                connected_at    = excluded.connected_at,
                error_message   = NULL
        """), {
            "p": platform, "tok": token_encrypted,
            "acct_id": account_id, "acct_name": account_name, "now": now,
        })


def disconnect_connection(platform):
    """Mark a platform disconnected and wipe the stored token."""
    with _writer() as conn:
        conn.execute(text("""
            UPDATE platform_connections
            SET status = 'disconnected', token_encrypted = NULL,
                account_id = NULL, account_name = NULL, error_message = NULL
            WHERE platform = :p
        """), {"p": platform})


def get_connection_token(platform):
    """Return the decrypted token for a platform, or None if not connected."""
    with _reader() as conn:
        row = _row(conn.execute(
            text("SELECT token_encrypted FROM platform_connections WHERE platform = :p"),
            {"p": platform}
        ))
    if not row or not row["token_encrypted"]:
        return None
    from auth import decrypt_token
    return decrypt_token(row["token_encrypted"])


# ── CSV export ────────────────────────────────────────────────────────────────

def export_transactions_csv():
    """Write all transactions to a temp CSV and return the file path (or None)."""
    rows, _ = get_transactions(limit=10000, offset=0)
    if not rows:
        return None

    fd, path = tempfile.mkstemp(suffix=".csv", prefix="altusflow_budget_")
    os.close(fd)

    fields = [
        "id", "transaction_date", "platform", "description",
        "amount", "direction", "transaction_type", "status",
        "reference_id", "notes",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return path
