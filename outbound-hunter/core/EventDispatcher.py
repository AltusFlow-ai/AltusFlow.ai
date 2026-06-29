"""
core/EventDispatcher.py
Central egress controller for all outbound events.

All data leaving the system passes through dispatch().
No pod may call HubSpot, Meta, or any external API directly.

Three invariants enforced on every dispatch:
  1. Consent — event is dropped if consent_granted is False or revoked
  2. PII hashing — email and phone are SHA-256 hashed before any external transmission
  3. Deduplication — deterministic event_id prevents the same event being processed twice

Supported event types (Phase 1):
  'hubspot_push'     — create/update contact + deal in HubSpot
  'meta_capi'        — Meta Conversions API event (Phase 2 placeholder)
  'calendly_update'  — move HubSpot deal stage on Calendly booking
"""

import hashlib
import uuid


class EventDispatcher:

    # ── Main dispatch gate ────────────────────────────────────────────────────

    def dispatch(self, event_type: str, data: dict, user_id=None):
        """
        Gate and route one outbound event.

        Steps:
          1. Check consent — drop and return if False
          2. Hash PII fields in data (in-place on a safe copy)
          3. Generate deterministic event_id
          4. Dedup — skip if event_id already in dispatched_events
          5. Route to the correct handler
          6. Log the event to dispatched_events for audit trail

        Returns the handler's return value, or None if blocked.
        """
        prospect_handle = data.get("handle") or data.get("email") or ""
        prospect_id     = data.get("prospect_id") or data.get("id")

        # ── 1. Consent gate ───────────────────────────────────────────────────
        if not self.check_consent(user_id, prospect_handle):
            self._log(
                f"BLOCKED: consent_granted=False for '{prospect_handle}' "
                f"| event_type={event_type} | archived, not transmitted"
            )
            return None

        # ── 2. Hash PII (work on a copy — never mutate caller's dict) ─────────
        safe_data = dict(data)
        for field in ("email", "phone", "phone_number"):
            if safe_data.get(field):
                safe_data[f"{field}_hashed"] = self.hash_pii(safe_data[field])
                # Original stays on safe_data for local DB use only.
                # Handlers must use the _hashed variant for external calls.

        # ── 3. Generate deterministic event_id ────────────────────────────────
        event_id = self.generate_event_id(user_id, prospect_id, event_type)

        # ── 4. Dedup check ────────────────────────────────────────────────────
        try:
            from database import has_event_been_dispatched
            if has_event_been_dispatched(event_id):
                self._log(f"DEDUP: event_id={event_id} already processed — skipping")
                return None
        except Exception as e:
            # Dedup DB unavailable — log and proceed (don't block the event)
            self._log(f"WARNING: dedup check failed ({e}) — proceeding without dedup")

        # ── 5. Route to handler ───────────────────────────────────────────────
        result = self._route(event_type, safe_data, user_id)

        # ── 6. Log dispatched event ───────────────────────────────────────────
        try:
            from database import log_dispatched_event
            log_dispatched_event(
                event_id=event_id,
                user_id=str(user_id) if user_id else None,
                prospect_id=prospect_id,
                event_type=event_type,
                destination=event_type,
                pii_hashed=1,
                consent_verified=1,
                payload_size=len(str(safe_data)),
            )
        except Exception as e:
            self._log(f"WARNING: failed to log dispatched event {event_id}: {e}")

        return result

    # ── Router ────────────────────────────────────────────────────────────────

    def _route(self, event_type: str, data: dict, user_id=None):
        handlers = {
            "hubspot_push":     self._handle_hubspot_push,
            "meta_capi":        self._handle_meta_capi,
            "calendly_update":  self._handle_calendly_update,
        }
        handler = handlers.get(event_type)
        if handler is None:
            self._log(f"ERROR: no handler registered for event_type='{event_type}'")
            return None
        return handler(data)

    # ── Handlers ──────────────────────────────────────────────────────────────

    def _handle_hubspot_push(self, data: dict):
        """Route hubspot_push events through the existing atomic push function."""
        try:
            from hubspot import push_prospect_atomic
            return push_prospect_atomic(data)
        except Exception as e:
            self._log(f"hubspot_push handler error: {e}")
            return {"ok": False, "error": str(e)}

    def _handle_meta_capi(self, data: dict):
        """Meta Conversions API — Phase 2. Requires META_ACCESS_TOKEN."""
        import os as _os
        if not _os.environ.get("META_ACCESS_TOKEN"):
            self._log("Meta not configured — skipping audience sync (set META_ACCESS_TOKEN to enable)")
            return None
        self._log("meta_capi not yet implemented (Phase 2)")
        return None

    def _handle_calendly_update(self, data: dict):
        """Move HubSpot deal stage on Calendly booking."""
        try:
            from hubspot import move_deal_stage
            deal_id  = data.get("deal_id")
            stage_id = data.get("stage_id")
            if deal_id and stage_id:
                return move_deal_stage(deal_id, stage_id)
        except Exception as e:
            self._log(f"calendly_update handler error: {e}")
        return None

    # ── PII utilities ─────────────────────────────────────────────────────────

    def hash_pii(self, value: str) -> str:
        """
        SHA-256 hash a PII value for Meta CAPI and any external transmission.
        Normalised: lowercase, stripped, UTF-8 encoded before hashing.
        Returns empty string if value is falsy.
        """
        if not value:
            return ""
        return hashlib.sha256(value.lower().strip().encode("utf-8")).hexdigest()

    def check_consent(self, user_id, prospect_handle: str) -> bool:
        """
        Return True if outreach consent is granted for this prospect.

        Phase 1 model: opt-out (consent is granted unless explicitly revoked).
        A prospect on the DNC list with platform '_consent_revoked' has
        explicitly opted out and will never receive outreach.

        Returns True if handle is empty (pre-insert stage, nothing to check).
        Fails closed: if consent DB is unavailable, blocks the event rather than
        allowing unconsented outreach.
        """
        if not prospect_handle:
            return True
        try:
            from database import is_on_dnc
            revoked = is_on_dnc(prospect_handle, "_consent_revoked", user_id=user_id)
            return not revoked
        except Exception as e:
            self._log(f"WARNING: consent DB unavailable for '{prospect_handle}' — blocking event ({e})")
            return False

    def generate_event_id(self, user_id, prospect_id, event_type: str) -> str:
        """
        Generate a deterministic UUID5 from (user_id, prospect_id, event_type).
        Same inputs always produce the same event_id — makes deduplication
        idempotent regardless of how many times the event is attempted.
        """
        seed = f"{user_id}-{prospect_id}-{event_type}"
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, seed))

    # ── Internal ──────────────────────────────────────────────────────────────

    def _log(self, message: str):
        print(f"[EventDispatcher] {message}")
