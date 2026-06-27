"""
pods/_template/bootstrap.py
TEMPLATE — copy to your pod directory and fill in the blanks.

Run on pod startup. Validates the environment before any action.
If validation fails, pod does not start and the circuit breaker is tripped.

Usage:
  python bootstrap.py             # run standalone
  from bootstrap import validate  # called by heartbeat.run()
"""

import os
import sys

# Ensure outbound-hunter root is on sys.path when run directly
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

POD_DIR   = os.path.dirname(os.path.abspath(__file__))
POD_SLUG  = "REPLACE_ME"  # e.g. "financial-advisors"

REQUIRED_ENV_VARS = [
    "ANTHROPIC_API_KEY",
    "HUBSPOT_TOKEN",
    "APIFY_API_TOKEN",
    # Add any pod-specific env vars here
]

REQUIRED_POD_FILES = [
    "identity.md",
    "soul.md",
    "tasks.json",
    "tools.json",
    "user.md",
    "hunter.py",
    "heartbeat.py",
]


def validate() -> dict:
    """
    Run all pre-flight checks for this pod.

    Returns:
      {
        "passed": bool,                   # False = pod must not start
        "checks": [
          {"name": str, "ok": bool, "detail": str},
          ...
        ]
      }

    Checks:
      1. Required environment variables present
      2. Required pod files exist
      3. Database connectivity
      4. Niche module registered in scrapers.niches
      5. HubSpot API reachable (lightweight token ping)
    """
    checks = []

    # ── 1. Environment variables ──────────────────────────────────────────────
    for var in REQUIRED_ENV_VARS:
        present = bool(os.environ.get(var))
        checks.append({
            "name":   f"env:{var}",
            "ok":     present,
            "detail": "present" if present else f"MISSING — add {var} to .env",
        })

    # ── 2. Pod files ──────────────────────────────────────────────────────────
    for fname in REQUIRED_POD_FILES:
        path   = os.path.join(POD_DIR, fname)
        exists = os.path.isfile(path)
        checks.append({
            "name":   f"file:{fname}",
            "ok":     exists,
            "detail": "present" if exists else f"MISSING — expected at {path}",
        })

    # ── 3. Database ───────────────────────────────────────────────────────────
    try:
        from database import init_db
        init_db()
        checks.append({"name": "database:connect", "ok": True, "detail": "connected"})
    except Exception as e:
        checks.append({"name": "database:connect", "ok": False, "detail": str(e)})

    # ── 4. Niche module ───────────────────────────────────────────────────────
    try:
        from scrapers.niches import get_niche
        niche = get_niche(POD_SLUG)
        ok    = niche is not None
        checks.append({
            "name":   f"niche:{POD_SLUG}",
            "ok":     ok,
            "detail": "loaded" if ok else f"'{POD_SLUG}' not found in scrapers.niches registry",
        })
    except Exception as e:
        checks.append({"name": f"niche:{POD_SLUG}", "ok": False, "detail": str(e)})

    # ── 5. HubSpot API ───────────────────────────────────────────────────────
    try:
        import urllib.request as _ur
        token = os.environ.get("HUBSPOT_TOKEN", "")
        if token:
            req = _ur.Request(
                "https://api.hubapi.com/crm/v3/objects/contacts?limit=1",
                headers={"Authorization": f"Bearer {token}"},
            )
            with _ur.urlopen(req, timeout=10) as r:
                ok = r.status == 200
            checks.append({"name": "hubspot:api", "ok": ok, "detail": "connection verified"})
        else:
            checks.append({"name": "hubspot:api", "ok": False, "detail": "HUBSPOT_TOKEN not set"})
    except Exception as e:
        checks.append({"name": "hubspot:api", "ok": False, "detail": f"failed: {e}"})

    passed = all(c["ok"] for c in checks)
    return {"passed": passed, "checks": checks}


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    report = validate()
    print(f"\nBootstrap [{POD_SLUG}]: {'PASS' if report['passed'] else 'FAIL'}")
    for c in report["checks"]:
        icon = "✓" if c["ok"] else "✗"
        print(f"  {icon} {c['name']}: {c['detail']}")
