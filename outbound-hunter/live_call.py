"""
live_call.py — Real-time call intelligence

Flow:
  1. Inbound call → /webhooks/twilio/voice returns TwiML with <Start><Stream>
  2. Twilio opens WebSocket to /ws/call-stream
  3. Audio chunks (mulaw 8kHz base64) → forwarded to Deepgram Nova-2
  4. Deepgram callbacks push transcripts → _push() → SSE clients
  5. Every ~5 utterances, Claude Haiku generates a suggestion
  6. React LiveCall.jsx renders live transcript + suggestions
  7. call_ended SSE event → React navigates back to /dashboard/calls
"""
import os
import json
import base64
import time
import threading
from queue import Queue, Empty

from flask import Blueprint, Response, stream_with_context

live_bp = Blueprint('live', __name__)

# ── Shared state ──────────────────────────────────────────────────────────────
_lock = threading.Lock()
_state = {
    'active':           False,
    'call_sid':         None,
    'prospect':         {},
    'started_at':       None,
    'transcript':       [],
    'suggestions':      [],
    'hermes_calls_on':  False,
}
_sse_queues: list[Queue] = []


def _snapshot():
    with _lock:
        return {
            'active':      _state['active'],
            'call_sid':    _state['call_sid'],
            'prospect':    _state['prospect'],
            'started_at':  _state['started_at'],
            'transcript':  list(_state['transcript']),
            'suggestions': list(_state['suggestions']),
        }


def _update(**kw):
    with _lock:
        _state.update(kw)


def _push(event: str, data: dict):
    """Broadcast an SSE event to all connected clients."""
    msg = f'event: {event}\ndata: {json.dumps(data)}\n\n'
    dead = []
    with _lock:
        clients = list(_sse_queues)
    for q in clients:
        try:
            q.put_nowait(msg)
        except Exception:
            dead.append(q)
    if dead:
        with _lock:
            for q in dead:
                try:
                    _sse_queues.remove(q)
                except ValueError:
                    pass


# ── SSE endpoint ──────────────────────────────────────────────────────────────

@live_bp.route('/api/calls/live-stream')
def sse_stream():
    q = Queue(maxsize=200)
    with _lock:
        _sse_queues.append(q)

    def generate():
        yield f'event: init\ndata: {json.dumps(_snapshot())}\n\n'
        try:
            while True:
                try:
                    yield q.get(timeout=25)
                except Empty:
                    yield ': heartbeat\n\n'
        except GeneratorExit:
            pass
        finally:
            with _lock:
                try:
                    _sse_queues.remove(q)
                except ValueError:
                    pass

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@live_bp.route('/api/settings/hermes-calls', methods=['GET', 'POST'])
def hermes_calls_setting():
    if request.method == 'POST':
        data = request.get_json(silent=True) or {}
        _update(hermes_calls_on=bool(data.get('on', False)))
        return {'ok': True}
    with _lock:
        return {'on': _state['hermes_calls_on']}


@live_bp.route('/api/calls/active')
def active_call():
    with _lock:
        return {
            'active':   _state['active'],
            'call_sid': _state['call_sid'],
            'prospect': dict(_state['prospect']),
        }


# ── WebSocket handler (called from app.py via flask-sock) ─────────────────────

def handle_media_stream(ws):
    """
    Registered as @sock.route('/ws/call-stream') in app.py.
    Receives Twilio Media Stream messages and streams audio to Deepgram.
    """
    dg_key        = os.environ.get('DEEPGRAM_API_KEY', '')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')

    dg_conn      = None
    utterances   = []
    last_suggest = 0.0
    first_spk    = None   # first detected speaker int → labelled 'YOU'

    def on_transcript(self_or_result, result=None, **kwargs):
        nonlocal last_suggest, utterances, first_spk
        r = result if result is not None else self_or_result
        try:
            alt  = r.channel.alternatives[0]
            text = (alt.transcript or '').strip()
            if not text:
                return
            is_final = r.is_final

            # Speaker diarization — first speaker heard = YOU
            words   = getattr(alt, 'words', None) or []
            raw_spk = getattr(words[0], 'speaker', 0) if words else 0
            if first_spk is None:
                first_spk = raw_spk
            label = 'YOU' if raw_spk == first_spk else 'THEM'

            line = {'speaker': label, 'text': text, 'ts': time.time(), 'final': is_final}

            if is_final:
                with _lock:
                    _state['transcript'].append(line)
                    utterances.append(line)
                _push('transcript', line)

                now = time.time()
                if (len(utterances) >= 5 or now - last_suggest > 20) and anthropic_key:
                    last_suggest = now
                    batch = list(utterances[-10:])
                    utterances.clear()
                    threading.Thread(target=_suggest, args=(batch, anthropic_key), daemon=True).start()
            else:
                _push('partial', line)
        except Exception:
            pass

    def start_deepgram():
        nonlocal dg_conn
        if not dg_key:
            return
        try:
            from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents
            dg   = DeepgramClient(dg_key)
            conn = dg.listen.live.v('1')
            conn.on(LiveTranscriptionEvents.Transcript, on_transcript)
            opts = LiveOptions(
                model='nova-2',
                encoding='mulaw',
                sample_rate=8000,
                channels=1,
                diarize=True,
                punctuate=True,
                interim_results=True,
                utterance_end_ms='1000',
                vad_events=True,
            )
            conn.start(opts)
            dg_conn = conn
        except Exception as exc:
            print(f'[live_call] Deepgram init: {exc}')

    call_sid = None
    try:
        while True:
            raw = ws.receive()
            if raw is None:
                break
            try:
                msg   = json.loads(raw)
                event = msg.get('event')
            except Exception:
                continue

            if event == 'start':
                call_sid = msg.get('start', {}).get('callSid', '')
                _update(
                    active=True, call_sid=call_sid,
                    started_at=time.time(), transcript=[], suggestions=[], prospect={},
                )
                _push('call_started', {'call_sid': call_sid})
                threading.Thread(target=start_deepgram, daemon=True).start()

            elif event == 'media':
                if dg_conn:
                    try:
                        dg_conn.send(base64.b64decode(msg['media']['payload']))
                    except Exception:
                        pass

            elif event == 'stop':
                break

    finally:
        if dg_conn:
            try:
                dg_conn.finish()
            except Exception:
                pass
        _update(active=False)
        _push('call_ended', {'call_sid': call_sid})


def _suggest(utterances: list, anthropic_key: str):
    """Generate a Hermes suggestion from recent utterances and push to SSE clients."""
    try:
        import anthropic as _ant
        snippet = '\n'.join(f"{u['speaker']}: {u['text']}" for u in utterances)
        msg = _ant.Anthropic(api_key=anthropic_key).messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=120,
            messages=[{'role': 'user', 'content': (
                'Real-time sales coach. One specific suggestion for what to say or ask next '
                '(max 25 words, no preamble):\n\n' + snippet
            )}],
        )
        text = msg.content[0].text.strip()
        s    = {'text': text, 'ts': time.time()}
        with _lock:
            _state['suggestions'].insert(0, s)
            _state['suggestions'] = _state['suggestions'][:5]
        _push('suggestion', s)
    except Exception:
        pass


@live_bp.route('/api/calls/simulate', methods=['POST'])
def simulate_call():
    """Push a fake live call through the SSE stream — no Twilio or Deepgram needed."""
    with _lock:
        if _state['active']:
            return {'ok': False, 'error': 'Call already active'}, 409

    LINES = [
        ('YOU',  "Hey Jake, thanks for jumping on. You mentioned you were struggling with consistency?"),
        ('THEM', "Yeah, I've been trading two years but I keep blowing up. Last month I was up $4k then gave it all back in one day."),
        ('YOU',  "That sounds like a revenge trading pattern. When you gave it back — did it happen right after a loss?"),
        ('THEM', "Exactly. I just couldn't let it go. I kept doubling down trying to get it back."),
        ('YOU',  "Got it. So your strategy works — the issue is the psychological side. Have you worked with a coach before?"),
        ('THEM', "No. I've just tried doing it alone. YouTube, books, that sort of thing."),
        ('YOU',  "Most traders at your level hit this exact ceiling. The edge is there but the mindset isn't managed."),
        ('THEM', "That's literally me. I'm profitable in demo but the moment real money is on the line it all falls apart."),
        ('YOU',  "The demo-to-live gap is super common. It's not the strategy — it's the emotional load of real risk."),
        ('THEM', "So what would working with you actually look like?"),
        ('YOU',  "We do eight sessions. First two are about your trading psychology profile — understanding your specific triggers."),
        ('THEM', "How much does it run?"),
        ('YOU',  "The program is two thousand. Most traders recover that in the first month just from cutting bad trades."),
        ('THEM', "That's fair honestly. I've lost way more than that revenge trading."),
        ('YOU',  "Exactly. Want to lock in a discovery call this week? I have Wednesday at nine AM open."),
        ('THEM', "Yeah, let's do it. Wednesday works."),
    ]
    SUGGESTIONS = [
        "He's showing revenge trading pattern — ask about position sizing when he's down.",
        "Demo-to-live gap confirmed. Emphasize emotional load over strategy gap.",
        "Price objection likely next — anchor to what revenge trading has already cost him.",
        "Strong buying signal. Close with a specific time slot, not open-ended.",
    ]

    def _run():
        _update(
            active=True, call_sid='SIM-001',
            started_at=time.time(), transcript=[], suggestions=[],
            prospect={'name': 'Jake T.', 'niche': 'Trading Coach'},
        )
        _push('call_started', {'call_sid': 'SIM-001'})

        sug_idx = 0
        for i, (speaker, text) in enumerate(LINES):
            delay = 0.8 if i == 0 else 1.2 + (len(text) / 120)
            time.sleep(delay)
            line = {'speaker': speaker, 'text': text, 'ts': time.time(), 'final': True}
            with _lock:
                _state['transcript'].append(line)
            _push('transcript', line)

            if (i + 1) % 4 == 0 and sug_idx < len(SUGGESTIONS):
                time.sleep(0.5)
                s = {'text': SUGGESTIONS[sug_idx], 'ts': time.time()}
                sug_idx += 1
                with _lock:
                    _state['suggestions'].insert(0, s)
                _push('suggestion', s)

        time.sleep(2)
        _update(active=False)
        _push('call_ended', {'call_sid': 'SIM-001'})

    threading.Thread(target=_run, daemon=True).start()
    return {'ok': True}


def register(app):
    """Call this from app.py to wire up Flask-Sock + the blueprint."""
    try:
        from flask_sock import Sock
        sock = Sock(app)

        @sock.route('/ws/call-stream')
        def call_stream_ws(ws):
            handle_media_stream(ws)

    except ImportError:
        app.logger.warning('[live_call] flask-sock not installed — WebSocket endpoint disabled')

    app.register_blueprint(live_bp)
