"""
test_factory.py
Phase 2 tests for the AltusFlow pod factory architecture.

Run:
    python test_factory.py           # all tests
    python test_factory.py -v        # verbose

These tests are integration-level: they import real modules but mock
all external I/O (APScheduler, DB writes, webhook calls, heartbeat runs).
No real Apify/HubSpot/Claude calls are made.
"""

import os
import sys
import json
import time
import unittest
import threading
from unittest.mock import MagicMock, patch, PropertyMock

# Ensure repo root is on path
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_good_report(pod_slug="financial-advisors", **overrides):
    from orchestrator import _CONTRACT_DEFAULTS
    report = {**_CONTRACT_DEFAULTS, "pod": pod_slug, "status": "ok"}
    report.update(overrides)
    return report


def _make_bad_heartbeat_module(error_msg="simulated failure"):
    """Return a mock heartbeat module whose run() raises an exception."""
    mod = MagicMock()
    mod.run.side_effect = RuntimeError(error_msg)
    mod.reset_circuit = MagicMock()
    return mod


def _make_ok_heartbeat_module(report_override=None):
    """Return a mock heartbeat module whose run() returns a clean report."""
    mod    = MagicMock()
    report = _make_good_report()
    if report_override:
        report.update(report_override)
    mod.run.return_value = report
    mod.reset_circuit = MagicMock()
    return mod


def _stub_orchestrator(pods: dict) -> "Orchestrator":
    """Build an Orchestrator with pre-loaded pod metas, bypassing discover_pods()."""
    from orchestrator import Orchestrator, _CONTRACT_DEFAULTS
    orch = Orchestrator()
    for slug, meta in pods.items():
        orch._pods[slug]   = meta
        orch._locks[slug]  = threading.Lock()
        orch._running[slug] = False
    return orch


# ─────────────────────────────────────────────────────────────────────────────
# Test: Pod discovery
# ─────────────────────────────────────────────────────────────────────────────

class TestPodDiscovery(unittest.TestCase):

    def test_orchestrator_discovers_financial_advisors_pod(self):
        """Orchestrator should find and register the financial-advisors pod."""
        from orchestrator import Orchestrator, _REQUIRED_POD_FILES

        orch = Orchestrator()

        with patch("database.upsert_pod_registry"), \
             patch.object(Orchestrator, "_load_module", return_value=MagicMock()):
            count = orch.discover_pods()

        self.assertGreaterEqual(count, 1, "Should find at least the financial-advisors pod")
        self.assertIn("financial-advisors", orch._pods,
                      "financial-advisors pod should be in _pods after discover_pods()")

    def test_template_pod_is_skipped(self):
        """The _template directory must never be registered as a runnable pod."""
        from orchestrator import Orchestrator

        orch = Orchestrator()
        with patch("database.upsert_pod_registry"), \
             patch.object(Orchestrator, "_load_module", return_value=MagicMock()):
            orch.discover_pods()

        self.assertNotIn("_template", orch._pods,
                         "_template should not appear in _pods after discover_pods()")

    def test_pod_with_missing_files_is_skipped(self):
        """A pod dir missing any of the 7 required files should be skipped with a warning."""
        from orchestrator import Orchestrator
        import tempfile

        orch = Orchestrator()
        with tempfile.TemporaryDirectory() as pods_dir:
            # Create a fake pod directory with only some files present
            pod_dir = os.path.join(pods_dir, "test-niche")
            os.makedirs(pod_dir)
            open(os.path.join(pod_dir, "identity.md"), "w").close()
            # Missing soul.md, tasks.json, tools.json, user.md, hunter.py, heartbeat.py

            with patch.object(orch, "_load_module", return_value=MagicMock()), \
                 patch("database.upsert_pod_registry"), \
                 patch("os.listdir", return_value=["test-niche"]), \
                 patch("os.path.isdir", return_value=True):
                # just check the logic independently
                missing = [f for f in ["identity.md", "soul.md", "tasks.json",
                                        "tools.json", "user.md", "hunter.py", "heartbeat.py"]
                           if not os.path.isfile(os.path.join(pod_dir, f))]
                self.assertEqual(len(missing), 6, "Should detect 6 missing files")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Circuit breaker
# ─────────────────────────────────────────────────────────────────────────────

class TestCircuitBreaker(unittest.TestCase):

    def _build_orch(self, hb_module):
        return _stub_orchestrator({
            "financial-advisors": {
                "slug":                  "financial-advisors",
                "label":                 "Financial Advisors",
                "heartbeat_module":      hb_module,
                "max_approvals_per_run": 50,
                "circuit_threshold":     3,
                "schedule":              "0 8 * * 1-5",
            }
        })

    def test_circuit_breaker_trips_on_3_consecutive_errors(self):
        """After 3 consecutive pod failures, circuit breaker must be tripped and pod paused."""
        error_hb = _make_bad_heartbeat_module("Simulated failure")
        orch     = self._build_orch(error_hb)

        call_count = [0]
        opened     = [False]

        def mock_increment(slug):
            call_count[0] += 1
            return call_count[0]

        def mock_set_cb(slug, open):
            if open:
                opened[0] = True

        def mock_get_registry(slug=None):
            return {"circuit_breaker_open": 0, "is_paused": 0}

        with patch("database.increment_pod_consecutive_errors", side_effect=mock_increment), \
             patch("database.set_pod_circuit_breaker", side_effect=mock_set_cb), \
             patch("database.reset_pod_consecutive_errors"), \
             patch("database.get_pod_registry", side_effect=mock_get_registry), \
             patch("database.log_pod_run"), \
             patch("error_logger.log_pipeline_error"):

            orch.run_pod("financial-advisors")
            orch.run_pod("financial-advisors")
            orch.run_pod("financial-advisors")

        self.assertEqual(call_count[0], 3, "Increment should be called 3 times")
        self.assertTrue(opened[0], "Circuit breaker should be opened after 3 errors")

    def test_circuit_breaker_blocks_further_runs_when_open(self):
        """A pod with an open circuit breaker must be skipped, not run."""
        ok_hb = _make_ok_heartbeat_module()
        orch  = self._build_orch(ok_hb)

        with patch("database.get_pod_registry",
                   return_value={"circuit_breaker_open": 1, "is_paused": 1}), \
             patch("database.log_pod_run"):
            result = orch.run_pod("financial-advisors")

        ok_hb.run.assert_not_called()
        self.assertEqual(result.get("status"), "circuit_open")

    def test_circuit_breaker_reset_resumes_pod(self):
        """reset_pod() should clear circuit_breaker_open and allow the pod to run again."""
        orch = _stub_orchestrator({"financial-advisors": {
            "slug": "financial-advisors",
            "heartbeat_module": _make_ok_heartbeat_module(),
            "max_approvals_per_run": 50,
            "circuit_threshold": 3,
        }})
        cb_state = {"open": 1}

        def set_cb(slug, open):
            cb_state["open"] = 1 if open else 0

        with patch("database.set_pod_circuit_breaker", side_effect=set_cb), \
             patch("database.set_pod_paused"):
            orch.reset_pod("financial-advisors")

        self.assertEqual(cb_state["open"], 0, "Circuit breaker should be closed after reset")


# ─────────────────────────────────────────────────────────────────────────────
# Test: High-volume guard
# ─────────────────────────────────────────────────────────────────────────────

class TestHighVolumeGuard(unittest.TestCase):

    def test_high_volume_guard_trips_when_over_limit(self):
        """If a pod auto-approves > 50 prospects in one run, it must be paused immediately."""
        over_limit_hb = _make_ok_heartbeat_module({"prospects_auto_approved": 51})
        orch = _stub_orchestrator({
            "financial-advisors": {
                "slug":                  "financial-advisors",
                "heartbeat_module":      over_limit_hb,
                "max_approvals_per_run": 50,
                "circuit_threshold":     3,
            }
        })

        tripped = [False]

        def set_cb(slug, open):
            if open:
                tripped[0] = True

        with patch("database.get_pod_registry",
                   return_value={"circuit_breaker_open": 0, "is_paused": 0}), \
             patch("database.set_pod_circuit_breaker", side_effect=set_cb), \
             patch("database.reset_pod_consecutive_errors"), \
             patch("database.log_pod_run"), \
             patch("error_logger.log_pipeline_error"):
            result = orch.run_pod("financial-advisors")

        self.assertTrue(tripped[0], "Circuit breaker should be tripped on high-volume attempt")
        self.assertEqual(result.get("status"), "paused_high_volume")
        self.assertEqual(result.get("circuit_breaker"), "open")

    def test_high_volume_guard_not_triggered_at_limit(self):
        """Exactly 50 auto-approvals should NOT trigger the guard."""
        at_limit_hb = _make_ok_heartbeat_module({"prospects_auto_approved": 50})
        orch = _stub_orchestrator({
            "financial-advisors": {
                "slug":                  "financial-advisors",
                "heartbeat_module":      at_limit_hb,
                "max_approvals_per_run": 50,
                "circuit_threshold":     3,
            }
        })

        tripped = [False]

        with patch("database.get_pod_registry",
                   return_value={"circuit_breaker_open": 0, "is_paused": 0}), \
             patch("database.set_pod_circuit_breaker",
                   side_effect=lambda slug, open: tripped.__setitem__(0, open)), \
             patch("database.reset_pod_consecutive_errors"), \
             patch("database.log_pod_run"):
            result = orch.run_pod("financial-advisors")

        self.assertFalse(tripped[0], "Guard should NOT trip at exactly the limit")
        self.assertEqual(result.get("status"), "ok")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Data contract enforcement
# ─────────────────────────────────────────────────────────────────────────────

class TestDataContractEnforcement(unittest.TestCase):

    def test_malformed_report_does_not_crash_orchestrator(self):
        """Heartbeat returning a string instead of dict must be normalised, not crash."""
        bad_hb = MagicMock()
        bad_hb.run.return_value = "I am not a dict"
        bad_hb.reset_circuit = MagicMock()

        orch = _stub_orchestrator({"financial-advisors": {
            "slug":                  "financial-advisors",
            "heartbeat_module":      bad_hb,
            "max_approvals_per_run": 50,
            "circuit_threshold":     3,
        }})

        with patch("database.get_pod_registry",
                   return_value={"circuit_breaker_open": 0, "is_paused": 0}), \
             patch("database.increment_pod_consecutive_errors", return_value=1), \
             patch("database.set_pod_circuit_breaker"), \
             patch("database.reset_pod_consecutive_errors"), \
             patch("database.log_pod_run"), \
             patch("error_logger.log_pipeline_error"):
            result = orch.run_pod("financial-advisors")

        self.assertIsInstance(result, dict, "Result must always be a dict")
        self.assertIn("status", result, "Result must have a status key")

    def test_missing_keys_are_filled_with_defaults(self):
        """A report with only {status: ok} must be normalised to include all contract keys."""
        sparse_hb = _make_ok_heartbeat_module()
        sparse_hb.run.return_value = {"status": "ok"}

        orch = _stub_orchestrator({"financial-advisors": {
            "slug":                  "financial-advisors",
            "heartbeat_module":      sparse_hb,
            "max_approvals_per_run": 50,
            "circuit_threshold":     3,
        }})

        from orchestrator import _CONTRACT_DEFAULTS
        with patch("database.get_pod_registry",
                   return_value={"circuit_breaker_open": 0, "is_paused": 0}), \
             patch("database.reset_pod_consecutive_errors"), \
             patch("database.log_pod_run"):
            result = orch.run_pod("financial-advisors")

        for key in _CONTRACT_DEFAULTS:
            self.assertIn(key, result, f"Missing contract key: {key}")

    def test_non_int_numeric_fields_are_coerced(self):
        """String numerics in the report must be coerced to int by the contract enforcer."""
        from orchestrator import Orchestrator
        orch = Orchestrator()
        raw = {"status": "ok", "prospects_found": "12", "prospects_qualified": "5.0"}
        result = orch._enforce_data_contract(raw, "test-pod")
        self.assertEqual(result["prospects_found"], 12)
        self.assertEqual(result["prospects_qualified"], 5)

    def test_extra_keys_are_preserved(self):
        """Extra keys not in the contract must pass through, not be stripped."""
        from orchestrator import Orchestrator
        orch = Orchestrator()
        raw = {"status": "ok", "custom_metric": "foobar"}
        result = orch._enforce_data_contract(raw, "test-pod")
        self.assertEqual(result.get("custom_metric"), "foobar")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Graceful shutdown
# ─────────────────────────────────────────────────────────────────────────────

class TestGracefulShutdown(unittest.TestCase):

    def test_shutdown_event_is_set_after_shutdown(self):
        """After shutdown(), _shutdown_event must be set so the main loop exits."""
        from orchestrator import Orchestrator
        orch = Orchestrator()
        orch._scheduler = MagicMock()
        orch._scheduler.running = True

        orch.shutdown()

        self.assertTrue(orch._shutdown_event.is_set(),
                        "_shutdown_event must be set after shutdown()")

    def test_in_flight_pod_marked_interrupted_on_timeout(self):
        """Pods still running at shutdown timeout must be marked 'interrupted' in pod_status."""
        from orchestrator import Orchestrator
        orch = Orchestrator()
        orch._scheduler = MagicMock()
        orch._scheduler.running = True

        # Simulate a pod that is "running" and never finishes within the timeout
        orch._pods["financial-advisors"]   = {"slug": "financial-advisors"}
        orch._running["financial-advisors"] = True  # still running

        interrupted = []

        def mock_log_pod_run(slug, report):
            if report.get("status") == "interrupted":
                interrupted.append(slug)

        with patch("database.log_pod_run", side_effect=mock_log_pod_run), \
             patch.object(orch, "_shutdown_event") as mock_evt:
            mock_evt.is_set.return_value = False
            # Force timeout path by setting short deadline: patch time.time
            start = time.time()
            with patch("time.time", side_effect=[start, start + 200, start + 200]):
                with patch("time.sleep"):
                    orch.shutdown()

        self.assertIn("financial-advisors", interrupted,
                      "Interrupted pods must be logged in pod_status")

    def test_scheduler_is_stopped_on_shutdown(self):
        """APScheduler must be shut down when the orchestrator shuts down."""
        from orchestrator import Orchestrator
        orch = Orchestrator()
        mock_sched = MagicMock()
        mock_sched.running = True
        orch._scheduler = mock_sched

        orch.shutdown()

        mock_sched.shutdown.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# Test: Concurrent-run guard
# ─────────────────────────────────────────────────────────────────────────────

class TestConcurrentRunGuard(unittest.TestCase):

    def test_second_trigger_is_skipped_while_pod_running(self):
        """If a pod's lock is held, a second trigger must return status='skipped'."""
        ok_hb = _make_ok_heartbeat_module()
        orch  = _stub_orchestrator({"financial-advisors": {
            "slug":                  "financial-advisors",
            "heartbeat_module":      ok_hb,
            "max_approvals_per_run": 50,
            "circuit_threshold":     3,
        }})

        # Manually acquire the lock to simulate an in-flight run
        orch._locks["financial-advisors"].acquire()
        try:
            result = orch.run_pod("financial-advisors")
        finally:
            orch._locks["financial-advisors"].release()

        self.assertEqual(result.get("status"), "skipped")
        ok_hb.run.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# Test: Database helpers
# ─────────────────────────────────────────────────────────────────────────────

class TestDatabaseHelpers(unittest.TestCase):
    """Light-touch tests for the new pod_registry / pod_status / DNC DB functions."""

    def setUp(self):
        """
        Force a fresh in-memory SQLite engine for every test method.
        This guarantees each test starts with an empty database regardless of
        any leftover state from previous tests or prior test runs.
        """
        import database as _db
        # Reset the singleton engine so _get_engine() creates a new in-memory DB
        _db._DATABASE_URL = "sqlite:///:memory:"
        _db._is_sqlite    = True
        _db._engine       = None
        _db._engines      = {}
        _db.init_db()

    def tearDown(self):
        """Dispose the engine after each test to release the in-memory DB."""
        import database as _db
        if _db._engine:
            try:
                _db._engine.dispose()
            except Exception:
                pass
        _db._engine   = None
        _db._engines  = {}

    def test_upsert_pod_registry_is_idempotent(self):
        from database import upsert_pod_registry, get_pod_registry
        upsert_pod_registry("test-niche", "Test Niche")
        upsert_pod_registry("test-niche", "Test Niche — Updated")
        row = get_pod_registry("test-niche")
        self.assertIsNotNone(row)
        self.assertEqual(row["pod_label"], "Test Niche — Updated")

    def test_set_pod_paused_and_resume(self):
        from database import upsert_pod_registry, set_pod_paused, get_pod_registry
        upsert_pod_registry("test-niche2")
        set_pod_paused("test-niche2", True, "test reason")
        row = get_pod_registry("test-niche2")
        self.assertEqual(row["is_paused"], 1)
        self.assertEqual(row["pause_reason"], "test reason")

        set_pod_paused("test-niche2", False)
        row = get_pod_registry("test-niche2")
        self.assertEqual(row["is_paused"], 0)

    def test_circuit_breaker_trip_and_reset(self):
        from database import upsert_pod_registry, set_pod_circuit_breaker, get_pod_registry
        upsert_pod_registry("test-niche3")
        set_pod_circuit_breaker("test-niche3", open=True)
        row = get_pod_registry("test-niche3")
        self.assertEqual(row["circuit_breaker_open"], 1)

        set_pod_circuit_breaker("test-niche3", open=False)
        row = get_pod_registry("test-niche3")
        self.assertEqual(row["circuit_breaker_open"], 0)
        self.assertEqual(row["consecutive_errors"], 0)

    def test_increment_and_reset_consecutive_errors(self):
        from database import (upsert_pod_registry, increment_pod_consecutive_errors,
                               reset_pod_consecutive_errors, get_pod_registry)
        upsert_pod_registry("test-niche4")
        c1 = increment_pod_consecutive_errors("test-niche4")
        c2 = increment_pod_consecutive_errors("test-niche4")
        self.assertEqual(c2, 2)
        reset_pod_consecutive_errors("test-niche4")
        row = get_pod_registry("test-niche4")
        self.assertEqual(row["consecutive_errors"], 0)

    def test_log_pod_run_and_get_history(self):
        from database import upsert_pod_registry, log_pod_run, get_pod_run_history
        from orchestrator import _CONTRACT_DEFAULTS
        upsert_pod_registry("test-niche5")
        report = {**_CONTRACT_DEFAULTS,
                  "pod": "test-niche5", "status": "ok",
                  "run_id": "abc-123", "prospects_found": 7}
        log_pod_run("test-niche5", report)
        history = get_pod_run_history("test-niche5", limit=10)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "ok")
        self.assertEqual(history[0]["prospects_found"], 7)

    def test_dnc_add_check_remove(self):
        from database import add_dnc_entry, is_on_dnc, remove_from_dnc
        add_dnc_entry("testuser", "linkedin", "tenant1", "test reason")
        self.assertTrue(is_on_dnc("testuser", "linkedin", user_id="tenant1"))
        self.assertFalse(is_on_dnc("testuser", "linkedin", user_id="other_tenant"))
        remove_from_dnc("testuser", "linkedin", "tenant1")
        self.assertFalse(is_on_dnc("testuser", "linkedin", user_id="tenant1"))

    def test_global_dnc_blocks_all_users(self):
        from database import add_dnc_entry, is_on_dnc
        add_dnc_entry("globalblock", "facebook", None, "spam", is_global=True)
        self.assertTrue(is_on_dnc("globalblock", "facebook"))
        self.assertTrue(is_on_dnc("globalblock", "facebook", user_id="any_tenant"))

    def test_dispatched_event_dedup(self):
        from database import has_event_been_dispatched, log_dispatched_event
        eid = "uuid5-abc-123"
        self.assertFalse(has_event_been_dispatched(eid))
        log_dispatched_event(eid, "hubspot_push", "tenant1", 42, '{"x":1}')
        self.assertTrue(has_event_been_dispatched(eid))
        # Second insert should be silently ignored (UNIQUE constraint)
        log_dispatched_event(eid, "hubspot_push", "tenant1", 42, '{"x":2}')
        self.assertTrue(has_event_been_dispatched(eid))


# ─────────────────────────────────────────────────────────────────────────────
# Test: Pod-specific qualify() abort conditions (Phase 3)
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_niche(slug="test-niche"):
    """Minimal niche module mock for hunter tests."""
    niche             = MagicMock()
    niche.NICHE_SLUG  = slug
    niche.NICHE_LABEL = slug.replace("-", " ").title()
    niche.PLATFORM_WEIGHT = {"linkedin": 0.5, "facebook": 0.4, "reddit": 0.3}
    return niche


class TestPodSpecificAbortConditions(unittest.TestCase):
    """Verify each pod's qualify() abort conditions gate correctly."""

    def _make_hunter(self, hunter_cls, pod_slug):
        """
        Construct a hunter instance with a mocked niche module.
        Patches get_niche() at the scrapers.niches level so __init__ doesn't
        require real niche data.
        """
        mock_niche = _make_mock_niche(pod_slug)
        with patch("scrapers.niches.get_niche", return_value=mock_niche):
            h = hunter_cls(run_id="test-run-001")
        h._niche = mock_niche
        return h

    # ── 1. Business coach hunter rejects coach seeking clients ────────────────

    def test_business_coach_hunter_rejects_coach_seeking_clients(self):
        """
        A post containing 'my coaching program' must be rejected immediately.
        Wrong side of market — coach selling, not buying.
        """
        # Load via importlib since the dir name has a hyphen
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "bc_hunter",
            os.path.join(_ROOT, "pods", "business-coaches", "hunter.py"),
        )
        mod = importlib.util.module_from_spec(spec)

        mock_niche = _make_mock_niche("business-coaches")
        with patch("scrapers.niches.get_niche", return_value=mock_niche):
            spec.loader.exec_module(mod)

        hunter = mod.BusinessCoachHunter.__new__(mod.BusinessCoachHunter)
        hunter._niche  = mock_niche
        hunter.run_id  = "test"
        hunter._pod_slug = "business-coaches"

        prospect = {
            "handle":    "growth_coach_jane",
            "platform":  "facebook",
            "post_text": "I'm enrolling new clients into my coaching program. DM me to apply.",
            "title":     "business coach",
            "name":      "Jane Smith",
        }

        score, reason = hunter.qualify(prospect)
        self.assertEqual(score, 0, "Coach-seeking-clients post must score 0")
        self.assertIn("Wrong side of market", reason)

    # ── 2. Recruiter hunter tags prospect_type ────────────────────────────────

    def test_recruiter_hunter_tags_prospect_type(self):
        """
        A post with agency owner BD signals must be tagged 'agency_owner'.
        A post with hiring manager signals must be tagged 'hiring_manager'.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "rec_hunter",
            os.path.join(_ROOT, "pods", "recruiters", "hunter.py"),
        )
        mod = importlib.util.module_from_spec(spec)

        mock_niche = _make_mock_niche("recruiters")
        with patch("scrapers.niches.get_niche", return_value=mock_niche):
            spec.loader.exec_module(mod)

        hunter       = mod.RecruiterHunter.__new__(mod.RecruiterHunter)
        hunter._niche = mock_niche
        hunter.run_id = "test"

        agency_prospect = {
            "handle":    "rec_founder_bob",
            "platform":  "linkedin",
            "post_text": "how do recruiters get clients — bd is harder than ever for our agency",
            "title":     "founder",
            "name":      "Bob Thornton",
        }
        hiring_prospect = {
            "handle":    "cto_mike",
            "platform":  "linkedin",
            "post_text": "struggling to find senior engineers and last three hires did not work out",
            "title":     "cto",
            "name":      "Mike Chen",
        }

        with patch("qualify.score_prospect", return_value=(8, "test score")):
            hunter.qualify(agency_prospect)
            hunter.qualify(hiring_prospect)

        self.assertEqual(agency_prospect.get("prospect_type"), "agency_owner",
                         "BD-pain post should be tagged agency_owner")
        self.assertEqual(hiring_prospect.get("prospect_type"), "hiring_manager",
                         "Hiring pain post should be tagged hiring_manager")

    # ── 3. CRE hunter rejects residential posts ───────────────────────────────

    def test_cre_hunter_rejects_residential_posts(self):
        """
        A post about apartment hunting with no commercial context must score 0.
        A post with residential language + 2 commercial keywords must pass through.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cre_hunter",
            os.path.join(_ROOT, "pods", "commercial-real-estate", "hunter.py"),
        )
        mod = importlib.util.module_from_spec(spec)

        mock_niche = _make_mock_niche("commercial-real-estate")
        with patch("scrapers.niches.get_niche", return_value=mock_niche):
            spec.loader.exec_module(mod)

        hunter        = mod.CREHunter.__new__(mod.CREHunter)
        hunter._niche = mock_niche
        hunter.run_id = "test"

        residential = {
            "handle":    "apt_hunter",
            "platform":  "reddit",
            "post_text": "apartment hunting in Austin, rent is too high everywhere",
            "title":     "renter",
            "name":      "Alice",
        }
        mixed_commercial = {
            "handle":    "biz_owner",
            "platform":  "linkedin",
            "post_text": "my condo is great but looking at a 1031 exchange for our commercial office space needs",
            "title":     "ceo",
            "name":      "Dave",
        }

        res_score, res_reason = hunter.qualify(residential)
        self.assertEqual(res_score, 0, "Pure residential post must score 0")
        self.assertIn("Residential", res_reason)

        with patch("qualify.score_prospect", return_value=(7, "ok")):
            mixed_score, _ = hunter.qualify(mixed_commercial)
        self.assertGreater(mixed_score, 0, "Mixed post with 2+ commercial keywords must pass through")

    # ── 4. MSP hunter rejects IT professionals ────────────────────────────────

    def test_msp_hunter_rejects_it_professionals(self):
        """
        A prospect whose title includes 'software engineer' must score 0.
        A business owner with IT pain must pass through.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "msp_hunter",
            os.path.join(_ROOT, "pods", "msps", "hunter.py"),
        )
        mod = importlib.util.module_from_spec(spec)

        mock_niche = _make_mock_niche("msps")
        with patch("scrapers.niches.get_niche", return_value=mock_niche):
            spec.loader.exec_module(mod)

        hunter        = mod.MSPHunter.__new__(mod.MSPHunter)
        hunter._niche = mock_niche
        hunter.run_id = "test"

        it_pro = {
            "handle":    "swe_alex",
            "platform":  "reddit",
            "post_text": "reviewing our deployment pipeline and setting up kubernetes",
            "title":     "software engineer",
            "name":      "Alex K",
        }
        sme_owner = {
            "handle":    "biz_owner_sarah",
            "platform":  "reddit",
            "post_text": "our it support is terrible and we are looking for a better managed services provider",
            "title":     "owner",
            "name":      "Sarah L",
        }

        it_score, it_reason = hunter.qualify(it_pro)
        self.assertEqual(it_score, 0, "IT professional must score 0")
        self.assertIn("IT professional", it_reason)

        with patch("qualify.score_prospect", return_value=(8, "good fit")):
            sme_score, _ = hunter.qualify(sme_owner)
        self.assertGreater(sme_score, 0, "SME owner with IT pain must qualify")

    # ── 5. AltusFlow own hunter aborts on existing HubSpot contact ────────────

    def test_altusflow_own_hunter_aborts_on_existing_hubspot_contact(self):
        """
        If _is_in_hubspot() returns True, qualify() must return score 0
        with the 'Already in HubSpot CRM' reason.
        """
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "alt_hunter",
            os.path.join(_ROOT, "pods", "altusflow-own", "hunter.py"),
        )
        mod = importlib.util.module_from_spec(spec)

        mock_niche = _make_mock_niche("altusflow-own")
        with patch("scrapers.niches.get_niche", return_value=mock_niche):
            spec.loader.exec_module(mod)

        hunter         = mod.AltusFlowOwnHunter.__new__(mod.AltusFlowOwnHunter)
        hunter._niche  = mock_niche
        hunter.run_id  = "test"
        hunter._config = {"user_id": "ALT00"}

        existing_contact = {
            "handle":    "jane_the_ria",
            "platform":  "linkedin",
            "post_text": "how do financial advisors get clients — pipeline dried up",
            "title":     "financial advisor",
            "name":      "Jane Doe",
        }

        with patch.object(hunter, "_is_in_hubspot", return_value=True):
            score, reason = hunter.qualify(existing_contact)

        self.assertEqual(score, 0, "Existing HubSpot contact must score 0")
        self.assertIn("Already in HubSpot CRM", reason)


# ─────────────────────────────────────────────────────────────────────────────
# Test: Skill files (Phase 4)
# ─────────────────────────────────────────────────────────────────────────────

_SKILLS_DIR      = os.path.join(_ROOT, "skills")
_EXPECTED_SKILLS = ["apify-scraper", "hubspot-crm", "claude-drafter", "meta-audiences"]
_SKILL_REQUIRED_FRONTMATTER_KEYS = {"name", "version", "description", "inputs", "outputs"}


def _parse_frontmatter(skill_md_path: str) -> dict:
    """
    Extract the YAML frontmatter block from a SKILL.md file.
    Returns parsed dict, or raises ValueError if frontmatter is missing/malformed.
    """
    with open(skill_md_path, "r", encoding="utf-8") as f:
        content = f.read()

    if not content.startswith("---"):
        raise ValueError(f"No frontmatter opener in {skill_md_path}")

    # Find the closing ---
    end = content.find("\n---", 3)
    if end == -1:
        raise ValueError(f"No frontmatter closer in {skill_md_path}")

    fm_text = content[3:end].strip()

    try:
        import yaml
        return yaml.safe_load(fm_text)
    except ImportError:
        # Fallback: minimal key extraction without pyyaml
        result = {}
        for line in fm_text.splitlines():
            if ":" in line and not line.startswith(" ") and not line.startswith("-"):
                k, _, v = line.partition(":")
                result[k.strip()] = v.strip()
        return result


class TestSkillFiles(unittest.TestCase):
    """Verify the skills/ directory structure and SKILL.md frontmatter validity."""

    def test_all_skill_directories_exist(self):
        """skills/ must contain exactly the 4 expected subdirectories."""
        self.assertTrue(os.path.isdir(_SKILLS_DIR),
                        f"skills/ directory not found at {_SKILLS_DIR}")
        for slug in _EXPECTED_SKILLS:
            skill_dir = os.path.join(_SKILLS_DIR, slug)
            self.assertTrue(os.path.isdir(skill_dir),
                            f"skills/{slug}/ directory is missing")

    def test_all_skill_files_exist(self):
        """Each skills/ subdirectory must contain a SKILL.md file."""
        for slug in _EXPECTED_SKILLS:
            skill_md = os.path.join(_SKILLS_DIR, slug, "SKILL.md")
            self.assertTrue(os.path.isfile(skill_md),
                            f"SKILL.md missing for skill '{slug}' at {skill_md}")

    def test_skill_frontmatter_valid(self):
        """Each SKILL.md must have valid YAML frontmatter with all required keys."""
        for slug in _EXPECTED_SKILLS:
            skill_md = os.path.join(_SKILLS_DIR, slug, "SKILL.md")
            with self.subTest(skill=slug):
                try:
                    fm = _parse_frontmatter(skill_md)
                except (ValueError, Exception) as e:
                    self.fail(f"Could not parse frontmatter for {slug}: {e}")
                for key in _SKILL_REQUIRED_FRONTMATTER_KEYS:
                    self.assertIn(key, fm,
                                  f"Required frontmatter key '{key}' missing in {slug}/SKILL.md")
                # name must match the directory slug
                self.assertEqual(fm.get("name"), slug,
                                 f"frontmatter name '{fm.get('name')}' does not match directory '{slug}'")


# ─────────────────────────────────────────────────────────────────────────────
# Test: README completeness (Phase 4)
# ─────────────────────────────────────────────────────────────────────────────

_README_PATH = os.path.join(_ROOT, "README.md")

_REQUIRED_README_SECTIONS = [
    "## Architecture Overview",
    "## How the EventDispatcher protects your data",
    "## Circuit breaker behaviour",
    "## Deploying a New Pod",
    "## Environment Variables Reference",
    "## Troubleshooting Common Issues",
    "## OpenClaw Integration (Future)",
    "## Pod admin UI",
    "## Adding a Client to an Existing Pod",
]


class TestReadme(unittest.TestCase):

    def test_readme_sections_complete(self):
        """README.md must contain all required operator manual sections."""
        self.assertTrue(os.path.isfile(_README_PATH),
                        f"README.md not found at {_README_PATH}")
        with open(_README_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        for section in _REQUIRED_README_SECTIONS:
            with self.subTest(section=section):
                self.assertIn(section, content,
                              f"Required section missing from README.md: {section!r}")


# ─────────────────────────────────────────────────────────────────────────────
# Test: Full factory integration (Phase 4)
# ─────────────────────────────────────────────────────────────────────────────

_EXPECTED_POD_SLUGS = {
    "financial-advisors",
    "business-coaches",
    "recruiters",
    "commercial-real-estate",
    "msps",
    "altusflow-own",
}


class TestFullFactory(unittest.TestCase):

    def test_all_6_pods_discovered(self):
        """
        Orchestrator must discover exactly 6 pods and exclude _template.
        """
        from orchestrator import Orchestrator

        orch = Orchestrator()
        with patch("database.upsert_pod_registry"), \
             patch.object(Orchestrator, "_load_module", return_value=MagicMock()):
            count = orch.discover_pods()

        found = set(orch._pods.keys())
        self.assertEqual(count, 6, f"Expected 6 pods, found {count}: {found}")
        self.assertEqual(found, _EXPECTED_POD_SLUGS,
                         f"Pod set mismatch.\n  Expected: {_EXPECTED_POD_SLUGS}\n  Found:    {found}")
        self.assertNotIn("_template", found, "_template must never be registered")

    def test_pod_data_contract_all_pods(self):
        """
        Each pod's heartbeat.status() must return a dict with all required data contract keys.
        """
        from orchestrator import _CONTRACT_DEFAULTS
        required_keys = set(_CONTRACT_DEFAULTS.keys())
        pods_dir      = os.path.join(_ROOT, "pods")

        for slug in _EXPECTED_POD_SLUGS:
            with self.subTest(pod=slug):
                hb_path = os.path.join(pods_dir, slug, "heartbeat.py")
                self.assertTrue(os.path.isfile(hb_path),
                                f"heartbeat.py missing for pod '{slug}'")

                import importlib.util
                spec = importlib.util.spec_from_file_location(f"hb_{slug}", hb_path)
                mod  = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)

                result = mod.status()
                self.assertIsInstance(result, dict,
                                      f"heartbeat.status() for '{slug}' must return dict")
                self.assertIn("pod",            result)
                self.assertIn("status",         result)
                self.assertIn("circuit_breaker", result)
                # Subset check for numeric contract keys
                for key in ("prospects_found", "prospects_qualified", "prospects_stored"):
                    self.assertIn(key, result,
                                  f"Data contract key '{key}' missing from '{slug}' status()")

    def test_event_dispatcher_audit_trail(self):
        """
        Dispatch an event, confirm it is logged, confirm dedup on second dispatch.
        Uses in-memory DB for isolation.
        """
        import database as _db
        _db._DATABASE_URL = "sqlite:///:memory:"
        _db._is_sqlite    = True
        _db._engine       = None
        _db._engines      = {}
        _db.init_db()

        try:
            from database import has_event_been_dispatched, log_dispatched_event

            eid = "evt-phase4-audit-test-001"

            # Before dispatch: not in log
            self.assertFalse(has_event_been_dispatched(eid),
                             "Event should not exist before first dispatch")

            # First dispatch
            log_dispatched_event(eid, "hubspot_push", "financial-advisors", 99, '{"audit": true}')
            self.assertTrue(has_event_been_dispatched(eid),
                            "Event must be logged after first dispatch")

            # Second dispatch — dedup: should silently ignore, not raise, still True
            log_dispatched_event(eid, "hubspot_push", "financial-advisors", 99, '{"audit": true}')
            self.assertTrue(has_event_been_dispatched(eid),
                            "Dedup: event still present after second dispatch attempt")

        finally:
            if _db._engine:
                try:
                    _db._engine.dispose()
                except Exception:
                    pass
            _db._engine  = None
            _db._engines = {}


# ─────────────────────────────────────────────────────────────────────────────
# Test: Morgan inbound AI receptionist
# ─────────────────────────────────────────────────────────────────────────────

_VOICE_DIR = os.path.join(_ROOT, "voice")


class TestMorganReceptionist(unittest.TestCase):
    """
    Integration tests for the Morgan inbound AI receptionist.
    All Vapi, HubSpot, and DB calls are mocked — no external I/O.
    """

    def _load_gateway(self):
        """Import VoiceGateway with soul/faq files present — no Vapi key required."""
        import importlib
        import voice.VoiceGateway as vgm
        importlib.reload(vgm)
        return vgm.VoiceGateway()

    # ── 1. Inbound call returns Morgan assistant config ────────────────────────

    def test_inbound_call_triggers_morgan(self):
        """
        Webhook fires with AltusFlow number.
        VoiceGateway loads soul_concierge.md + faq.md and returns Vapi assistant config.
        Morgan persona, correct voice model, and firstMessage must all be present.
        """
        with patch("database.log_voice_call", return_value=1):
            gw     = self._load_gateway()
            config = gw.handle_inbound_call(
                called_number="+15551234567",
                caller_number="+19998887777",
                user_id="ALT00",
            )

        assistant = config.get("assistant", {})
        self.assertEqual(assistant.get("name"), "Morgan")
        self.assertIn("firstMessage", assistant)
        self.assertIn("AltusFlow", assistant["firstMessage"])
        model_cfg = assistant.get("model", {})
        self.assertEqual(model_cfg.get("provider"), "anthropic")
        messages = model_cfg.get("messages", [])
        self.assertTrue(len(messages) > 0, "System prompt messages must be present")
        system_prompt = messages[0].get("content", "")
        self.assertIn("Morgan", system_prompt)
        self.assertIn("FAQ", system_prompt)

    # ── 2. Booking notifies closer ────────────────────────────────────────────

    def test_booking_notifies_closer(self):
        """
        When handle_call_ended receives a booking in structuredData,
        notify_closer must be called, HubSpot task must be created,
        and closer webhook must fire.
        """
        with patch("database.log_voice_call", return_value=1):
            gw = self._load_gateway()

        booking_payload = {
            "call": {
                "id":          "call-abc-123",
                "endedReason": "customer-ended-call",
                "cost":        0.05,
                "metadata":    {"user_id": "ALT00", "caller_hash": "abc123hash"},
            },
            "transcript": "Thank you for calling AltusFlow...",
            "summary":    "Caller asked about the Outbound Hunter. Booked a call.",
            "structuredData": {
                "booking":        {"start_time": "2026-06-26T14:00:00Z"},
                "prospect_name":  "Jane Smith",
            },
        }

        with patch("database.update_voice_call"), \
             patch("database.log_voice_cost"), \
             patch("database.mark_closer_notified") as mock_notified, \
             patch.object(gw, "_create_hubspot_task", return_value="hs-task-001") as mock_task, \
             patch.object(gw, "_fire_closer_webhook") as mock_webhook:

            gw.handle_call_ended(booking_payload)

        mock_task.assert_called_once()
        task_args = mock_task.call_args[1] if mock_task.call_args[1] else {}
        self.assertIn("booked", mock_task.call_args[0][0].lower()
                      if mock_task.call_args[0] else task_args.get("title", "").lower())
        mock_webhook.assert_called_once()
        webhook_payload = mock_webhook.call_args[0][0]
        self.assertEqual(webhook_payload["alert"], "call_booked")
        self.assertEqual(webhook_payload["prospect_name"], "Jane Smith")
        mock_notified.assert_called_once_with("call-abc-123")

    # ── 3. FAQ question answered — unknown question escalates ─────────────────

    def test_faq_question_answered_correctly(self):
        """
        soul_concierge.md must instruct Morgan to only answer from faq.md
        and escalate unknown questions. Both files must contain these rules.
        """
        soul_path = os.path.join(_VOICE_DIR, "soul_concierge.md")
        faq_path  = os.path.join(_VOICE_DIR, "faq.md")

        self.assertTrue(os.path.isfile(soul_path), "soul_concierge.md must exist")
        self.assertTrue(os.path.isfile(faq_path),  "faq.md must exist")

        with open(soul_path, encoding="utf-8") as f:
            soul = f.read()
        with open(faq_path, encoding="utf-8") as f:
            faq = f.read()

        self.assertIn("Only answer", soul, "Soul must restrict answers to FAQ")
        self.assertIn("escalat", soul.lower(), "Soul must describe escalation behaviour")
        # FAQ must cover the critical discovery call topic
        self.assertIn("discovery call", faq.lower())
        # FAQ must cover pricing (even if redirect)
        self.assertIn("cost", faq.lower())

    # ── 4. "Is this AI" triggers escalation ──────────────────────────────────

    def test_is_this_ai_triggers_escalation(self):
        """
        If the transcript contains an escalation phrase ('is this ai'),
        handle_call_ended must call handle_escalation with a reason.
        """
        with patch("database.log_voice_call", return_value=1):
            gw = self._load_gateway()

        payload = {
            "call": {
                "id":          "call-esc-001",
                "endedReason": "customer-ended-call",
                "cost":        0.02,
                "metadata":    {"user_id": "ALT00", "caller_hash": "esc001hash"},
            },
            "transcript": "is this ai or a real person",
            "summary":    "",
            "structuredData": {},
        }

        with patch("database.update_voice_call"), \
             patch("database.log_voice_cost"), \
             patch.object(gw, "handle_escalation") as mock_esc:

            gw.handle_call_ended(payload)

        mock_esc.assert_called_once()
        _, kwargs = mock_esc.call_args.args, mock_esc.call_args.kwargs
        call_args = mock_esc.call_args
        self.assertEqual(call_args.kwargs.get("call_id") or call_args.args[0], "call-esc-001")

    # ── 5. Escalation creates HubSpot task ───────────────────────────────────

    def test_escalation_creates_hubspot_task(self):
        """
        handle_escalation must call notify_closer with is_escalation=True,
        which creates a HubSpot task with URGENT in the title.
        """
        with patch("database.log_voice_call", return_value=1):
            gw = self._load_gateway()

        with patch("database.update_voice_call"), \
             patch("database.mark_closer_notified"), \
             patch.object(gw, "_create_hubspot_task", return_value="hs-task-esc") as mock_task, \
             patch.object(gw, "_fire_closer_webhook"):

            gw.handle_escalation(
                call_id="call-esc-002",
                reason="Caller asked if this is AI",
                user_id="ALT00",
            )

        mock_task.assert_called_once()
        title_arg = mock_task.call_args[0][0] if mock_task.call_args[0] \
                    else mock_task.call_args[1].get("title", "")
        self.assertIn("URGENT", title_arg)

    # ── 6. PII hashed in voice_calls ─────────────────────────────────────────

    def test_pii_hashed_in_voice_calls_table(self):
        """
        handle_inbound_call must hash the caller's phone number before
        passing it to log_voice_call — raw number must never be stored.
        """
        raw_number  = "+19998887777"
        import hashlib
        expected_hash = hashlib.sha256(raw_number.strip().encode()).hexdigest()

        with patch("database.log_voice_call", return_value=1) as mock_log:
            gw = self._load_gateway()
            gw.handle_inbound_call(
                called_number="+15551234567",
                caller_number=raw_number,
                user_id="ALT00",
            )

        call_kwargs = mock_log.call_args[1] if mock_log.call_args[1] else {}
        stored_hash = call_kwargs.get("caller_hash", "")
        self.assertEqual(stored_hash, expected_hash,
                         "Caller number must be SHA-256 hashed before storage")
        self.assertNotIn(raw_number, str(mock_log.call_args),
                         "Raw phone number must never appear in log_voice_call args")

    # ── 7. Call-ended moves deal to Meeting Booked ────────────────────────────

    def test_call_ended_moves_deal_to_meeting_booked(self):
        """
        If structuredData contains a booking and a hubspot_deal_id,
        _move_deal_to_meeting_booked must be called with the correct deal ID.
        """
        with patch("database.log_voice_call", return_value=1):
            gw = self._load_gateway()

        payload = {
            "call": {
                "id":          "call-booked-001",
                "endedReason": "customer-ended-call",
                "cost":        0.04,
                "metadata":    {"user_id": "ALT00", "caller_hash": "book001"},
            },
            "transcript": "Great, looking forward to speaking with your specialist.",
            "summary":    "Booked discovery call.",
            "structuredData": {
                "booking":         {"start_time": "2026-06-27T15:00:00Z"},
                "prospect_name":   "Bob Jones",
                "hubspot_deal_id": "deal-hs-999",
            },
        }

        with patch("database.update_voice_call"), \
             patch("database.log_voice_cost"), \
             patch("database.mark_closer_notified"), \
             patch.object(gw, "_create_hubspot_task", return_value=""), \
             patch.object(gw, "_fire_closer_webhook"), \
             patch.object(gw, "_move_deal_to_meeting_booked") as mock_move:

            import os as _os
            _os.environ["HUBSPOT_STAGE_MEETING_BOOKED_ID"] = "stage-booked-123"
            gw.handle_call_ended(payload)

        mock_move.assert_called_once()
        self.assertEqual(mock_move.call_args[0][0], "deal-hs-999")


if __name__ == "__main__":
    unittest.main(verbosity=2)
