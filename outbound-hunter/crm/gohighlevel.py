"""
crm/gohighlevel.py
GoHighLevel (GHL) CRM adapter.

Required env vars:
  GHL_API_KEY                   — Private Integration API key
                                  (GHL → Settings → Integrations → API Keys)
  GHL_LOCATION_ID               — Sub-account / location ID
  GHL_PIPELINE_ID               — Sales pipeline ID
  GHL_STAGE_1_ID                — Initial stage (New Lead)
  GHL_STAGE_REPLIED_ID
  GHL_STAGE_MEETING_BOOKED_ID
  GHL_STAGE_CALL_COMPLETED_ID
  GHL_STAGE_CLOSED_WON_ID
  GHL_STAGE_CLOSED_LOST_ID

Finding IDs:
  Pipelines & stages: GHL → Settings → Pipelines (hover stage → copy ID from URL)
  Location ID: GHL → Settings → Business Profile → Location ID
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from crm.base import CRMAdapter

_BASE       = "https://rest.gohighlevel.com/v1"
GHL_API_KEY = os.environ.get("GHL_API_KEY", "")
GHL_LOC_ID  = os.environ.get("GHL_LOCATION_ID", "")
GHL_PIPE_ID = os.environ.get("GHL_PIPELINE_ID", "")
GHL_STAGE_1 = os.environ.get("GHL_STAGE_1_ID", "")

_STAGE_ENV = {
    "replied":        "GHL_STAGE_REPLIED_ID",
    "meeting_booked": "GHL_STAGE_MEETING_BOOKED_ID",
    "call_completed": "GHL_STAGE_CALL_COMPLETED_ID",
    "closed_won":     "GHL_STAGE_CLOSED_WON_ID",
    "closed_lost":    "GHL_STAGE_CLOSED_LOST_ID",
}


def _req(method: str, path: str, body=None):
    url  = f"{_BASE}{path}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {GHL_API_KEY}",
            "Content-Type":  "application/json",
            "Version":       "2021-07-28",
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


def _find_contact(email: str) -> str | None:
    encoded = urllib.parse.quote(email, safe="")
    status, resp = _req("GET", f"/contacts/?email={encoded}&locationId={GHL_LOC_ID}")
    if status == 200:
        contacts = resp.get("contacts") or []
        if contacts:
            return contacts[0]["id"]
    return None


def _upsert_contact(prospect: dict) -> str:
    email = (
        prospect.get("email")
        or f"{prospect.get('handle','unknown').lstrip('@').lower()}@outbound.altusflow.ai"
    )
    existing = _find_contact(email)
    if existing:
        return existing

    name  = prospect.get("name") or prospect.get("handle") or "Unknown"
    parts = name.strip().split(" ", 1)
    payload = {
        "locationId": GHL_LOC_ID,
        "email":      email,
        "firstName":  parts[0] if parts else "",
        "lastName":   parts[1] if len(parts) > 1 else "",
        "tags":       ["altusflow", "outbound-hunter", prospect.get("niche", "")],
        "customField": [
            {"id": "altusflow_icp_score",  "value": str(prospect.get("icp_score", ""))},
            {"id": "altusflow_signal",     "value": prospect.get("signal_phrase", "")},
            {"id": "altusflow_source",     "value": prospect.get("platform", "reddit")},
        ],
    }
    status, resp = _req("POST", "/contacts/", payload)
    if status not in (200, 201):
        raise RuntimeError(f"GHL contact create failed ({status}): {resp}")
    return resp.get("contact", {}).get("id") or resp.get("id")


def _create_opportunity(contact_id: str, prospect: dict) -> str:
    name = prospect.get("name") or prospect.get("handle") or "Unknown"
    payload = {
        "pipelineId":      GHL_PIPE_ID,
        "locationId":      GHL_LOC_ID,
        "name":            f"{name} [AltusFlow Outbound]",
        "pipelineStageId": GHL_STAGE_1,
        "status":          "open",
        "contactId":       contact_id,
    }
    status, resp = _req("POST", "/opportunities/", payload)
    if status not in (200, 201):
        raise RuntimeError(f"GHL opportunity create failed ({status}): {resp}")
    return resp.get("opportunity", {}).get("id") or resp.get("id")


def _prospect_note_body(prospect: dict) -> str:
    return (
        f"ALTUSFLOW PROSPECT INTELLIGENCE\n"
        f"{'─' * 34}\n"
        f"Signal: {prospect.get('signal_phrase', '')}\n"
        f"Platform: {prospect.get('platform', 'reddit')}\n"
        f"Niche: {prospect.get('niche', '')}\n"
        f"ICP Score: {prospect.get('icp_score', '')}/10\n\n"
        f"Their post:\n\"{prospect.get('post_text', '')}\"\n"
        f"{'─' * 34}\n"
        f"Outreach drafted:\n{prospect.get('drafted_message', '')}"
    )


def _call_note_body(call: dict) -> str:
    raw_tx = call.get("transcript") or []
    tx = (
        "\n".join(f"{t.get('speaker','?')}: {t.get('text','')}" for t in raw_tx)
        if isinstance(raw_tx, list) else str(raw_tx)
    )
    return (
        f"CALL COMPLETED — {call.get('name', 'Unknown')}\n"
        f"{'─' * 34}\n"
        f"Date: {call.get('created_at', '')}\n"
        f"Duration: {call.get('duration', '')}\n"
        f"Outcome: {call.get('outcome') or call.get('notes', 'Not recorded')}\n"
        f"Summary: {call.get('summary', '')}\n\n"
        f"TRANSCRIPT:\n{tx or 'Not available'}\n"
        f"{'─' * 34}"
    )


class GoHighLevelAdapter(CRMAdapter):

    def push_prospect(self, prospect: dict) -> dict:
        if not GHL_API_KEY:
            return {"ok": False, "error": "GHL_API_KEY not configured"}
        try:
            contact_id = _upsert_contact(prospect)
            deal_id    = _create_opportunity(contact_id, prospect)
            self.add_note(contact_id, _prospect_note_body(prospect))
            return {"ok": True, "contact_id": contact_id, "deal_id": deal_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def move_deal_stage(self, deal_id: str, stage_key: str) -> dict:
        if not GHL_API_KEY:
            return {"ok": False, "error": "GHL_API_KEY not configured"}
        stage_id = os.environ.get(_STAGE_ENV.get(stage_key, ""), "")
        if not stage_id:
            return {"ok": False, "error": f"GHL stage ID for '{stage_key}' not configured"}
        status, resp = _req("PUT", f"/opportunities/{deal_id}", {"pipelineStageId": stage_id})
        if status not in (200, 201):
            return {"ok": False, "error": f"GHL stage move failed ({status}): {resp}"}
        return {"ok": True}

    def push_call(self, contact_id: str, deal_id, call: dict) -> dict:
        if not GHL_API_KEY:
            return {"ok": False, "error": "GHL_API_KEY not configured"}
        result = self.add_note(contact_id, _call_note_body(call))
        if result["ok"] and deal_id:
            self.move_deal_stage(deal_id, "call_completed")
        return result

    def add_note(self, contact_id: str, body: str, deal_id=None) -> dict:
        if not GHL_API_KEY:
            return {"ok": False, "error": "GHL_API_KEY not configured"}
        status, resp = _req("POST", f"/contacts/{contact_id}/notes", {"body": body})
        if status not in (200, 201):
            return {"ok": False, "error": f"GHL note failed ({status}): {resp}"}
        return {"ok": True}

    def update_deal_value(self, deal_id: str, value: float, currency: str = "USD") -> dict:
        if not GHL_API_KEY:
            return {"ok": False, "error": "GHL_API_KEY not configured"}
        status, resp = _req("PUT", f"/opportunities/{deal_id}", {"monetaryValue": value})
        if status not in (200, 201):
            return {"ok": False, "error": f"GHL deal value update failed ({status}): {resp}"}
        return {"ok": True}
