"""
core/BaseHunter.py
Parent class all niche pods inherit.

Encapsulates shared logic that is never duplicated across pods:
  - pre_flight_check: DNC, consent, cooldown, minimum fields
  - draft: calls drafter.py with Insufficient Intel guard
  - dispatch: always routes through EventDispatcher

Pods MUST override scan() and qualify().
Pods MUST NOT call HubSpot, Meta, or any external API directly — use dispatch().
"""

import os
import sys

# Allow the core/ package to be imported from the outbound-hunter root
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


class BaseHunter:
    """
    Base class for all outbound niche pods.

    Lifecycle (called by heartbeat.run()):
      1. __init__     — load pod identity and config
      2. pre_flight   — gate each prospect before any processing
      3. scan()       — scrape raw prospects (implemented in each pod)
      4. qualify()    — score a prospect (implemented in each pod)
      5. draft()      — generate outreach via drafter.py
      6. dispatch()   — route all egress through EventDispatcher
    """

    def __init__(self, pod_config: dict):
        """
        pod_config keys:
          slug     (required) — matches NICHE_SLUG from the niche module
          label    — human-readable name
          user_id  — tenant slug for multi-tenant deployments
          run_id   — current scan run ID for error logging
        """
        if "slug" not in pod_config:
            raise ValueError("pod_config must contain 'slug'")

        self.slug    = pod_config["slug"]
        self.label   = pod_config.get("label", self.slug)
        self.user_id = pod_config.get("user_id")
        self.run_id  = pod_config.get("run_id")
        self.config  = pod_config

        # Lazy-init so circular imports and missing deps don't fail at definition time
        self._dnc        = None
        self._dispatcher = None

    # ── Lazy properties ───────────────────────────────────────────────────────

    @property
    def dnc(self):
        if self._dnc is None:
            from core.DNC import DNCScrubber
            self._dnc = DNCScrubber()
        return self._dnc

    @property
    def dispatcher(self):
        if self._dispatcher is None:
            from core.EventDispatcher import EventDispatcher
            self._dispatcher = EventDispatcher()
        return self._dispatcher

    @property
    def cost_save_mode(self) -> bool:
        """
        True when Cost Save Mode is active for this pod.
        In cost-save mode, scan() should use only free platforms (Reddit via PRAW)
        and skip paid Apify actors (LinkedIn, Facebook).
        Fails open (returns False) if the DB is unavailable.
        """
        try:
            from database import get_pod_registry
            row = get_pod_registry(self.slug)
            return bool(row and row.get("cost_save_mode", 0))
        except Exception:
            return False

    # ── Pre-flight check ──────────────────────────────────────────────────────

    def pre_flight_check(self, prospect: dict) -> bool:
        """
        Gate a single prospect through 5 checks before any processing.

        Returns True if clear to proceed, False to abort (silently logged).

        Order matters — cheaper checks first so we abort before hitting the DB:
          1. Minimum required fields (handle + platform must be present)
          2. DNC list check (user-specific + global)
          3. Consent check (consent_granted must not be revoked)
          4. 90-day cooldown in global_registry
          5. Log pre-flight result to scan_runs (via error_logger)
        """
        handle   = (prospect.get("handle") or "").strip()
        platform = (prospect.get("platform") or "").strip()
        name     = prospect.get("name") or handle or "unknown"

        # ── 1. Minimum fields ─────────────────────────────────────────────────
        if not handle or not platform:
            self._log(
                f"pre_flight FAIL [{name}]: missing handle or platform — skipped",
                level="warning",
            )
            return False

        # ── 2. DNC check ──────────────────────────────────────────────────────
        if self.dnc.is_blocked(handle, platform, user_id=self.user_id):
            self._log(f"pre_flight FAIL [{handle}]: on DNC list — aborted")
            return False

        # ── 3. Consent check ─────────────────────────────────────────────────
        if not self.dispatcher.check_consent(self.user_id, handle):
            self._log(f"pre_flight FAIL [{handle}]: consent_granted=False — event dropped")
            return False

        # ── 4. 90-day registry cooldown ───────────────────────────────────────
        try:
            from database import check_registry
            if check_registry(handle, platform):
                self._log(f"pre_flight FAIL [{handle}]: 90-day cooldown active — skipped")
                return False
        except Exception as e:
            # Fail closed — if registry check errors, don't proceed
            self._log(
                f"pre_flight FAIL [{handle}]: registry check error ({e}) — aborted for safety",
                level="warning",
            )
            return False

        return True

    # ── Abstract — must be implemented in each pod ────────────────────────────

    def scan(self) -> list:
        """
        Scrape raw prospects for this niche from all configured platforms.
        Returns a list of raw prospect dicts (not yet scored or deduped).
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement scan()")

    def qualify(self, prospect: dict) -> tuple:
        """
        Score a single prospect.
        Returns (score: int, notes: str).
        """
        raise NotImplementedError(f"{self.__class__.__name__} must implement qualify()")

    # ── Drafting ──────────────────────────────────────────────────────────────

    def draft(self, prospect: dict) -> dict:
        """
        Generate personalised outreach via drafter.py.

        Abort condition: if post_text is shorter than 20 characters, log
        'Insufficient Intel' and return an empty draft. Never hallucinate
        context that isn't present in the prospect's post.
        """
        post_text = (prospect.get("post_text") or "").strip()

        if len(post_text) < 20:
            handle = prospect.get("handle", "?")
            self._log(
                f"draft ABORT [{handle}]: Insufficient Intel — "
                f"post_text is {len(post_text)} chars (minimum 20). "
                "Returning empty draft.",
                level="warning",
            )
            from drafter import build_cta_url
            return {
                "connection_request": "",
                "dm":                 "",
                "call_opener":        "",
                "cta_url":            build_cta_url(prospect.get("signal_phrase", ""), prospect.get("platform", "linkedin")),
                "error":              "Insufficient Intel — post too short to personalise",
            }

        from drafter import draft_message
        return draft_message(prospect)

    # ── Event dispatching ─────────────────────────────────────────────────────

    def dispatch(self, event_type: str, data: dict):
        """
        Route all data egress through EventDispatcher.

        Pods MUST use this method instead of calling external APIs directly.
        EventDispatcher enforces consent, PII hashing, and deduplication
        before routing to the appropriate handler.
        """
        self.dispatcher.dispatch(event_type, data, user_id=self.user_id)

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _log(self, message: str, level: str = "info"):
        """Route logs to error_logger for warnings/errors, stdout for info."""
        prefix = f"[{self.slug}]"
        try:
            from error_logger import log_pipeline_error, WARNING, CRITICAL
            if level in ("warning", "critical"):
                sev = CRITICAL if level == "critical" else WARNING
                log_pipeline_error(self.run_id, "pod", f"{prefix} {message}", sev)
                return
        except Exception:
            pass
        print(f"{prefix} {message}")
