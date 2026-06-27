"""
crm/base.py
Abstract CRM adapter interface. All adapters implement these five methods.
Every method returns {"ok": True, ...} or {"ok": False, "error": "..."}.
"""


class CRMAdapter:

    def push_prospect(self, prospect: dict) -> dict:
        """
        Atomically push a prospect: upsert contact + create deal + add intelligence note.
        Returns {"ok": True, "contact_id": str, "deal_id": str}.
        """
        return {"ok": False, "error": "not implemented"}

    def move_deal_stage(self, deal_id: str, stage_key: str) -> dict:
        """
        Advance a deal/opportunity to a new stage.
        stage_key: replied | meeting_booked | call_completed | closed_won | closed_lost
        """
        return {"ok": False, "error": "not implemented"}

    def push_call(self, contact_id: str, deal_id: str | None, call: dict) -> dict:
        """
        Log a completed call: add transcript + outcome note, move deal to call_completed.
        call dict: name, duration, outcome, summary, transcript (list|str), created_at
        """
        return {"ok": False, "error": "not implemented"}

    def add_note(self, contact_id: str, body: str, deal_id: str | None = None) -> dict:
        """Add a plain-text note to a contact (and optionally a deal)."""
        return {"ok": False, "error": "not implemented"}

    def update_deal_value(self, deal_id: str, value: float, currency: str = "USD") -> dict:
        """Update the monetary value on a deal. Optional — adapters may no-op."""
        return {"ok": True, "skipped": True}


class NullAdapter(CRMAdapter):
    """No-op adapter: used when CRM_PROVIDER=none or env var is missing."""

    def push_prospect(self, prospect):
        return {"ok": True, "contact_id": None, "deal_id": None, "crm": "none"}

    def move_deal_stage(self, deal_id, stage_key):
        return {"ok": True, "crm": "none"}

    def push_call(self, contact_id, deal_id, call):
        return {"ok": True, "crm": "none"}

    def add_note(self, contact_id, body, deal_id=None):
        return {"ok": True, "crm": "none"}
