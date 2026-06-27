"""
crm/hubspot_adapter.py
HubSpot CRM adapter — wraps existing hubspot.py functions.
No new env vars needed beyond what hubspot.py already uses.
"""
from crm.base import CRMAdapter
from hubspot import (
    push_prospect_atomic,
    push_deal_stage_by_key,
    push_call_note,
    _hs_request,
)
from datetime import datetime, timezone


class HubSpotAdapter(CRMAdapter):

    def push_prospect(self, prospect: dict) -> dict:
        return push_prospect_atomic(prospect)

    def move_deal_stage(self, deal_id: str, stage_key: str) -> dict:
        return push_deal_stage_by_key(deal_id, stage_key)

    def push_call(self, contact_id: str, deal_id, call: dict) -> dict:
        return push_call_note(contact_id, deal_id, call)

    def add_note(self, contact_id: str, body: str, deal_id=None) -> dict:
        status, resp = _hs_request("POST", "/crm/v3/objects/notes", {
            "properties": {
                "hs_note_body": body,
                "hs_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
            },
            "associations": [{
                "to":    {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 202}]
            }]
        })
        if status not in (200, 201):
            return {"ok": False, "error": f"HubSpot note failed ({status}): {resp}"}
        return {"ok": True}
