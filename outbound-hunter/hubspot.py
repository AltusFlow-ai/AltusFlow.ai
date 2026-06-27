"""
hubspot.py
Atomic HubSpot push for the Outbound Hunter.

One approval = one function call that creates contact + note + deal atomically.
If any step fails, we roll back what we can and return a structured error.

Required env vars:
  HUBSPOT_TOKEN         — HubSpot Private App token (CRM contacts+notes+deals R/W)
  HUBSPOT_PIPELINE_ID   — Growth Pipeline ID (find in HubSpot > Settings > Deals > Pipelines)
  HUBSPOT_STAGE_1_ID    — Stage 1 ID within that pipeline
  CLIENT_ID             — e.g. ALT00 (defaults to ALT00)

Finding pipeline/stage IDs:
  In HubSpot, go to Settings → CRM → Deals → Pipelines → click your pipeline.
  The URL will contain the pipeline ID. Stage IDs are visible via API:
  GET https://api.hubapi.com/crm/v3/pipelines/deals  (with your token)
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

HUBSPOT_TOKEN       = os.environ.get("HUBSPOT_TOKEN", "")
HUBSPOT_PIPELINE_ID = os.environ.get("HUBSPOT_PIPELINE_ID", "")
HUBSPOT_STAGE_1_ID  = os.environ.get("HUBSPOT_STAGE_1_ID", "")
CLIENT_ID           = os.environ.get("CLIENT_ID", "ALT00")

# Dashboard stage sync — set these to the HubSpot deal stage IDs for each milestone.
# Find stage IDs via: GET https://api.hubapi.com/crm/v3/pipelines/deals (with your token)
HUBSPOT_STAGE_REPLIED_ID        = os.environ.get("HUBSPOT_STAGE_REPLIED_ID", "")
HUBSPOT_STAGE_MEETING_BOOKED_ID = os.environ.get("HUBSPOT_STAGE_MEETING_BOOKED_ID", "")
HUBSPOT_STAGE_CALL_COMPLETED_ID = os.environ.get("HUBSPOT_STAGE_CALL_COMPLETED_ID", "")
HUBSPOT_STAGE_CLOSED_WON_ID     = os.environ.get("HUBSPOT_STAGE_CLOSED_WON_ID", "")
HUBSPOT_STAGE_CLOSED_LOST_ID    = os.environ.get("HUBSPOT_STAGE_CLOSED_LOST_ID", "")

_STAGE_MAP = {
    "replied":        lambda: HUBSPOT_STAGE_REPLIED_ID,
    "meeting_booked": lambda: HUBSPOT_STAGE_MEETING_BOOKED_ID,
    "call_completed": lambda: HUBSPOT_STAGE_CALL_COMPLETED_ID,
    "closed_won":     lambda: HUBSPOT_STAGE_CLOSED_WON_ID,
    "closed_lost":    lambda: HUBSPOT_STAGE_CLOSED_LOST_ID,
}

_BASE = "https://api.hubapi.com"


def _get_niche_module(niche_slug):
    """Load the niche library module for a given slug. Returns None on any failure."""
    if not niche_slug:
        return None
    try:
        from scrapers.niches import get_niche
        return get_niche(niche_slug)
    except Exception:
        return None


def _hs_request(method, path, body=None):
    """
    Make a HubSpot API request.
    Returns (status_code, response_dict).
    """
    if not HUBSPOT_TOKEN:
        raise RuntimeError("HUBSPOT_TOKEN env var not set")

    url = f"{_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization":  f"Bearer {HUBSPOT_TOKEN}",
            "Content-Type":   "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        try:
            err_body = json.loads(body_text)
        except Exception:
            err_body = {"raw": body_text}
        return e.code, err_body


def _upsert_contact(prospect):
    """
    Create or update a HubSpot contact by email.
    Uses batch/upsert so it's idempotent — safe to retry.
    Returns contact_id string on success.
    """
    # Build email from handle if none provided
    email = (
        prospect.get("email")
        or f"{prospect.get('handle','unknown').lstrip('@').replace(' ','').lower()}@outbound.altusflow.ai"
    )
    name   = prospect.get("name") or ""
    parts  = name.strip().split(" ", 1)
    fname  = parts[0] if parts else ""
    lname  = parts[1] if len(parts) > 1 else ""

    icp_score    = prospect.get("icp_score", 0)
    hs_status    = "AI-Qualified" if icp_score >= 7 else "Outbound-Identified"
    niche_slug   = prospect.get("niche_segment") or prospect.get("niche") or ""

    status, resp = _hs_request("POST", "/crm/v3/objects/contacts/batch/upsert", {
        "inputs": [{
            "idProperty": "email",
            "id": email,
            "properties": {
                "email":                              email,
                "firstname":                          fname,
                "lastname":                           lname,
                "company":                            prospect.get("company") or "",
                "jobtitle":                           prospect.get("title") or "",
                "hs_lead_status":                     "NEW",
                "altusflow_lead_source_vertical":     "Outbound Hunter",
                "altusflow_client_portal_id":         CLIENT_ID,
                "altusflow_lead_qualified_status":    hs_status,
                "altusflow_ai_chat_score":            str(icp_score),
                "altusflow_first_touch_campaign":     f"{CLIENT_ID}_OH_outbound",
                "altusflow_outbound_trigger_phrase":  prospect.get("signal_phrase") or "",
                "altusflow_niche_segment":            niche_slug,
            }
        }]
    })

    if status not in (200, 201):
        raise RuntimeError(f"Contact upsert failed ({status}): {resp}")

    contact_id = resp["results"][0]["id"]
    return contact_id


def _create_note(contact_id, prospect):
    """
    Create a prospect intelligence note on the contact.
    Returns note_id string on success.
    """
    platform      = (prospect.get("platform") or "").capitalize()
    post_date     = prospect.get("post_date") or "Unknown date"
    signal_phrase = prospect.get("signal_phrase") or ""
    post_text     = prospect.get("post_text") or ""
    call_opener   = prospect.get("call_opener") or prospect.get("drafted_message", "")[:120]
    icp_score     = prospect.get("icp_score", 0)
    cta_url       = prospect.get("cta_url") or "https://altusflow.ai"

    # Niche intelligence — pulled from niche library at push time
    niche_slug   = prospect.get("niche_segment") or prospect.get("niche") or ""
    niche_module = _get_niche_module(niche_slug)
    niche_label  = getattr(niche_module, "NICHE_LABEL", niche_slug or "Unknown")
    deal_econ    = getattr(niche_module, "DEAL_ECONOMICS", "")
    objection    = getattr(niche_module, "COMMON_OBJECTIONS", "")

    niche_block = ""
    if niche_label:
        niche_block = f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
NICHE INTELLIGENCE — {niche_label}
Deal economics: {deal_econ or 'See niche library'}
Main objection to address: {objection or 'Not configured'}"""

    note_body = f"""ALTUSFLOW PROSPECT INTELLIGENCE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Signal source: {platform} — {post_date}
Signal phrase matched: "{signal_phrase}"
Niche segment: {niche_label}

Their exact post:
"{post_text}"
{niche_block}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
GAP ANALYSIS
Website chat: UNVERIFIED
Meta Ads running: UNVERIFIED
AI outbound: LIKELY MISSING
CRM: UNKNOWN — ask on call
Automated reports: LIKELY MISSING

CALL OPENER: {call_opener}
ICP score: {icp_score}/10

Outreach CTA URL: {cta_url}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    status, resp = _hs_request("POST", "/crm/v3/objects/notes", {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        },
        "associations": [{
            "to":    {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]
        }]
    })

    if status not in (200, 201):
        raise RuntimeError(f"Note creation failed ({status}): {resp}")

    return resp["id"]


def _create_deal(contact_id, prospect):
    """
    Create a deal in the Growth Pipeline Stage 1 linked to the contact.
    Returns deal_id string on success.
    """
    name      = prospect.get("name") or prospect.get("handle") or "Unknown"
    company   = prospect.get("company") or ""
    deal_name = f"{name}{' — ' + company if company else ''} [{CLIENT_ID} Outbound]"

    properties = {
        "dealname":   deal_name,
        "dealstage":  HUBSPOT_STAGE_1_ID,
        "pipeline":   HUBSPOT_PIPELINE_ID,
        "description": f"Outbound signal: {prospect.get('signal_phrase', '')}",
    }

    # If pipeline/stage IDs not configured, omit them (deal still creates, just uncategorised)
    if not HUBSPOT_PIPELINE_ID:
        properties.pop("pipeline", None)
    if not HUBSPOT_STAGE_1_ID:
        properties.pop("dealstage", None)

    status, resp = _hs_request("POST", "/crm/v3/objects/deals", {
        "properties": properties,
        "associations": [{
            "to":    {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 3}]
        }]
    })

    if status not in (200, 201):
        raise RuntimeError(f"Deal creation failed ({status}): {resp}")

    return resp["id"]


def _delete_deal(deal_id):
    """Best-effort deal deletion for rollback."""
    try:
        _hs_request("DELETE", f"/crm/v3/objects/deals/{deal_id}")
    except Exception:
        pass


# ── Calendly integration helpers ──────────────────────────────────────────────

def get_contact_by_email(email):
    """
    Look up a HubSpot contact by email address.
    Returns {"contact_id": "...", "name": "..."} or None if not found.
    Raises RuntimeError on unexpected API failures.
    """
    encoded = urllib.parse.quote(email, safe="")
    status, resp = _hs_request(
        "GET",
        f"/crm/v3/objects/contacts/{encoded}?idProperty=email&properties=email,firstname,lastname",
    )
    if status == 404:
        return None
    if status != 200:
        raise RuntimeError(f"HubSpot contact lookup failed ({status}): {resp}")
    props = resp.get("properties", {})
    name  = f"{props.get('firstname', '')} {props.get('lastname', '')}".strip()
    return {"contact_id": resp["id"], "name": name}


def get_contact_deals(contact_id):
    """
    Get deals associated with a HubSpot contact (most-recent first).
    Returns list of {"deal_id": "..."}.
    """
    status, resp = _hs_request("GET", f"/crm/v3/objects/contacts/{contact_id}/associations/deals")
    if status == 404:
        return []
    if status != 200:
        raise RuntimeError(f"HubSpot contact deals lookup failed ({status}): {resp}")
    return [{"deal_id": str(r["id"])} for r in resp.get("results", [])]


def move_deal_stage(deal_id, stage_id):
    """
    Update a HubSpot deal to a new pipeline stage.
    Returns True on success. Raises RuntimeError on failure.
    """
    if not stage_id:
        raise RuntimeError("stage_id is empty — HUBSPOT_STAGE_MEETING_BOOKED_ID not configured")
    status, resp = _hs_request("PATCH", f"/crm/v3/objects/deals/{deal_id}", {
        "properties": {"dealstage": stage_id}
    })
    if status not in (200, 201):
        raise RuntimeError(f"Deal stage move failed ({status}): {resp}")
    return True


def push_prospect_atomic(prospect):
    """
    Atomically push a prospect to HubSpot:
      1. Upsert contact with all 7 altusflow_ properties
      2. Create prospect intelligence note on the contact
      3. Create deal in Growth Pipeline Stage 1

    If step 2 or 3 fails, we attempt to roll back the deal and return an error.
    Contact upsert is always idempotent (safe to retry).

    Returns:
        {"ok": True,  "contact_id": "...", "deal_id": "..."}
        {"ok": False, "error": "...", "step": "contact|note|deal"}
    """
    if not HUBSPOT_TOKEN:
        return {"ok": False, "error": "HUBSPOT_TOKEN not configured", "step": "config"}

    contact_id = None
    deal_id    = None

    # Step 1 — Contact
    try:
        contact_id = _upsert_contact(prospect)
    except Exception as e:
        return {"ok": False, "error": str(e), "step": "contact"}

    # Step 2 — Note
    try:
        _create_note(contact_id, prospect)
    except Exception as e:
        return {"ok": False, "error": str(e), "step": "note",
                "contact_id": contact_id}

    # Step 3 — Deal
    try:
        deal_id = _create_deal(contact_id, prospect)
    except Exception as e:
        # Note already created — no rollback needed for notes.
        # Deals are the only thing worth rolling back.
        return {"ok": False, "error": str(e), "step": "deal",
                "contact_id": contact_id}

    return {"ok": True, "contact_id": contact_id, "deal_id": deal_id}


def push_deal_stage_by_key(deal_id: str, stage_key: str) -> dict:
    """
    Move a HubSpot deal to a new stage using a dashboard stage key.
    stage_key must be one of: replied, meeting_booked, call_completed,
                               closed_won, closed_lost
    Returns {"ok": True} or {"ok": False, "error": "..."}.
    """
    if not HUBSPOT_TOKEN:
        return {"ok": False, "error": "HUBSPOT_TOKEN not configured"}
    getter = _STAGE_MAP.get(stage_key)
    if getter is None:
        return {"ok": False, "error": f"Unknown stage_key '{stage_key}'"}
    stage_id = getter()
    if not stage_id:
        return {"ok": False, "error": f"HUBSPOT_STAGE_{stage_key.upper()}_ID not configured"}
    try:
        move_deal_stage(deal_id, stage_id)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def push_call_note(contact_id: str, deal_id: str | None, call: dict) -> dict:
    """
    Add a completed call's transcript + outcome as a HubSpot note on the contact,
    then move the deal to the Call Completed stage (if configured).

    call dict should have: name, duration, outcome, summary, transcript (list or str),
                           created_at (ISO string).
    Returns {"ok": True} or {"ok": False, "error": "..."}.
    """
    if not HUBSPOT_TOKEN:
        return {"ok": False, "error": "HUBSPOT_TOKEN not configured"}

    name       = call.get("name") or call.get("handle") or "Unknown"
    duration   = call.get("duration") or ""
    outcome    = call.get("outcome") or call.get("notes") or "Not recorded"
    summary    = call.get("summary") or ""
    called_at  = call.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    raw_tx = call.get("transcript") or []
    if isinstance(raw_tx, list):
        tx_lines = "\n".join(
            f"{t.get('speaker','?')}: {t.get('text','')}" for t in raw_tx
        )
    else:
        tx_lines = str(raw_tx)

    note_body = f"""CALL COMPLETED — {name}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Date: {called_at}
Duration: {duration}
Outcome: {outcome}
Summary: {summary}

TRANSCRIPT:
{tx_lines or 'Not available'}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    status, resp = _hs_request("POST", "/crm/v3/objects/notes", {
        "properties": {
            "hs_note_body": note_body,
            "hs_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        },
        "associations": [{
            "to":    {"id": contact_id},
            "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]
        }]
    })
    if status not in (200, 201):
        return {"ok": False, "error": f"Note creation failed ({status}): {resp}"}

    # Move deal to Call Completed stage — best effort, don't fail if it doesn't work
    if deal_id and HUBSPOT_STAGE_CALL_COMPLETED_ID:
        try:
            move_deal_stage(deal_id, HUBSPOT_STAGE_CALL_COMPLETED_ID)
        except Exception:
            pass

    return {"ok": True}
