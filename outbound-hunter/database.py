"""
database.py
Storage layer for the Outbound Hunter.

Supports SQLite (local dev) and PostgreSQL (production) via DATABASE_URL env var.
If DATABASE_URL is set, PostgreSQL is used. Otherwise falls back to SQLite.

Quick start (production):
  export DATABASE_URL=postgresql://user:pass@host:5432/dbname
  Free tiers: supabase.com or neon.tech
"""

import os
import csv
import json
import threading
from datetime import datetime, timezone, timedelta
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

# ── Engine setup ──────────────────────────────────────────────────────────────

_DB_FILE      = os.environ.get("DB_FILE", "outbound_hunter.db")
_DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{_DB_FILE}")
CLIENT_ID     = os.environ.get("CLIENT_ID", "ALT00")

# Normalise Heroku/Supabase 'postgres://' → 'postgresql://'
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = _DATABASE_URL.startswith("sqlite")

# ── Multi-tenant engine registry ──────────────────────────────────────────────
# Per-tenant databases live at tenants/{slug}/outbound_hunter.db (always SQLite).
# set_tenant_slug() is called by app.py's before_request hook (Flask context)
# and by the scheduler before each per-tenant pipeline run (background thread).

_tenant_local = threading.local()   # per-thread tenant slug
_engines      = {}                  # {slug: SQLAlchemy engine}
_engine       = None                # legacy single-tenant fallback engine


def set_tenant_slug(slug):
    """Bind a tenant slug to the current thread. All DB calls will route to that tenant's DB."""
    _tenant_local.slug = slug


def _current_tenant_slug():
    """Return the active tenant slug for this thread, or None for legacy single-tenant mode."""
    # 1. Threading local (scheduler background threads + explicit calls)
    slug = getattr(_tenant_local, "slug", None)
    if slug:
        return slug
    # 2. Flask g (request context)
    try:
        from flask import g
        slug = getattr(g, "tenant_slug", None)
        if slug:
            return slug
    except RuntimeError:
        pass
    return None


def _get_engine():
    """
    Return the SQLAlchemy engine for the current tenant.
    If no tenant is active, falls back to the global DATABASE_URL (legacy single-tenant mode).
    Per-tenant engines are always SQLite regardless of DATABASE_URL.
    """
    slug = _current_tenant_slug()
    if slug:
        if slug not in _engines:
            db_path = os.path.join("tenants", slug, "outbound_hunter.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            _engines[slug] = create_engine(
                f"sqlite:///{db_path}",
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        return _engines[slug]

    # Legacy fallback — single-tenant mode (no login, env var config)
    global _engine
    if _engine is None:
        if _is_sqlite:
            _engine = create_engine(
                _DATABASE_URL,
                connect_args={"check_same_thread": False},
                poolclass=StaticPool,
            )
        else:
            _engine = create_engine(
                _DATABASE_URL,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=10,
            )
    return _engine


@contextmanager
def _writer():
    """Context manager for write operations — auto-commits, rolls back on error."""
    with _get_engine().begin() as conn:
        yield conn


@contextmanager
def _reader():
    """Context manager for read operations."""
    with _get_engine().connect() as conn:
        yield conn


def _rows(result):
    return [dict(r._mapping) for r in result.fetchall()]


def _row(result):
    r = result.fetchone()
    return dict(r._mapping) if r else None


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── Schema DDL ────────────────────────────────────────────────────────────────

def _ddl(sqlite_sql, pg_sql):
    return sqlite_sql if _is_sqlite else pg_sql


_PROSPECTS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS prospects (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id           TEXT    NOT NULL DEFAULT 'ALT00',
        niche               TEXT,
        platform            TEXT    NOT NULL,
        handle              TEXT    NOT NULL,
        name                TEXT,
        title               TEXT,
        company             TEXT,
        profile_url         TEXT,
        post_text           TEXT    NOT NULL,
        post_url            TEXT,
        post_date           TEXT,
        signal_phrase       TEXT,
        icp_score           INTEGER DEFAULT 0,
        icp_notes           TEXT,
        confidence_score    INTEGER,
        confidence_reason   TEXT,
        routing_decision    TEXT    DEFAULT 'pending',
        drafted_message     TEXT,
        call_opener         TEXT,
        cta_url             TEXT,
        status              TEXT    DEFAULT 'pending',
        approved_at         TEXT,
        sent_at             TEXT,
        notes               TEXT,
        hs_contact_id       TEXT,
        hs_deal_id          TEXT,
        hs_pushed_at        TEXT,
        hs_status           TEXT    DEFAULT 'pending',
        hs_error            TEXT,
        created_at          TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS prospects (
        id                  SERIAL  PRIMARY KEY,
        client_id           TEXT    NOT NULL DEFAULT 'ALT00',
        niche               TEXT,
        platform            TEXT    NOT NULL,
        handle              TEXT    NOT NULL,
        name                TEXT,
        title               TEXT,
        company             TEXT,
        profile_url         TEXT,
        post_text           TEXT    NOT NULL,
        post_url            TEXT,
        post_date           TEXT,
        signal_phrase       TEXT,
        icp_score           INTEGER DEFAULT 0,
        icp_notes           TEXT,
        confidence_score    INTEGER,
        confidence_reason   TEXT,
        routing_decision    TEXT    DEFAULT 'pending',
        drafted_message     TEXT,
        call_opener         TEXT,
        cta_url             TEXT,
        status              TEXT    DEFAULT 'pending',
        approved_at         TEXT,
        sent_at             TEXT,
        notes               TEXT,
        hs_contact_id       TEXT,
        hs_deal_id          TEXT,
        hs_pushed_at        TEXT,
        hs_status           TEXT    DEFAULT 'pending',
        hs_error            TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_SENT_LOG_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS sent_log (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id     INTEGER REFERENCES prospects(id),
        touch_number    INTEGER DEFAULT 1,
        message_sent    TEXT,
        sent_at         TEXT,
        replied         INTEGER DEFAULT 0,
        reply_text      TEXT,
        reply_at        TEXT,
        outcome         TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sent_log (
        id              SERIAL  PRIMARY KEY,
        prospect_id     INTEGER REFERENCES prospects(id),
        touch_number    INTEGER DEFAULT 1,
        message_sent    TEXT,
        sent_at         TEXT,
        replied         INTEGER DEFAULT 0,
        reply_text      TEXT,
        reply_at        TEXT,
        outcome         TEXT
    )
    """
)

_SEARCH_RUNS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS search_runs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_at          TEXT DEFAULT (datetime('now')),
        platform        TEXT,
        signal_phrase   TEXT,
        results_found   INTEGER DEFAULT 0,
        qualified       INTEGER DEFAULT 0,
        drafted         INTEGER DEFAULT 0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS search_runs (
        id              SERIAL PRIMARY KEY,
        run_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        platform        TEXT,
        signal_phrase   TEXT,
        results_found   INTEGER DEFAULT 0,
        qualified       INTEGER DEFAULT 0,
        drafted         INTEGER DEFAULT 0
    )
    """
)

_SCAN_RUNS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS scan_runs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id       TEXT    NOT NULL DEFAULT 'ALT00',
        started_at      TEXT    NOT NULL,
        completed_at    TEXT,
        prospects_found INTEGER DEFAULT 0,
        qualified       INTEGER DEFAULT 0,
        drafted         INTEGER DEFAULT 0,
        pushed_to_hs    INTEGER DEFAULT 0,
        status          TEXT    DEFAULT 'queued',
        error_log       TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scan_runs (
        id              SERIAL  PRIMARY KEY,
        client_id       TEXT    NOT NULL DEFAULT 'ALT00',
        started_at      TEXT    NOT NULL,
        completed_at    TEXT,
        prospects_found INTEGER DEFAULT 0,
        qualified       INTEGER DEFAULT 0,
        drafted         INTEGER DEFAULT 0,
        pushed_to_hs    INTEGER DEFAULT 0,
        status          TEXT    DEFAULT 'queued',
        error_log       TEXT
    )
    """
)

_NOTIFICATIONS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id          INTEGER,
        type            TEXT    NOT NULL,
        severity        TEXT    NOT NULL,
        title           TEXT    NOT NULL,
        body            TEXT,
        suggested_fix   TEXT,
        created_at      TEXT    DEFAULT (datetime('now')),
        acknowledged_at TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS notifications (
        id              SERIAL  PRIMARY KEY,
        run_id          INTEGER,
        type            TEXT    NOT NULL,
        severity        TEXT    NOT NULL,
        title           TEXT    NOT NULL,
        body            TEXT,
        suggested_fix   TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        acknowledged_at TEXT
    )
    """
)

_SCHEDULER_STATE_DDL = """
    CREATE TABLE IF NOT EXISTS scheduler_state (
        id              INTEGER PRIMARY KEY,
        is_paused       INTEGER DEFAULT 0,
        paused_at       TEXT,
        paused_reason   TEXT,
        last_updated    TEXT
    )
"""

_GLOBAL_REGISTRY_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS global_registry (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        handle            TEXT NOT NULL,
        platform          TEXT NOT NULL,
        niche_segment     TEXT,
        first_contacted_at TEXT,
        last_contacted_at  TEXT,
        contact_count     INTEGER DEFAULT 0,
        cooldown_until    TEXT,
        UNIQUE(handle, platform)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS global_registry (
        id                SERIAL PRIMARY KEY,
        handle            TEXT NOT NULL,
        platform          TEXT NOT NULL,
        niche_segment     TEXT,
        first_contacted_at TEXT,
        last_contacted_at  TEXT,
        contact_count     INTEGER DEFAULT 0,
        cooldown_until    TEXT,
        UNIQUE(handle, platform)
    )
    """
)

_CALENDLY_BOOKINGS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS calendly_bookings (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_uuid      TEXT    NOT NULL UNIQUE,
        invitee_email   TEXT    NOT NULL,
        prospect_id     INTEGER REFERENCES prospects(id),
        deal_id         TEXT,
        brief_generated INTEGER DEFAULT 0,
        stage_moved     INTEGER DEFAULT 0,
        processed_at    TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS calendly_bookings (
        id              SERIAL  PRIMARY KEY,
        event_uuid      TEXT    NOT NULL UNIQUE,
        invitee_email   TEXT    NOT NULL,
        prospect_id     INTEGER REFERENCES prospects(id),
        deal_id         TEXT,
        brief_generated INTEGER DEFAULT 0,
        stage_moved     INTEGER DEFAULT 0,
        processed_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_PLATFORM_STATS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS platform_stats (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        platform      TEXT NOT NULL,
        niche_segment TEXT,
        scan_date     TEXT NOT NULL,
        prospects_found INTEGER DEFAULT 0,
        qualified     INTEGER DEFAULT 0,
        avg_icp_score REAL DEFAULT 0.0
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS platform_stats (
        id            SERIAL PRIMARY KEY,
        platform      TEXT NOT NULL,
        niche_segment TEXT,
        scan_date     TEXT NOT NULL,
        prospects_found INTEGER DEFAULT 0,
        qualified     INTEGER DEFAULT 0,
        avg_icp_score REAL DEFAULT 0.0
    )
    """
)

_MARKETING_BUDGET_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS marketing_budget (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        budget_name     TEXT    NOT NULL UNIQUE,
        budget_type     TEXT    NOT NULL DEFAULT 'monthly',
        total_allocated REAL    DEFAULT 0,
        period_start    TEXT,
        period_end      TEXT,
        status          TEXT    DEFAULT 'active',
        created_at      TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS marketing_budget (
        id              SERIAL  PRIMARY KEY,
        budget_name     TEXT    NOT NULL UNIQUE,
        budget_type     TEXT    NOT NULL DEFAULT 'monthly',
        total_allocated REAL    DEFAULT 0,
        period_start    TEXT,
        period_end      TEXT,
        status          TEXT    DEFAULT 'active',
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_BUDGET_TRANSACTIONS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS budget_transactions (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        budget_id        INTEGER REFERENCES marketing_budget(id),
        transaction_type TEXT    NOT NULL DEFAULT 'spend',
        platform         TEXT    NOT NULL,
        description      TEXT    NOT NULL,
        amount           REAL    NOT NULL,
        direction        TEXT    NOT NULL DEFAULT 'out',
        transaction_date TEXT    DEFAULT (datetime('now')),
        reference_id     TEXT,
        reference_type   TEXT,
        meta_campaign_id TEXT,
        meta_ad_id       TEXT,
        apify_run_id     TEXT,
        prospect_id      INTEGER REFERENCES prospects(id),
        status           TEXT    DEFAULT 'confirmed',
        receipt_url      TEXT,
        notes            TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS budget_transactions (
        id               SERIAL  PRIMARY KEY,
        budget_id        INTEGER REFERENCES marketing_budget(id),
        transaction_type TEXT    NOT NULL DEFAULT 'spend',
        platform         TEXT    NOT NULL,
        description      TEXT    NOT NULL,
        amount           REAL    NOT NULL,
        direction        TEXT    NOT NULL DEFAULT 'out',
        transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        reference_id     TEXT,
        reference_type   TEXT,
        meta_campaign_id TEXT,
        meta_ad_id       TEXT,
        apify_run_id     TEXT,
        prospect_id      INTEGER REFERENCES prospects(id),
        status           TEXT    DEFAULT 'confirmed',
        receipt_url      TEXT,
        notes            TEXT
    )
    """
)

_PLATFORM_CONNECTIONS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS platform_connections (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        platform        TEXT    NOT NULL UNIQUE,
        status          TEXT    DEFAULT 'disconnected',
        token_encrypted TEXT,
        account_id      TEXT,
        account_name    TEXT,
        connected_at    TEXT,
        last_sync_at    TEXT,
        error_message   TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS platform_connections (
        id              SERIAL  PRIMARY KEY,
        platform        TEXT    NOT NULL UNIQUE,
        status          TEXT    DEFAULT 'disconnected',
        token_encrypted TEXT,
        account_id      TEXT,
        account_name    TEXT,
        connected_at    TIMESTAMP,
        last_sync_at    TIMESTAMP,
        error_message   TEXT
    )
    """
)


_POD_STATUS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS pod_status (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        pod_slug              TEXT NOT NULL,
        user_id               TEXT,
        run_id                TEXT UNIQUE,
        started_at            TEXT,
        completed_at          TEXT,
        duration_seconds      INTEGER,
        status                TEXT,
        platforms_scanned     TEXT,
        prospects_found       INTEGER DEFAULT 0,
        prospects_qualified   INTEGER DEFAULT 0,
        auto_approved         INTEGER DEFAULT 0,
        pending_review        INTEGER DEFAULT 0,
        skipped_dnc           INTEGER DEFAULT 0,
        skipped_cooldown      INTEGER DEFAULT 0,
        insufficient_intel    INTEGER DEFAULT 0,
        hs_pushes_ok          INTEGER DEFAULT 0,
        hs_pushes_failed      INTEGER DEFAULT 0,
        meta_pushes_ok        INTEGER DEFAULT 0,
        errors                TEXT,
        circuit_breaker       TEXT DEFAULT 'closed',
        consecutive_errors    INTEGER DEFAULT 0,
        next_run              TEXT,
        created_at            TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pod_status (
        id                    SERIAL  PRIMARY KEY,
        pod_slug              TEXT NOT NULL,
        user_id               TEXT,
        run_id                TEXT UNIQUE,
        started_at            TEXT,
        completed_at          TEXT,
        duration_seconds      INTEGER,
        status                TEXT,
        platforms_scanned     TEXT,
        prospects_found       INTEGER DEFAULT 0,
        prospects_qualified   INTEGER DEFAULT 0,
        auto_approved         INTEGER DEFAULT 0,
        pending_review        INTEGER DEFAULT 0,
        skipped_dnc           INTEGER DEFAULT 0,
        skipped_cooldown      INTEGER DEFAULT 0,
        insufficient_intel    INTEGER DEFAULT 0,
        hs_pushes_ok          INTEGER DEFAULT 0,
        hs_pushes_failed      INTEGER DEFAULT 0,
        meta_pushes_ok        INTEGER DEFAULT 0,
        errors                TEXT,
        circuit_breaker       TEXT DEFAULT 'closed',
        consecutive_errors    INTEGER DEFAULT 0,
        next_run              TEXT,
        created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_POD_REGISTRY_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS pod_registry (
        id                    INTEGER PRIMARY KEY AUTOINCREMENT,
        pod_slug              TEXT UNIQUE NOT NULL,
        pod_label             TEXT,
        is_active             INTEGER DEFAULT 1,
        is_paused             INTEGER DEFAULT 0,
        pause_reason          TEXT,
        paused_at             TEXT,
        last_run_at           TEXT,
        last_run_status       TEXT,
        total_runs            INTEGER DEFAULT 0,
        total_prospects       INTEGER DEFAULT 0,
        consecutive_errors    INTEGER DEFAULT 0,
        circuit_breaker_open  INTEGER DEFAULT 0,
        cost_save_mode        INTEGER DEFAULT 0,
        created_at            TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS pod_registry (
        id                    SERIAL  PRIMARY KEY,
        pod_slug              TEXT UNIQUE NOT NULL,
        pod_label             TEXT,
        is_active             INTEGER DEFAULT 1,
        is_paused             INTEGER DEFAULT 0,
        pause_reason          TEXT,
        paused_at             TEXT,
        last_run_at           TEXT,
        last_run_status       TEXT,
        total_runs            INTEGER DEFAULT 0,
        total_prospects       INTEGER DEFAULT 0,
        consecutive_errors    INTEGER DEFAULT 0,
        circuit_breaker_open  INTEGER DEFAULT 0,
        cost_save_mode        INTEGER DEFAULT 0,
        created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_DNC_LIST_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS dnc_list (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        handle      TEXT    NOT NULL,
        platform    TEXT    NOT NULL,
        user_id     TEXT    NOT NULL DEFAULT '',
        is_global   INTEGER NOT NULL DEFAULT 0,
        reason      TEXT,
        added_by    TEXT    DEFAULT 'system',
        added_at    TEXT    DEFAULT (datetime('now')),
        UNIQUE(handle, platform, user_id, is_global)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dnc_list (
        id          SERIAL  PRIMARY KEY,
        handle      TEXT    NOT NULL,
        platform    TEXT    NOT NULL,
        user_id     TEXT    NOT NULL DEFAULT '',
        is_global   INTEGER NOT NULL DEFAULT 0,
        reason      TEXT,
        added_by    TEXT    DEFAULT 'system',
        added_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(handle, platform, user_id, is_global)
    )
    """
)

_VOICE_CALLS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS voice_calls (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id             TEXT    UNIQUE,
        user_id             TEXT    NOT NULL DEFAULT 'ALT00',
        direction           TEXT    NOT NULL DEFAULT 'inbound',
        called_number       TEXT,
        caller_hash         TEXT    NOT NULL,
        transcript          TEXT,
        summary             TEXT,
        duration_seconds    INTEGER,
        outcome             TEXT,
        escalation_reason   TEXT,
        booking_confirmed   INTEGER DEFAULT 0,
        closer_notified     INTEGER DEFAULT 0,
        closer_notified_at  TEXT,
        cost_usd            REAL    DEFAULT 0.0,
        prospect_id         INTEGER REFERENCES prospects(id),
        hs_deal_id          TEXT,
        hs_task_id          TEXT,
        created_at          TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS voice_calls (
        id                  SERIAL  PRIMARY KEY,
        call_id             TEXT    UNIQUE,
        user_id             TEXT    NOT NULL DEFAULT 'ALT00',
        direction           TEXT    NOT NULL DEFAULT 'inbound',
        called_number       TEXT,
        caller_hash         TEXT    NOT NULL,
        transcript          TEXT,
        summary             TEXT,
        duration_seconds    INTEGER,
        outcome             TEXT,
        escalation_reason   TEXT,
        booking_confirmed   INTEGER DEFAULT 0,
        closer_notified     INTEGER DEFAULT 0,
        closer_notified_at  TIMESTAMP,
        cost_usd            REAL    DEFAULT 0.0,
        prospect_id         INTEGER REFERENCES prospects(id),
        hs_deal_id          TEXT,
        hs_task_id          TEXT,
        created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_SIGNAL_FEEDBACK_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS signal_feedback (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_phrase   TEXT    NOT NULL,
        rating          INTEGER NOT NULL DEFAULT 0,
        note            TEXT,
        submitted_by    TEXT    DEFAULT 'owner',
        created_at      TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signal_feedback (
        id              SERIAL  PRIMARY KEY,
        signal_phrase   TEXT    NOT NULL,
        rating          INTEGER NOT NULL DEFAULT 0,
        note            TEXT,
        submitted_by    TEXT    DEFAULT 'owner',
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_GOLDEN_HISTORY_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS golden_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        signal_phrase   TEXT    NOT NULL,
        feedback_type   TEXT    NOT NULL,
        feedback_note   TEXT,
        example_message TEXT,
        outreach_angle  TEXT,
        source          TEXT    DEFAULT 'owner',
        created_at      TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS golden_history (
        id              SERIAL  PRIMARY KEY,
        signal_phrase   TEXT    NOT NULL,
        feedback_type   TEXT    NOT NULL,
        feedback_note   TEXT,
        example_message TEXT,
        outreach_angle  TEXT,
        source          TEXT    DEFAULT 'owner',
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_SCRAPE_JOBS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS scrape_jobs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          TEXT    NOT NULL UNIQUE,
        pod_slug        TEXT    NOT NULL,
        status          TEXT    NOT NULL DEFAULT 'PENDING',
        started_at      TEXT,
        completed_at    TEXT,
        result_json     TEXT,
        error           TEXT,
        created_at      TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS scrape_jobs (
        id              SERIAL  PRIMARY KEY,
        job_id          TEXT    NOT NULL UNIQUE,
        pod_slug        TEXT    NOT NULL,
        status          TEXT    NOT NULL DEFAULT 'PENDING',
        started_at      TEXT,
        completed_at    TEXT,
        result_json     TEXT,
        error           TEXT,
        created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_MARKET_INSIGHTS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS market_insights (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id         INTEGER REFERENCES prospects(id),
        pod_slug            TEXT,
        primary_pain_point  TEXT,
        competitor_mentions TEXT,
        intent_score        REAL    DEFAULT 0.0,
        raw_signals         TEXT,
        extracted_at        TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS market_insights (
        id                  SERIAL  PRIMARY KEY,
        prospect_id         INTEGER REFERENCES prospects(id),
        pod_slug            TEXT,
        primary_pain_point  TEXT,
        competitor_mentions TEXT,
        intent_score        REAL    DEFAULT 0.0,
        raw_signals         TEXT,
        extracted_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_DISPATCHED_EVENTS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS dispatched_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id    TEXT    NOT NULL UNIQUE,
        event_type  TEXT    NOT NULL,
        user_id     TEXT,
        prospect_id INTEGER,
        data_json   TEXT,
        dispatched_at TEXT  DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dispatched_events (
        id          SERIAL  PRIMARY KEY,
        event_id    TEXT    NOT NULL UNIQUE,
        event_type  TEXT    NOT NULL,
        user_id     TEXT,
        prospect_id INTEGER,
        data_json   TEXT,
        dispatched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_JOURNEY_EVENTS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS journey_events (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id  INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
        event        TEXT    NOT NULL,
        icon         TEXT    DEFAULT '📌',
        detail       TEXT,
        full_message TEXT,
        created_at   TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS journey_events (
        id           SERIAL  PRIMARY KEY,
        prospect_id  INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
        event        TEXT    NOT NULL,
        icon         TEXT    DEFAULT '📌',
        detail       TEXT,
        full_message TEXT,
        created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CONVERSATIONS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        prospect_id  INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
        advisor_id   TEXT,
        platform     TEXT    DEFAULT 'reddit',
        mode         TEXT    DEFAULT 'assist',
        unread       INTEGER DEFAULT 0,
        updated_at   TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversations (
        id           SERIAL  PRIMARY KEY,
        prospect_id  INTEGER NOT NULL REFERENCES prospects(id) ON DELETE CASCADE,
        advisor_id   TEXT,
        platform     TEXT    DEFAULT 'reddit',
        mode         TEXT    DEFAULT 'assist',
        unread       INTEGER DEFAULT 0,
        updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_CONVERSATION_MESSAGES_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        sender          TEXT    NOT NULL,
        body            TEXT    NOT NULL,
        sent_at         TEXT    DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS conversation_messages (
        id              SERIAL  PRIMARY KEY,
        conversation_id INTEGER NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
        sender          TEXT    NOT NULL,
        body            TEXT    NOT NULL,
        sent_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)

_TENANT_SETTINGS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS tenant_settings (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        key         TEXT NOT NULL UNIQUE,
        value       TEXT,
        updated_at  TEXT DEFAULT (datetime('now'))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS tenant_settings (
        id          SERIAL PRIMARY KEY,
        key         TEXT NOT NULL UNIQUE,
        value       TEXT,
        updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """
)


_INTEGRATIONS_DDL = _ddl(
    """
    CREATE TABLE IF NOT EXISTS integrations (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        advisor_id TEXT    NOT NULL,
        slug       TEXT    NOT NULL,
        enabled    INTEGER NOT NULL DEFAULT 0,
        config     TEXT    NOT NULL DEFAULT '{}',
        created_at TEXT    NOT NULL DEFAULT (datetime('now')),
        updated_at TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(advisor_id, slug)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS integrations (
        id         SERIAL  PRIMARY KEY,
        advisor_id TEXT    NOT NULL,
        slug       TEXT    NOT NULL,
        enabled    INTEGER NOT NULL DEFAULT 0,
        config     TEXT    NOT NULL DEFAULT '{}',
        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(advisor_id, slug)
    )
    """
)


def init_db():
    """
    Create all tables and run column migrations on existing DBs.

    Three-phase init to handle existing databases safely:
      Phase 1 — CREATE TABLE IF NOT EXISTS (no-op on existing DBs)
      Phase 2 — _migrate_columns() adds any new columns via ALTER TABLE
      Phase 3 — Create indexes, including any on newly-migrated columns
    """
    # Phase 1: tables
    with _get_engine().begin() as conn:
        conn.execute(text(_PROSPECTS_DDL))
        conn.execute(text(_SENT_LOG_DDL))
        conn.execute(text(_SEARCH_RUNS_DDL))
        conn.execute(text(_SCAN_RUNS_DDL))
        conn.execute(text(_NOTIFICATIONS_DDL))
        conn.execute(text(_SCHEDULER_STATE_DDL))
        conn.execute(text(_GLOBAL_REGISTRY_DDL))
        conn.execute(text(_PLATFORM_STATS_DDL))
        conn.execute(text(_CALENDLY_BOOKINGS_DDL))
        conn.execute(text(_MARKETING_BUDGET_DDL))
        conn.execute(text(_BUDGET_TRANSACTIONS_DDL))
        conn.execute(text(_PLATFORM_CONNECTIONS_DDL))
        conn.execute(text(_POD_STATUS_DDL))
        conn.execute(text(_POD_REGISTRY_DDL))
        conn.execute(text(_DNC_LIST_DDL))
        conn.execute(text(_DISPATCHED_EVENTS_DDL))
        conn.execute(text(_TENANT_SETTINGS_DDL))
        conn.execute(text(_VOICE_CALLS_DDL))
        conn.execute(text(_SIGNAL_FEEDBACK_DDL))
        conn.execute(text(_JOURNEY_EVENTS_DDL))
        conn.execute(text(_CONVERSATIONS_DDL))
        conn.execute(text(_CONVERSATION_MESSAGES_DDL))
        conn.execute(text(_GOLDEN_HISTORY_DDL))
        conn.execute(text(_SCRAPE_JOBS_DDL))
        conn.execute(text(_MARKET_INSIGHTS_DDL))
        conn.execute(text(_INTEGRATIONS_DDL))
        _upsert_scheduler_row(conn)
        conn.execute(text(_REDDIT_TOP_POSTS_DDL))
        conn.execute(text(_CONTENT_PLANS_DDL))

    # Phase 2: column migrations (adds niche, confidence_*, routing_decision to existing tables)
    _migrate_columns()

    # Phase 3: indexes (must come after migrations so new columns are guaranteed to exist)
    with _get_engine().begin() as conn:
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prospects_status       ON prospects(status)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prospects_platform     ON prospects(platform)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prospects_handle       ON prospects(handle)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prospects_niche        ON prospects(niche)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prospects_niche_seg    ON prospects(niche_segment)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_prospects_outreach_m   ON prospects(outreach_method)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_scan_runs_client       ON scan_runs(client_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_notifications_sev      ON notifications(severity)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_registry_handle_plat   ON global_registry(handle, platform)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_registry_cooldown      ON global_registry(cooldown_until)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_platform_stats_date    ON platform_stats(scan_date, platform)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_budget_tx_platform     ON budget_transactions(platform)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_budget_tx_date         ON budget_transactions(transaction_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_budget_tx_direction    ON budget_transactions(direction)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pod_status_slug        ON pod_status(pod_slug)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pod_status_created     ON pod_status(created_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dnc_handle_platform    ON dnc_list(handle, platform)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dnc_global             ON dnc_list(is_global)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_dispatched_event_id    ON dispatched_events(event_id)"))


def _upsert_scheduler_row(conn):
    """Insert the singleton scheduler config row if it doesn't exist."""
    if _is_sqlite:
        conn.execute(text("INSERT OR IGNORE INTO scheduler_state (id, is_paused) VALUES (1, 0)"))
    else:
        conn.execute(text(
            "INSERT INTO scheduler_state (id, is_paused) VALUES (1, 0) ON CONFLICT (id) DO NOTHING"
        ))


def _migrate_columns():
    """Add new columns to existing tables without losing data."""
    new_cols = [
        # Per-niche pause state + Calendly last poll checkpoint on scheduler row
        ("scheduler_state", "niche_pauses",          "TEXT DEFAULT '{}'"),
        ("scheduler_state", "calendly_last_checked",  "TEXT"),
        # Columns added in the autonomous-system refactor
        ("prospects", "niche",              "TEXT"),
        ("prospects", "confidence_score",   "INTEGER"),
        ("prospects", "confidence_reason",  "TEXT"),
        ("prospects", "routing_decision",   "TEXT DEFAULT 'pending'"),
        # Columns from previous sessions (idempotent — already exist on new DBs)
        ("prospects", "client_id",          "TEXT DEFAULT 'ALT00'"),
        ("prospects", "call_opener",        "TEXT"),
        ("prospects", "cta_url",            "TEXT"),
        ("prospects", "hs_contact_id",      "TEXT"),
        ("prospects", "hs_deal_id",         "TEXT"),
        ("prospects", "hs_pushed_at",       "TEXT"),
        ("prospects", "hs_status",          "TEXT DEFAULT 'pending'"),
        ("prospects", "hs_error",           "TEXT"),
        # 5-niche refactor columns
        ("prospects", "niche_segment",      "TEXT"),
        ("prospects", "outreach_method",    "TEXT DEFAULT 'direct'"),
        ("prospects", "reddit_username",    "TEXT"),
        ("prospects", "linkedin_search_url","TEXT"),
        ("prospects", "upvote_score",       "INTEGER DEFAULT 0"),
        ("prospects", "group_name",         "TEXT"),
        ("prospects", "subreddit",          "TEXT"),
        ("prospects", "pre_call_brief",     "TEXT"),
        ("prospects", "consent_granted",    "INTEGER DEFAULT 1"),
        # Cost Save Mode toggle (Phase 4)
        ("pod_registry", "cost_save_mode", "INTEGER DEFAULT 0"),
        # Voice calls — closer notification columns
        ("voice_calls", "closer_notified",    "INTEGER DEFAULT 0"),
        ("voice_calls", "closer_notified_at", "TEXT"),
        # Celery async + multi-tenant evolution
        ("prospects", "intent_score", "REAL DEFAULT 0.0"),
        ("prospects", "pod_id",       "TEXT"),
        # Hermes learning gate — auto-send unlocks at 50
        ("scheduler_state", "hermes_convo_count", "INTEGER DEFAULT 0"),
        ("scheduler_state", "hermes_auto_enabled", "INTEGER DEFAULT 0"),
        # Omnichannel: track which platform each market insight came from
        ("market_insights", "source", "TEXT DEFAULT 'reddit'"),
        # Compliance audit log — channel + disclosure tracking
        ("sent_log", "channel",            "TEXT DEFAULT 'unknown'"),
        ("sent_log", "advisor_id",         "TEXT"),
        ("sent_log", "disclosure_appended","INTEGER DEFAULT 0"),
        ("sent_log", "prospect_handle",    "TEXT"),
        ("sent_log", "prospect_platform",  "TEXT"),
        ("sent_log", "niche",              "TEXT"),
        # AI intent scoring result stored on prospect
        ("prospects", "ai_intent_score",   "REAL DEFAULT 0.0"),
        # Unified inbox — lead source + context for Hermes
        ("conversations", "source",         "TEXT DEFAULT 'cold_stream'"),
        ("conversations", "source_context", "TEXT"),
        ("conversations", "handle",         "TEXT"),
        ("conversations", "subreddit",      "TEXT"),
        # Value post comment tracking
        ("value_posts", "post_url",              "TEXT"),
        ("value_posts", "comments_checked_at",   "TEXT"),
        ("value_posts", "commenters_found",      "INTEGER DEFAULT 0"),
    ]
    with _get_engine().begin() as conn:
        for table, col, typedef in new_cols:
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {typedef}"))
            except Exception:
                pass  # Column already exists — safe to ignore


# ── Prospects ─────────────────────────────────────────────────────────────────

def prospect_exists(handle, platform):
    with _reader() as conn:
        r = conn.execute(
            text("SELECT id FROM prospects WHERE handle=:h AND platform=:p"),
            {"h": handle, "p": platform}
        ).fetchone()
    return r is not None


def insert_prospect(data):
    with _writer() as conn:
        result = conn.execute(
            text("""
                INSERT INTO prospects
                    (client_id, niche, niche_segment, platform, handle, name, title, company,
                     profile_url, post_text, post_url, post_date, signal_phrase,
                     icp_score, icp_notes, drafted_message, call_opener, cta_url,
                     outreach_method, reddit_username, linkedin_search_url,
                     upvote_score, group_name, subreddit, status)
                VALUES
                    (:client_id, :niche, :niche_segment, :platform, :handle, :name, :title, :company,
                     :profile_url, :post_text, :post_url, :post_date, :signal_phrase,
                     :icp_score, :icp_notes, :drafted_message, :call_opener, :cta_url,
                     :outreach_method, :reddit_username, :linkedin_search_url,
                     :upvote_score, :group_name, :subreddit, 'pending')
            """),
            {
                "client_id":          data.get("client_id", CLIENT_ID),
                "niche":              data.get("niche") or data.get("niche_segment"),
                "niche_segment":      data.get("niche_segment") or data.get("niche"),
                "platform":           data.get("platform", ""),
                "handle":             data.get("handle", ""),
                "name":               data.get("name"),
                "title":              data.get("title"),
                "company":            data.get("company"),
                "profile_url":        data.get("profile_url"),
                "post_text":          data.get("post_text", ""),
                "post_url":           data.get("post_url"),
                "post_date":          data.get("post_date"),
                "signal_phrase":      data.get("signal_phrase"),
                "icp_score":          data.get("icp_score", 0),
                "icp_notes":          data.get("icp_notes"),
                "drafted_message":    data.get("drafted_message"),
                "call_opener":        data.get("call_opener"),
                "cta_url":            data.get("cta_url"),
                "outreach_method":    data.get("outreach_method", "direct"),
                "reddit_username":    data.get("reddit_username"),
                "linkedin_search_url": data.get("linkedin_search_url"),
                "upvote_score":       data.get("upvote_score", 0),
                "group_name":         data.get("group_name"),
                "subreddit":          data.get("subreddit"),
            }
        )
        pid = result.lastrowid

    # Auto-record journey events for detection + qualification
    try:
        platform  = data.get("platform", "")
        subreddit = data.get("subreddit", "")
        phrase    = data.get("signal_phrase", "")
        score     = data.get("icp_score", 0)
        source    = f"r/{subreddit}" if subreddit else platform
        add_journey_event(pid, "Detected", "🔍",
                          f"{source} — signal phrase \"{phrase}\"" if phrase else source)
        add_journey_event(pid, "Qualified", "✅",
                          f"ICP score {score}/10")
    except Exception:
        pass

    return pid


def get_prospect(prospect_id):
    with _reader() as conn:
        r = conn.execute(
            text("SELECT * FROM prospects WHERE id=:id"), {"id": prospect_id}
        )
        return _row(r)


def get_pending(niche=None):
    """Manual-review queue: score 4-8, routed to 'pending' by auto_router."""
    with _reader() as conn:
        if niche:
            r = conn.execute(text(
                "SELECT * FROM prospects WHERE status='pending' AND niche=:n "
                "ORDER BY icp_score DESC, created_at DESC"
            ), {"n": niche})
        else:
            r = conn.execute(text(
                "SELECT * FROM prospects WHERE status='pending' "
                "ORDER BY icp_score DESC, created_at DESC"
            ))
        return _rows(r)


def get_auto_approved(niche=None):
    """Batch-confirm queue: score 9-10 prospects approved by auto_router."""
    with _reader() as conn:
        if niche:
            r = conn.execute(text(
                "SELECT * FROM prospects WHERE status='auto_approved' AND niche=:n "
                "ORDER BY confidence_score DESC, icp_score DESC, created_at DESC"
            ), {"n": niche})
        else:
            r = conn.execute(text(
                "SELECT * FROM prospects WHERE status='auto_approved' "
                "ORDER BY confidence_score DESC, icp_score DESC, created_at DESC"
            ))
        return _rows(r)


def get_approved(niche=None):
    """Outreach-ready queue: founder-confirmed, awaiting manual send."""
    with _reader() as conn:
        if niche:
            r = conn.execute(text(
                "SELECT * FROM prospects WHERE status='approved' AND niche=:n "
                "ORDER BY approved_at DESC"
            ), {"n": niche})
        else:
            r = conn.execute(text(
                "SELECT * FROM prospects WHERE status='approved' ORDER BY approved_at DESC"
            ))
        return _rows(r)


def get_distinct_niches():
    """Return all niche values that have at least one prospect (for filter dropdowns)."""
    with _reader() as conn:
        r = conn.execute(text(
            "SELECT DISTINCT niche FROM prospects WHERE niche IS NOT NULL ORDER BY niche"
        ))
        return [row[0] for row in r.fetchall()]


def update_status(prospect_id, status, drafted_message=None):
    now = _now() if status in ("approved", "auto_approved") else None
    with _writer() as conn:
        if drafted_message is not None:
            conn.execute(
                text("UPDATE prospects SET status=:s, drafted_message=:m, approved_at=:t WHERE id=:id"),
                {"s": status, "m": drafted_message, "t": now, "id": prospect_id}
            )
        else:
            conn.execute(
                text("UPDATE prospects SET status=:s, approved_at=:t WHERE id=:id"),
                {"s": status, "t": now, "id": prospect_id}
            )
    # Journey event
    _STATUS_JOURNEY = {
        "approved":      ("Approved",      "👍", "Approved for outreach"),
        "auto_approved": ("Auto-approved", "⚡", "Score 9+ — auto-approved by Hermes"),
        "skipped":       ("Skipped",       "⏭️", "Skipped — not a fit"),
        "replied":       ("Replied",       "↩️", "Prospect replied"),
        "booked":        ("Call booked",   "📅", "Discovery call booked"),
    }
    if status in _STATUS_JOURNEY:
        ev, icon, detail = _STATUS_JOURNEY[status]
        try:
            add_journey_event(prospect_id, ev, icon, detail)
        except Exception:
            pass
    # Fire integrations (best-effort)
    try:
        from integrations import notify_integrations
        p = get_prospect(prospect_id)
        if p:
            notify_integrations(
                _current_tenant_slug() or CLIENT_ID,
                f"prospect.{status}",
                p,
            )
    except Exception:
        pass


def update_routing(prospect_id, confidence_score, confidence_reason, routing_decision):
    """
    Write auto_router output to a prospect.
    routing_decision is one of: 'auto_approved' | 'pending' | 'auto_skipped'
    The status column mirrors routing_decision as the initial workflow state.
    """
    with _writer() as conn:
        conn.execute(
            text("""
                UPDATE prospects
                SET confidence_score=:cs, confidence_reason=:cr,
                    routing_decision=:rd, status=:st
                WHERE id=:id
            """),
            {
                "cs": confidence_score,
                "cr": confidence_reason,
                "rd": routing_decision,
                "st": routing_decision,
                "id": prospect_id,
            }
        )


def update_hs_result(prospect_id, contact_id=None, deal_id=None, status="pushed", error=None):
    with _writer() as conn:
        conn.execute(
            text("""
                UPDATE prospects
                SET hs_contact_id=:cid, hs_deal_id=:did,
                    hs_pushed_at=:t, hs_status=:s, hs_error=:e
                WHERE id=:id
            """),
            {
                "cid": contact_id, "did": deal_id,
                "t": _now(), "s": status, "e": error, "id": prospect_id
            }
        )


def mark_sent(prospect_id, message):
    with _writer() as conn:
        conn.execute(
            text("UPDATE prospects SET status='sent', sent_at=:t WHERE id=:id"),
            {"t": _now(), "id": prospect_id}
        )
        conn.execute(
            text("INSERT INTO sent_log (prospect_id, message_sent, sent_at) VALUES (:pid, :msg, :t)"),
            {"pid": prospect_id, "msg": message, "t": _now()}
        )
    try:
        snippet = (message or "")[:100]
        add_journey_event(prospect_id, "Message sent", "💬",
                          f"Outreach sent", full_message=message)
        # Auto-create conversation thread so replies can be tracked
        create_conversation(prospect_id)
    except Exception:
        pass


def mark_prospect_sent(prospect_id: int, channel: str = "unknown", advisor_id: str = None,
                       message: str = None, disclosure_appended: bool = False):
    """
    Mark a prospect as sent and write a compliance-ready sent_log entry.
    Called by any outreach send path (Reddit DM, LinkedIn, email, etc.).
    """
    prospect = get_prospect(prospect_id) or {}
    with _writer() as conn:
        conn.execute(
            text("UPDATE prospects SET status='sent', sent_at=:t WHERE id=:id"),
            {"t": _now(), "id": prospect_id}
        )
        conn.execute(
            text("""
                INSERT INTO sent_log
                    (prospect_id, message_sent, sent_at, channel, advisor_id,
                     disclosure_appended, prospect_handle, prospect_platform, niche)
                VALUES
                    (:pid, :msg, :t, :ch, :aid, :disc, :handle, :platform, :niche)
            """),
            {
                "pid":    prospect_id,
                "msg":    message or (prospect.get("drafted_message") if prospect else ""),
                "t":      _now(),
                "ch":     channel,
                "aid":    advisor_id or CLIENT_ID,
                "disc":   1 if disclosure_appended else 0,
                "handle": prospect.get("handle"),
                "platform": prospect.get("platform"),
                "niche":  prospect.get("niche_segment") or prospect.get("niche"),
            }
        )


    # Fire integrations (best-effort)
    try:
        from integrations import notify_integrations
        p = get_prospect(prospect_id) or prospect
        if p:
            notify_integrations(
                advisor_id or _current_tenant_slug() or CLIENT_ID,
                "prospect.sent",
                p,
            )
    except Exception:
        pass


def get_tenant_setting(key: str, default=None):
    """Read a single key from tenant_settings. Returns default if not set."""
    try:
        with _reader() as conn:
            row = conn.execute(
                text("SELECT value FROM tenant_settings WHERE key=:k"), {"k": key}
            ).fetchone()
        return row[0] if row else default
    except Exception:
        return default


def set_tenant_setting(key: str, value: str):
    """Upsert a key in tenant_settings."""
    with _writer() as conn:
        if _is_sqlite:
            conn.execute(
                text("INSERT OR REPLACE INTO tenant_settings (key, value, updated_at) VALUES (:k, :v, :t)"),
                {"k": key, "v": value, "t": _now()}
            )
        else:
            conn.execute(
                text("""
                    INSERT INTO tenant_settings (key, value, updated_at) VALUES (:k, :v, :t)
                    ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, updated_at=EXCLUDED.updated_at
                """),
                {"k": key, "v": value, "t": _now()}
            )


def get_notification_settings(client_id: str = None) -> dict:
    """Return notification preferences stored in tenant_settings."""
    import json as _json
    try:
        with _reader() as conn:
            row = conn.execute(
                text("SELECT value FROM tenant_settings WHERE key='notification_prefs'")
            ).fetchone()
        if row and row[0]:
            return _json.loads(row[0])
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"[db] get_notification_settings failed: {e}")
    return {}


def save_notification_settings(client_id: str, prefs: dict) -> bool:
    """Persist notification preferences to tenant_settings."""
    import json as _json
    try:
        value = _json.dumps(prefs)
        set_tenant_setting('notification_prefs', value)
        return True
    except Exception as e:
        import traceback; traceback.print_exc()
        print(f"[db] save_notification_settings failed: {e}")
        return False


def get_sent_log_for_compliance(limit: int = 1000):
    """
    Return sent_log rows joined with prospect details for compliance export.
    Columns: sent_at, advisor_id, prospect_handle, prospect_platform, niche,
             channel, disclosure_appended, message_sent, replied, outcome.
    """
    with _reader() as conn:
        rows = conn.execute(text("""
            SELECT
                sl.sent_at,
                sl.advisor_id,
                sl.prospect_handle,
                sl.prospect_platform,
                sl.niche,
                sl.channel,
                sl.disclosure_appended,
                sl.message_sent,
                sl.replied,
                sl.outcome,
                p.icp_score,
                p.signal_phrase,
                p.post_url
            FROM sent_log sl
            LEFT JOIN prospects p ON p.id = sl.prospect_id
            ORDER BY sl.sent_at DESC
            LIMIT :lim
        """), {"lim": limit}).fetchall()
    return [dict(r._mapping) for r in rows] if rows else []


def get_stats():
    with _reader() as conn:
        stats = {}
        for status in ["pending", "auto_approved", "approved", "auto_skipped", "skipped", "sent"]:
            r = conn.execute(
                text("SELECT COUNT(*) as n FROM prospects WHERE status=:s"), {"s": status}
            ).fetchone()
            stats[status] = r[0]
        stats["total"] = sum(stats.values())
        runs = conn.execute(text("SELECT COUNT(*) as n FROM search_runs")).fetchone()
        stats["search_runs"] = runs[0]
    # Opened a separate connection after the reader above closes cleanly
    stats["unread_alerts"] = get_unacknowledged_count()
    return stats


def export_approved_csv():
    os.makedirs("exports", exist_ok=True)
    prospects = get_approved()
    if not prospects:
        return None
    path = "exports/queue.csv"
    fields = [
        "id", "name", "handle", "platform", "niche", "title", "company",
        "profile_url", "post_text", "post_url", "post_date",
        "signal_phrase", "icp_score", "confidence_score",
        "drafted_message", "cta_url", "approved_at"
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(prospects)
    return path


# ── Search / scan run logging ─────────────────────────────────────────────────

def log_search_run(platform, signal_phrase, found, qualified, drafted):
    """Legacy function — kept for backward compat with main.py."""
    with _writer() as conn:
        conn.execute(
            text("""
                INSERT INTO search_runs (run_at, platform, signal_phrase, results_found, qualified, drafted)
                VALUES (:t, :p, :sp, :f, :q, :d)
            """),
            {"t": _now(), "p": platform, "sp": signal_phrase, "f": found, "q": qualified, "d": drafted}
        )


def start_scan_run(client_id=None):
    """Create a new scan_run record in 'running' state. Returns run_id."""
    with _writer() as conn:
        result = conn.execute(
            text("""
                INSERT INTO scan_runs (client_id, started_at, status)
                VALUES (:c, :t, 'running')
            """),
            {"c": client_id or CLIENT_ID, "t": _now()}
        )
        return result.lastrowid


def complete_scan_run(run_id, found=0, qualified=0, drafted=0, pushed=0,
                      status="complete", error=None):
    with _writer() as conn:
        conn.execute(
            text("""
                UPDATE scan_runs
                SET completed_at=:t, prospects_found=:f, qualified=:q,
                    drafted=:d, pushed_to_hs=:ph, status=:s, error_log=:e
                WHERE id=:id
            """),
            {
                "t": _now(), "f": found, "q": qualified, "d": drafted,
                "ph": pushed, "s": status, "e": error, "id": run_id
            }
        )


def append_scan_error(run_id, entry):
    """
    Append a structured error dict to scan_runs.error_log.
    error_log is stored as JSON: {"errors": [...]}
    """
    with _writer() as conn:
        row = conn.execute(
            text("SELECT error_log FROM scan_runs WHERE id=:id"), {"id": run_id}
        ).fetchone()
        if row is None:
            return
        try:
            current = json.loads(row[0] or '{"errors":[]}')
        except (json.JSONDecodeError, TypeError):
            current = {"errors": []}
        current.setdefault("errors", []).append(entry)
        conn.execute(
            text("UPDATE scan_runs SET error_log=:e WHERE id=:id"),
            {"e": json.dumps(current), "id": run_id}
        )


# ── Health / monitoring ───────────────────────────────────────────────────────

def get_health_data():
    """
    Returns per-client health status.
    Used by /health endpoint (UptimeRobot) and /admin page.
    """
    with _reader() as conn:
        clients_result = conn.execute(text("SELECT DISTINCT client_id FROM scan_runs"))
        client_ids = [r[0] for r in clients_result.fetchall()]
        if not client_ids:
            client_ids = [CLIENT_ID]

        health = []
        now = datetime.now(timezone.utc)

        for cid in client_ids:
            last_run = conn.execute(
                text("""
                    SELECT started_at, completed_at, status, prospects_found
                    FROM scan_runs
                    WHERE client_id=:c AND status IN ('complete', 'failed')
                    ORDER BY started_at DESC LIMIT 1
                """),
                {"c": cid}
            ).fetchone()

            if last_run:
                last_scan_at = last_run[0]
                last_status  = last_run[2]
                found        = last_run[3] or 0
                try:
                    last_dt = datetime.fromisoformat(last_scan_at.replace("Z", "+00:00"))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    hours_since = round((now - last_dt).total_seconds() / 3600, 1)
                except Exception:
                    hours_since = 999
            else:
                last_scan_at = None
                last_status  = "never"
                found        = 0
                hours_since  = 999

            health.append({
                "client_id":        cid,
                "last_scan_at":     last_scan_at,
                "last_scan_status": last_status,
                "prospects_found":  found,
                "hours_since_scan": hours_since,
            })

    return health


def get_scan_status(run_id=None):
    with _reader() as conn:
        if run_id:
            r = conn.execute(
                text("SELECT * FROM scan_runs WHERE id=:id"), {"id": run_id}
            )
        else:
            r = conn.execute(text(
                "SELECT * FROM scan_runs ORDER BY started_at DESC LIMIT 1"
            ))
        return _row(r)


# ── Notifications ─────────────────────────────────────────────────────────────

def log_notification(notif_type, severity, title, body=None, suggested_fix=None, run_id=None):
    """Write a notification record. Called by error_logger for critical events."""
    with _writer() as conn:
        conn.execute(
            text("""
                INSERT INTO notifications (run_id, type, severity, title, body, suggested_fix, created_at)
                VALUES (:rid, :t, :s, :ti, :b, :sf, :ca)
            """),
            {
                "rid": run_id, "t": notif_type, "s": severity,
                "ti": title, "b": body, "sf": suggested_fix, "ca": _now(),
            }
        )


def get_notifications(severity=None, unacknowledged_only=True):
    """Fetch notifications for the UI. Default: unacknowledged only."""
    with _reader() as conn:
        conditions = []
        params     = {}
        if unacknowledged_only:
            conditions.append("acknowledged_at IS NULL")
        if severity:
            conditions.append("severity=:sev")
            params["sev"] = severity
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        r = conn.execute(
            text(f"SELECT * FROM notifications {where} ORDER BY created_at DESC LIMIT 100"),
            params
        )
        return _rows(r)


def acknowledge_notification(notification_id):
    with _writer() as conn:
        conn.execute(
            text("UPDATE notifications SET acknowledged_at=:t WHERE id=:id"),
            {"t": _now(), "id": notification_id}
        )


def acknowledge_all_notifications():
    with _writer() as conn:
        conn.execute(
            text("UPDATE notifications SET acknowledged_at=:t WHERE acknowledged_at IS NULL"),
            {"t": _now()}
        )


def get_unacknowledged_count():
    """Count of unacknowledged critical notifications. Used for topbar badge."""
    with _reader() as conn:
        r = conn.execute(text(
            "SELECT COUNT(*) FROM notifications WHERE acknowledged_at IS NULL AND severity='critical'"
        )).fetchone()
        return r[0] if r else 0


# ── Scheduler state ───────────────────────────────────────────────────────────

def get_scheduler_state():
    """Return the singleton scheduler config row."""
    with _reader() as conn:
        r = conn.execute(text("SELECT * FROM scheduler_state WHERE id=1"))
        row = _row(r)
        return row or {"id": 1, "is_paused": 0, "paused_at": None, "paused_reason": None}


def set_scheduler_paused(paused, reason=""):
    """Pause or resume the scheduled pipeline. State persists across app restarts."""
    with _writer() as conn:
        conn.execute(
            text("""
                UPDATE scheduler_state
                SET is_paused=:p, paused_at=:t, paused_reason=:r, last_updated=:u
                WHERE id=1
            """),
            {
                "p": 1 if paused else 0,
                "t": _now() if paused else None,
                "r": reason if paused else None,
                "u": _now(),
            }
        )


def is_niche_paused(niche_slug):
    """Returns True if this specific niche is independently paused."""
    state = get_scheduler_state()
    try:
        pauses = json.loads(state.get("niche_pauses") or "{}")
        return bool(pauses.get(niche_slug, {}).get("paused", False))
    except (json.JSONDecodeError, AttributeError, TypeError):
        return False


def set_niche_paused(niche_slug, paused, reason=""):
    """Pause or unpause a single niche without affecting the global pause or other niches."""
    with _writer() as conn:
        row = conn.execute(
            text("SELECT niche_pauses FROM scheduler_state WHERE id=1")
        ).fetchone()
        try:
            pauses = json.loads(row[0] or "{}") if row and row[0] else {}
        except (json.JSONDecodeError, TypeError):
            pauses = {}
        if paused:
            pauses[niche_slug] = {"paused": True, "paused_at": _now(), "reason": reason}
        else:
            pauses.pop(niche_slug, None)
        conn.execute(
            text("UPDATE scheduler_state SET niche_pauses=:np, last_updated=:t WHERE id=1"),
            {"np": json.dumps(pauses), "t": _now()}
        )


def get_niche_pause_states():
    """Return {niche_slug: {paused, paused_at, reason}} for all paused niches."""
    state = get_scheduler_state()
    try:
        return json.loads(state.get("niche_pauses") or "{}")
    except (json.JSONDecodeError, AttributeError, TypeError):
        return {}


# ── Global registry ───────────────────────────────────────────────────────────

def check_registry(handle, platform):
    """
    Returns True if this handle/platform combination is in an active cooldown
    (cooldown_until is in the future). Returns False if safe to contact.
    """
    with _reader() as conn:
        r = conn.execute(
            text("""
                SELECT cooldown_until FROM global_registry
                WHERE handle=:h AND platform=:p
            """),
            {"h": handle, "p": platform}
        ).fetchone()
    if r is None:
        return False
    cooldown_str = r[0]
    if not cooldown_str:
        return False
    try:
        cooldown_dt = datetime.fromisoformat(cooldown_str.replace("Z", "+00:00"))
        if cooldown_dt.tzinfo is None:
            cooldown_dt = cooldown_dt.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) < cooldown_dt
    except Exception:
        return False


def add_to_registry(handle, platform, niche_segment=None):
    """
    Upsert a handle/platform into the global registry.
    Sets cooldown_until = now + 90 days. Updates contact_count on repeat contacts.
    """
    cooldown = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    now = _now()
    with _writer() as conn:
        if _is_sqlite:
            conn.execute(
                text("""
                    INSERT INTO global_registry
                        (handle, platform, niche_segment, first_contacted_at,
                         last_contacted_at, contact_count, cooldown_until)
                    VALUES (:h, :p, :ns, :now, :now, 1, :cd)
                    ON CONFLICT(handle, platform) DO UPDATE SET
                        last_contacted_at = :now,
                        contact_count     = contact_count + 1,
                        cooldown_until    = :cd,
                        niche_segment     = COALESCE(:ns, global_registry.niche_segment)
                """),
                {"h": handle, "p": platform, "ns": niche_segment, "now": now, "cd": cooldown}
            )
        else:
            conn.execute(
                text("""
                    INSERT INTO global_registry
                        (handle, platform, niche_segment, first_contacted_at,
                         last_contacted_at, contact_count, cooldown_until)
                    VALUES (:h, :p, :ns, :now, :now, 1, :cd)
                    ON CONFLICT(handle, platform) DO UPDATE SET
                        last_contacted_at = EXCLUDED.last_contacted_at,
                        contact_count     = global_registry.contact_count + 1,
                        cooldown_until    = EXCLUDED.cooldown_until,
                        niche_segment     = COALESCE(EXCLUDED.niche_segment, global_registry.niche_segment)
                """),
                {"h": handle, "p": platform, "ns": niche_segment, "now": now, "cd": cooldown}
            )


def get_registry_stats():
    """
    Returns a summary of the global registry:
      total, active_cooldowns, breakdown by niche_segment.
    """
    now = _now()
    with _reader() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM global_registry")).fetchone()[0]
        active = conn.execute(
            text("SELECT COUNT(*) FROM global_registry WHERE cooldown_until > :now"),
            {"now": now}
        ).fetchone()[0]
        by_niche = _rows(conn.execute(text("""
            SELECT niche_segment, COUNT(*) as total,
                   SUM(CASE WHEN cooldown_until > :now THEN 1 ELSE 0 END) as on_cooldown
            FROM global_registry
            GROUP BY niche_segment
            ORDER BY niche_segment
        """), {"now": now}))
    return {
        "total":           total,
        "active_cooldowns": active,
        "by_niche":        by_niche,
    }


# ── Platform stats logging ─────────────────────────────────────────────────────

def log_platform_stat(platform, niche_segment, prospects_found, qualified, avg_icp_score=0.0):
    """Log per-platform per-niche results for the admin performance chart."""
    today = datetime.now(timezone.utc).date().isoformat()
    with _writer() as conn:
        conn.execute(
            text("""
                INSERT INTO platform_stats
                    (platform, niche_segment, scan_date, prospects_found, qualified, avg_icp_score)
                VALUES (:pl, :ns, :dt, :pf, :q, :avg)
            """),
            {
                "pl": platform, "ns": niche_segment, "dt": today,
                "pf": prospects_found, "q": qualified, "avg": avg_icp_score,
            }
        )


def get_platform_stats(days=7):
    """Return per-platform stats for the last N days."""
    with _reader() as conn:
        r = conn.execute(
            text("""
                SELECT platform, niche_segment,
                       SUM(prospects_found) as total_found,
                       SUM(qualified) as total_qualified,
                       AVG(avg_icp_score) as avg_icp
                FROM platform_stats
                WHERE scan_date >= date('now', :offset)
                GROUP BY platform, niche_segment
                ORDER BY platform, niche_segment
            """),
            {"offset": f"-{days} days"}
        )
        return _rows(r)


def get_platform_health():
    """
    Returns last-scan time and today's prospect count per platform.
    Used by /health endpoint.
    """
    with _reader() as conn:
        platforms = ["linkedin", "facebook", "reddit"]
        result    = {}
        today     = datetime.now(timezone.utc).date().isoformat()
        for pl in platforms:
            last = conn.execute(
                text("""
                    SELECT MAX(created_at) as last_scan
                    FROM prospects WHERE platform=:pl
                """),
                {"pl": pl}
            ).fetchone()
            today_count = conn.execute(
                text("""
                    SELECT COUNT(*) FROM prospects
                    WHERE platform=:pl AND DATE(created_at)=:today
                """),
                {"pl": pl, "today": today}
            ).fetchone()
            last_scan_str = last[0] if last and last[0] else None
            hours_since   = 999
            if last_scan_str:
                try:
                    last_dt = datetime.fromisoformat(last_scan_str.replace("Z", "+00:00"))
                    if last_dt.tzinfo is None:
                        last_dt = last_dt.replace(tzinfo=timezone.utc)
                    hours_since = round(
                        (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600, 1
                    )
                except Exception:
                    pass
            result[pl] = {
                "last_scan":       last_scan_str,
                "status":          "ok" if hours_since < 26 else "stale",
                "prospects_today": today_count[0] if today_count else 0,
                "hours_since":     hours_since,
            }
    return result


# ── Pre-call brief ─────────────────────────────────────────────────────────────

def save_pre_call_brief(prospect_id, brief_text):
    with _writer() as conn:
        conn.execute(
            text("UPDATE prospects SET pre_call_brief=:b WHERE id=:id"),
            {"b": brief_text, "id": prospect_id}
        )


def get_niche_counts():
    """
    Return {niche_slug: count} of actionable (pending + auto_approved) prospects per niche.
    Used for counts on the niche filter chips.
    """
    with _reader() as conn:
        r = conn.execute(text("""
            SELECT niche_segment, COUNT(*) as n
            FROM prospects
            WHERE status IN ('pending', 'auto_approved')
              AND niche_segment IS NOT NULL
            GROUP BY niche_segment
        """))
        return {row[0]: row[1] for row in r.fetchall()}


# ── Calendly integration ──────────────────────────────────────────────────────

def get_calendly_last_checked():
    """Return the ISO timestamp of the last successful Calendly poll, or None."""
    with _reader() as conn:
        r = conn.execute(
            text("SELECT calendly_last_checked FROM scheduler_state WHERE id=1")
        ).fetchone()
        return r[0] if r and r[0] else None


def set_calendly_last_checked(iso_ts):
    """Update the Calendly poll checkpoint on the singleton scheduler row."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE scheduler_state SET calendly_last_checked=:ts WHERE id=1"),
            {"ts": iso_ts},
        )


def is_calendly_event_processed(event_uuid):
    """Return True if this Calendly event UUID has already been recorded."""
    with _reader() as conn:
        r = conn.execute(
            text("SELECT id FROM calendly_bookings WHERE event_uuid=:u"),
            {"u": event_uuid},
        ).fetchone()
        return r is not None


def record_calendly_booking(event_uuid, invitee_email, prospect_id=None,
                             deal_id=None, brief_generated=False, stage_moved=False):
    """
    Insert a Calendly booking record. Idempotent — silently ignores duplicate UUIDs.
    """
    with _writer() as conn:
        try:
            conn.execute(
                text("""
                    INSERT INTO calendly_bookings
                        (event_uuid, invitee_email, prospect_id, deal_id,
                         brief_generated, stage_moved, processed_at)
                    VALUES (:u, :e, :pid, :did, :bg, :sm, :t)
                """),
                {
                    "u":   event_uuid,
                    "e":   invitee_email,
                    "pid": prospect_id,
                    "did": deal_id,
                    "bg":  1 if brief_generated else 0,
                    "sm":  1 if stage_moved else 0,
                    "t":   _now(),
                },
            )
        except Exception:
            pass  # UNIQUE constraint — event already recorded


def get_prospect_by_hs_contact_id(hs_contact_id):
    """
    Return a prospect dict whose HubSpot contact ID matches the given value.
    Used by Calendly watcher to match a booking email → HubSpot contact → DB prospect.
    Returns None if no match.
    """
    with _reader() as conn:
        r = conn.execute(
            text("SELECT * FROM prospects WHERE hs_contact_id=:cid LIMIT 1"),
            {"cid": str(hs_contact_id)},
        )
        return _row(r)


# ── Pod registry & status ─────────────────────────────────────────────────────

def upsert_pod_registry(pod_slug: str, pod_label: str = None, is_active: bool = True):
    """Register a discovered pod or update its label. Safe to call on every startup."""
    with _writer() as conn:
        if _is_sqlite:
            conn.execute(text("""
                INSERT INTO pod_registry (pod_slug, pod_label, is_active)
                VALUES (:slug, :label, :active)
                ON CONFLICT(pod_slug) DO UPDATE SET
                    pod_label = COALESCE(:label, pod_registry.pod_label),
                    is_active = :active
            """), {"slug": pod_slug, "label": pod_label, "active": 1 if is_active else 0})
        else:
            conn.execute(text("""
                INSERT INTO pod_registry (pod_slug, pod_label, is_active)
                VALUES (:slug, :label, :active)
                ON CONFLICT(pod_slug) DO UPDATE SET
                    pod_label = COALESCE(EXCLUDED.pod_label, pod_registry.pod_label),
                    is_active = EXCLUDED.is_active
            """), {"slug": pod_slug, "label": pod_label, "active": 1 if is_active else 0})


def get_pod_registry(pod_slug: str = None):
    """Return one pod row (if slug given) or all rows as list."""
    with _reader() as conn:
        if pod_slug:
            r = conn.execute(
                text("SELECT * FROM pod_registry WHERE pod_slug=:s"), {"s": pod_slug}
            )
            return _row(r)
        r = conn.execute(text("SELECT * FROM pod_registry ORDER BY pod_slug"))
        return _rows(r)


def set_pod_paused(pod_slug: str, paused: bool, reason: str = None):
    """Pause or resume a pod. Independent of circuit breaker."""
    with _writer() as conn:
        conn.execute(text("""
            UPDATE pod_registry
            SET is_paused=:p, pause_reason=:r, paused_at=:t
            WHERE pod_slug=:s
        """), {
            "p": 1 if paused else 0,
            "r": reason if paused else None,
            "t": _now() if paused else None,
            "s": pod_slug,
        })


def set_pod_circuit_breaker(pod_slug: str, open: bool):
    """Trip or reset the circuit breaker for a pod. Also pauses the pod when tripped."""
    with _writer() as conn:
        conn.execute(text("""
            UPDATE pod_registry
            SET circuit_breaker_open=:o, is_paused=:p,
                pause_reason=:r, paused_at=:t
            WHERE pod_slug=:s
        """), {
            "o": 1 if open else 0,
            "p": 1 if open else 0,
            "r": "Circuit breaker tripped — manual reset required" if open else None,
            "t": _now() if open else None,
            "s": pod_slug,
        })
        if not open:
            conn.execute(text("""
                UPDATE pod_registry SET consecutive_errors=0 WHERE pod_slug=:s
            """), {"s": pod_slug})


def set_cost_save_mode(pod_slug: str, enabled: bool):
    """Enable or disable Cost Save Mode for a single pod (Reddit-only scanning)."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE pod_registry SET cost_save_mode=:v WHERE pod_slug=:s"),
            {"v": 1 if enabled else 0, "s": pod_slug},
        )


def set_global_cost_save_mode(enabled: bool):
    """Set Cost Save Mode for ALL registered pods at once."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE pod_registry SET cost_save_mode=:v"),
            {"v": 1 if enabled else 0},
        )


def increment_pod_consecutive_errors(pod_slug: str) -> int:
    """Increment the consecutive error counter. Returns the new count."""
    with _writer() as conn:
        conn.execute(text("""
            UPDATE pod_registry
            SET consecutive_errors = consecutive_errors + 1
            WHERE pod_slug=:s
        """), {"s": pod_slug})
        r = conn.execute(
            text("SELECT consecutive_errors FROM pod_registry WHERE pod_slug=:s"),
            {"s": pod_slug}
        ).fetchone()
        return r[0] if r else 0


def reset_pod_consecutive_errors(pod_slug: str):
    """Reset the consecutive error counter to 0 on a successful run."""
    with _writer() as conn:
        conn.execute(text("""
            UPDATE pod_registry SET consecutive_errors=0 WHERE pod_slug=:s
        """), {"s": pod_slug})


def log_pod_run(pod_slug: str, report: dict):
    """
    Insert a pod run report into pod_status and update last_run_* fields in pod_registry.
    report must conform to the orchestrator data contract.
    """
    import json as _json
    with _writer() as conn:
        conn.execute(text("""
            INSERT OR IGNORE INTO pod_status
                (pod_slug, run_id, started_at, completed_at, duration_seconds,
                 status, platforms_scanned, prospects_found, prospects_qualified,
                 auto_approved, pending_review, skipped_dnc, skipped_cooldown,
                 insufficient_intel, hs_pushes_ok, hs_pushes_failed, meta_pushes_ok,
                 errors, circuit_breaker, next_run, created_at)
            VALUES
                (:slug, :rid, :sat, :cat, :dur,
                 :status, :platforms, :found, :qual,
                 :aa, :pr, :dnc, :cool,
                 :intel, :hs_ok, :hs_fail, :meta_ok,
                 :errors, :cb, :next_run, :now)
        """), {
            "slug":     pod_slug,
            "rid":      report.get("run_id"),
            "sat":      report.get("started_at"),
            "cat":      report.get("completed_at"),
            "dur":      report.get("duration_seconds", 0),
            "status":   report.get("status", "unknown"),
            "platforms": _json.dumps(report.get("platforms_scanned", [])),
            "found":    report.get("prospects_found", 0),
            "qual":     report.get("prospects_qualified", 0),
            "aa":       report.get("prospects_auto_approved", 0),
            "pr":       report.get("prospects_pending_review", 0),
            "dnc":      report.get("prospects_skipped_dnc", 0),
            "cool":     report.get("prospects_skipped_cooldown", 0),
            "intel":    report.get("prospects_skipped_insufficient_intel", 0),
            "hs_ok":    report.get("hubspot_pushes_succeeded", 0),
            "hs_fail":  report.get("hubspot_pushes_failed", 0),
            "meta_ok":  report.get("meta_pushes_succeeded", 0),
            "errors":   _json.dumps(report.get("errors", [])),
            "cb":       report.get("circuit_breaker", "closed"),
            "next_run": report.get("next_run"),
            "now":      _now(),
        })
        found = report.get("prospects_found", 0)
        conn.execute(text("""
            UPDATE pod_registry
            SET last_run_at=:t, last_run_status=:s,
                total_runs = total_runs + 1,
                total_prospects = total_prospects + :found
            WHERE pod_slug=:slug
        """), {"t": _now(), "s": report.get("status"), "found": found, "slug": pod_slug})


def get_pod_run_history(pod_slug: str, limit: int = 50) -> list:
    """Return the last N run reports for a pod, newest first."""
    with _reader() as conn:
        r = conn.execute(text("""
            SELECT * FROM pod_status
            WHERE pod_slug=:s
            ORDER BY created_at DESC
            LIMIT :lim
        """), {"s": pod_slug, "lim": limit})
        return _rows(r)


def get_all_pod_statuses() -> list:
    """
    Return one row per pod: pod_registry joined with its most recent pod_status run.
    """
    with _reader() as conn:
        r = conn.execute(text("""
            SELECT pr.*,
                   ps.status         AS last_status,
                   ps.prospects_found AS last_found,
                   ps.auto_approved  AS last_auto_approved,
                   ps.errors         AS last_errors,
                   ps.next_run       AS next_scheduled_run,
                   ps.created_at     AS last_run_created
            FROM pod_registry pr
            LEFT JOIN pod_status ps ON ps.id = (
                SELECT id FROM pod_status
                WHERE pod_slug = pr.pod_slug
                ORDER BY created_at DESC LIMIT 1
            )
            ORDER BY pr.pod_slug
        """))
        return _rows(r)


# ── DNC (Do Not Contact) registry ────────────────────────────────────────────

def is_on_dnc(handle: str, platform: str, user_id=None) -> bool:
    """
    Return True if this handle/platform is on the DNC list.
    Checks user-level DNC first (if user_id given), then global DNC (is_global=1).
    Fails open (returns False) if DB is unavailable — don't block leads due to infra errors.

    user_id='' and user_id=None are both treated as "no user context — check global only".
    Global entries are stored with user_id='' and is_global=1.
    User-level entries are stored with user_id=<slug> and is_global=0.
    """
    try:
        with _reader() as conn:
            # User-level check
            if user_id:
                r = conn.execute(
                    text("""
                        SELECT id FROM dnc_list
                        WHERE handle=:h AND platform=:p AND user_id=:u AND is_global=0
                        LIMIT 1
                    """),
                    {"h": handle, "p": platform, "u": str(user_id)}
                ).fetchone()
                if r:
                    return True
            # Global check (user_id='' marks global entries)
            r = conn.execute(
                text("""
                    SELECT id FROM dnc_list
                    WHERE handle=:h AND platform=:p AND is_global=1
                    LIMIT 1
                """),
                {"h": handle, "p": platform}
            ).fetchone()
            return r is not None
    except Exception:
        return False  # Fail open — DB unavailable


def add_dnc_entry(handle: str, platform: str, user_id, reason: str,
                  added_by: str = "system", is_global: bool = False):
    """
    Add a handle/platform to the DNC list. Silently ignores duplicates.
    Global entries: user_id stored as '' (empty string), is_global=1.
    User entries:   user_id stored as the actual slug, is_global=0.
    """
    with _writer() as conn:
        try:
            stored_uid = "" if is_global else (str(user_id) if user_id else "")
            conn.execute(
                text("""
                    INSERT INTO dnc_list (handle, platform, user_id, is_global, reason, added_by, added_at)
                    VALUES (:h, :p, :u, :g, :r, :ab, :t)
                """),
                {
                    "h":  handle,
                    "p":  platform,
                    "u":  stored_uid,
                    "g":  1 if is_global else 0,
                    "r":  reason,
                    "ab": added_by,
                    "t":  _now(),
                }
            )
        except Exception:
            pass  # UNIQUE constraint — already on DNC


def remove_from_dnc(handle: str, platform: str, user_id):
    """Remove a user-level DNC entry. Does not touch global DNC entries."""
    with _writer() as conn:
        conn.execute(
            text("""
                DELETE FROM dnc_list
                WHERE handle=:h AND platform=:p AND user_id=:u AND is_global=0
            """),
            {"h": handle, "p": platform, "u": str(user_id) if user_id else ""}
        )


# ── EventDispatcher deduplication ─────────────────────────────────────────────

def has_event_been_dispatched(event_id: str) -> bool:
    """Return True if this deterministic UUID5 event_id has already been processed."""
    try:
        with _reader() as conn:
            r = conn.execute(
                text("SELECT id FROM dispatched_events WHERE event_id=:eid LIMIT 1"),
                {"eid": event_id}
            ).fetchone()
            return r is not None
    except Exception:
        return False  # Fail open — don't silently drop events due to DB hiccup


def log_dispatched_event(event_id: str, event_type: str, user_id=None,
                         prospect_id=None, data_json: str = None):
    """Record a successfully dispatched event. Idempotent — ignores duplicate event_id."""
    with _writer() as conn:
        try:
            conn.execute(
                text("""
                    INSERT INTO dispatched_events
                        (event_id, event_type, user_id, prospect_id, data_json, dispatched_at)
                    VALUES (:eid, :et, :u, :pid, :dj, :t)
                """),
                {
                    "eid": event_id,
                    "et":  event_type,
                    "u":   user_id,
                    "pid": prospect_id,
                    "dj":  data_json,
                    "t":   _now(),
                }
            )
        except Exception:
            pass  # UNIQUE constraint on event_id — already recorded


# ── Voice calls ───────────────────────────────────────────────────────────────

def log_voice_call(called_number: str, caller_hash: str,
                   user_id: str = "ALT00", direction: str = "inbound",
                   call_id: str = None) -> int:
    """Insert a new voice_calls row. Returns the row id."""
    with _writer() as conn:
        result = conn.execute(
            text("""
                INSERT INTO voice_calls
                    (call_id, user_id, direction, called_number, caller_hash, created_at)
                VALUES (:cid, :uid, :dir, :cn, :ch, :t)
            """),
            {
                "cid": call_id,
                "uid": user_id,
                "dir": direction,
                "cn":  called_number,
                "ch":  caller_hash,
                "t":   _now(),
            },
        )
        return result.lastrowid


def update_voice_call(call_id, transcript=None, summary=None,
                      duration_seconds=None, outcome=None,
                      escalation_reason=None, booking_confirmed=None,
                      hs_deal_id=None, hs_task_id=None):
    """Update a voice_calls row after the call ends. Only sets non-None fields."""
    fields, params = [], {"cid": call_id}
    if transcript        is not None: fields.append("transcript=:tr");         params["tr"]  = transcript
    if summary           is not None: fields.append("summary=:su");            params["su"]  = summary
    if duration_seconds  is not None: fields.append("duration_seconds=:ds");   params["ds"]  = duration_seconds
    if outcome           is not None: fields.append("outcome=:oc");            params["oc"]  = outcome
    if escalation_reason is not None: fields.append("escalation_reason=:er");  params["er"]  = escalation_reason
    if booking_confirmed is not None: fields.append("booking_confirmed=:bc");  params["bc"]  = 1 if booking_confirmed else 0
    if hs_deal_id        is not None: fields.append("hs_deal_id=:hd");         params["hd"]  = hs_deal_id
    if hs_task_id        is not None: fields.append("hs_task_id=:ht");         params["ht"]  = hs_task_id
    if not fields:
        return
    with _writer() as conn:
        conn.execute(
            text(f"UPDATE voice_calls SET {', '.join(fields)} WHERE call_id=:cid"),
            params,
        )


def mark_closer_notified(call_id):
    with _writer() as conn:
        conn.execute(
            text("UPDATE voice_calls SET closer_notified=1, closer_notified_at=:t WHERE call_id=:cid"),
            {"t": _now(), "cid": call_id},
        )


def log_voice_cost(call_id: str, cost_usd: float, user_id: str = "ALT00"):
    """Log Vapi call cost to budget_transactions and update voice_calls.cost_usd."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE voice_calls SET cost_usd=:c WHERE call_id=:cid"),
            {"c": cost_usd, "cid": call_id},
        )
        conn.execute(
            text("""
                INSERT INTO budget_transactions
                    (transaction_type, platform, description, amount, direction,
                     transaction_date, reference_id, reference_type, notes)
                VALUES ('spend', 'vapi', 'Inbound call — Morgan AI Receptionist',
                        :amt, 'out', :t, :ref, 'voice_call', :notes)
            """),
            {
                "amt":   cost_usd,
                "t":     _now(),
                "ref":   call_id,
                "notes": f"user_id={user_id}",
            },
        )


def get_voice_calls(limit: int = 50, user_id: str = None) -> list:
    with _reader() as conn:
        if user_id:
            r = conn.execute(
                text("SELECT * FROM voice_calls WHERE user_id=:u ORDER BY created_at DESC LIMIT :lim"),
                {"u": user_id, "lim": limit},
            )
        else:
            r = conn.execute(
                text("SELECT * FROM voice_calls ORDER BY created_at DESC LIMIT :lim"),
                {"lim": limit},
            )
        return _rows(r)


# ── Hermes learning gate ─────────────────────────────────────────────────────

def get_hermes_convo_count() -> int:
    """Return how many conversations Hermes has drafted messages for."""
    with _reader() as conn:
        r = conn.execute(
            text("SELECT hermes_convo_count FROM scheduler_state WHERE id=1")
        ).fetchone()
        return int(r[0]) if r and r[0] is not None else 0


def increment_hermes_convo_count() -> int:
    """Increment Hermes conversation counter. Returns new count."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE scheduler_state SET hermes_convo_count = hermes_convo_count + 1 WHERE id=1")
        )
        r = conn.execute(
            text("SELECT hermes_convo_count FROM scheduler_state WHERE id=1")
        ).fetchone()
        count = int(r[0]) if r else 0
        if count == 50:
            conn.execute(
                text("UPDATE scheduler_state SET hermes_auto_enabled=1 WHERE id=1")
            )
        return count


def is_hermes_auto_enabled() -> bool:
    """True once Hermes has reached 50 conversations and the owner hasn't disabled it."""
    with _reader() as conn:
        r = conn.execute(
            text("SELECT hermes_auto_enabled, hermes_convo_count FROM scheduler_state WHERE id=1")
        ).fetchone()
        if not r:
            return False
        return bool(r[0]) and int(r[1] or 0) >= 50


def set_hermes_auto_enabled(enabled: bool):
    """Manually enable or disable Hermes auto-send (owner override)."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE scheduler_state SET hermes_auto_enabled=:v WHERE id=1"),
            {"v": 1 if enabled else 0}
        )


# ── Scrape jobs (Celery async) ────────────────────────────────────────────────

def create_scrape_job(job_id: str, pod_slug: str) -> int:
    """Insert a new scrape_jobs row in PENDING state. Returns row id."""
    with _writer() as conn:
        result = conn.execute(
            text("""
                INSERT INTO scrape_jobs (job_id, pod_slug, status, created_at)
                VALUES (:jid, :slug, 'PENDING', :t)
            """),
            {"jid": job_id, "slug": pod_slug, "t": _now()}
        )
        return result.lastrowid


def get_scrape_job(job_id: str) -> dict | None:
    """Return a scrape_jobs row by Celery task ID."""
    with _reader() as conn:
        r = conn.execute(
            text("SELECT * FROM scrape_jobs WHERE job_id=:jid"),
            {"jid": job_id}
        )
        return _row(r)


# ── Market insights (Hermes LLM output) ───────────────────────────────────────

def save_market_insight(prospect_id: int, pod_slug: str, pain_point: str,
                        competitor_mentions: list, intent_score: float,
                        raw_signals: dict = None, source: str = None) -> int:
    """Store one Hermes market insight extraction. Returns row id."""
    import json as _json
    # Derive source from the prospect's platform if not provided
    if source is None:
        try:
            with _reader() as rconn:
                row = rconn.execute(
                    text("SELECT platform FROM prospects WHERE id=:id"), {"id": prospect_id}
                ).fetchone()
                source = row[0] if row else "reddit"
        except Exception:
            source = "reddit"

    with _writer() as conn:
        result = conn.execute(
            text("""
                INSERT INTO market_insights
                    (prospect_id, pod_slug, primary_pain_point, competitor_mentions,
                     intent_score, raw_signals, source, extracted_at)
                VALUES (:pid, :slug, :pain, :comp, :score, :raw, :src, :t)
            """),
            {
                "pid":   prospect_id,
                "slug":  pod_slug,
                "pain":  pain_point,
                "comp":  _json.dumps(competitor_mentions or []),
                "score": intent_score,
                "raw":   _json.dumps(raw_signals or {}),
                "src":   source,
                "t":     _now(),
            }
        )
        # Also stamp intent_score on the prospect row itself
        conn.execute(
            text("UPDATE prospects SET intent_score=:s WHERE id=:id"),
            {"s": intent_score, "id": prospect_id}
        )
        return result.lastrowid


def get_market_insights(pod_slug: str = None, limit: int = 100) -> list:
    """Return recent market insights, optionally filtered by pod."""
    with _reader() as conn:
        if pod_slug:
            r = conn.execute(
                text("SELECT * FROM market_insights WHERE pod_slug=:slug ORDER BY extracted_at DESC LIMIT :lim"),
                {"slug": pod_slug, "lim": limit}
            )
        else:
            r = conn.execute(
                text("SELECT * FROM market_insights ORDER BY extracted_at DESC LIMIT :lim"),
                {"lim": limit}
            )
        return _rows(r)


def get_market_pulse_data(pod_slug: str = None, source: str = None) -> list:
    """
    Return market insights joined with prospect platform data for the pulse widget.
    Resolves source from market_insights.source first, then falls back to
    prospects.platform so older rows (before migration) still appear correctly.
    Limits to the last 7 days of data.
    """
    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    conditions = ["mi.extracted_at >= :cutoff"]
    params: dict = {"cutoff": cutoff}

    if pod_slug:
        conditions.append("mi.pod_slug = :slug")
        params["slug"] = pod_slug

    if source:
        conditions.append("(COALESCE(mi.source, p.platform, 'reddit') = :src)")
        params["src"] = source

    where = " AND ".join(conditions)

    with _reader() as conn:
        r = conn.execute(
            text(f"""
                SELECT
                    mi.*,
                    COALESCE(mi.source, p.platform, 'reddit') AS source,
                    p.platform AS prospect_platform,
                    p.niche    AS prospect_niche
                FROM market_insights mi
                LEFT JOIN prospects p ON p.id = mi.prospect_id
                WHERE {where}
                ORDER BY mi.extracted_at DESC
                LIMIT 200
            """),
            params,
        )
        return _rows(r)


# ── Signal feedback & Golden History ─────────────────────────────────────────

def save_signal_feedback(signal_phrase: str, rating: int, note: str = None,
                          submitted_by: str = "owner") -> int:
    """
    Save a thumbs up (rating=1) or thumbs down (rating=-1) for a signal phrase.
    Returns the new row id.
    """
    with _writer() as conn:
        result = conn.execute(
            text("""
                INSERT INTO signal_feedback (signal_phrase, rating, note, submitted_by, created_at)
                VALUES (:phrase, :rating, :note, :by, :t)
            """),
            {"phrase": signal_phrase, "rating": rating, "note": note, "by": submitted_by, "t": _now()}
        )
        return result.lastrowid


def get_signal_feedback(signal_phrase: str) -> list:
    """Return all feedback rows for a given phrase, newest first."""
    with _reader() as conn:
        r = conn.execute(
            text("SELECT * FROM signal_feedback WHERE signal_phrase=:p ORDER BY created_at DESC"),
            {"p": signal_phrase}
        )
        return _rows(r)


def log_golden_history(signal_phrase: str, feedback_type: str,
                        feedback_note: str = None, example_message: str = None,
                        outreach_angle: str = None, source: str = "owner") -> int:
    """
    Append an entry to the Golden History database.
    This is the few-shot example bank used when building Hermes prompts.
    feedback_type: 'positive' | 'negative' | 'refresh'
    """
    with _writer() as conn:
        result = conn.execute(
            text("""
                INSERT INTO golden_history
                    (signal_phrase, feedback_type, feedback_note, example_message,
                     outreach_angle, source, created_at)
                VALUES (:phrase, :type, :note, :msg, :angle, :src, :t)
            """),
            {
                "phrase": signal_phrase,
                "type":   feedback_type,
                "note":   feedback_note,
                "msg":    example_message,
                "angle":  outreach_angle,
                "src":    source,
                "t":      _now(),
            }
        )
        return result.lastrowid


def get_golden_history(signal_phrase: str = None, limit: int = 20) -> list:
    """
    Return Golden History entries — used to build few-shot context for Hermes.
    If signal_phrase is given, returns entries for that phrase only.
    """
    with _reader() as conn:
        if signal_phrase:
            r = conn.execute(
                text("""
                    SELECT * FROM golden_history
                    WHERE signal_phrase=:p
                    ORDER BY created_at DESC LIMIT :lim
                """),
                {"p": signal_phrase, "lim": limit}
            )
        else:
            r = conn.execute(
                text("SELECT * FROM golden_history ORDER BY created_at DESC LIMIT :lim"),
                {"lim": limit}
            )
        return _rows(r)


def get_signal_summary() -> list:
    """
    Aggregate signal phrase performance: found count, thumbs up/down totals.
    Joins signal_feedback with prospects to derive reply-rate-adjacent data.
    """
    with _reader() as conn:
        r = conn.execute(text("""
            SELECT
                sf.signal_phrase,
                COUNT(sf.id)                                          AS feedback_count,
                SUM(CASE WHEN sf.rating = 1  THEN 1 ELSE 0 END)      AS thumbs_up,
                SUM(CASE WHEN sf.rating = -1 THEN 1 ELSE 0 END)      AS thumbs_down,
                MAX(sf.created_at)                                    AS last_feedback_at
            FROM signal_feedback sf
            GROUP BY sf.signal_phrase
            ORDER BY last_feedback_at DESC
        """))
        return _rows(r)


# ── Journey events ────────────────────────────────────────────────────────────

def add_journey_event(prospect_id: int, event: str, icon: str = '📌',
                      detail: str = None, full_message: str = None) -> int:
    """Record one step in a prospect's journey. Returns new event id."""
    with _writer() as conn:
        r = conn.execute(
            text("""
                INSERT INTO journey_events (prospect_id, event, icon, detail, full_message)
                VALUES (:pid, :ev, :ic, :det, :msg)
            """),
            {"pid": prospect_id, "ev": event, "ic": icon, "det": detail, "msg": full_message},
        )
        return r.lastrowid


def get_journey_list(advisor_id=None, search=None, niche=None, stage=None) -> list:
    """
    Return all prospects that have at least one journey event, with their latest
    event and overall stage. Used by the Journey screen list view.
    """
    conditions = ["1=1"]
    params: dict = {}
    if niche and niche != "all":
        conditions.append("p.niche_segment = :niche")
        params["niche"] = niche
    if search:
        conditions.append("(p.name LIKE :s OR p.handle LIKE :s)")
        params["s"] = f"%{search}%"
    if stage:
        conditions.append("p.status = :stage")
        params["stage"] = stage

    where = " AND ".join(conditions)
    with _reader() as conn:
        r = conn.execute(text(f"""
            SELECT
                p.id, p.handle, p.name, p.platform, p.niche_segment AS niche,
                p.icp_score, p.status, p.drafted_message, p.signal_phrase,
                p.post_text, p.scraped_at,
                j.event AS latest_event, j.icon AS latest_icon,
                j.created_at AS latest_at,
                (SELECT COUNT(*) FROM journey_events WHERE prospect_id=p.id) AS event_count
            FROM prospects p
            LEFT JOIN journey_events j ON j.id = (
                SELECT id FROM journey_events WHERE prospect_id=p.id
                ORDER BY created_at DESC LIMIT 1
            )
            WHERE {where}
            ORDER BY COALESCE(j.created_at, p.scraped_at) DESC
            LIMIT 200
        """), params)
        return _rows(r)


def get_prospect_journey(prospect_id: int) -> dict:
    """
    Return a prospect dict with its full journey event list.
    Used by Journey detail view.
    """
    with _reader() as conn:
        p = conn.execute(
            text("SELECT * FROM prospects WHERE id=:id"), {"id": prospect_id}
        ).fetchone()
        if not p:
            return {}
        events = conn.execute(
            text("SELECT * FROM journey_events WHERE prospect_id=:pid ORDER BY created_at ASC"),
            {"pid": prospect_id}
        )
        result = dict(p._mapping)
        result["journey"] = _rows(events)
        return result


# ── Conversations ─────────────────────────────────────────────────────────────

def create_conversation(prospect_id: int, advisor_id: str = None,
                        platform: str = "reddit", source: str = "cold_stream",
                        source_context: dict = None, handle: str = None,
                        subreddit: str = None) -> int:
    """
    Create a conversation thread for a prospect. Idempotent — returns existing
    conversation id if one already exists for this prospect.
    source: 'cold_stream' | 'post_comment' | 'scrapebadger' | 'creator'
    source_context: dict with signal, post_url, post_title, pain_point etc.
    """
    import json as _json
    ctx_str = _json.dumps(source_context) if source_context else None
    with _writer() as conn:
        existing = conn.execute(
            text("SELECT id FROM conversations WHERE prospect_id=:pid"),
            {"pid": prospect_id}
        ).fetchone()
        if existing:
            return existing[0]
        r = conn.execute(
            text("""
                INSERT INTO conversations
                    (prospect_id, advisor_id, platform, source, source_context, handle, subreddit)
                VALUES (:pid, :aid, :plat, :src, :ctx, :handle, :sub)
            """),
            {"pid": prospect_id, "aid": advisor_id, "plat": platform,
             "src": source, "ctx": ctx_str, "handle": handle, "sub": subreddit},
        )
        return r.lastrowid


def get_conversations(advisor_id=None, source: str = None) -> list:
    """Return all conversations with their latest message and prospect info."""
    import json as _json
    where = "WHERE 1=1"
    params = {}
    if source:
        where += " AND c.source = :src"
        params["src"] = source
    with _reader() as conn:
        r = conn.execute(text(f"""
            SELECT
                c.id, c.prospect_id, c.platform, c.mode, c.unread, c.updated_at,
                COALESCE(c.handle, p.handle)        AS handle,
                p.name, p.niche_segment             AS niche,
                p.drafted_message,
                COALESCE(c.subreddit, p.subreddit)  AS subreddit,
                c.source, c.source_context,
                (SELECT body FROM conversation_messages
                 WHERE conversation_id=c.id ORDER BY sent_at DESC LIMIT 1) AS last_message,
                (SELECT sender FROM conversation_messages
                 WHERE conversation_id=c.id ORDER BY sent_at DESC LIMIT 1) AS last_sender
            FROM conversations c
            JOIN prospects p ON p.id = c.prospect_id
            {where}
            ORDER BY c.updated_at DESC
            LIMIT 100
        """), params)
        rows = _rows(r)
    # Parse source_context JSON
    for row in rows:
        if isinstance(row.get('source_context'), str):
            try:
                row['source_context'] = _json.loads(row['source_context'])
            except Exception:
                row['source_context'] = {}
    return rows


def get_conversation_messages(conversation_id: int) -> list:
    """Return all messages in a conversation ordered by time."""
    with _reader() as conn:
        r = conn.execute(
            text("SELECT * FROM conversation_messages WHERE conversation_id=:cid ORDER BY sent_at ASC"),
            {"cid": conversation_id},
        )
        return _rows(r)


def send_message(conversation_id: int, sender: str, body: str) -> int:
    """Add a message to a conversation and bump updated_at. Returns message id."""
    with _writer() as conn:
        r = conn.execute(
            text("""
                INSERT INTO conversation_messages (conversation_id, sender, body)
                VALUES (:cid, :sender, :body)
            """),
            {"cid": conversation_id, "sender": sender, "body": body},
        )
        conn.execute(
            text("UPDATE conversations SET updated_at=:t, unread=CASE WHEN :sender='prospect' THEN 1 ELSE unread END WHERE id=:cid"),
            {"t": _now(), "sender": sender, "cid": conversation_id},
        )
        return r.lastrowid


def update_conversation_mode(conversation_id: int, mode: str) -> bool:
    """Update Hermes mode (auto/assist/human) for a conversation."""
    with _writer() as conn:
        conn.execute(
            text("UPDATE conversations SET mode=:mode WHERE id=:cid"),
            {"mode": mode, "cid": conversation_id},
        )
        return True


def get_prospect_by_conversation(conversation_id: int) -> dict:
    """Return the prospect record linked to a conversation."""
    with _reader() as conn:
        r = conn.execute(
            text("""
                SELECT p.* FROM prospects p
                JOIN conversations c ON c.prospect_id = p.id
                WHERE c.id = :cid
            """),
            {"cid": conversation_id},
        ).fetchone()
        return dict(r._mapping) if r else {}


def log_reply(prospect_id: int, body: str, sender: str = "prospect") -> int:
    """
    Log a manual reply (e.g. pasted in from LinkedIn or Facebook).
    Creates a conversation thread if one doesn't exist, adds the message,
    records a journey event, and returns the message id.
    """
    conv_id = create_conversation(prospect_id)
    msg_id  = send_message(conv_id, sender, body)
    snippet = body[:120] + ("..." if len(body) > 120 else "")
    add_journey_event(
        prospect_id, "Replied", "↩️",
        f'Replied: "{snippet}"', full_message=body
    )
    with _writer() as conn:
        conn.execute(
            text("UPDATE prospects SET status='replied' WHERE id=:id AND status NOT IN ('booked','closed_won','closed_lost')"),
            {"id": prospect_id},
        )
    return msg_id


# ── Integrations ──────────────────────────────────────────────────────────────

def get_integrations(advisor_id=None) -> list:
    aid = advisor_id or CLIENT_ID
    try:
        with _reader() as conn:
            rows = conn.execute(
                text("SELECT id, slug, enabled, config FROM integrations WHERE advisor_id=:aid ORDER BY slug"),
                {"aid": aid}
            ).mappings().all()
        result = []
        for r in rows:
            cfg = r['config']
            if isinstance(cfg, str):
                try:
                    cfg = json.loads(cfg)
                except Exception:
                    cfg = {}
            result.append({
                'id':      r['id'],
                'slug':    r['slug'],
                'enabled': bool(r['enabled']),
                'config':  cfg,
            })
        return result
    except Exception:
        return []


def get_integration(advisor_id, slug) -> dict:
    aid = advisor_id or CLIENT_ID
    try:
        with _reader() as conn:
            row = conn.execute(
                text("SELECT id, slug, enabled, config FROM integrations WHERE advisor_id=:aid AND slug=:slug"),
                {"aid": aid, "slug": slug}
            ).mappings().first()
        if not row:
            return None
        cfg = row['config']
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:
                cfg = {}
        return {'id': row['id'], 'slug': row['slug'], 'enabled': bool(row['enabled']), 'config': cfg}
    except Exception:
        return None


def save_integration(advisor_id, slug, enabled, config) -> bool:
    aid     = advisor_id or CLIENT_ID
    cfg_str = json.dumps(config) if isinstance(config, dict) else (config or '{}')
    now     = _now()
    try:
        with _writer() as conn:
            if _is_sqlite:
                conn.execute(
                    text("""
                        INSERT OR REPLACE INTO integrations
                            (advisor_id, slug, enabled, config, updated_at)
                        VALUES (:aid, :slug, :en, :cfg, :now)
                    """),
                    {"aid": aid, "slug": slug, "en": 1 if enabled else 0, "cfg": cfg_str, "now": now}
                )
            else:
                conn.execute(
                    text("""
                        INSERT INTO integrations (advisor_id, slug, enabled, config, updated_at)
                        VALUES (:aid, :slug, :en, :cfg, :now)
                        ON CONFLICT (advisor_id, slug) DO UPDATE SET
                            enabled    = EXCLUDED.enabled,
                            config     = EXCLUDED.config,
                            updated_at = EXCLUDED.updated_at
                    """),
                    {"aid": aid, "slug": slug, "en": 1 if enabled else 0, "cfg": cfg_str, "now": now}
                )
        return True
    except Exception as e:
        print(f"[db] save_integration error: {e}", file=sys.stderr)
        return False


# ── Mod outreach ──────────────────────────────────────────────────────────────
# Subreddit moderator introductions are stored HERE, never in prospects.
# Reps must see these as distinct from sales leads.

_MOD_OUTREACH_DDL = _ddl(
    """CREATE TABLE IF NOT EXISTS mod_outreach (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        subreddit    TEXT    NOT NULL UNIQUE,
        niche        TEXT,
        client_id    TEXT,
        draft        TEXT,
        status       TEXT    NOT NULL DEFAULT 'pending_review',
        sent_at      TEXT,
        response     TEXT,
        created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS mod_outreach (
        id           SERIAL  PRIMARY KEY,
        subreddit    TEXT    NOT NULL UNIQUE,
        niche        TEXT,
        client_id    TEXT,
        draft        TEXT,
        status       TEXT    NOT NULL DEFAULT 'pending_review',
        sent_at      TIMESTAMP,
        response     TEXT,
        created_at   TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
)


def _ensure_mod_outreach_table():
    try:
        with _writer() as conn:
            conn.execute(text(_MOD_OUTREACH_DDL))
    except Exception:
        pass


def has_mod_outreach(subreddit: str) -> bool:
    """True if we already have a mod outreach record for this subreddit."""
    try:
        _ensure_mod_outreach_table()
        with _reader() as conn:
            r = conn.execute(
                text("SELECT id FROM mod_outreach WHERE subreddit=:s"),
                {"s": subreddit},
            ).fetchone()
        return r is not None
    except Exception:
        return False


def queue_mod_outreach(subreddit: str, niche: str, draft: str, client_id: str = None) -> bool:
    """Insert a new pending mod outreach record with Hermes-drafted intro message."""
    try:
        _ensure_mod_outreach_table()
        cid = client_id or CLIENT_ID
        with _writer() as conn:
            if _is_sqlite:
                conn.execute(
                    text("""
                        INSERT OR IGNORE INTO mod_outreach (subreddit, niche, client_id, draft, status)
                        VALUES (:sub, :niche, :cid, :draft, 'pending_review')
                    """),
                    {"sub": subreddit, "niche": niche, "cid": cid, "draft": draft},
                )
            else:
                conn.execute(
                    text("""
                        INSERT INTO mod_outreach (subreddit, niche, client_id, draft, status)
                        VALUES (:sub, :niche, :cid, :draft, 'pending_review')
                        ON CONFLICT (subreddit) DO NOTHING
                    """),
                    {"sub": subreddit, "niche": niche, "cid": cid, "draft": draft},
                )
        return True
    except Exception as e:
        print(f"[db] queue_mod_outreach error: {e}", file=sys.stderr)
        return False


def get_mod_outreach(status: str = None) -> list:
    """Return mod outreach records, optionally filtered by status."""
    try:
        _ensure_mod_outreach_table()
        with _reader() as conn:
            if status:
                r = conn.execute(
                    text("SELECT * FROM mod_outreach WHERE status=:s ORDER BY created_at DESC"),
                    {"s": status},
                )
            else:
                r = conn.execute(
                    text("SELECT * FROM mod_outreach ORDER BY created_at DESC")
                )
            return _rows(r)
    except Exception:
        return []


def update_mod_outreach(mid: int, status: str, response: str = None) -> bool:
    """Mark a mod outreach as sent/approved/dismissed."""
    try:
        _ensure_mod_outreach_table()
        now = _now()
        with _writer() as conn:
            conn.execute(
                text("""
                    UPDATE mod_outreach
                    SET status=:s, response=:r,
                        sent_at=CASE WHEN :s='sent' THEN :now ELSE sent_at END
                    WHERE id=:id
                """),
                {"s": status, "r": response, "now": now, "id": mid},
            )
        return True
    except Exception as e:
        print(f"[db] update_mod_outreach error: {e}", file=sys.stderr)
        return False


def save_mod_outreach_draft(mid: int, draft: str) -> bool:
    """Update the Hermes draft for a mod outreach record (rep edited it)."""
    try:
        _ensure_mod_outreach_table()
        with _writer() as conn:
            conn.execute(
                text("UPDATE mod_outreach SET draft=:d WHERE id=:id"),
                {"d": draft, "id": mid},
            )
        return True
    except Exception:
        return False


# ── Value posts (viral data contribution tactic) ──────────────────────────────

_VALUE_POSTS_DDL = _ddl(
    """CREATE TABLE IF NOT EXISTS value_posts (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id      TEXT,
        subreddit      TEXT    NOT NULL,
        type           TEXT    NOT NULL DEFAULT 'insight_digest',
        title          TEXT    NOT NULL,
        body           TEXT    NOT NULL,
        topic          TEXT,
        signals        TEXT,
        post_count     INTEGER DEFAULT 0,
        status         TEXT    NOT NULL DEFAULT 'draft',
        posted_at      TEXT,
        upvotes        INTEGER DEFAULT 0,
        comments       INTEGER DEFAULT 0,
        created_at     TEXT    NOT NULL DEFAULT (datetime('now')),
        auto_generated INTEGER DEFAULT 0,
        source_signal  TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS value_posts (
        id             SERIAL  PRIMARY KEY,
        client_id      TEXT,
        subreddit      TEXT    NOT NULL,
        type           TEXT    NOT NULL DEFAULT 'insight_digest',
        title          TEXT    NOT NULL,
        body           TEXT    NOT NULL,
        topic          TEXT,
        signals        TEXT,
        post_count     INTEGER DEFAULT 0,
        status         TEXT    NOT NULL DEFAULT 'draft',
        posted_at      TIMESTAMP,
        upvotes        INTEGER DEFAULT 0,
        comments       INTEGER DEFAULT 0,
        created_at     TIMESTAMP NOT NULL DEFAULT NOW(),
        auto_generated INTEGER DEFAULT 0,
        source_signal  TEXT
    )""",
)


_REDDIT_TOP_POSTS_DDL = _ddl(
    """CREATE TABLE IF NOT EXISTS reddit_top_posts (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id     TEXT    NOT NULL DEFAULT 'ALT00',
        subreddit     TEXT    NOT NULL,
        post_id       TEXT,
        title         TEXT    NOT NULL,
        body          TEXT,
        score         INTEGER DEFAULT 0,
        upvote_ratio  REAL    DEFAULT 0,
        comment_count INTEGER DEFAULT 0,
        post_url      TEXT,
        time_period   TEXT    DEFAULT 'week',
        fetched_at    TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS reddit_top_posts (
        id            SERIAL  PRIMARY KEY,
        client_id     TEXT    NOT NULL DEFAULT 'ALT00',
        subreddit     TEXT    NOT NULL,
        post_id       TEXT,
        title         TEXT    NOT NULL,
        body          TEXT,
        score         INTEGER DEFAULT 0,
        upvote_ratio  REAL    DEFAULT 0,
        comment_count INTEGER DEFAULT 0,
        post_url      TEXT,
        time_period   TEXT    DEFAULT 'week',
        fetched_at    TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
)

_CONTENT_PLANS_DDL = _ddl(
    """CREATE TABLE IF NOT EXISTS content_plans (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id   TEXT    NOT NULL DEFAULT 'ALT00',
        plan_json   TEXT    NOT NULL,
        source_data TEXT,
        niche       TEXT,
        created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS content_plans (
        id          SERIAL  PRIMARY KEY,
        client_id   TEXT    NOT NULL DEFAULT 'ALT00',
        plan_json   TEXT    NOT NULL,
        source_data TEXT,
        niche       TEXT,
        created_at  TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
)


def _ensure_value_posts_table():
    try:
        with _writer() as conn:
            conn.execute(text(_VALUE_POSTS_DDL))
    except Exception:
        pass
    for col_sql in [
        "ALTER TABLE value_posts ADD COLUMN auto_generated INTEGER DEFAULT 0",
        "ALTER TABLE value_posts ADD COLUMN source_signal TEXT",
        "ALTER TABLE value_posts ADD COLUMN post_url TEXT",
        "ALTER TABLE value_posts ADD COLUMN comments_checked_at TEXT",
        "ALTER TABLE value_posts ADD COLUMN commenters_found INTEGER DEFAULT 0",
        "ALTER TABLE value_posts ADD COLUMN scheduled_for TEXT",
        "ALTER TABLE value_posts ADD COLUMN image_prompt TEXT",
        "ALTER TABLE value_posts ADD COLUMN platform TEXT DEFAULT 'reddit'",
        "ALTER TABLE value_posts ADD COLUMN signal_example TEXT",
        "ALTER TABLE value_posts ADD COLUMN perf_checked INTEGER DEFAULT 0",
    ]:
        try:
            with _writer() as conn:
                conn.execute(text(col_sql))
        except Exception:
            pass

    # warmup_comments table — daily account-warming comments
    try:
        with _writer() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS warmup_comments (
                    id           INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id      TEXT    NOT NULL UNIQUE,
                    subreddit    TEXT    NOT NULL,
                    comment_text TEXT    NOT NULL,
                    post_url     TEXT,
                    status       TEXT    DEFAULT 'pending',
                    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """))
    except Exception:
        pass

    # comment_leads table — commenters on our posts who qualify as prospects
    try:
        with _writer() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS comment_leads (
                    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
                    client_id            TEXT,
                    value_post_id        INTEGER,
                    subreddit            TEXT,
                    post_url             TEXT,
                    commenter            TEXT    NOT NULL,
                    comment_text         TEXT    NOT NULL,
                    comment_url          TEXT,
                    comment_score        INTEGER DEFAULT 0,
                    account_age_days     INTEGER DEFAULT 0,
                    karma                INTEGER DEFAULT 0,
                    qualification_score  INTEGER DEFAULT 0,
                    signal_match         TEXT,
                    suggested_reply      TEXT,
                    reply_status         TEXT    DEFAULT 'pending',
                    reply_posted_at      TEXT,
                    created_at           TEXT    NOT NULL DEFAULT (datetime('now'))
                )
            """))
    except Exception:
        pass


def create_value_post(subreddit: str, post_type: str, title: str, body: str,
                      topic: str = None, signals: list = None,
                      post_count: int = 0, client_id: str = None,
                      auto_generated: bool = False, source_signal: str = None,
                      platform: str = 'reddit', image_prompt: str = None) -> int | None:
    try:
        _ensure_value_posts_table()
        cid = client_id or CLIENT_ID
        with _writer() as conn:
            r = conn.execute(text("""
                INSERT INTO value_posts (client_id, subreddit, type, title, body, topic, signals,
                                        post_count, auto_generated, source_signal, platform, image_prompt)
                VALUES (:cid, :sub, :type, :title, :body, :topic, :signals, :pc, :ag, :ss, :plat, :ip)
            """), {
                "cid":     cid,
                "sub":     subreddit,
                "type":    post_type,
                "title":   title,
                "body":    body,
                "topic":   topic,
                "signals": json.dumps(signals or []),
                "pc":      post_count,
                "ag":      1 if auto_generated else 0,
                "ss":      source_signal,
                "plat":    platform,
                "ip":      image_prompt,
            })
            return r.lastrowid
    except Exception as e:
        print(f"[db] create_value_post error: {e}", file=sys.stderr)
        return None


def get_value_posts(client_id: str = None, subreddit: str = None, limit: int = 50) -> list:
    try:
        _ensure_value_posts_table()
        cid = client_id or CLIENT_ID
        with _reader() as conn:
            if subreddit:
                r = conn.execute(text("""
                    SELECT * FROM value_posts WHERE client_id=:cid AND subreddit=:sub
                    ORDER BY created_at DESC LIMIT :lim
                """), {"cid": cid, "sub": subreddit, "lim": limit})
            else:
                r = conn.execute(text("""
                    SELECT * FROM value_posts WHERE client_id=:cid
                    ORDER BY created_at DESC LIMIT :lim
                """), {"cid": cid, "lim": limit})
            return _rows(r)
    except Exception:
        return []


def get_value_posts_performance(client_id: str) -> list:
    """
    Return approved/posted value_posts with lead attribution from prospects.
    Joins on signal_phrase matching source_signal or topic.
    """
    try:
        _ensure_value_posts_table()
        with _reader() as conn:
            r = conn.execute(text("""
                SELECT
                    vp.id, vp.title, vp.subreddit, vp.type, vp.status, vp.topic,
                    vp.source_signal, vp.created_at, vp.posted_at, vp.auto_generated,
                    COUNT(DISTINCT p.id) AS lead_count,
                    COUNT(DISTINCT CASE WHEN p.status IN ('replied','meeting_booked','converted') THEN p.id END) AS converted_count
                FROM value_posts vp
                LEFT JOIN prospects p ON (
                    (p.signal_phrase IS NOT NULL AND p.signal_phrase = vp.source_signal)
                    OR (vp.topic IS NOT NULL AND p.signal_phrase = vp.topic)
                )
                WHERE vp.client_id = :cid
                  AND vp.status IN ('approved', 'posted')
                GROUP BY vp.id
                ORDER BY lead_count DESC, vp.created_at DESC
                LIMIT 50
            """), {"cid": client_id})
            return [dict(row._mapping) for row in r.fetchall()]
    except Exception:
        return []


def update_value_post(post_id: int, title: str = None, body: str = None,
                      status: str = None, upvotes: int = None, comments: int = None,
                      post_url: str = None, comments_checked_at: str = None,
                      commenters_found: int = None, scheduled_for: str = None,
                      perf_checked: int = None) -> bool:
    try:
        _ensure_value_posts_table()
        sets, params = [], {"id": post_id, "now": _now()}
        if title    is not None: sets.append("title=:title");     params["title"]    = title
        if body     is not None: sets.append("body=:body");        params["body"]     = body
        if post_url is not None: sets.append("post_url=:post_url"); params["post_url"] = post_url
        if status   is not None:
            sets.append("status=:status")
            params["status"] = status
            if status == 'posted':
                sets.append("posted_at=:now")
        if upvotes          is not None: sets.append("upvotes=:upvotes");                   params["upvotes"]           = upvotes
        if comments         is not None: sets.append("comments=:comments");                 params["comments"]          = comments
        if comments_checked_at is not None: sets.append("comments_checked_at=:cca");        params["cca"]               = comments_checked_at
        if commenters_found    is not None: sets.append("commenters_found=:cf");             params["cf"]                = commenters_found
        if scheduled_for       is not None: sets.append("scheduled_for=:sf");                params["sf"]                = scheduled_for
        if perf_checked        is not None: sets.append("perf_checked=:pc2");                params["pc2"]               = perf_checked
        if not sets:
            return False
        with _writer() as conn:
            conn.execute(text(f"UPDATE value_posts SET {', '.join(sets)} WHERE id=:id"), params)
        return True
    except Exception as e:
        print(f"[db] update_value_post error: {e}", file=sys.stderr)
        return False


def get_winning_opener_patterns(niche: str = None, limit: int = 3) -> list:
    """
    Return the first human-sent messages from conversations that received
    a prospect reply — i.e. openers that actually worked.
    Optionally filtered by niche_segment.
    Used by Hermes to calibrate its suggestions based on proven patterns.
    """
    try:
        with _reader() as conn:
            niche_clause = "AND p.niche_segment = :niche" if niche else ""
            rows = conn.execute(text(f"""
                SELECT cm.body, p.niche_segment, p.icp_score
                FROM conversation_messages cm
                JOIN conversations c ON c.id = cm.conversation_id
                JOIN prospects p ON p.id = c.prospect_id
                WHERE cm.sender = 'human'
                  AND cm.id = (
                      SELECT MIN(id) FROM conversation_messages
                      WHERE conversation_id = c.id AND sender = 'human'
                  )
                  AND EXISTS (
                      SELECT 1 FROM conversation_messages
                      WHERE conversation_id = c.id AND sender = 'prospect'
                  )
                  {niche_clause}
                ORDER BY RANDOM()
                LIMIT :lim
            """), {"niche": niche, "lim": limit}).fetchall()
        return [{"body": r[0], "niche": r[1], "icp_score": r[2]} for r in rows]
    except Exception as e:
        print(f"[db] get_winning_opener_patterns error: {e}", file=sys.stderr)
        return []


def get_post_outcome_intelligence(client_id: str = None, limit: int = 20) -> list:
    """
    Join value_posts → linked conversations → prospect replies → calls booked.
    Returns per-post outcome stats ranked by call conversion, then reply rate.
    Used by Hermes and the content generator to prioritise high-converting topics.
    """
    try:
        _ensure_value_posts_table()
        cid = client_id or CLIENT_ID
        with _reader() as conn:
            rows = conn.execute(text("""
                SELECT
                    vp.id,
                    vp.topic,
                    vp.title,
                    vp.signals,
                    vp.subreddit,
                    COALESCE(vp.commenters_found, 0) AS comments_pulled,
                    COUNT(DISTINCT c.id)   AS dms_initiated,
                    COUNT(DISTINCT cm.id)  AS replies_received,
                    COUNT(DISTINCT je.id)  AS calls_booked
                FROM value_posts vp
                LEFT JOIN conversations c
                    ON c.source = 'post_comment'
                    AND c.source_context LIKE '%"value_post_id": ' || vp.id || '%'
                LEFT JOIN conversation_messages cm
                    ON cm.conversation_id = c.id AND cm.sender = 'prospect'
                LEFT JOIN journey_events je
                    ON je.prospect_id = c.prospect_id
                    AND je.event LIKE '%Call booked%'
                WHERE vp.status = 'posted'
                  AND (vp.client_id = :cid OR vp.client_id IS NULL)
                GROUP BY vp.id
                ORDER BY calls_booked DESC, replies_received DESC, dms_initiated DESC
                LIMIT :lim
            """), {"cid": cid, "lim": limit}).fetchall()

        out = []
        for r in rows:
            signals = []
            try:
                raw = r[3]
                if raw:
                    signals = json.loads(raw) if isinstance(raw, str) else raw
            except Exception:
                pass
            out.append({
                "post_id":          r[0],
                "topic":            r[1] or "",
                "title":            r[2] or "",
                "signals":          signals,
                "subreddit":        r[4] or "",
                "comments_pulled":  r[5],
                "dms_initiated":    r[6],
                "replies_received": r[7],
                "calls_booked":     r[8],
                "reply_rate": round(r[7] / r[6] * 100) if r[6] > 0 else 0,
            })
        return out
    except Exception as e:
        print(f"[db] get_post_outcome_intelligence error: {e}", file=sys.stderr)
        return []


def get_value_post_performance(post_id: int) -> dict:
    """
    Return engagement funnel metrics for a single value post.
    Counts conversations, prospect replies, and calls booked that
    originated from comments on this post.
    """
    try:
        _ensure_value_posts_table()
        with _reader() as conn:
            # Base stats already on the post row
            vp = conn.execute(
                text("SELECT commenters_found, comments, upvotes, title FROM value_posts WHERE id=:id"),
                {"id": post_id},
            ).fetchone()
            if not vp:
                return {"comments_pulled": 0, "dms_initiated": 0, "replies_received": 0, "calls_booked": 0}

            commenters_found = vp[0] or 0
            upvotes          = vp[2] or 0

            # Conversations whose source_context links to this value_post_id
            # Works for both SQLite (json_extract) and LIKE fallback
            try:
                conv_rows = conn.execute(
                    text("""
                        SELECT id, prospect_id FROM conversations
                        WHERE source = 'post_comment'
                        AND (
                            source_context LIKE :like_pid
                        )
                    """),
                    {"like_pid": f'%"value_post_id": {post_id}%'},
                ).fetchall()
            except Exception:
                conv_rows = []

            conv_ids     = [r[0] for r in conv_rows]
            prospect_ids = [r[1] for r in conv_rows]
            dms_initiated = len(conv_ids)

            replies_received = 0
            if conv_ids:
                placeholders = ",".join(str(c) for c in conv_ids)
                rr = conn.execute(
                    text(f"""
                        SELECT COUNT(*) FROM conversation_messages
                        WHERE conversation_id IN ({placeholders})
                        AND sender = 'prospect'
                    """)
                ).fetchone()
                replies_received = rr[0] if rr else 0

            calls_booked = 0
            if prospect_ids:
                placeholders = ",".join(str(p) for p in prospect_ids)
                cb = conn.execute(
                    text(f"""
                        SELECT COUNT(*) FROM journey_events
                        WHERE prospect_id IN ({placeholders})
                        AND event LIKE '%Call booked%'
                    """)
                ).fetchone()
                calls_booked = cb[0] if cb else 0

        return {
            "comments_pulled":  commenters_found,
            "dms_initiated":    dms_initiated,
            "replies_received": replies_received,
            "calls_booked":     calls_booked,
            "upvotes":          upvotes,
        }
    except Exception as e:
        print(f"[db] get_value_post_performance error: {e}", file=sys.stderr)
        return {"comments_pulled": 0, "dms_initiated": 0, "replies_received": 0, "calls_booked": 0}


def update_conversation_sentiment(conversation_id: int, sentiment: dict) -> bool:
    """
    Merge a sentiment_shift dict into conversations.source_context.
    sentiment should be: { label, shift, intent }
    """
    try:
        with _writer() as conn:
            row = conn.execute(
                text("SELECT source_context FROM conversations WHERE id=:cid"),
                {"cid": conversation_id},
            ).fetchone()
            if not row:
                return False
            ctx = {}
            try:
                ctx = json.loads(row[0]) if row[0] else {}
            except Exception:
                pass
            ctx["sentiment_shift"] = sentiment
            conn.execute(
                text("UPDATE conversations SET source_context=:ctx WHERE id=:cid"),
                {"ctx": json.dumps(ctx), "cid": conversation_id},
            )
        return True
    except Exception as e:
        print(f"[db] update_conversation_sentiment error: {e}", file=sys.stderr)
        return False


# ── Discord channels ──────────────────────────────────────────────────────────

_DISCORD_CHANNELS_DDL = _ddl(
    """CREATE TABLE IF NOT EXISTS discord_channels (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        client_id       TEXT    NOT NULL DEFAULT 'ALT00',
        guild_id        TEXT    NOT NULL,
        guild_name      TEXT,
        channel_id      TEXT    NOT NULL,
        channel_name    TEXT,
        pod_slug        TEXT,
        last_message_id TEXT,
        enabled         INTEGER NOT NULL DEFAULT 1,
        added_at        TEXT    NOT NULL DEFAULT (datetime('now')),
        UNIQUE(client_id, channel_id)
    )""",
    """CREATE TABLE IF NOT EXISTS discord_channels (
        id              SERIAL  PRIMARY KEY,
        client_id       TEXT    NOT NULL DEFAULT 'ALT00',
        guild_id        TEXT    NOT NULL,
        guild_name      TEXT,
        channel_id      TEXT    NOT NULL,
        channel_name    TEXT,
        pod_slug        TEXT,
        last_message_id TEXT,
        enabled         INTEGER NOT NULL DEFAULT 1,
        added_at        TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(client_id, channel_id)
    )""",
)


def _ensure_discord_channels_table():
    try:
        with _writer() as conn:
            conn.execute(text(_DISCORD_CHANNELS_DDL))
    except Exception:
        pass


def get_discord_channels(client_id: str = None, enabled_only: bool = True) -> list:
    try:
        _ensure_discord_channels_table()
        cid = client_id or CLIENT_ID
        with _reader() as conn:
            clause = "AND enabled=1" if enabled_only else ""
            rows = conn.execute(
                text(f"SELECT * FROM discord_channels WHERE client_id=:cid {clause} ORDER BY added_at DESC"),
                {"cid": cid},
            ).fetchall()
        return _rows(rows)
    except Exception as e:
        print(f"[db] get_discord_channels error: {e}", file=sys.stderr)
        return []


def add_discord_channel(guild_id: str, channel_id: str, guild_name: str = None,
                        channel_name: str = None, pod_slug: str = None,
                        client_id: str = None) -> dict | None:
    try:
        _ensure_discord_channels_table()
        cid = client_id or CLIENT_ID
        with _writer() as conn:
            if _is_sqlite:
                conn.execute(text("""
                    INSERT OR REPLACE INTO discord_channels
                        (client_id, guild_id, guild_name, channel_id, channel_name, pod_slug, enabled)
                    VALUES (:cid, :gid, :gname, :chn, :chname, :pod, 1)
                """), {"cid": cid, "gid": guild_id, "gname": guild_name,
                       "chn": channel_id, "chname": channel_name, "pod": pod_slug})
            else:
                conn.execute(text("""
                    INSERT INTO discord_channels
                        (client_id, guild_id, guild_name, channel_id, channel_name, pod_slug, enabled)
                    VALUES (:cid, :gid, :gname, :chn, :chname, :pod, 1)
                    ON CONFLICT (client_id, channel_id) DO UPDATE SET
                        guild_name=EXCLUDED.guild_name, channel_name=EXCLUDED.channel_name,
                        pod_slug=EXCLUDED.pod_slug, enabled=1
                """), {"cid": cid, "gid": guild_id, "gname": guild_name,
                       "chn": channel_id, "chname": channel_name, "pod": pod_slug})
        return {"guild_id": guild_id, "channel_id": channel_id,
                "guild_name": guild_name, "channel_name": channel_name, "pod_slug": pod_slug}
    except Exception as e:
        print(f"[db] add_discord_channel error: {e}", file=sys.stderr)
        return None


def remove_discord_channel(channel_id: str, client_id: str = None) -> bool:
    try:
        _ensure_discord_channels_table()
        cid = client_id or CLIENT_ID
        with _writer() as conn:
            conn.execute(
                text("DELETE FROM discord_channels WHERE client_id=:cid AND channel_id=:ch"),
                {"cid": cid, "ch": channel_id},
            )
        return True
    except Exception as e:
        print(f"[db] remove_discord_channel error: {e}", file=sys.stderr)
        return False


def update_discord_last_id(channel_id: str, last_message_id: str, client_id: str = None) -> bool:
    try:
        _ensure_discord_channels_table()
        cid = client_id or CLIENT_ID
        with _writer() as conn:
            conn.execute(
                text("UPDATE discord_channels SET last_message_id=:lid WHERE client_id=:cid AND channel_id=:ch"),
                {"lid": last_message_id, "cid": cid, "ch": channel_id},
            )
        return True
    except Exception as e:
        print(f"[db] update_discord_last_id error: {e}", file=sys.stderr)
        return False


# ── Lead attribution ───────────────────────────────────────────────────────────

_LEAD_ATTRIBUTION_DDL = _ddl(
    """CREATE TABLE IF NOT EXISTS lead_attribution (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        lead_id          TEXT    NOT NULL UNIQUE,
        prospect_id      INTEGER,
        conversation_id  INTEGER,
        value_post_id    INTEGER,
        pod_slug         TEXT,
        link_clicked     INTEGER NOT NULL DEFAULT 0,
        clicked_at       TEXT,
        converted        INTEGER NOT NULL DEFAULT 0,
        converted_at     TEXT,
        internal_user_id TEXT,
        source_platform  TEXT    DEFAULT 'reddit',
        utm_params       TEXT,
        created_at       TEXT    NOT NULL DEFAULT (datetime('now'))
    )""",
    """CREATE TABLE IF NOT EXISTS lead_attribution (
        id               SERIAL  PRIMARY KEY,
        lead_id          TEXT    NOT NULL UNIQUE,
        prospect_id      INTEGER,
        conversation_id  INTEGER,
        value_post_id    INTEGER,
        pod_slug         TEXT,
        link_clicked     INTEGER NOT NULL DEFAULT 0,
        clicked_at       TIMESTAMP,
        converted        INTEGER NOT NULL DEFAULT 0,
        converted_at     TIMESTAMP,
        internal_user_id TEXT,
        source_platform  TEXT    DEFAULT 'reddit',
        utm_params       TEXT,
        created_at       TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""",
)


def _ensure_lead_attribution_table():
    try:
        with _writer() as conn:
            conn.execute(text(_LEAD_ATTRIBUTION_DDL))
    except Exception:
        pass


def create_lead_attribution(prospect_id: int = None, conversation_id: int = None,
                            value_post_id: int = None, pod_slug: str = None,
                            source_platform: str = 'reddit') -> str | None:
    """Create a new lead attribution record and return the unique lead_id."""
    import uuid
    try:
        _ensure_lead_attribution_table()
        lead_id = str(uuid.uuid4())[:12].replace('-', '')
        with _writer() as conn:
            conn.execute(text("""
                INSERT INTO lead_attribution
                    (lead_id, prospect_id, conversation_id, value_post_id, pod_slug, source_platform)
                VALUES (:lid, :pid, :cid, :vpid, :pod, :src)
            """), {"lid": lead_id, "pid": prospect_id, "cid": conversation_id,
                   "vpid": value_post_id, "pod": pod_slug, "src": source_platform})
        return lead_id
    except Exception as e:
        print(f"[db] create_lead_attribution error: {e}", file=sys.stderr)
        return None


def record_lead_click(lead_id: str) -> bool:
    """Record that the tracking link was clicked."""
    try:
        _ensure_lead_attribution_table()
        with _writer() as conn:
            conn.execute(
                text("UPDATE lead_attribution SET link_clicked=1, clicked_at=:now WHERE lead_id=:lid"),
                {"now": _now(), "lid": lead_id},
            )
        return True
    except Exception:
        return False


def record_lead_conversion(lead_id: str, internal_user_id: str) -> bool:
    """Mark a tracked lead as converted when the user signs up."""
    try:
        _ensure_lead_attribution_table()
        with _writer() as conn:
            conn.execute(
                text("""
                    UPDATE lead_attribution
                    SET converted=1, converted_at=:now, internal_user_id=:uid
                    WHERE lead_id=:lid
                """),
                {"now": _now(), "uid": internal_user_id, "lid": lead_id},
            )
            # Also update the linked prospect status
            row = conn.execute(
                text("SELECT prospect_id FROM lead_attribution WHERE lead_id=:lid"),
                {"lid": lead_id},
            ).fetchone()
            if row and row[0]:
                conn.execute(
                    text("UPDATE prospects SET status='converted' WHERE id=:pid"),
                    {"pid": row[0]},
                )
        return True
    except Exception as e:
        print(f"[db] record_lead_conversion error: {e}", file=sys.stderr)
        return False


def get_attribution_by_lead_id(lead_id: str) -> dict | None:
    try:
        _ensure_lead_attribution_table()
        with _reader() as conn:
            row = conn.execute(
                text("SELECT * FROM lead_attribution WHERE lead_id=:lid"),
                {"lid": lead_id},
            ).fetchone()
        return dict(row._mapping) if row else None
    except Exception:
        return None


def get_attribution_stats(client_id: str = None, pod_slug: str = None) -> dict:
    """Return high-level conversion stats for the attribution dashboard."""
    try:
        _ensure_lead_attribution_table()
        with _reader() as conn:
            clause = "WHERE 1=1"
            params = {}
            if pod_slug:
                clause += " AND pod_slug=:pod"
                params["pod"] = pod_slug

            r = conn.execute(text(f"""
                SELECT
                    COUNT(*) AS total_links,
                    SUM(link_clicked) AS clicks,
                    SUM(converted) AS conversions
                FROM lead_attribution {clause}
            """), params).fetchone()

        total     = r[0] or 0
        clicks    = r[1] or 0
        converted = r[2] or 0
        return {
            "total_links":   total,
            "clicks":        clicks,
            "conversions":   converted,
            "click_rate":    round(clicks / total * 100) if total > 0 else 0,
            "conv_rate":     round(converted / clicks * 100) if clicks > 0 else 0,
        }
    except Exception as e:
        print(f"[db] get_attribution_stats error: {e}", file=sys.stderr)
        return {"total_links": 0, "clicks": 0, "conversions": 0, "click_rate": 0, "conv_rate": 0}


# ── Reddit Top Posts ──────────────────────────────────────────────────────────

def save_top_post(client_id, subreddit, post_id, title, body,
                  score, upvote_ratio, comment_count, post_url, time_period, fetched_at):
    """Upsert a top Reddit post (insert or replace on post_id)."""
    try:
        cid = client_id or CLIENT_ID
        with _writer() as conn:
            # Delete existing record for this post_id so we refresh scores
            if post_id:
                conn.execute(
                    text("DELETE FROM reddit_top_posts WHERE post_id=:pid AND client_id=:cid"),
                    {"pid": post_id, "cid": cid},
                )
            conn.execute(text("""
                INSERT INTO reddit_top_posts
                    (client_id, subreddit, post_id, title, body, score, upvote_ratio,
                     comment_count, post_url, time_period, fetched_at)
                VALUES
                    (:cid, :sub, :pid, :title, :body, :score, :ratio,
                     :comments, :url, :period, :fetched)
            """), {
                "cid":      cid,
                "sub":      subreddit,
                "pid":      post_id,
                "title":    title,
                "body":     body,
                "score":    score,
                "ratio":    upvote_ratio,
                "comments": comment_count,
                "url":      post_url,
                "period":   time_period,
                "fetched":  fetched_at,
            })
    except Exception as e:
        print(f"[db] save_top_post error: {e}", file=sys.stderr)


def get_top_posts(subreddit: str = None, client_id: str = None,
                  period: str = "week", limit: int = 10) -> list:
    """Return top-performing posts sorted by score descending."""
    try:
        cid = client_id or CLIENT_ID
        params: dict = {"cid": cid, "limit": limit}
        where = "WHERE client_id = :cid"
        if subreddit:
            where += " AND LOWER(subreddit) = LOWER(:sub)"
            params["sub"] = subreddit
        if period:
            where += " AND time_period = :period"
            params["period"] = period

        with _reader() as conn:
            rows = conn.execute(text(f"""
                SELECT id, subreddit, post_id, title, body,
                       score, upvote_ratio, comment_count, post_url, fetched_at
                FROM reddit_top_posts
                {where}
                ORDER BY score DESC, comment_count DESC
                LIMIT :limit
            """), params).fetchall()

        return [dict(r._mapping) for r in rows]
    except Exception as e:
        print(f"[db] get_top_posts error: {e}", file=sys.stderr)
        return []


# ── Content Plans ─────────────────────────────────────────────────────────────

def save_content_plan(plan_json: str, source_data: str = None,
                      niche: str = None, client_id: str = None) -> int | None:
    try:
        cid = client_id or CLIENT_ID
        with _writer() as conn:
            r = conn.execute(text("""
                INSERT INTO content_plans (client_id, plan_json, source_data, niche)
                VALUES (:cid, :plan, :src, :niche)
            """), {"cid": cid, "plan": plan_json, "src": source_data, "niche": niche})
            return r.lastrowid
    except Exception as e:
        print(f"[db] save_content_plan error: {e}", file=sys.stderr)
        return None


def get_content_plans(client_id: str = None, limit: int = 5) -> list:
    try:
        cid = client_id or CLIENT_ID
        with _reader() as conn:
            rows = conn.execute(text("""
                SELECT id, plan_json, source_data, niche, created_at
                FROM content_plans
                WHERE client_id = :cid
                ORDER BY created_at DESC
                LIMIT :limit
            """), {"cid": cid, "limit": limit}).fetchall()

        result = []
        for r in rows:
            try:
                plan = json.loads(r[1])
            except Exception:
                plan = {}
            result.append({
                "id":         r[0],
                "plan":       plan,
                "niche":      r[3],
                "created_at": r[4],
            })
        return result
    except Exception as e:
        print(f"[db] get_content_plans error: {e}", file=sys.stderr)
        return []


def get_posted_value_posts(client_id: str = None) -> list:
    """All posts with status=posted, for performance tracking."""
    try:
        _ensure_value_posts_table()
        cid = client_id or CLIENT_ID
        with _reader() as conn:
            r = conn.execute(text("""
                SELECT id, title, subreddit, platform, post_url, posted_at,
                       upvotes, comments, commenters_found, source_signal,
                       perf_checked, comments_checked_at
                FROM value_posts
                WHERE client_id=:cid AND status='posted' AND post_url IS NOT NULL
                ORDER BY posted_at DESC
            """), {"cid": cid})
            return _rows(r)
    except Exception:
        return []


def get_scheduled_value_posts(client_id: str = None) -> list:
    """Posts approved and waiting for their scheduled_for window."""
    try:
        _ensure_value_posts_table()
        cid = client_id or CLIENT_ID
        with _reader() as conn:
            r = conn.execute(text("""
                SELECT * FROM value_posts
                WHERE client_id=:cid AND status='approved'
                  AND scheduled_for IS NOT NULL
                  AND scheduled_for <= datetime('now')
                ORDER BY scheduled_for ASC
            """), {"cid": cid})
            return _rows(r)
    except Exception:
        return []


def get_recent_posts_for_subreddit(client_id: str, subreddit: str, days: int = 14) -> list:
    """For duplicate guard — recent posts to the same subreddit."""
    try:
        _ensure_value_posts_table()
        with _reader() as conn:
            r = conn.execute(text("""
                SELECT title, body, topic, source_signal, created_at
                FROM value_posts
                WHERE client_id=:cid AND subreddit=:sub
                  AND created_at >= datetime('now', :since)
                  AND status NOT IN ('rejected')
                ORDER BY created_at DESC
            """), {"cid": client_id, "sub": subreddit, "since": f"-{days} days"})
            return _rows(r)
    except Exception:
        return []


def count_recent_posts_to_subreddit(client_id: str, subreddit: str, days: int = 7) -> int:
    """Count approved/posted value_posts to a subreddit in the last N days."""
    try:
        _ensure_value_posts_table()
        with _reader() as conn:
            result = conn.execute(text("""
                SELECT COUNT(*) FROM value_posts
                WHERE client_id=:cid AND subreddit=:sub
                  AND status IN ('approved', 'posted')
                  AND created_at >= datetime('now', :since)
            """), {"cid": client_id, "sub": subreddit, "since": f"-{days} days"})
            row = result.fetchone()
        return int(row[0]) if row else 0
    except Exception:
        return 0


def save_comment_lead(client_id: str, value_post_id: int, subreddit: str,
                      post_url: str, commenter: str, comment_text: str,
                      comment_url: str = None, comment_score: int = 0,
                      account_age_days: int = 0, karma: int = 0,
                      qualification_score: int = 0, signal_match: str = None,
                      suggested_reply: str = None) -> int | None:
    try:
        _ensure_value_posts_table()
        # Don't double-save same commenter on same post
        with _reader() as conn:
            exists = conn.execute(text("""
                SELECT id FROM comment_leads
                WHERE value_post_id=:pid AND commenter=:u LIMIT 1
            """), {"pid": value_post_id, "u": commenter}).fetchone()
        if exists:
            return None
        with _writer() as conn:
            r = conn.execute(text("""
                INSERT INTO comment_leads
                (client_id, value_post_id, subreddit, post_url, commenter,
                 comment_text, comment_url, comment_score, account_age_days,
                 karma, qualification_score, signal_match, suggested_reply)
                VALUES (:cid, :pid, :sub, :purl, :u, :ct, :curl, :cs, :age,
                        :karma, :qs, :sm, :sr)
            """), {
                "cid": client_id, "pid": value_post_id, "sub": subreddit,
                "purl": post_url, "u": commenter, "ct": comment_text,
                "curl": comment_url, "cs": comment_score, "age": account_age_days,
                "karma": karma, "qs": qualification_score, "sm": signal_match,
                "sr": suggested_reply,
            })
            return r.lastrowid
    except Exception as e:
        print(f"[db] save_comment_lead error: {e}", file=sys.stderr)
        return None


def get_comment_leads(client_id: str = None, value_post_id: int = None,
                      reply_status: str = None) -> list:
    try:
        _ensure_value_posts_table()
        cid = client_id or CLIENT_ID
        filters, params = ["client_id=:cid"], {"cid": cid}
        if value_post_id is not None:
            filters.append("value_post_id=:pid")
            params["pid"] = value_post_id
        if reply_status is not None:
            filters.append("reply_status=:rs")
            params["rs"] = reply_status
        where = " AND ".join(filters)
        with _reader() as conn:
            r = conn.execute(text(f"""
                SELECT * FROM comment_leads WHERE {where}
                ORDER BY qualification_score DESC, created_at DESC
                LIMIT 100
            """), params)
            return _rows(r)
    except Exception:
        return []


def update_comment_lead(lead_id: int, reply_status: str = None,
                        suggested_reply: str = None, reply_posted_at: str = None) -> bool:
    try:
        _ensure_value_posts_table()
        sets, params = [], {"id": lead_id}
        if reply_status     is not None: sets.append("reply_status=:rs");      params["rs"]  = reply_status
        if suggested_reply  is not None: sets.append("suggested_reply=:sr");   params["sr"]  = suggested_reply
        if reply_posted_at  is not None: sets.append("reply_posted_at=:rpa");  params["rpa"] = reply_posted_at
        if not sets:
            return False
        with _writer() as conn:
            conn.execute(text(f"UPDATE comment_leads SET {', '.join(sets)} WHERE id=:id"), params)
        return True
    except Exception as e:
        print(f"[db] update_comment_lead error: {e}", file=sys.stderr)
        return False


def get_content_results(client_id: str = None) -> dict:
    """Aggregate stats for the Results tab."""
    try:
        _ensure_value_posts_table()
        cid = client_id or CLIENT_ID
        with _reader() as conn:
            # Overall stats
            stats = conn.execute(text("""
                SELECT
                    COUNT(*) AS total_posted,
                    COALESCE(AVG(upvotes), 0) AS avg_upvotes,
                    COALESCE(AVG(comments), 0) AS avg_comments,
                    COALESCE(SUM(upvotes), 0) AS total_upvotes,
                    COALESCE(SUM(comments), 0) AS total_comments
                FROM value_posts
                WHERE client_id=:cid AND status='posted'
            """), {"cid": cid}).fetchone()

            # Best subreddits
            subs = conn.execute(text("""
                SELECT subreddit,
                       COUNT(*) AS post_count,
                       COALESCE(AVG(upvotes), 0) AS avg_upvotes,
                       COALESCE(SUM(upvotes), 0) AS total_upvotes
                FROM value_posts
                WHERE client_id=:cid AND status='posted'
                GROUP BY subreddit
                ORDER BY avg_upvotes DESC
                LIMIT 5
            """), {"cid": cid}).fetchall()

            # Best content types
            types = conn.execute(text("""
                SELECT type,
                       COUNT(*) AS post_count,
                       COALESCE(AVG(upvotes), 0) AS avg_upvotes
                FROM value_posts
                WHERE client_id=:cid AND status='posted'
                GROUP BY type
                ORDER BY avg_upvotes DESC
            """), {"cid": cid}).fetchall()

            # Recent posts with performance
            posts = conn.execute(text("""
                SELECT vp.id, vp.title, vp.subreddit, vp.type, vp.platform,
                       vp.upvotes, vp.comments, vp.posted_at, vp.post_url,
                       vp.source_signal,
                       COUNT(cl.id) AS lead_count
                FROM value_posts vp
                LEFT JOIN comment_leads cl ON cl.value_post_id = vp.id
                WHERE vp.client_id=:cid AND vp.status='posted'
                GROUP BY vp.id
                ORDER BY vp.posted_at DESC
                LIMIT 20
            """), {"cid": cid}).fetchall()

            # Total leads
            lead_total = conn.execute(text("""
                SELECT COUNT(*) FROM comment_leads WHERE client_id=:cid
            """), {"cid": cid}).fetchone()

        return {
            "total_posted":   stats[0] if stats else 0,
            "avg_upvotes":    round(stats[1], 1) if stats else 0,
            "avg_comments":   round(stats[2], 1) if stats else 0,
            "total_upvotes":  stats[3] if stats else 0,
            "total_comments": stats[4] if stats else 0,
            "total_leads":    lead_total[0] if lead_total else 0,
            "best_subreddits": [
                {"subreddit": r[0], "post_count": r[1],
                 "avg_upvotes": round(r[2], 1), "total_upvotes": r[3]}
                for r in (subs or [])
            ],
            "best_types": [
                {"type": r[0], "post_count": r[1], "avg_upvotes": round(r[2], 1)}
                for r in (types or [])
            ],
            "recent_posts": [
                {"id": r[0], "title": r[1], "subreddit": r[2], "type": r[3],
                 "platform": r[4], "upvotes": r[5] or 0, "comments": r[6] or 0,
                 "posted_at": r[7], "post_url": r[8], "source_signal": r[9],
                 "lead_count": r[10] or 0}
                for r in (posts or [])
            ],
        }
    except Exception as e:
        print(f"[db] get_content_results error: {e}", file=sys.stderr)
        return {
            "total_posted": 0, "avg_upvotes": 0, "avg_comments": 0,
            "total_upvotes": 0, "total_comments": 0, "total_leads": 0,
            "best_subreddits": [], "best_types": [], "recent_posts": [],
        }


if __name__ == "__main__":
    init_db()
    print(f"Database ready -- {'SQLite' if _is_sqlite else 'PostgreSQL'}")
    print(f"  Path/URL: {_DATABASE_URL}")
