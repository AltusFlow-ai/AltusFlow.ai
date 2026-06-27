"""
crm/salesforce.py
Salesforce CRM adapter.

Salesforce requires OAuth 2.0 (Connected App). Setup:
  1. Salesforce → Setup → App Manager → New Connected App
  2. Enable OAuth, add scope: api, refresh_token
  3. Set SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET
  4. Authenticate once via username/password flow (or web OAuth) to get refresh token
  5. Set SALESFORCE_REFRESH_TOKEN and SALESFORCE_INSTANCE_URL

Required env vars:
  SALESFORCE_CLIENT_ID
  SALESFORCE_CLIENT_SECRET
  SALESFORCE_REFRESH_TOKEN       — long-lived refresh token from initial OAuth flow
  SALESFORCE_INSTANCE_URL        — e.g. https://yourorg.my.salesforce.com
  SALESFORCE_OPPORTUNITY_STAGE_1 — e.g. "Prospecting"
  SALESFORCE_STAGE_REPLIED       — e.g. "Contacted"
  SALESFORCE_STAGE_MEETING_BOOKED — e.g. "Meeting Booked"
  SALESFORCE_STAGE_CALL_COMPLETED — e.g. "Discovery Complete"
  SALESFORCE_STAGE_CLOSED_WON    — e.g. "Closed Won"
  SALESFORCE_STAGE_CLOSED_LOST   — e.g. "Closed Lost"

Note: Salesforce stage names are string labels, not IDs.
"""

import os
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from crm.base import CRMAdapter

SF_CLIENT_ID     = os.environ.get("SALESFORCE_CLIENT_ID", "")
SF_CLIENT_SECRET = os.environ.get("SALESFORCE_CLIENT_SECRET", "")
SF_REFRESH_TOKEN = os.environ.get("SALESFORCE_REFRESH_TOKEN", "")
SF_INSTANCE_URL  = os.environ.get("SALESFORCE_INSTANCE_URL", "").rstrip("/")

_STAGE_ENV = {
    "replied":        "SALESFORCE_STAGE_REPLIED",
    "meeting_booked": "SALESFORCE_STAGE_MEETING_BOOKED",
    "call_completed": "SALESFORCE_STAGE_CALL_COMPLETED",
    "closed_won":     "SALESFORCE_STAGE_CLOSED_WON",
    "closed_lost":    "SALESFORCE_STAGE_CLOSED_LOST",
}

_access_token_cache: dict = {}


def _get_access_token() -> str:
    """Refresh the Salesforce access token using the stored refresh token."""
    if not SF_CLIENT_ID or not SF_CLIENT_SECRET or not SF_REFRESH_TOKEN:
        raise RuntimeError("Salesforce OAuth credentials not configured")
    payload = urllib.parse.urlencode({
        "grant_type":    "refresh_token",
        "client_id":     SF_CLIENT_ID,
        "client_secret": SF_CLIENT_SECRET,
        "refresh_token": SF_REFRESH_TOKEN,
    }).encode()
    req = urllib.request.Request(
        "https://login.salesforce.com/services/oauth2/token",
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.loads(r.read())
    return data["access_token"]


def _sf_req(method: str, path: str, body=None) -> tuple[int, dict]:
    token = _get_access_token()
    url   = f"{SF_INSTANCE_URL}/services/data/v57.0{path}"
    data  = json.dumps(body).encode() if body else None
    req   = urllib.request.Request(
        url, data=data,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type":  "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        try:
            err_body = json.loads(body_text)
        except Exception:
            err_body = {"raw": body_text}
        return e.code, err_body


def _find_contact(email: str) -> str | None:
    encoded = urllib.parse.quote(f"SELECT Id FROM Contact WHERE Email = '{email}' LIMIT 1")
    status, resp = _sf_req("GET", f"/query?q={encoded}")
    if status == 200 and resp.get("records"):
        return resp["records"][0]["Id"]
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
        "FirstName":  parts[0] if parts else "",
        "LastName":   parts[1] if len(parts) > 1 else name,
        "Email":      email,
        "LeadSource": "AltusFlow Outbound",
        "Description": f"ICP Score: {prospect.get('icp_score','')}/10\nSignal: {prospect.get('signal_phrase','')}",
    }
    status, resp = _sf_req("POST", "/sobjects/Contact", payload)
    if status not in (200, 201):
        raise RuntimeError(f"Salesforce contact create failed ({status}): {resp}")
    return resp["id"]


def _create_opportunity(contact_id: str, prospect: dict) -> str:
    name       = prospect.get("name") or prospect.get("handle") or "Unknown"
    close_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stage1     = os.environ.get("SALESFORCE_OPPORTUNITY_STAGE_1", "Prospecting")
    payload    = {
        "Name":        f"{name} [AltusFlow Outbound]",
        "StageName":   stage1,
        "CloseDate":   close_date,
        "Description": prospect.get("signal_phrase", ""),
        "LeadSource":  "AltusFlow Outbound",
    }
    status, resp = _sf_req("POST", "/sobjects/Opportunity", payload)
    if status not in (200, 201):
        raise RuntimeError(f"Salesforce opportunity create failed ({status}): {resp}")
    opp_id = resp["id"]
    # Associate contact to opportunity via OpportunityContactRole
    _sf_req("POST", "/sobjects/OpportunityContactRole", {
        "OpportunityId": opp_id,
        "ContactId":     contact_id,
        "IsPrimary":     True,
    })
    return opp_id


class SalesforceAdapter(CRMAdapter):

    def push_prospect(self, prospect: dict) -> dict:
        if not SF_INSTANCE_URL:
            return {"ok": False, "error": "SALESFORCE_INSTANCE_URL not configured"}
        try:
            contact_id = _upsert_contact(prospect)
            deal_id    = _create_opportunity(contact_id, prospect)
            self.add_note(contact_id, self._prospect_note(prospect), deal_id)
            return {"ok": True, "contact_id": contact_id, "deal_id": deal_id}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def move_deal_stage(self, deal_id: str, stage_key: str) -> dict:
        if not SF_INSTANCE_URL:
            return {"ok": False, "error": "Salesforce not configured"}
        stage_name = os.environ.get(_STAGE_ENV.get(stage_key, ""), "")
        if not stage_name:
            return {"ok": False, "error": f"Salesforce stage name for '{stage_key}' not configured"}
        status, resp = _sf_req("PATCH", f"/sobjects/Opportunity/{deal_id}", {"StageName": stage_name})
        if status not in (200, 201, 204):
            return {"ok": False, "error": f"Salesforce stage move failed ({status}): {resp}"}
        return {"ok": True}

    def push_call(self, contact_id: str, deal_id, call: dict) -> dict:
        if not SF_INSTANCE_URL:
            return {"ok": False, "error": "Salesforce not configured"}
        result = self.add_note(contact_id, self._call_note(call), deal_id)
        if result["ok"] and deal_id:
            self.move_deal_stage(deal_id, "call_completed")
        return result

    def add_note(self, contact_id: str, body: str, deal_id=None) -> dict:
        if not SF_INSTANCE_URL:
            return {"ok": False, "error": "Salesforce not configured"}
        payload: dict = {
            "ParentId":    contact_id,
            "Title":       "AltusFlow Note",
            "Body":        body,
            "IsPrivate":   False,
        }
        status, resp = _sf_req("POST", "/sobjects/Note", payload)
        if status not in (200, 201):
            return {"ok": False, "error": f"Salesforce note failed ({status}): {resp}"}
        return {"ok": True}

    def _prospect_note(self, prospect: dict) -> str:
        return (
            f"ALTUSFLOW PROSPECT INTELLIGENCE\n"
            f"Signal: {prospect.get('signal_phrase','')}\n"
            f"Platform: {prospect.get('platform','reddit')}\n"
            f"ICP Score: {prospect.get('icp_score','')}/10\n\n"
            f"Their post:\n\"{prospect.get('post_text','')}\"\n\n"
            f"Outreach drafted:\n{prospect.get('drafted_message','')}"
        )

    def _call_note(self, call: dict) -> str:
        raw_tx = call.get("transcript") or []
        tx = (
            "\n".join(f"{t.get('speaker','?')}: {t.get('text','')}" for t in raw_tx)
            if isinstance(raw_tx, list) else str(raw_tx)
        )
        return (
            f"CALL COMPLETED — {call.get('name','Unknown')}\n"
            f"Duration: {call.get('duration','')}\n"
            f"Outcome: {call.get('outcome') or call.get('notes','Not recorded')}\n"
            f"Summary: {call.get('summary','')}\n\n"
            f"TRANSCRIPT:\n{tx or 'Not available'}"
        )
