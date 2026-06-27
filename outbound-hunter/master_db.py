"""
master_db.py
Master database — tenants, users, and per-tenant configuration.
Stored in master.db, completely separate from per-tenant outbound_hunter.db files.

This is the source of truth for:
  - Which companies are clients (tenants)
  - Who has login access (users)
  - Per-tenant API keys and settings (tenant_config)

One master.db per deployment. Many per-tenant DBs inside tenants/{slug}/.
"""

import os
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

_MASTER_DB_FILE = os.environ.get("MASTER_DB_FILE", "master.db")
_master_engine  = None


def _get_master_engine():
    global _master_engine
    if _master_engine is None:
        _master_engine = create_engine(
            f"sqlite:///{_MASTER_DB_FILE}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return _master_engine


def _now():
    return datetime.now(timezone.utc).isoformat()


# ── Schema ────────────────────────────────────────────────────────────────────

def init_master_db():
    """Create all master DB tables. Safe to call on every app startup."""
    with _get_master_engine().begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tenants (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                slug         TEXT    NOT NULL UNIQUE,
                company_name TEXT    NOT NULL,
                plan         TEXT    NOT NULL DEFAULT 'starter',
                is_active    INTEGER NOT NULL DEFAULT 1,
                created_at   TEXT    DEFAULT (datetime('now'))
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id     INTEGER NOT NULL REFERENCES tenants(id),
                email         TEXT    NOT NULL UNIQUE,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL DEFAULT 'admin',
                created_at    TEXT    DEFAULT (datetime('now')),
                last_login_at TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tenant_config (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id INTEGER NOT NULL REFERENCES tenants(id),
                key       TEXT    NOT NULL,
                value     TEXT,
                UNIQUE(tenant_id, key)
            )
        """))


# ── Tenants ───────────────────────────────────────────────────────────────────

def create_tenant(slug, company_name, plan="starter"):
    """Insert a new tenant row. Returns the new tenant id."""
    with _get_master_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO tenants (slug, company_name, plan, created_at)
            VALUES (:slug, :name, :plan, :now)
        """), {"slug": slug, "name": company_name, "plan": plan, "now": _now()})
        return conn.execute(
            text("SELECT id FROM tenants WHERE slug=:s"), {"s": slug}
        ).fetchone()[0]


def get_tenant_by_slug(slug):
    with _get_master_engine().connect() as conn:
        r = conn.execute(text("SELECT * FROM tenants WHERE slug=:s"), {"s": slug}).fetchone()
        return dict(r._mapping) if r else None


def get_active_tenants():
    """Return all tenants with is_active=1, ordered by slug."""
    with _get_master_engine().connect() as conn:
        r = conn.execute(text("SELECT * FROM tenants WHERE is_active=1 ORDER BY slug"))
        return [dict(row._mapping) for row in r.fetchall()]


def set_tenant_active(slug, active):
    with _get_master_engine().begin() as conn:
        conn.execute(
            text("UPDATE tenants SET is_active=:a WHERE slug=:s"),
            {"a": 1 if active else 0, "s": slug},
        )


# ── Users ─────────────────────────────────────────────────────────────────────

def create_user(tenant_id, email, password, role="admin"):
    """Insert a user record with a hashed password."""
    pw_hash = generate_password_hash(password)
    with _get_master_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO users (tenant_id, email, password_hash, role, created_at)
            VALUES (:tid, :email, :pw, :role, :now)
        """), {
            "tid":   tenant_id,
            "email": email.lower().strip(),
            "pw":    pw_hash,
            "role":  role,
            "now":   _now(),
        })


def get_user_by_id(user_id):
    with _get_master_engine().connect() as conn:
        r = conn.execute(text("""
            SELECT u.*, t.slug AS tenant_slug, t.company_name, t.plan,
                   t.is_active AS tenant_active
            FROM users u JOIN tenants t ON u.tenant_id = t.id
            WHERE u.id=:id
        """), {"id": int(user_id)}).fetchone()
        return dict(r._mapping) if r else None


def get_user_by_email(email):
    with _get_master_engine().connect() as conn:
        r = conn.execute(text("""
            SELECT u.*, t.slug AS tenant_slug, t.company_name, t.plan,
                   t.is_active AS tenant_active
            FROM users u JOIN tenants t ON u.tenant_id = t.id
            WHERE u.email=:e
        """), {"e": email.lower().strip()}).fetchone()
        return dict(r._mapping) if r else None


def verify_password(email, password):
    """
    Check credentials. Returns the user row dict on success, None on failure.
    Also rejects login if the tenant is deactivated.
    """
    user = get_user_by_email(email)
    if not user or not user.get("tenant_active"):
        return None
    if check_password_hash(user["password_hash"], password):
        _update_last_login(user["id"])
        return user
    return None


def _update_last_login(user_id):
    with _get_master_engine().begin() as conn:
        conn.execute(
            text("UPDATE users SET last_login_at=:t WHERE id=:id"),
            {"t": _now(), "id": user_id},
        )


def get_tenant_users(tenant_id):
    with _get_master_engine().connect() as conn:
        r = conn.execute(
            text("SELECT id, email, role, created_at, last_login_at FROM users WHERE tenant_id=:tid ORDER BY created_at"),
            {"tid": tenant_id},
        )
        return [dict(row._mapping) for row in r.fetchall()]


# ── Tenant config ─────────────────────────────────────────────────────────────

def set_tenant_config(tenant_id, key, value):
    """Upsert a config key for a tenant (API keys, feature flags, etc.)."""
    with _get_master_engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO tenant_config (tenant_id, key, value)
            VALUES (:tid, :k, :v)
            ON CONFLICT(tenant_id, key) DO UPDATE SET value=EXCLUDED.value
        """), {"tid": tenant_id, "k": key, "v": str(value) if value is not None else None})


def get_tenant_config(tenant_id, key, default=None):
    with _get_master_engine().connect() as conn:
        r = conn.execute(
            text("SELECT value FROM tenant_config WHERE tenant_id=:tid AND key=:k"),
            {"tid": tenant_id, "k": key},
        ).fetchone()
        return r[0] if r else default


def get_all_tenant_config(tenant_id):
    """Return {key: value} dict of all config entries for a tenant."""
    with _get_master_engine().connect() as conn:
        r = conn.execute(
            text("SELECT key, value FROM tenant_config WHERE tenant_id=:tid"),
            {"tid": tenant_id},
        )
        return {row[0]: row[1] for row in r.fetchall()}


if __name__ == "__main__":
    init_master_db()
    print(f"Master DB ready at {_MASTER_DB_FILE}")
