"""
orchestrator.py
Master controller for the AltusFlow pod factory.

Discovers all pods in /pods/ (skips /pods/_template/), schedules them via
APScheduler CronTrigger (from each pod's tasks.json), enforces circuit breakers,
high-volume guards, and the uniform data contract.

Never touches business logic — that lives in the pods.

Startup:
    from orchestrator import Orchestrator
    orch = Orchestrator()
    orch.discover_pods()
    orch.start_scheduler()
    orch.run_all_now()

Or run standalone:
    python orchestrator.py

USE_POD_ORCHESTRATOR env var (default false):
    When false, orchestrator.py can be imported and used but app.py's scheduler.py
    still manages the daily pipeline. Set true to switch scheduling to pod mode.
"""

import os
import sys
import json
import time
import signal
import logging
import threading
import importlib.util
from datetime import datetime, timezone

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────────

_REQUIRED_POD_FILES = [
    "identity.md", "soul.md", "tasks.json", "tools.json",
    "user.md", "hunter.py", "heartbeat.py",
]

_DEFAULT_MAX_APPROVALS    = 50
_DEFAULT_CIRCUIT_THRESHOLD = 3

# Canonical keys every pod report must include (filled with defaults if absent)
_CONTRACT_DEFAULTS = {
    "run_id":                             None,
    "started_at":                         None,
    "completed_at":                       None,
    "duration_seconds":                   0,
    "status":                             "unknown",
    "platforms_scanned":                  [],
    "prospects_found":                    0,
    "prospects_qualified":                0,
    "prospects_auto_approved":            0,
    "prospects_pending_review":           0,
    "prospects_skipped_dnc":              0,
    "prospects_skipped_cooldown":         0,
    "prospects_skipped_insufficient_intel": 0,
    "hubspot_pushes_succeeded":           0,
    "hubspot_pushes_failed":              0,
    "meta_pushes_succeeded":              0,
    "errors":                             [],
    "circuit_breaker":                    "closed",
    "next_run":                           None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Orchestrator ───────────────────────────────────────────────────────────────

class Orchestrator:
    """
    Manages all registered pods: discovery, scheduling, circuit breaking,
    data contract enforcement, and graceful shutdown.
    """

    def __init__(self):
        self._pods       = {}           # {slug: meta_dict}
        self._locks      = {}           # {slug: threading.Lock}
        self._running    = {}           # {slug: bool}
        self._scheduler  = None
        self._shutdown_event = threading.Event()

    # ── Pod discovery ──────────────────────────────────────────────────────────

    def discover_pods(self) -> int:
        """
        Scan /pods/ directory and register every valid pod.
        Skips any directory whose name starts with '_' (template, pycache, etc.).
        Returns count of pods registered.
        """
        pods_dir = os.path.join(_ROOT, "pods")
        if not os.path.isdir(pods_dir):
            logger.error("Pods directory not found: %s", pods_dir)
            return 0

        count = 0
        for name in sorted(os.listdir(pods_dir)):
            pod_dir = os.path.join(pods_dir, name)
            if not os.path.isdir(pod_dir):
                continue
            if name.startswith("_"):
                continue  # skip _template, __pycache__, etc.

            # ── Validate required files ─────────────────────────────────────
            missing = [f for f in _REQUIRED_POD_FILES
                       if not os.path.isfile(os.path.join(pod_dir, f))]
            if missing:
                logger.warning("[%s] Skipping — missing files: %s", name, missing)
                self._fire_alert({
                    "alert": "pod_validation_failed",
                    "pod": name,
                    "missing_files": missing,
                })
                continue

            # ── Load config ─────────────────────────────────────────────────
            try:
                tasks_cfg = self._load_json(os.path.join(pod_dir, "tasks.json"))
                tools_cfg = self._load_json(os.path.join(pod_dir, "tools.json"))
            except Exception as e:
                logger.warning("[%s] Skipping — config load failed: %s", name, e)
                continue

            # Extract scheduling + limits from tasks.json
            daily_task      = next((t for t in tasks_cfg.get("tasks", [])
                                    if t.get("id") == "daily_scan"), {})
            schedule        = daily_task.get("schedule", "0 8 * * 1-5")
            circuit_thresh  = daily_task.get("circuit_breaker_threshold", _DEFAULT_CIRCUIT_THRESHOLD)
            global_limits   = tasks_cfg.get("global_limits", {})
            max_approvals   = global_limits.get("max_prospects_per_run", _DEFAULT_MAX_APPROVALS)
            pod_label       = tasks_cfg.get("label") or tools_cfg.get("pod_slug") or name

            # ── Load heartbeat module via importlib (hyphen-safe) ────────────
            heartbeat_mod = self._load_module(
                f"pod_{name.replace('-', '_')}_heartbeat",
                os.path.join(pod_dir, "heartbeat.py"),
                pod_dir,
            )
            if heartbeat_mod is None:
                logger.warning("[%s] Skipping — heartbeat.py could not be loaded", name)
                continue

            # ── Register ────────────────────────────────────────────────────
            self._pods[name] = {
                "slug":                  name,
                "label":                 pod_label,
                "pod_dir":               pod_dir,
                "heartbeat_module":      heartbeat_mod,
                "schedule":              schedule,
                "max_approvals_per_run": max_approvals,
                "circuit_threshold":     circuit_thresh,
                "tasks_config":          tasks_cfg,
                "tools_config":          tools_cfg,
            }
            self._locks[name]   = threading.Lock()
            self._running[name] = False

            try:
                from database import upsert_pod_registry
                upsert_pod_registry(name, pod_label, is_active=True)
            except Exception as e:
                logger.warning("[%s] DB registry update failed: %s", name, e)

            logger.info("[%s] Discovered — label: %s, schedule: %s", name, pod_label, schedule)
            count += 1

        logger.info("Pod discovery complete: %d pod(s) registered.", count)
        return count

    # ── Scheduler ─────────────────────────────────────────────────────────────

    def start_scheduler(self):
        """
        Create one APScheduler CronTrigger job per pod using the schedule
        from that pod's tasks.json. Pods run independently.
        """
        if self._scheduler and self._scheduler.running:
            logger.info("Scheduler already running — start_scheduler() is a no-op.")
            return

        self._scheduler = BackgroundScheduler(daemon=True)

        for slug, meta in self._pods.items():
            cron_expr = meta.get("schedule", "0 8 * * 1-5")
            parts     = cron_expr.split()
            if len(parts) == 5:
                minute, hour, day, month, day_of_week = parts
            else:
                minute, hour, day, month, day_of_week = "0", "8", "*", "*", "1-5"
                logger.warning("[%s] Invalid cron '%s' — defaulting to 08:00 weekdays", slug, cron_expr)

            self._scheduler.add_job(
                self._make_pod_runner(slug),
                trigger=CronTrigger(
                    minute=minute, hour=hour,
                    day=day, month=month, day_of_week=day_of_week,
                ),
                id=f"pod_{slug.replace('-', '_')}",
                name=f"Pod: {slug}",
                replace_existing=True,
                misfire_grace_time=300,
                coalesce=True,
            )
            logger.info("[%s] Scheduled — cron: %s", slug, cron_expr)

        self._scheduler.start()
        logger.info("Orchestrator scheduler started with %d pod job(s).", len(self._pods))

    def _make_pod_runner(self, slug: str):
        """Return a zero-argument callable that runs a named pod."""
        def _runner():
            self.run_pod(slug)
        _runner.__name__ = f"run_{slug.replace('-', '_')}"
        return _runner

    def run_all_now(self):
        """
        Fire all pods immediately in separate threads.
        Used for the first-run-on-startup behaviour.
        """
        logger.info("run_all_now() — launching %d pod(s).", len(self._pods))
        threads = []
        for slug in self._pods:
            t = threading.Thread(
                target=self.run_pod,
                args=(slug,),
                name=f"pod_immediate_{slug}",
                daemon=True,
            )
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

    def run_pod_now(self, slug: str) -> dict:
        """
        Force-run a single pod immediately in a background thread.
        Returns immediately — result is logged to pod_status.
        """
        if slug not in self._pods:
            return {"ok": False, "error": f"Pod '{slug}' not found"}
        t = threading.Thread(
            target=self.run_pod, args=(slug,),
            name=f"pod_force_{slug}", daemon=True,
        )
        t.start()
        return {"ok": True, "message": f"Pod '{slug}' run started in background."}

    # ── Core run cycle ────────────────────────────────────────────────────────

    def run_pod(self, pod_slug: str) -> dict:
        """
        Run one full pod cycle. Called by scheduler trigger, run_all_now(), or force run.
          1. Concurrent-run guard
          2. Circuit breaker check
          3. Invoke heartbeat.run()
          4. Enforce data contract
          5. High-volume guard
          6. Update error counter / circuit breaker
          7. Log to pod_status
        """
        meta = self._pods.get(pod_slug)
        if not meta:
            return {"status": "error", "pod": pod_slug, "errors": [f"Pod not registered"]}

        lock = self._locks.get(pod_slug)
        if lock and not lock.acquire(blocking=False):
            logger.info("[%s] Already running — skipping concurrent trigger", pod_slug)
            return {"status": "skipped", "pod": pod_slug, "errors": ["concurrent run skipped"]}

        try:
            self._running[pod_slug] = True

            # ── Circuit breaker ────────────────────────────────────────────
            cb_open = self._is_circuit_open(pod_slug)
            if cb_open:
                logger.info("[%s] Circuit breaker OPEN — run skipped", pod_slug)
                return {**_CONTRACT_DEFAULTS, "pod": pod_slug, "status": "circuit_open",
                        "circuit_breaker": "open"}

            started_at = _now_iso()
            t_start    = time.time()

            # ── Run heartbeat ──────────────────────────────────────────────
            try:
                heartbeat_mod = meta["heartbeat_module"]
                raw_report    = heartbeat_mod.run()
            except Exception as e:
                raw_report = {"status": "error", "errors": [f"{type(e).__name__}: {e}"]}
                logger.exception("[%s] Heartbeat raised: %s", pod_slug, e)

            # ── Data contract ──────────────────────────────────────────────
            report = self._enforce_data_contract(raw_report, pod_slug)
            if "pod" not in report:
                report["pod"] = pod_slug
            report["started_at"]       = report.get("started_at") or started_at
            report["completed_at"]     = _now_iso()
            report["duration_seconds"] = int(time.time() - t_start)

            # ── Next-run time from scheduler ───────────────────────────────
            report["next_run"] = self._get_next_run_time(pod_slug)

            # ── High-volume guard ──────────────────────────────────────────
            auto_approved = report.get("prospects_auto_approved", 0)
            max_approvals = meta.get("max_approvals_per_run", _DEFAULT_MAX_APPROVALS)
            if auto_approved > max_approvals:
                self._trip_high_volume(pod_slug, auto_approved,
                                       run_id=report.get("run_id"))
                report["status"]          = "paused_high_volume"
                report["circuit_breaker"] = "open"

            # ── Error tracking ─────────────────────────────────────────────
            if report.get("status") in ("ok", "partial"):
                self._reset_pod_errors(pod_slug)
                report["circuit_breaker"] = "closed"
            elif report.get("status") not in ("skipped", "circuit_open"):
                self._increment_pod_errors(
                    pod_slug, report.get("errors", []),
                    meta.get("circuit_threshold", _DEFAULT_CIRCUIT_THRESHOLD),
                )

            # ── Persist ────────────────────────────────────────────────────
            try:
                from database import log_pod_run
                log_pod_run(pod_slug, report)
            except Exception as e:
                logger.warning("[%s] log_pod_run failed: %s", pod_slug, e)

            logger.info(
                "[%s] Run complete — status: %s, found: %d, qualified: %d",
                pod_slug, report.get("status"), report.get("prospects_found", 0),
                report.get("prospects_qualified", 0),
            )
            return report

        finally:
            self._running[pod_slug] = False
            if lock:
                try:
                    lock.release()
                except RuntimeError:
                    pass

    # ── Data contract enforcement ─────────────────────────────────────────────

    def _enforce_data_contract(self, report, pod_slug: str) -> dict:
        """
        Ensure the report from a pod heartbeat conforms to the data contract.
        Missing keys get their default value. Extra keys are preserved.
        Never lets a malformed report crash the orchestrator.
        """
        if not isinstance(report, dict):
            logger.warning("[%s] Heartbeat returned non-dict: %r — normalising", pod_slug, type(report))
            report = {"status": "error", "errors": [f"Non-dict return: {type(report).__name__}"]}

        normalised = dict(_CONTRACT_DEFAULTS)
        normalised.update(report)

        # Coerce types for critical int fields
        for key in ("prospects_found", "prospects_qualified", "prospects_auto_approved",
                    "prospects_pending_review", "prospects_skipped_dnc",
                    "prospects_skipped_cooldown", "prospects_skipped_insufficient_intel",
                    "hubspot_pushes_succeeded", "hubspot_pushes_failed",
                    "meta_pushes_succeeded", "duration_seconds"):
            try:
                normalised[key] = int(float(normalised.get(key) or 0))
            except (TypeError, ValueError):
                normalised[key] = 0

        if not isinstance(normalised.get("errors"), list):
            normalised["errors"] = [str(normalised["errors"])] if normalised.get("errors") else []

        if not isinstance(normalised.get("platforms_scanned"), list):
            normalised["platforms_scanned"] = []

        if normalised.get("circuit_breaker") not in ("open", "closed"):
            normalised["circuit_breaker"] = "closed"

        return normalised

    # ── Circuit breaker helpers ───────────────────────────────────────────────

    def _is_circuit_open(self, pod_slug: str) -> bool:
        try:
            from database import get_pod_registry
            row = get_pod_registry(pod_slug)
            if row:
                return bool(row.get("circuit_breaker_open") or row.get("is_paused"))
        except Exception:
            pass
        return False

    def _increment_pod_errors(self, pod_slug: str, errors: list, threshold: int):
        try:
            from database import increment_pod_consecutive_errors, set_pod_circuit_breaker
            count = increment_pod_consecutive_errors(pod_slug)
            if count >= threshold:
                set_pod_circuit_breaker(pod_slug, open=True)
                self._fire_circuit_breaker_alert(pod_slug, count, errors)
                logger.critical("[%s] Circuit breaker TRIPPED after %d errors", pod_slug, count)
        except Exception as e:
            logger.warning("[%s] Error tracking failed: %s", pod_slug, e)

    def _reset_pod_errors(self, pod_slug: str):
        try:
            from database import reset_pod_consecutive_errors
            reset_pod_consecutive_errors(pod_slug)
        except Exception:
            pass

    def _trip_high_volume(self, pod_slug: str, count: int, run_id=None):
        """Pause pod immediately due to high-volume outbound attempt."""
        try:
            from database import set_pod_circuit_breaker
            set_pod_circuit_breaker(pod_slug, open=True)
        except Exception as e:
            logger.warning("[%s] Could not set circuit breaker: %s", pod_slug, e)

        try:
            from error_logger import log_pipeline_error, CRITICAL
            log_pipeline_error(
                run_id, "high_volume_guard",
                f"[{pod_slug}] HIGH-VOLUME GUARD: {count} auto_approvals in one run "
                f"(limit: {_DEFAULT_MAX_APPROVALS}). Pod paused — manual reset required.",
                CRITICAL,
            )
        except Exception:
            pass

        self._fire_alert({
            "alert":              "high_volume_guard_tripped",
            "pod":                pod_slug,
            "auto_approvals":     count,
            "limit":              _DEFAULT_MAX_APPROVALS,
            "action":             "pod paused — manual reset required",
            "reset_url":          f"/admin/pods/{pod_slug}/reset",
        })
        logger.critical("[%s] High-volume guard TRIPPED — %d approvals, pod paused", pod_slug, count)

    def _fire_circuit_breaker_alert(self, pod_slug: str, count: int, errors: list):
        try:
            from database import get_pod_registry
            row = get_pod_registry(pod_slug) or {}
        except Exception:
            row = {}

        self._fire_alert({
            "alert":             "circuit_breaker_tripped",
            "pod":               pod_slug,
            "consecutive_errors": count,
            "last_error":        errors[-1] if errors else "unknown",
            "action":            "pod paused — manual reset required",
            "reset_url":         f"/admin/pods/{pod_slug}/reset",
        })

        try:
            from error_logger import log_pipeline_error, CRITICAL
            log_pipeline_error(
                None, "circuit_breaker",
                f"[{pod_slug}] Circuit breaker tripped after {count} consecutive errors. "
                f"Last error: {errors[-1] if errors else 'unknown'}",
                CRITICAL,
                suggested_fix=f"Investigate errors, fix root cause, then POST /admin/pods/{pod_slug}/reset",
            )
        except Exception:
            pass

    def _fire_alert(self, payload: dict):
        """POST alert payload to ALERT_WEBHOOK_URL if configured."""
        webhook_url = os.environ.get("ALERT_WEBHOOK_URL", "")
        if not webhook_url:
            return
        import urllib.request as _ur
        try:
            body = json.dumps(payload).encode()
            req  = _ur.Request(
                webhook_url,
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            _ur.urlopen(req, timeout=5)
        except Exception:
            pass

    # ── Scheduler helpers ─────────────────────────────────────────────────────

    def _get_next_run_time(self, pod_slug: str):
        """Return next scheduled run time as ISO string, or None."""
        if not self._scheduler:
            return None
        job_id = f"pod_{pod_slug.replace('-', '_')}"
        try:
            job = self._scheduler.get_job(job_id)
            if job and job.next_run_time:
                return job.next_run_time.isoformat()
        except Exception:
            pass
        return None

    def get_status(self) -> dict:
        """Return a summary of all pods for the admin UI."""
        pods_status = []
        for slug, meta in self._pods.items():
            pods_status.append({
                "slug":         slug,
                "label":        meta.get("label", slug),
                "running":      self._running.get(slug, False),
                "circuit_open": self._is_circuit_open(slug),
                "next_run":     self._get_next_run_time(slug),
                "schedule":     meta.get("schedule"),
            })
        return {
            "scheduler_alive": bool(self._scheduler and self._scheduler.running),
            "pod_count":       len(self._pods),
            "pods":            pods_status,
        }

    # ── Health check ──────────────────────────────────────────────────────────

    def health_check(self):
        """
        Called periodically from the main loop.
        Logs any pods that are in error state but have not had their circuit tripped.
        """
        for slug in self._pods:
            if self._is_circuit_open(slug):
                logger.warning("[%s] Health check: circuit breaker is OPEN", slug)

    # ── Graceful shutdown ─────────────────────────────────────────────────────

    def shutdown(self):
        """
        Graceful shutdown: stop accepting new runs, wait for in-flight runs to finish,
        log the shutdown event.
        """
        logger.info("Orchestrator shutdown initiated...")

        in_flight = [slug for slug, running in self._running.items() if running]
        if in_flight:
            logger.info("Waiting for in-flight pods: %s", in_flight)
            deadline = time.time() + 120  # max 2 minutes
            while time.time() < deadline:
                still_running = [s for s in in_flight if self._running.get(s)]
                if not still_running:
                    break
                time.sleep(2)
            still_running = [s for s in in_flight if self._running.get(s)]
            if still_running:
                logger.warning("Shutdown timed out — pods still running: %s", still_running)
                # Mark incomplete runs as interrupted
                try:
                    from database import log_pod_run
                    for slug in still_running:
                        log_pod_run(slug, {
                            **_CONTRACT_DEFAULTS,
                            "pod":    slug,
                            "status": "interrupted",
                            "errors": ["Process shut down while run was in progress"],
                        })
                except Exception:
                    pass

        if self._scheduler and self._scheduler.running:
            self._scheduler.shutdown(wait=False)

        logger.info("Orchestrator shutdown complete.")
        self._shutdown_event.set()

    # ── Admin operations ──────────────────────────────────────────────────────

    def pause_pod(self, pod_slug: str, reason: str = "Paused via admin UI"):
        from database import set_pod_paused
        set_pod_paused(pod_slug, True, reason)
        logger.info("[%s] Paused: %s", pod_slug, reason)

    def resume_pod(self, pod_slug: str):
        from database import set_pod_paused
        set_pod_paused(pod_slug, False)
        logger.info("[%s] Resumed.", pod_slug)

    def reset_pod(self, pod_slug: str):
        """Reset circuit breaker and resume. Operator must confirm root cause is fixed."""
        from database import set_pod_circuit_breaker, set_pod_paused
        set_pod_circuit_breaker(pod_slug, open=False)
        set_pod_paused(pod_slug, False)
        # Also reset the in-module circuit breaker state inside heartbeat
        meta = self._pods.get(pod_slug)
        if meta:
            hb = meta.get("heartbeat_module")
            if hb and hasattr(hb, "reset_circuit"):
                hb.reset_circuit()
        logger.info("[%s] Circuit breaker reset.", pod_slug)

    # ── Utilities ─────────────────────────────────────────────────────────────

    @staticmethod
    def _load_json(path: str) -> dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    @staticmethod
    def _load_module(module_name: str, file_path: str, pod_dir: str):
        """Load a .py file as a module using importlib. Handles hyphenated directories."""
        if pod_dir not in sys.path:
            sys.path.insert(0, pod_dir)
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            mod  = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return mod
        except Exception as e:
            logger.warning("Could not load module '%s' from '%s': %s", module_name, file_path, e)
            return None


# ── Singleton for app.py integration ─────────────────────────────────────────
# app.py imports this when USE_POD_ORCHESTRATOR=true
_orchestrator: Orchestrator | None = None


def get_orchestrator() -> Orchestrator | None:
    """Return the running orchestrator singleton, or None if not initialised."""
    return _orchestrator


def init_orchestrator() -> Orchestrator:
    """Discover pods, start scheduler. Called once at app startup."""
    global _orchestrator
    if _orchestrator is not None:
        return _orchestrator
    _orchestrator = Orchestrator()
    _orchestrator.discover_pods()
    _orchestrator.start_scheduler()
    return _orchestrator


# ── Standalone entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    import logging as _logging
    _logging.basicConfig(
        level=_logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from dotenv import load_dotenv
    load_dotenv()

    from database import init_db
    init_db()

    print("AltusFlow Orchestrator starting...")

    orchestrator = Orchestrator()
    orchestrator.discover_pods()
    orchestrator.start_scheduler()

    # First-run — run all pods immediately on startup
    if os.environ.get("SKIP_INITIAL_RUN", "").lower() != "true":
        orchestrator.run_all_now()

    def _handle_signal(signum, frame):
        print(f"\nSignal {signum} received — shutting down gracefully...")
        orchestrator.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT,  _handle_signal)

    try:
        while not orchestrator._shutdown_event.is_set():
            time.sleep(60)
            orchestrator.health_check()
    except (KeyboardInterrupt, SystemExit):
        orchestrator.shutdown()
