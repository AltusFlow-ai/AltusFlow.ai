"""
auth.py
Flask-Login authentication for the AltusFlow Outbound Hunter.

Routes (registered as 'auth' blueprint):
  GET/POST /login   — login form
  GET      /logout  — clear session, redirect to /login

All other app routes are decorated with @login_required.
After login, current_user.tenant_slug is picked up by app.py's
before_request hook and written to database.set_tenant_slug() so
every DB query automatically hits the correct per-tenant database.
"""

import os
import base64
import hashlib

from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    logout_user,
    login_required,
    current_user,
)

login_manager = LoginManager()
login_manager.login_view            = "auth.login"
login_manager.login_message         = "Please log in to access the dashboard."
login_manager.login_message_category = "info"

auth_bp = Blueprint("auth", __name__)


class User(UserMixin):
    """
    Thin wrapper around the master DB user row consumed by Flask-Login.
    All per-tenant state (slug, plan, company name) is available on current_user.
    """
    def __init__(self, row):
        self.id           = str(row["id"])
        self.email        = row["email"]
        self.role         = row["role"]
        self.tenant_id    = row["tenant_id"]
        self.tenant_slug  = row["tenant_slug"]
        self.company_name = row["company_name"]
        self.plan         = row["plan"]

    def get_id(self):
        return self.id

    @property
    def is_admin(self):
        return self.role == "admin"


def _dev_row():
    """Build the NO_AUTH bypass user from env vars so it matches the real CLIENT_ID in the DB."""
    return {
        "id":           os.environ.get("CLIENT_ID", "dev-0"),
        "email":        os.environ.get("ADMIN_EMAIL", "dev@local"),
        "role":         "admin",
        "tenant_id":    0,
        "tenant_slug":  "",
        "company_name": os.environ.get("DEV_COMPANY_NAME", "AltusFlow"),
        "plan":         "pro",
    }


@login_manager.request_loader
def load_user_from_request(request):
    """When NO_AUTH=true, inject a dev user on every request — no session needed."""
    if os.environ.get("NO_AUTH", "false").lower() == "true":
        return User(_dev_row())
    return None


@login_manager.user_loader
def load_user(user_id):
    """Called by Flask-Login on every request to restore the session user."""
    from master_db import get_user_by_id
    row = get_user_by_id(user_id)
    return User(row) if row else None


# ── Routes ────────────────────────────────────────────────────────────────────

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    error = None
    if request.method == "POST":
        from master_db import verify_password
        email    = (request.form.get("email") or "").strip()
        password = request.form.get("password") or ""
        row      = verify_password(email, password)
        if row:
            user = User(row)
            login_user(user, remember=True)
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        error = "Invalid email or password."

    return render_template("login.html", error=error)


@auth_bp.route("/logout")
def logout():
    logout_user()
    resp = redirect(url_for("auth.login"))
    resp.delete_cookie("remember_token")
    resp.delete_cookie("session")
    return resp


# ── Token encryption (Fernet symmetric) ──────────────────────────────────────
# Used to store third-party API tokens (HubSpot, Meta, Apify, Calendly) in the
# database without exposing them in plaintext. The key is derived from SECRET_KEY
# via SHA-256 so any arbitrary string works as the env var.

def _get_fernet():
    from cryptography.fernet import Fernet
    raw = os.environ.get("SECRET_KEY", "altusflow-default-key-CHANGE-IN-PRODUCTION")
    derived = base64.urlsafe_b64encode(hashlib.sha256(raw.encode()).digest())
    return Fernet(derived)


def encrypt_token(token: str) -> str | None:
    """Encrypt a plaintext API token for database storage."""
    if not token:
        return None
    return _get_fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str | None:
    """Decrypt a Fernet-encrypted token retrieved from the database."""
    if not encrypted:
        return None
    try:
        return _get_fernet().decrypt(encrypted.encode()).decode()
    except Exception:
        return None
