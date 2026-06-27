"""
pods/options/bootstrap.py
Pre-flight validation for the Options Trading pod.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

POD_DIR  = os.path.dirname(os.path.abspath(__file__))
POD_SLUG = "options"

REQUIRED_ENV_VARS  = ["ANTHROPIC_API_KEY", "REDDIT_CLIENT_ID", "REDDIT_CLIENT_SECRET"]
REQUIRED_POD_FILES = ["identity.md", "soul.md", "tasks.json", "tools.json",
                      "user.md", "hunter.py", "heartbeat.py"]


def validate() -> dict:
    checks = []

    for var in REQUIRED_ENV_VARS:
        present = bool(os.environ.get(var))
        checks.append({"name": f"env:{var}", "ok": present,
                       "detail": "present" if present else f"MISSING — add {var} to .env"})

    for fname in REQUIRED_POD_FILES:
        path   = os.path.join(POD_DIR, fname)
        exists = os.path.isfile(path)
        checks.append({"name": f"file:{fname}", "ok": exists,
                       "detail": "present" if exists else f"MISSING — expected at {path}"})

    try:
        from database import init_db
        init_db()
        checks.append({"name": "database:connect", "ok": True, "detail": "connected"})
    except Exception as e:
        checks.append({"name": "database:connect", "ok": False, "detail": str(e)})

    try:
        from scrapers.niches import get_niche
        niche = get_niche(POD_SLUG)
        ok    = niche is not None
        checks.append({"name": f"niche:{POD_SLUG}", "ok": ok,
                       "detail": "loaded" if ok else f"'{POD_SLUG}' not found in registry"})
    except Exception as e:
        checks.append({"name": f"niche:{POD_SLUG}", "ok": False, "detail": str(e)})

    passed = all(c["ok"] for c in checks)
    return {"passed": passed, "checks": checks}


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    report = validate()
    print(f"\nBootstrap [{POD_SLUG}]: {'PASS' if report['passed'] else 'FAIL'}")
    for c in report["checks"]:
        print(f"  {'✓' if c['ok'] else '✗'} {c['name']}: {c['detail']}")
