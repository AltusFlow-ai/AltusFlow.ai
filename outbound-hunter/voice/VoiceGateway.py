"""
voice/VoiceGateway.py
Inbound voice handling for AltusFlow — Morgan AI Receptionist.

Inbound only. No outbound voice calling. No phone pool rotation.
No pitch-page-visit-to-call automation.

Flow:
  Prospect calls AltusFlow Twilio number
  → Vapi receives call (Twilio number registered in Vapi dashboard)
  → Vapi POSTs to /webhooks/voice/inbound
  → VoiceGateway.handle_inbound_call() returns Morgan's assistant config
  → Vapi runs the call using Morgan's soul + FAQ
  → Vapi POSTs to /webhooks/voice/call-ended with transcript + outcome
  → VoiceGateway.handle_call_ended() stores transcript, notifies closer if booked

Required env vars:
  VAPI_API_KEY              — console.vapi.ai → Account → API Keys
  TWILIO_ALTUSFLOW_NUMBER   — your AltusFlow inbound Twilio number e.g. +15551234567
  CLOSER_WEBHOOK_URL        — Slack/Make/Zapier URL for closer notifications (optional)
  CLOSER_EMAIL              — backup notification email (optional)
  CLOSER_NAME               — used in HubSpot task assignment
  HUBSPOT_TOKEN             — for deal stage moves + task creation
  HUBSPOT_STAGE_MEETING_BOOKED_ID — deal stage to move to when Morgan books a call
"""

import os
import json
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone

_VOICE_DIR = os.path.dirname(os.path.abspath(__file__))
_SOUL_PATH = os.path.join(_VOICE_DIR, "soul_concierge.md")
_FAQ_PATH  = os.path.join(_VOICE_DIR, "faq.md")

VAPI_API_KEY    = os.environ.get("VAPI_API_KEY", "")
CLOSER_WEBHOOK  = os.environ.get("CLOSER_WEBHOOK_URL", "")
CLOSER_EMAIL    = os.environ.get("CLOSER_EMAIL", "")
CLOSER_NAME     = os.environ.get("CLOSER_NAME", "Growth Specialist")
HUBSPOT_TOKEN   = os.environ.get("HUBSPOT_TOKEN", "")
HUBSPOT_STAGE_MEETING_BOOKED_ID = os.environ.get("HUBSPOT_STAGE_MEETING_BOOKED_ID", "")
APP_URL         = os.environ.get("SITE_URL", "https://altusflow.ai")

_ESCALATION_PHRASES = [
    "is this ai", "am i talking to a robot", "are you a bot", "are you real",
    "is this a computer", "speak to a human", "talk to a person", "real person",
    "talk to someone", "human please",
]


def _hash_phone(number: str) -> str:
    """SHA-256 hash a phone number. Never store raw caller numbers."""
    return hashlib.sha256(number.strip().encode()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def _vapi_request(method: str, path: str, body: dict = None) -> dict:
    """Make a Vapi API request. Returns response dict or raises on error."""
    url  = f"https://api.vapi.ai{path}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {VAPI_API_KEY}",
            "Content-Type":  "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def _hs_request(method: str, path: str, body: dict = None) -> tuple:
    """HubSpot API call. Returns (status_code, response_dict)."""
    if not HUBSPOT_TOKEN:
        return 0, {}
    url  = f"https://api.hubapi.com{path}"
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {HUBSPOT_TOKEN}",
            "Content-Type":  "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}


# ── VoiceGateway ──────────────────────────────────────────────────────────────

class VoiceGateway:

    def __init__(self):
        self._soul = _load_file(_SOUL_PATH)
        self._faq  = _load_file(_FAQ_PATH)
        if not self._soul:
            raise RuntimeError(f"soul_concierge.md not found at {_SOUL_PATH}")
        if not self._faq:
            raise RuntimeError(f"faq.md not found at {_FAQ_PATH}")

    # ── Inbound call ──────────────────────────────────────────────────────────

    def handle_inbound_call(self, called_number: str, caller_number: str,
                            user_id: str = "ALT00") -> dict:
        """
        Called by POST /webhooks/voice/inbound within 500ms.
        Returns Vapi assistant config dict. Vapi uses this to start Morgan's session.

        called_number  — the AltusFlow Twilio number that was dialled
        caller_number  — the prospect's number (hashed before storage — never raw)
        user_id        — client ID (ALT00 for AltusFlow own calls)
        """
        caller_hash = _hash_phone(caller_number) if caller_number else ""

        # 1. Log call start to DB
        try:
            from database import log_voice_call
            call_id = log_voice_call(
                called_number=called_number,
                caller_hash=caller_hash,
                user_id=user_id,
                direction="inbound",
            )
        except Exception:
            call_id = None

        # 2. Build Morgan's system prompt = soul + FAQ
        system_prompt = (
            f"{self._soul}\n\n"
            f"---\n\n"
            f"# Knowledge Base (FAQ)\n\n"
            f"{self._faq}"
        )

        # 3. Return Vapi assistant configuration
        # Vapi reads this response and starts the call with these settings.
        return {
            "assistant": {
                "name": "Morgan",
                "voice": {
                    "provider": "11labs",
                    "voiceId":  "rachel",       # warm, professional female voice
                },
                "model": {
                    "provider": "anthropic",
                    "model":    "claude-sonnet-4-6",
                    "messages": [
                        {"role": "system", "content": system_prompt}
                    ],
                    "maxTokens":   512,
                    "temperature": 0.4,
                },
                "firstMessage": "Thank you for calling AltusFlow — this is Morgan, how can I help you today?",
                "endCallMessage": "Thank you for calling AltusFlow. Have a great day.",
                "endCallPhrases": [
                    "goodbye", "bye", "thank you goodbye", "that is all", "thanks bye"
                ],
                "transcriber": {
                    "provider": "deepgram",
                    "model":    "nova-2",
                    "language": "en-US",
                },
                "metadata": {
                    "call_id":      call_id,
                    "user_id":      user_id,
                    "caller_hash":  caller_hash,
                    "called_number": called_number,
                },
            }
        }

    # ── Escalation ────────────────────────────────────────────────────────────

    def handle_escalation(self, call_id: str, reason: str,
                          user_id: str = "ALT00") -> None:
        """
        Morgan detected an escalation trigger.
        Morgan collects a callback number, ends gracefully, then:
          - Creates HubSpot task for closer (URGENT)
          - Fires closer webhook
          - Updates voice_calls record
        """
        try:
            from database import update_voice_call
            update_voice_call(call_id, escalation_reason=reason, outcome="escalated")
        except Exception:
            pass

        self.notify_closer(
            call_id=call_id,
            booking_data=None,
            prospect_context={"escalation_reason": reason},
            is_escalation=True,
        )

    # ── Call ended ────────────────────────────────────────────────────────────

    def handle_call_ended(self, payload: dict) -> None:
        """
        Called by POST /webhooks/voice/call-ended.
        payload — full Vapi call-ended webhook body.

        Stores transcript (PII hashed), updates HubSpot if prospect identified,
        logs cost to budget_transactions, moves deal stage if booking made.
        """
        call_id       = payload.get("call", {}).get("id", "")
        transcript    = payload.get("transcript", "")
        summary       = payload.get("summary", "")
        duration_s    = payload.get("call", {}).get("endedAt") or 0
        cost_usd      = payload.get("call", {}).get("cost", 0.0)
        outcome       = payload.get("call", {}).get("endedReason", "unknown")
        booking_data  = payload.get("structuredData", {}).get("booking")
        metadata      = payload.get("call", {}).get("metadata", {})
        user_id       = metadata.get("user_id", "ALT00")
        caller_hash   = metadata.get("caller_hash", "")
        prospect_name = payload.get("structuredData", {}).get("prospect_name", "")

        # Hash any PII in transcript before storage
        safe_transcript = self._hash_transcript_pii(transcript)

        # 1. Update voice_calls record
        try:
            from database import update_voice_call
            update_voice_call(
                call_id,
                transcript=safe_transcript,
                summary=summary,
                duration_seconds=int(duration_s) if duration_s else None,
                outcome=outcome,
                booking_confirmed=bool(booking_data),
            )
        except Exception:
            pass

        # 2. Log cost to budget_transactions
        if cost_usd:
            try:
                from database import log_voice_cost
                log_voice_cost(call_id=call_id, cost_usd=float(cost_usd), user_id=user_id)
            except Exception:
                pass

        # 3. If booking was made — notify closer + move HubSpot deal
        if booking_data:
            self.notify_closer(
                call_id=call_id,
                booking_data=booking_data,
                prospect_context={
                    "prospect_name": prospect_name,
                    "caller_hash":   caller_hash,
                    "summary":       summary,
                    "user_id":       user_id,
                },
                is_escalation=False,
            )
            # Move HubSpot deal to Meeting Booked if we have a deal ID
            hs_deal_id = payload.get("structuredData", {}).get("hubspot_deal_id")
            if hs_deal_id and os.environ.get("HUBSPOT_STAGE_MEETING_BOOKED_ID", HUBSPOT_STAGE_MEETING_BOOKED_ID):
                self._move_deal_to_meeting_booked(hs_deal_id, booking_data)

        # 4. Check transcript for escalation keywords missed by Vapi
        elif self._contains_escalation_phrase(transcript):
            self.handle_escalation(
                call_id=call_id,
                reason="Escalation phrase detected in transcript",
                user_id=user_id,
            )

    # ── Closer notification ───────────────────────────────────────────────────

    def notify_closer(self, call_id: str, booking_data: dict,
                      prospect_context: dict, is_escalation: bool = False) -> None:
        """
        Closer gets everything they need before the call.

        1. Create HubSpot task on the deal (or as standalone task if no deal)
        2. Fire CLOSER_WEBHOOK_URL with full context
        3. Mark closer_notified in voice_calls
        """
        prospect_name = prospect_context.get("prospect_name") or "Unknown caller"
        summary       = prospect_context.get("summary", "")
        user_id       = prospect_context.get("user_id", "ALT00")

        if is_escalation:
            reason      = prospect_context.get("escalation_reason", "Unknown")
            task_title  = f"URGENT: Callback requested — {reason} — {_now()[:16].replace('T', ' ')} UTC"
            task_body   = (
                f"Morgan escalated this call.\n"
                f"Reason: {reason}\n"
                f"Call ID: {call_id}\n"
                f"Action required: Call the prospect back as soon as possible."
            )
            alert_type = "escalation_callback_requested"
        else:
            booked_dt   = booking_data.get("start_time", "") if booking_data else ""
            task_title  = f"Discovery call booked — {prospect_name} — {booked_dt}"
            task_body   = (
                f"Morgan booked a discovery call.\n\n"
                f"Prospect: {prospect_name}\n"
                f"Call time: {booked_dt}\n"
                f"Duration: 20 minutes\n\n"
                f"Morgan's summary:\n{summary}\n\n"
                f"Pre-call brief: {APP_URL}/prep/{call_id}"
            )
            alert_type = "call_booked"

        # HubSpot task
        hs_deal_id = (booking_data or {}).get("hubspot_deal_id") if booking_data else None
        hs_task_id = self._create_hubspot_task(
            title=task_title,
            body=task_body,
            deal_id=hs_deal_id,
        )

        # Webhook notification
        webhook_payload = {
            "alert":             alert_type,
            "prospect_name":     prospect_name,
            "call_date":         (booking_data or {}).get("start_time", "") if not is_escalation else "",
            "call_duration":     "20 minutes",
            "morgan_summary":    summary,
            "escalation_reason": prospect_context.get("escalation_reason", "") if is_escalation else "",
            "hubspot_task_id":   hs_task_id,
            "pre_call_brief_url": f"{APP_URL}/prep/{call_id}",
            "call_id":           call_id,
        }
        self._fire_closer_webhook(webhook_payload)

        # Mark notified in DB
        try:
            from database import mark_closer_notified
            mark_closer_notified(call_id)
        except Exception:
            pass

    # ── HubSpot helpers ───────────────────────────────────────────────────────

    def _create_hubspot_task(self, title: str, body: str,
                             deal_id: str = None) -> str:
        """Create a HubSpot task assigned to the closer. Returns task ID or ''."""
        if not HUBSPOT_TOKEN:
            return ""
        try:
            task_body = {
                "properties": {
                    "hs_task_subject":  title,
                    "hs_task_body":     body,
                    "hs_task_status":   "NOT_STARTED",
                    "hs_task_priority": "HIGH",
                    "hs_timestamp":     str(int(datetime.now(timezone.utc).timestamp() * 1000)),
                }
            }
            status, resp = _hs_request("POST", "/crm/v3/objects/tasks", task_body)
            task_id = resp.get("id", "")

            # Associate task with deal if we have one
            if task_id and deal_id:
                _hs_request(
                    "PUT",
                    f"/crm/v3/associations/tasks/deals/batch/create",
                    {"inputs": [{"from": {"id": task_id}, "to": {"id": deal_id},
                                 "type": "task_to_deal"}]},
                )
            return task_id
        except Exception:
            return ""

    def _move_deal_to_meeting_booked(self, deal_id: str, booking_data: dict) -> None:
        """Move a HubSpot deal to the Meeting Booked stage and stamp the date."""
        if not (HUBSPOT_TOKEN and HUBSPOT_STAGE_MEETING_BOOKED_ID and deal_id):
            return
        try:
            booked_date = (booking_data or {}).get("start_time", "")[:10]  # YYYY-MM-DD
            _hs_request("PATCH", f"/crm/v3/objects/deals/{deal_id}", {
                "properties": {
                    "dealstage":                       HUBSPOT_STAGE_MEETING_BOOKED_ID,
                    "altusflow_meeting_booked_date":   booked_date,
                }
            })
        except Exception:
            pass

    # ── Webhook helper ────────────────────────────────────────────────────────

    def _fire_closer_webhook(self, payload: dict) -> None:
        """POST the closer notification payload to CLOSER_WEBHOOK_URL."""
        if not CLOSER_WEBHOOK:
            return
        try:
            data = json.dumps(payload).encode()
            req  = urllib.request.Request(
                CLOSER_WEBHOOK,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=5)
        except Exception:
            pass  # Webhook failure never blocks the call flow

    # ── PII protection ────────────────────────────────────────────────────────

    def _hash_transcript_pii(self, transcript: str) -> str:
        """
        Remove raw phone numbers from transcript before storage.
        Replaces digit sequences that look like phone numbers with [PHONE_REDACTED].
        """
        import re
        # Match common phone number patterns (10-15 digits, with optional separators)
        return re.sub(
            r'\b(\+?1?\s*[-.]?\s*\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4})\b',
            '[PHONE_REDACTED]',
            transcript,
        )

    def _contains_escalation_phrase(self, transcript: str) -> bool:
        t = transcript.lower()
        return any(phrase in t for phrase in _ESCALATION_PHRASES)
