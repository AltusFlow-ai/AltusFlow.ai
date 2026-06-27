"""
calendly_watcher.py
Polls the Calendly API every 15 minutes to detect new meeting bookings.

When a booking is detected:
  1. Looks up the invitee email in HubSpot to find the contact + deal
  2. Moves the deal to the "Meeting Booked" stage
  3. Finds the matching prospect in our DB (via hs_contact_id)
  4. Generates and saves the pre-call brief automatically

Free-plan approach: personal access token + polling (no webhooks).
Webhooks become available on Calendly Standard ($10/mo) — swap
poll_new_bookings() for a Flask /calendly-webhook route when ready.

Required env vars:
  CALENDLY_TOKEN                  — Calendly personal access token
                                    (Account → Integrations → API & Webhooks)
  HUBSPOT_STAGE_MEETING_BOOKED_ID — HubSpot deal stage ID for "Meeting Booked"
                                    (find via GET /crm/v3/pipelines/deals)
  HUBSPOT_TOKEN                   — already set (shared with hubspot.py)
"""

import os
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone, timedelta

from database import (
    get_calendly_last_checked,
    set_calendly_last_checked,
    is_calendly_event_processed,
    record_calendly_booking,
    get_prospect_by_hs_contact_id,
)
from hubspot import get_contact_by_email, get_contact_deals, move_deal_stage
from brief_generator import generate_and_save

logger = logging.getLogger(__name__)

CALENDLY_TOKEN                  = os.environ.get("CALENDLY_TOKEN", "")
HUBSPOT_STAGE_MEETING_BOOKED_ID = os.environ.get("HUBSPOT_STAGE_MEETING_BOOKED_ID", "")
_CAL_BASE                       = "https://api.calendly.com"


# ── Calendly API ──────────────────────────────────────────────────────────────

def _cal_get(path, params=None):
    """GET request to Calendly API. Returns (status_code, dict)."""
    if not CALENDLY_TOKEN:
        raise RuntimeError("CALENDLY_TOKEN not configured")

    url = f"{_CAL_BASE}{path}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {CALENDLY_TOKEN}",
            "Content-Type":  "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        try:
            err = json.loads(body)
        except Exception:
            err = {"raw": body}
        return e.code, err


def _get_user_uri():
    """Get the current user's Calendly URI (required as a filter param on event queries)."""
    status, resp = _cal_get("/users/me")
    if status != 200:
        raise RuntimeError(f"Calendly /users/me failed ({status}): {resp}")
    return resp["resource"]["uri"]


def _get_events(user_uri, since_iso):
    """
    Get all active scheduled events with start_time >= since_iso.
    Returns list of event dicts from Calendly.
    """
    params = {
        "user":           user_uri,
        "min_start_time": since_iso,
        "status":         "active",
        "count":          100,
        "sort":           "start_time:asc",
    }
    status, resp = _cal_get("/scheduled_events", params)
    if status != 200:
        logger.warning("Calendly /scheduled_events failed (%s): %s", status, resp)
        return []
    return resp.get("collection", [])


def _get_invitees(event_uuid):
    """Get the invitee list for a scheduled event. Returns list of invitee dicts."""
    status, resp = _cal_get(f"/scheduled_events/{event_uuid}/invitees", {"count": 50})
    if status != 200:
        logger.warning("Calendly invitees failed (%s) for %s: %s", status, event_uuid, resp)
        return []
    return resp.get("collection", [])


def _event_uuid(event_uri):
    """Extract UUID from 'https://api.calendly.com/scheduled_events/UUID'."""
    return event_uri.rstrip("/").split("/")[-1]


# ── Booking processor ─────────────────────────────────────────────────────────

def _process_booking(event_uuid, email, name, start_time):
    """
    Process a single Calendly invitee booking end-to-end:
      1. HubSpot contact lookup by email
      2. Deal stage move → "Meeting Booked"
      3. Pre-call brief generation
      4. Record in calendly_bookings table

    Returns {"new": bool, "error": str|None}
    If the email doesn't match any HubSpot contact, we silently record and skip
    (it's likely an inbound booking, not from our outbound pipeline).
    """
    # ── Step 1: HubSpot contact lookup ───────────────────────────────────────
    contact = None
    try:
        contact = get_contact_by_email(email)
    except Exception as e:
        msg = f"HubSpot contact lookup failed for {email}: {e}"
        logger.warning(msg)
        record_calendly_booking(event_uuid, email)
        return {"new": True, "error": msg}

    if not contact:
        # Organic/inbound booking — not from our pipeline
        logger.info(
            "Calendly: no HubSpot contact for %s — not from outbound pipeline, skipping.",
            email,
        )
        record_calendly_booking(event_uuid, email)
        return {"new": False, "error": None}

    contact_id = contact["contact_id"]

    # ── Step 2: Move deal stage ───────────────────────────────────────────────
    deal_id     = None
    stage_moved = False
    if HUBSPOT_STAGE_MEETING_BOOKED_ID:
        try:
            deals = get_contact_deals(contact_id)
            if deals:
                deal_id = deals[0]["deal_id"]
                move_deal_stage(deal_id, HUBSPOT_STAGE_MEETING_BOOKED_ID)
                stage_moved = True
                logger.info(
                    "Calendly: deal %s moved to meeting-booked stage for %s (%s)",
                    deal_id, name, email,
                )
        except Exception as e:
            logger.warning("Calendly: deal stage move failed for %s: %s", email, e)
    else:
        logger.debug(
            "HUBSPOT_STAGE_MEETING_BOOKED_ID not set — deal stage not moved for %s", email
        )

    # ── Step 3: Pre-call brief ────────────────────────────────────────────────
    brief_generated = False
    prospect        = get_prospect_by_hs_contact_id(contact_id)
    if prospect:
        try:
            result = generate_and_save(prospect["id"])
            brief_generated = bool(result.get("ok"))
            if brief_generated:
                logger.info(
                    "Calendly: pre-call brief generated for prospect #%d (%s — %s)",
                    prospect["id"], name, email,
                )
            else:
                logger.warning(
                    "Calendly: brief generation failed for prospect #%d: %s",
                    prospect["id"], result.get("error"),
                )
        except Exception as e:
            logger.warning(
                "Calendly: brief generation exception for prospect #%d: %s",
                prospect["id"], e,
            )
    else:
        logger.info(
            "Calendly: no DB prospect matched hs_contact_id=%s (%s) — "
            "deal moved but no brief generated.",
            contact_id, email,
        )

    # ── Step 4: Record ────────────────────────────────────────────────────────
    record_calendly_booking(
        event_uuid,
        email,
        prospect_id=prospect["id"] if prospect else None,
        deal_id=deal_id,
        brief_generated=brief_generated,
        stage_moved=stage_moved,
    )

    return {"new": True, "error": None}


# ── Main entrypoint ───────────────────────────────────────────────────────────

def poll_new_bookings():
    """
    Check for new Calendly bookings since the last poll.
    Called by scheduler every 15 minutes.

    Returns dict: {"checked": int, "new_bookings": int, "errors": list[str]}
    """
    if not CALENDLY_TOKEN:
        logger.debug("CALENDLY_TOKEN not set — Calendly polling is disabled.")
        return {"checked": 0, "new_bookings": 0, "errors": []}

    now_iso    = datetime.now(timezone.utc).isoformat()
    last_check = get_calendly_last_checked()

    # First run: look back 7 days to pick up any existing bookings
    if not last_check:
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        logger.info("Calendly: first poll — scanning last 7 days.")
    else:
        since = last_check

    logger.info("Calendly poll: events with start_time >= %s", since)

    try:
        user_uri = _get_user_uri()
    except Exception as e:
        logger.error("Calendly: user URI fetch failed: %s", e)
        return {"checked": 0, "new_bookings": 0, "errors": [str(e)]}

    events = _get_events(user_uri, since)
    logger.info("Calendly: %d events in window.", len(events))

    errors       = []
    new_bookings = 0

    for event in events:
        event_uri  = event.get("uri", "")
        if not event_uri:
            continue

        event_uuid = _event_uuid(event_uri)
        start_time = event.get("start_time", "")

        # Skip events we've already fully processed
        if is_calendly_event_processed(event_uuid):
            continue

        invitees = _get_invitees(event_uuid)
        for invitee in invitees:
            email = (invitee.get("email") or "").strip().lower()
            name  = invitee.get("name") or email
            if not email:
                continue

            result = _process_booking(event_uuid, email, name, start_time)
            if result.get("new"):
                new_bookings += 1
            if result.get("error"):
                errors.append(result["error"])

    # Always advance the checkpoint — even if no events were found
    set_calendly_last_checked(now_iso)
    logger.info(
        "Calendly poll done: %d new bookings processed, %d errors.",
        new_bookings, len(errors),
    )
    return {"checked": len(events), "new_bookings": new_bookings, "errors": errors}
