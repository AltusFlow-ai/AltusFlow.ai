"""
webhooks.py — Twilio voice webhooks

Flow:
  1. Call arrives at Twilio number
  2. /webhooks/twilio/voice
       - Business hours + Hermes calls OFF → forward to cell with live stream + recording
       - Business hours + Hermes calls ON  → Hermes answers via live stream
       - After hours                        → IVR: callback / voicemail / book appointment
  3. /webhooks/twilio/recording-ready → download → Whisper → Hermes parse → DB
"""
import os
import json
import hashlib
import tempfile

import requests
from flask import Blueprint, request, Response
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

webhooks_bp = Blueprint('webhooks', __name__, url_prefix='/webhooks')


# ── Business hours check ─────────────────────────────────────────────────────

def _hermes_calls_on():
    """Read the Hermes calls toggle state from live_call shared state."""
    try:
        from live_call import _state, _lock
        with _lock:
            return _state.get('hermes_calls_on', False)
    except Exception:
        return False


def _is_business_hours():
    """Returns True if current time falls within configured business hours."""
    try:
        tz    = ZoneInfo(os.environ.get('BUSINESS_TZ', 'America/Chicago'))
        now   = datetime.now(tz)
        start = int(os.environ.get('BUSINESS_START', '9'))
        end   = int(os.environ.get('BUSINESS_END', '18'))
        days  = [int(d) for d in os.environ.get('BUSINESS_DAYS', '0,1,2,3,4').split(',')]
        return now.weekday() in days and start <= now.hour < end
    except Exception:
        return True  # fail open — never block a call due to a config error


# ── TwiML: forward + record ──────────────────────────────────────────────────

@webhooks_bp.route('/twilio/voice', methods=['GET', 'POST'])
def twilio_voice():
    """
    Route all inbound calls:
      - After hours → after-hours IVR (callback / voicemail / book)
      - Business hours → live stream + forward to cell (or Hermes if hermesCallsOn)
    """
    cell = os.environ.get('MY_CELL_NUMBER', '')

    hermes_on = _hermes_calls_on()
    if not _is_business_hours() and not hermes_on:
        return _after_hours_twiml(request.form.get('From', ''))

    server_url = os.environ.get('SERVER_URL', request.host_url.rstrip('/'))
    ws_url = server_url.replace('https://', 'wss://').replace('http://', 'ws://') + '/ws/call-stream'

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Start><Stream url="{ws_url}" /></Start>'
        f'<Dial record="record-from-answer"'
        f' recordingStatusCallback="/webhooks/twilio/recording-ready"'
        f' recordingStatusCallbackMethod="POST"'
        f' action="/webhooks/twilio/no-answer"'
        f' timeout="25">'
        f'<Number>{cell}</Number>'
        f'</Dial>'
        '</Response>'
    )
    return Response(xml, mimetype='text/xml')


def _after_hours_twiml(caller=''):
    """IVR played when a call comes in outside business hours."""
    name        = os.environ.get('BUSINESS_NAME', 'our team')
    booking_url = os.environ.get('BOOKING_URL', '')

    say_options = (
        f'Hey, thanks for calling. {name} is unavailable right now. '
        'Press 1 to request a callback. '
        'Press 2 to leave a voicemail. '
    )
    if booking_url:
        say_options += 'Or press 3 to receive a booking link by text. '

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        f'<Gather numDigits="1" action="/webhooks/twilio/after-hours-gather" method="POST" timeout="10">'
        f'<Say voice="Polly.Joanna">{say_options}</Say>'
        '</Gather>'
        '<Say voice="Polly.Joanna">We didn\'t catch that — we\'ll have someone reach out soon. Goodbye.</Say>'
        '</Response>'
    )
    return Response(xml, mimetype='text/xml')


@webhooks_bp.route('/twilio/after-hours-gather', methods=['POST'])
def after_hours_gather():
    """Handle keypress from the after-hours IVR."""
    digit       = request.form.get('Digits', '').strip()
    caller      = request.form.get('From', '')
    booking_url = os.environ.get('BOOKING_URL', '')

    if digit == '1':
        _notify_owner_sms(f'📞 Callback requested from {caller} (after hours). Call them back when you\'re free.')
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Say voice="Polly.Joanna">Got it — someone will call you back during business hours. Talk soon.</Say>'
            '</Response>'
        )

    elif digit == '2':
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Say voice="Polly.Joanna">Please leave your message after the tone. Press any key when done.</Say>'
            '<Record maxLength="120" action="/webhooks/twilio/voicemail-done"'
            ' finishOnKey="any" transcribe="true"'
            ' transcribeCallback="/webhooks/twilio/voicemail-transcript"/>'
            '</Response>'
        )

    elif digit == '3' and booking_url:
        _send_sms(caller, f'Hi — here\'s a link to book a time with us: {booking_url}')
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Say voice="Polly.Joanna">Check your texts for the booking link. Looking forward to speaking with you.</Say>'
            '</Response>'
        )

    else:
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response>'
            '<Say voice="Polly.Joanna">No problem — we\'ll be in touch soon. Goodbye.</Say>'
            '</Response>'
        )

    return Response(xml, mimetype='text/xml')


@webhooks_bp.route('/twilio/voicemail-done', methods=['POST'])
def voicemail_done():
    """Called when a voicemail recording finishes."""
    caller        = request.form.get('From', '')
    recording_url = request.form.get('RecordingUrl', '')
    _notify_owner_sms(f'📭 Voicemail from {caller} (after hours): {recording_url}.mp3')
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<Response>'
        '<Say voice="Polly.Joanna">Your message has been saved. We\'ll be in touch soon. Goodbye.</Say>'
        '</Response>'
    )
    return Response(xml, mimetype='text/xml')


@webhooks_bp.route('/twilio/voicemail-transcript', methods=['POST'])
def voicemail_transcript():
    """Twilio fires this with the transcribed voicemail text."""
    caller     = request.form.get('From', '')
    transcript = request.form.get('TranscriptionText', '')
    if transcript:
        _notify_owner_sms(f'📝 Voicemail transcript from {caller}: "{transcript}"')
    return '', 204


@webhooks_bp.route('/twilio/no-answer', methods=['POST'])
def no_answer():
    """Fires when a business-hours call isn't answered — offer after-hours options."""
    caller = request.form.get('From', '')
    return _after_hours_twiml(caller)


# ── SMS helpers ───────────────────────────────────────────────────────────────

def _send_sms(to: str, body: str):
    """Send an SMS via Twilio to any number."""
    sid   = os.environ.get('TWILIO_ACCOUNT_SID', '')
    token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    from_ = os.environ.get('TWILIO_PHONE_NUMBER', '')
    if not (sid and token and from_ and to):
        return
    try:
        requests.post(
            f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',
            auth=(sid, token),
            data={'From': from_, 'To': to, 'Body': body},
            timeout=10,
        )
    except Exception as e:
        print(f'[webhooks] SMS send: {e}')


def _notify_owner_sms(body: str):
    """Send an SMS alert to the owner's cell number."""
    _send_sms(os.environ.get('MY_CELL_NUMBER', ''), body)


# ── Recording ready: transcribe + parse + save ───────────────────────────────

@webhooks_bp.route('/twilio/recording-ready', methods=['POST'])
def recording_ready():
    """Twilio fires this when the recording MP3 is available."""
    recording_url = request.form.get('RecordingUrl', '')
    call_sid      = request.form.get('CallSid', '')
    duration_secs = int(request.form.get('RecordingDuration', 0) or 0)
    caller        = request.form.get('From', 'unknown')

    if not recording_url or not call_sid:
        return '', 204

    caller_hash = hashlib.sha256(caller.encode()).hexdigest()[:16]

    # Stub row so the call shows in dashboard immediately
    try:
        from database import log_voice_call
        log_voice_call(
            called_number=os.environ.get('TWILIO_PHONE_NUMBER', ''),
            caller_hash=caller_hash,
            call_id=call_sid,
        )
    except Exception as e:
        print(f'[webhooks] log_voice_call: {e}')

    # Download recording
    sid   = os.environ.get('TWILIO_ACCOUNT_SID', '')
    token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    try:
        r = requests.get(recording_url + '.mp3', auth=(sid, token), timeout=60)
        r.raise_for_status()
        audio = r.content
    except Exception as e:
        print(f'[webhooks] download recording: {e}')
        return '', 204

    transcript = _transcribe(audio)
    parsed     = _parse(transcript, caller, duration_secs)

    # Update row with full data
    try:
        from database import update_voice_call
        update_voice_call(
            call_id=call_sid,
            transcript=transcript,
            summary=parsed.get('summary', ''),
            duration_seconds=duration_secs,
            outcome=parsed.get('outcome', 'other'),
            booking_confirmed=parsed.get('outcome') == 'booked',
        )
    except Exception as e:
        print(f'[webhooks] update_voice_call: {e}')

    _save_learnings(parsed)
    return '', 204


# ── Transcription (Whisper) ───────────────────────────────────────────────────

def _transcribe(audio: bytes) -> str:
    key = os.environ.get('OPENAI_API_KEY', '')
    if not key:
        return '[Add OPENAI_API_KEY to .env.local to enable transcription]'
    try:
        import openai
        client = openai.OpenAI(api_key=key)
        with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as f:
            f.write(audio)
            tmp = f.name
        with open(tmp, 'rb') as f:
            result = client.audio.transcriptions.create(model='whisper-1', file=f)
        os.unlink(tmp)
        return result.text
    except Exception as e:
        print(f'[webhooks] whisper: {e}')
        return ''


# ── Hermes parsing ────────────────────────────────────────────────────────────

def _parse(transcript: str, caller: str, duration: int) -> dict:
    fallback = {
        'caller_name': 'Unknown', 'niche': 'Unknown', 'pain_points': [],
        'outcome': 'other', 'outcome_detail': '', 'follow_up': '',
        'learnings': [], 'summary': transcript[:200],
    }
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key or not transcript.strip():
        return fallback
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=600,
            messages=[{'role': 'user', 'content': f"""You are Hermes, AltusFlow's outbound sales AI.
A call just completed. Extract structured data from the transcript.

Caller: {caller} | Duration: {duration}s
Transcript:
{transcript}

Return ONLY valid JSON (no markdown, no explanation):
{{
  "caller_name": "first name or Unknown",
  "niche": "Financial Advisor | Trading Coach | Recruiter | MSP | CRE Broker | Other",
  "pain_points": ["short pain point strings"],
  "outcome": "booked | callback | not_interested | no_answer | other",
  "outcome_detail": "e.g. Demo booked Thu 10am",
  "follow_up": "next action if any",
  "learnings": ["2-4 insight strings for future calls"],
  "summary": "2-3 sentence summary of the call"
}}"""}],
        )
        return json.loads(msg.content[0].text)
    except Exception as e:
        print(f'[webhooks] hermes parse: {e}')
        return fallback


# ── Save learnings to DB ──────────────────────────────────────────────────────

def _save_learnings(parsed: dict):
    insights = [i for i in parsed.get('learnings', []) + parsed.get('pain_points', []) if i]
    if not insights:
        return
    try:
        from database import _writer
        from sqlalchemy import text
        now = datetime.now(timezone.utc).isoformat()
        niche = parsed.get('niche', 'Unknown')
        with _writer() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS call_learnings (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    niche      TEXT,
                    insight    TEXT,
                    source     TEXT DEFAULT 'call',
                    created_at TEXT DEFAULT (datetime('now'))
                )
            """))
            for item in insights:
                conn.execute(
                    text('INSERT INTO call_learnings (niche, insight, created_at) VALUES (:n, :i, :t)'),
                    {'n': niche, 'i': item, 't': now},
                )
            conn.commit()
    except Exception as e:
        print(f'[webhooks] save learnings: {e}')
