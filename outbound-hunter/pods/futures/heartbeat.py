"""
pods/futures/heartbeat.py
Scheduling and status reporting for the Futures Trading pod.
"""

import os
import sys
import json
from datetime import datetime, timezone

_ROOT    = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_POD_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in [_ROOT, _POD_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

POD_SLUG               = "futures"
MAX_CONSECUTIVE_ERRORS = 3

_circuit_open       = False
_consecutive_errors = 0
_last_run           = None
_last_status        = "not_run"
_last_errors        = []
_last_counts        = {"found": 0, "qualified": 0, "stored": 0}


def run(hunter_instance=None) -> dict:
    global _circuit_open, _consecutive_errors, _last_run, _last_status, _last_errors, _last_counts
    _last_errors = []

    if _circuit_open:
        print(f"[{POD_SLUG}] Circuit breaker OPEN — not running.")
        return status()

    from dotenv import load_dotenv
    load_dotenv()

    import bootstrap as _bs
    report = _bs.validate()
    if not report["passed"]:
        failed = [c for c in report["checks"] if not c["ok"]]
        _last_errors = [f"{c['name']}: {c['detail']}" for c in failed]
        _last_status = "error"
        _consecutive_errors += 1
        if _consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            _circuit_open = True
            print(f"[{POD_SLUG}] Circuit breaker OPEN after {_consecutive_errors} consecutive errors")
        return status()

    try:
        if hunter_instance is None:
            from database import start_scan_run
            run_id = start_scan_run()
            from hunter import FuturesHunter
            hunter = FuturesHunter(run_id=run_id)
        else:
            hunter = hunter_instance
            run_id = getattr(hunter, "run_id", None)

        raw = hunter.scan()

        from main import process_prospects
        from scrapers.niches import get_niche
        niche = get_niche(POD_SLUG)
        q, s, _routing = process_prospects(raw, POD_SLUG, run_id=run_id, niche_module=niche)

        _last_run           = datetime.now(timezone.utc).isoformat()
        _last_status        = "ok"
        _last_counts        = {"found": len(raw), "qualified": q, "stored": s}
        _consecutive_errors = 0

    except Exception as e:
        _last_errors = [f"{type(e).__name__}: {e}"]
        _last_status = "error"
        _consecutive_errors += 1
        if _consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            _circuit_open = True
            print(f"[{POD_SLUG}] Circuit breaker OPEN after {_consecutive_errors} consecutive errors")
        print(f"[{POD_SLUG}] Run failed: {e}")

    return status()


def status() -> dict:
    return {
        "pod":                 POD_SLUG,
        "last_run":            _last_run,
        "status":              _last_status,
        "prospects_found":     _last_counts.get("found", 0),
        "prospects_qualified": _last_counts.get("qualified", 0),
        "prospects_stored":    _last_counts.get("stored", 0),
        "errors":              _last_errors,
        "circuit_breaker":     "open" if _circuit_open else "closed",
    }


def reset_circuit():
    global _circuit_open, _consecutive_errors
    _circuit_open       = False
    _consecutive_errors = 0
    print(f"[{POD_SLUG}] Circuit breaker reset")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=f"AltusFlow pod: {POD_SLUG}")
    parser.add_argument("command", nargs="?", default="run",
                        choices=["run", "status", "validate", "reset"])
    args = parser.parse_args()

    if args.command == "run":
        result = run()
        print(json.dumps(result, indent=2))
    elif args.command == "status":
        print(json.dumps(status(), indent=2))
    elif args.command == "validate":
        import bootstrap as _bs
        r = _bs.validate()
        print(f"\nBootstrap [{POD_SLUG}]: {'PASS' if r['passed'] else 'FAIL'}")
        for c in r["checks"]:
            print(f"  {'✓' if c['ok'] else '✗'} {c['name']}: {c['detail']}")
    elif args.command == "reset":
        reset_circuit()
