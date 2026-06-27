"""
core/DNC.py
Global Do Not Contact registry.

Checked before any outreach attempt across all pods and all users.
Two tiers:
  user-level  (is_global=0) — specific to one client; only that client is blocked
  global      (is_global=1) — AltusFlow-wide; blocks the handle for ALL clients

Used exclusively through BaseHunter.pre_flight_check(). Pods never call
this directly — they inherit the check through the base class.
"""

from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


class DNCScrubber:
    """
    Checks handles against the dnc_list table before any outreach.

    All methods fail open: if the database is unavailable, the prospect
    is not blocked (better to process a prospect than to silently drop
    every lead because of a DB error). Failures are logged.
    """

    def is_blocked(self, handle: str, platform: str, user_id=None) -> bool:
        """
        Return True if this handle is blocked for outreach.

        Checks in order:
          1. User-specific DNC entry (only blocks for this client)
          2. Global AltusFlow DNC entry (blocks for all clients, is_global=1)

        Note: the 90-day registry cooldown is a separate check in
        BaseHunter.pre_flight_check() via database.check_registry().
        """
        if not handle:
            return False
        try:
            from database import is_on_dnc
            # User-specific DNC
            if user_id and is_on_dnc(handle, platform, user_id=str(user_id)):
                return True
            # Global DNC — checked regardless of user_id
            if is_on_dnc(handle, platform, user_id=None, global_only=True):
                return True
            return False
        except Exception as e:
            print(f"[DNC] WARNING: is_blocked check failed for {handle}: {e} — not blocking")
            return False

    def add_to_dnc(self, handle: str, platform: str, user_id: str,
                   reason: str, added_by: str = "system"):
        """
        Add a handle to the user-specific DNC list.
        Only blocks outreach for the specified user_id/client.
        """
        if not handle or not platform:
            return
        try:
            from database import add_dnc_entry
            add_dnc_entry(
                handle=handle,
                platform=platform,
                user_id=str(user_id),
                reason=reason,
                added_by=added_by,
                is_global=0,
            )
            print(f"[DNC] Added {handle}/{platform} to DNC for user {user_id}: {reason}")
        except Exception as e:
            print(f"[DNC] ERROR: Failed to add {handle} to DNC: {e}")

    def add_to_global_dnc(self, handle: str, platform: str,
                           reason: str, added_by: str = "admin"):
        """
        Add a handle to the global DNC list.
        Blocks outreach for ALL clients across the entire platform.
        Admin-only operation — should only be called after explicit confirmation.
        """
        if not handle or not platform:
            return
        try:
            from database import add_dnc_entry
            add_dnc_entry(
                handle=handle,
                platform=platform,
                user_id=None,
                reason=reason,
                added_by=added_by,
                is_global=1,
            )
            print(f"[DNC] GLOBAL: Added {handle}/{platform} to global DNC: {reason}")
        except Exception as e:
            print(f"[DNC] ERROR: Failed to add {handle} to global DNC: {e}")

    def remove_from_dnc(self, handle: str, platform: str, user_id: str):
        """
        Remove a user-specific DNC entry (e.g., prospect re-consents after opt-out).
        """
        try:
            from database import _get_engine
            from sqlalchemy import text
            with _get_engine().begin() as conn:
                conn.execute(
                    text("DELETE FROM dnc_list WHERE handle=:h AND platform=:p AND user_id=:u AND is_global=0"),
                    {"h": handle, "p": platform, "u": str(user_id)},
                )
            print(f"[DNC] Removed {handle}/{platform} from DNC for user {user_id}")
        except Exception as e:
            print(f"[DNC] ERROR: Failed to remove {handle} from DNC: {e}")
