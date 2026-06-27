"""
crm/pipedrive.py
Pipedrive CRM adapter.

Required env vars:
  PIPEDRIVE_API_TOKEN               — API token (Pipedrive → Settings → Personal → API)
  PIPEDRIVE_COMPANY_DOMAIN          — Your Pipedrive subdomain (e.g. "acme" for acme.pipedrive.com)
  PIPEDRIVE_PIPELINE_ID             — Pipeline ID (Pipedrive → Pipeline → URL contains the ID)
  PIPEDRIVE_STAGE_1_ID              — Initial stage ID (New Lead)
  PIPEDRIVE_STAGE_REPLIED_ID
  PIPEDRIVE_STAGE_MEETING_BOOKED_ID
  PIPEDRIVE_STAGE_CALL_COMPLETED_ID
  PIPEDRIVE_STAGE_CLOSED_WON_ID
  PIPEDRIVE_STAGE_CLOSED_LOST_ID
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from crm.base import CRMAdapter

PD_TOKEN  = os.environ.get("PIPEDRIVE_API_TOKEN", "")
PD_DOMAIN = os.environ.get("PIPEDRIVE_COMPANY_DOMAIN", "")
PD_PIPE   = os.environ.get("PIPEDRIVE_PIPELINE_ID", "")
PD_STAGE1 = os.environ.get("PIPEDRIVE_STAGE_1_ID", "")

_STAGE_ENV = {
    "replied":        "PIPEDRIVE_STAGE_REPLIED_ID",
    "meeting_booked": "PIPEDRIVE_STAGE_MEETING_BOOKED_ID",
    "call_completed": "PIPEDRIVE_STAGE_CALL_COMPLETED_ID",
    "closed_won":     "PIPEDRIVE_STAGE_CLOSED_WON_ID",
    "closed_lost":    "PIPEDRIVE_STAGE_CLOSED_LOST_ID",
}


def _base() -> str:
    return f"https://{PD_DOMAIN}.pipedrive.com/v1"


def _req(method: str, path: str, body=None):
    sep = "&" if "?" in path else "?"
    url = f"{_base()}{path}{sep}api_token={PD_TOKEN}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"},
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


def _find_person(email: str) -> str | None:
    encoded = urllib.parse.quote(email, safe="")
    status, resp = _req("GET", f"/persons/search?term={encoded}&fields=email&exact_match=true")
    if status == 200:
        items = (resp.get("data") or {}).get("items") or []
        if items:
            return str(items[0]["item"]["id"])
    return None


def _upsert_person(prospect: dict) -> str:
    email = (
        prospect.get("email")
        or f"{prospect.get('handle','unknown').lstrip('@').lower()}@outbound.altusflow.ai"
    )
    existing = _find_person(email)
    if existing:
        return existing

    name = prospect.get("name") or prospect.get("handle") or "Unknown"
    status, resp = _req("POST", "/persons", {
        "name":  name,
        "email": [{"value": email, "primary": True}],
    })
    if status not in (200, 201) or not resp.get("success"):
        raise RuntimeError(f"Pipedrive person create failed ({status}): {resp}")
    return str(resp["data"]["id"])


def _create_deal(person_id: str, prospect: dict) -> str:
    name = prospect.get("name") or prospect.get("handle") or "Unknown"
    payload: dict = {
        "title":      f"{name} [AltusFlow Outbound]",
        "person_id":  int(person_id),
        "stage_id":   int(PD_STAGE1) if PD_STAGE1 else None,
        "pipeline_id": int(PD_PIPE) if PD_PIPE else None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    status, resp = _req("POST", "/deals", payload)
    if status not in (200, 201) or not resp.get("success"):
        raise RuntimeError(f"Pipedrive deal create failed ({status}): {resp}")
    return str(resp["data"]["id"])


def _add_pd_note(person_id: str, deal_id: str | None, body: str):
    payload: dict = {
        "content":   body,
        "person_id": int(person_id),
    }
    if deal_id:
        payload["deal_id"] = int(deal_id)
    status, resp = _req("POST", "/notes", payload)
    if status not in (200, 201) or not resp.get("success"):
        raise RuntimeError(f"Pipedrive note failed ({status}): {resp}")


def _prospect_note(prospect: dict) -> str:
    return (
        f"<b>ALTUSFLOW PROSPECT INTELLIGENCE</b><br>"
        f"Signal: {prospect.get('signal_phrase', '')}<br>"
        f"Platform: {prospect.get('platform', 'reddit')}<br>"
        f"Niche: {prospect.get('niche', '')}<br>"
        f"ICP Score: {prospect.get('icp_score', '')}/10<br><br>"
        f"<i>Their post:</i><br>"
        f"\"{prospect.get('post_text', '')}\""
    )


def _call_note(call: dict) -> str:
    raw_tx = call.get("transcript") or []
    tx = (
        "<br>".join(f"<b>{t.get('speaker','?')}:</b> {t.get('text','')}" for t in raw_tx)
        if isinstance(raw_tx, list) else str(raw_tx)
    )
    return (
        f"<b>CALL COMPLETED — {call.get('name','Unknown')}</b><br>"
        f"Duration: {call.get('duration','')}<br>"
        f"Outcome: {call.get('outcome') or call.get('notes','Not recorded')}<br>"
        f"Summary: {call.get('summary','')}<br><br>"
        f"<b>Transcript:</b><br>{tx or 'Not available'}"
    )


class PipedriveAdapter(CRMAdapter):

    def push_prospect(self, prospect: dict) -> dict:
        if not PD_TOKEN or not PD_DOMAIN:
            return {"ok": False, "error": "PIPEDRIVE_API_TOKEN or PIPEDRIVE_COMPANY_DOMAIN not configured"}
        try:
            person_id = _upsert_person(prospect)
            deal_id   = _create_deal(person_id, prospect)
            _add_pd_note(person_id, deal_id, _prospect_note(prospect))
            return {"ok": True, "contact_id": person_id, "deal_id": deal_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def move_deal_stage(self, deal_id: str, stage_key: str) -> dict:
        if not PD_TOKEN or not PD_DOMAIN:
            return {"ok": False, "error": "Pipedrive not configured"}
        stage_id = os.environ.get(_STAGE_ENV.get(stage_key, ""), "")
        if not stage_id:
            return {"ok": False, "error": f"Pipedrive stage ID for '{stage_key}' not configured"}
        status, resp = _req("PATCH", f"/deals/{deal_id}", {"stage_id": int(stage_id)})
        if status not in (200, 201) or not resp.get("success"):
            return {"ok": False, "error": f"Pipedrive stage move failed ({status}): {resp}"}
        return {"ok": True}

    def push_call(self, contact_id: str, deal_id, call: dict) -> dict:
        if not PD_TOKEN or not PD_DOMAIN:
            return {"ok": False, "error": "Pipedrive not configured"}
        try:
            _add_pd_note(contact_id, deal_id, _call_note(call))
            if deal_id:
                self.move_deal_stage(deal_id, "call_completed")
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def add_note(self, contact_id: str, body: str, deal_id=None) -> dict:
        if not PD_TOKEN or not PD_DOMAIN:
            return {"ok": False, "error": "Pipedrive not configured"}
        try:
            _add_pd_note(contact_id, deal_id, body)
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def update_deal_value(self, deal_id: str, value: float, currency: str = "USD") -> dict:
        if not PD_TOKEN or not PD_DOMAIN:
            return {"ok": False, "error": "Pipedrive not configured"}
        status, resp = _req("PATCH", f"/deals/{deal_id}", {"value": value, "currency": currency})
        if status not in (200, 201) or not resp.get("success"):
            return {"ok": False, "error": f"Pipedrive deal value update failed ({status})"}
        return {"ok": True}
