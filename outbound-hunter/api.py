"""
Flask Blueprint: /api/* — Dashboard REST API
"""
from flask import Blueprint, request, jsonify, abort, send_file, session
from flask_login import login_required, current_user
import io, csv, json

try:
    from crm import get_adapter as _get_crm, active_provider as _crm_provider
    _CRM_ENABLED = True
except Exception:
    _CRM_ENABLED = False
    def _get_crm():
        class _Null:
            def push_prospect(self, *a, **k): return {"ok": False, "error": "crm not loaded"}
            def move_deal_stage(self, *a, **k): return {"ok": False, "error": "crm not loaded"}
            def push_call(self, *a, **k): return {"ok": False, "error": "crm not loaded"}
            def add_note(self, *a, **k): return {"ok": False, "error": "crm not loaded"}
        return _Null()
    def _crm_provider(): return "none"

try:
    from database import (
        get_prospects, get_prospect_by_id, approve_prospect, skip_prospect,
        get_conversations, get_conversation_messages, send_message,
        update_conversation_mode, create_conversation,
        get_journey_list, get_prospect_journey, add_journey_event,
        log_reply,
        get_pipeline_stages, get_daily_chart, get_subreddit_breakdown,
        get_funnel_stats, get_analytics_metrics, get_speed_to_touch,
        get_budget_summary, get_transactions,
        get_signal_phrase_performance, get_platform_performance,
        get_all_clients, create_client, get_pod_statuses,
        get_all_calls, get_call_by_id, save_call_notes, link_call_prospect,
        get_reports, get_report_path,
        get_connections, get_settings, save_settings,
        get_team, invite_team_member, remove_team_member,
        get_notification_settings, save_notification_settings,
        get_niches_with_counts,
        get_integrations, get_integration, save_integration,
    )
except ImportError as e:
    import sys
    print(f"[api.py] database import warning: {e}", file=sys.stderr)
    # Provide stubs so the blueprint still registers
    def _stub(*a, **k): return None
    (get_prospects, get_prospect_by_id, approve_prospect, skip_prospect,
     get_conversations, get_conversation_messages, send_message,
     update_conversation_mode, create_conversation,
     get_journey_list, get_prospect_journey, add_journey_event, log_reply,
     get_pipeline_stages, get_daily_chart, get_subreddit_breakdown,
     get_funnel_stats, get_analytics_metrics, get_speed_to_touch,
     get_budget_summary, get_transactions,
     get_signal_phrase_performance, get_platform_performance,
     get_all_clients, create_client, get_pod_statuses,
     get_all_calls, get_call_by_id, save_call_notes, link_call_prospect,
     get_reports, get_report_path,
     get_connections, get_settings, save_settings,
     get_team, invite_team_member, remove_team_member,
     get_notification_settings, save_notification_settings,
     get_niches_with_counts,
     get_integrations, get_integration, save_integration) = [_stub]*44

try:
    from hermes import get_suggestion, generate_intelligence_brief as _hermes_brief
except ImportError:
    def get_suggestion(*a, **k): return None
    def _hermes_brief(*a, **k): return None

api = Blueprint('api', __name__, url_prefix='/api')


def _uid():
    """Return current user id or None."""
    try:
        return current_user.id if current_user.is_authenticated else None
    except Exception:
        return None


@api.route('/me')
def me():
    from flask_login import current_user as _cu
    if not _cu.is_authenticated:
        return jsonify({'error': 'not authenticated'}), 401
    return jsonify({
        'id':           current_user.id,
        'email':        current_user.email,
        'role':         current_user.role,
        'is_admin':     current_user.is_admin,
        'company_name': current_user.company_name,
        'tenant_slug':  current_user.tenant_slug,
        'plan':         current_user.plan,
    })


# ── Public landing page lead capture ─────────────────────────────────────────

@api.route('/hubspot/contact', methods=['POST'])
def hubspot_contact():
    """
    Public endpoint — no login required.
    Called by both landing pages when a visitor submits their email.
    Creates/upserts a HubSpot contact tagged as a website lead.
    Falls back gracefully (returns 200) if HUBSPOT_TOKEN is not yet configured.
    """
    import os, json as _json, urllib.request, urllib.error
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or '').strip().lower()
    if not email or '@' not in email:
        return jsonify({'ok': False, 'error': 'valid email required'}), 400

    token = os.environ.get('HUBSPOT_TOKEN', '')
    if not token:
        # Token not configured yet — log and return success so the form UX works
        import logging
        logging.getLogger(__name__).warning('hubspot/contact: HUBSPOT_TOKEN not set — lead %s not pushed', email)
        return jsonify({'ok': True, 'note': 'token_not_configured'})

    niche   = data.get('niche', 'unknown')
    source  = data.get('altusflow_lead_source_vertical', 'Landing Page')
    cid     = data.get('altusflow_client_portal_id', os.environ.get('CLIENT_ID', 'ALT00'))
    utms    = data.get('utms', {})

    properties = {
        'email':                           email,
        'hs_lead_status':                  'NEW',
        'altusflow_lead_source_vertical':  source,
        'altusflow_client_portal_id':      cid,
        'altusflow_niche_segment':         niche,
        'altusflow_lead_qualified_status': 'Website-Lead',
        'altusflow_first_touch_campaign':  utms.get('utm_campaign', f'{cid}_landing'),
        'altusflow_utm_source':            utms.get('utm_source', 'organic'),
        'altusflow_utm_medium':            utms.get('utm_medium', ''),
        'altusflow_utm_content':           utms.get('utm_content', ''),
    }

    payload = _json.dumps({
        'inputs': [{'idProperty': 'email', 'id': email, 'properties': properties}]
    }).encode()

    req = urllib.request.Request(
        'https://api.hubapi.com/crm/v3/objects/contacts/batch/upsert',
        data=payload,
        headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return jsonify({'ok': True})
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors='replace')
        import logging
        logging.getLogger(__name__).error('hubspot/contact push failed %s: %s', e.code, err)
        return jsonify({'ok': False, 'error': f'hubspot {e.code}'}), 502
    except Exception as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 500


# ── Niches ────────────────────────────────────────────────────────────────────

@api.route('/niches')
@login_required
def niches():
    return jsonify(get_niches_with_counts(_uid()) or [])


# ── Prospects ─────────────────────────────────────────────────────────────────

@api.route('/prospects')
@login_required
def prospects():
    niche  = request.args.get('niche','')
    status = request.args.get('status','pending_review')
    tab    = request.args.get('tab','pending')
    return jsonify(get_prospects(_uid(), niche=niche, status=status, tab=tab) or [])


@api.route('/prospects/stats')
@login_required
def prospects_stats():
    from database import get_prospect_stats
    return jsonify(get_prospect_stats(_uid()) or {})


@api.route('/prospects/<int:pid>/approve', methods=['POST'])
@login_required
def prospect_approve(pid):
    ok = approve_prospect(pid, _uid())
    if not ok:
        return jsonify({'ok': False})
    crm_result = {'ok': False, 'error': 'skipped'}
    try:
        prospect = get_prospect_by_id(pid, _uid())
        if prospect:
            crm_result = _get_crm().push_prospect(prospect)
    except Exception as e:
        crm_result = {'ok': False, 'error': str(e)}
    return jsonify({'ok': True, 'crm': crm_result})


@api.route('/prospects/<int:pid>/skip', methods=['POST'])
@login_required
def prospect_skip(pid):
    ok = skip_prospect(pid, _uid())
    return jsonify({'ok': bool(ok)})


@api.route('/prospects/<int:pid>/send-reddit-dm', methods=['POST'])
@login_required
def send_prospect_reddit_dm(pid):
    """
    Send the drafted Reddit DM for an approved prospect.
    Body: { "subject": "...", "body": "..." }  (both optional — defaults to drafted_message)
    Returns: { "ok": bool, "error": "..." }
    """
    prospect = get_prospect_by_id(pid, _uid())
    if not prospect:
        return jsonify({'ok': False, 'error': 'Prospect not found'}), 404

    reddit_username = prospect.get('reddit_username') or prospect.get('handle')
    if not reddit_username:
        return jsonify({'ok': False, 'error': 'No Reddit username on this prospect'}), 400

    body_data = request.json or {}
    subject = body_data.get('subject') or 'Quick question from AltusFlow'
    message_body = body_data.get('body') or prospect.get('drafted_message') or ''

    if not message_body:
        return jsonify({'ok': False, 'error': 'No message body — draft a message first'}), 400

    try:
        from scrapers.reddit import send_reddit_dm
        result = send_reddit_dm(reddit_username, subject, message_body)
    except Exception as e:
        result = {'ok': False, 'error': str(e)}

    if result.get('ok'):
        try:
            from database import mark_prospect_sent
            mark_prospect_sent(
                pid,
                channel='reddit_dm',
                advisor_id=_uid(),
                message=message_body,
                disclosure_appended=prospect.get('disclosure_appended', False),
            )
        except Exception:
            pass

    return jsonify(result)


@api.route('/prospects/batch-approve', methods=['POST'])
@login_required
def batch_approve():
    ids = request.json.get('ids', [])
    results = [approve_prospect(i, _uid()) for i in ids]
    return jsonify({'approved': sum(bool(r) for r in results)})


@api.route('/prospects/export-csv')
@login_required
def export_prospects_csv():
    rows = get_prospects(_uid()) or []
    out  = io.StringIO()
    w    = csv.DictWriter(out, fieldnames=['id','handle','niche','icp_score','subreddit','status','created_at'])
    w.writeheader(); [w.writerow({k: r.get(k,'') for k in w.fieldnames}) for r in rows]
    return send_file(io.BytesIO(out.getvalue().encode()), mimetype='text/csv',
                     as_attachment=True, download_name='prospects.csv')


# ── Conversations / Reply Center ───────────────────────────────────────────────

@api.route('/conversations')
@login_required
def conversations():
    source = request.args.get('source')
    return jsonify(get_conversations(_uid(), source=source) or [])


@api.route('/conversations/<int:cid>/messages')
@login_required
def conversation_messages(cid):
    return jsonify(get_conversation_messages(cid) or [])


@api.route('/conversations/<int:cid>/send', methods=['POST'])
@login_required
def conversation_send(cid):
    body = request.json.get('message','').strip()
    if not body: abort(400)
    ok = send_message(cid, body, sender='human')
    return jsonify({'ok': bool(ok)})


@api.route('/conversations/<int:cid>/mode', methods=['POST'])
@login_required
def conversation_mode(cid):
    mode = request.json.get('mode')
    ok = update_conversation_mode(cid, mode)
    return jsonify({'ok': bool(ok)})


@api.route('/conversations/<int:cid>/hermes-suggestion')
@login_required
def hermes_suggestion(cid):
    msgs    = get_conversation_messages(cid) or []
    prospect = {}
    source_context = {}
    try:
        from database import get_prospect_by_conversation, _reader
        from sqlalchemy import text as _t
        prospect = get_prospect_by_conversation(cid) or {}
        with _reader() as conn:
            row = conn.execute(_t(
                "SELECT source, source_context FROM conversations WHERE id=:cid"
            ), {"cid": cid}).fetchone()
            if row:
                import json as _j
                src = row[0] or 'cold_stream'
                ctx = {}
                try: ctx = _j.loads(row[1]) if row[1] else {}
                except Exception: pass
                source_context = {"source": src, **ctx}
    except Exception:
        pass
    mode = request.args.get('mode', 'assist')
    suggestion = get_suggestion(prospect, msgs, mode, source_context=source_context)
    return jsonify({'suggestion': suggestion})


@api.route('/conversations/<int:cid>/hermes-send', methods=['POST'])
@login_required
def hermes_send(cid):
    body = request.json.get('message','').strip()
    if not body: abort(400)
    ok = send_message(cid, body, sender='hermes')
    return jsonify({'ok': bool(ok)})


@api.route('/conversations/<int:cid>/hermes-skip', methods=['POST'])
@login_required
def hermes_skip(cid):
    return jsonify({'ok': True})


@api.route('/conversations/<int:cid>/prospect-replied', methods=['POST'])
@login_required
def prospect_replied(cid):
    """
    Called when a prospect sends an inbound reply. Logs the message and syncs
    the CRM deal to the 'Replied' stage.
    Body: { message: str }  (optional — log the reply text)
    """
    body = (request.get_json() or {}).get('message', '').strip()
    if body:
        send_message(cid, body, sender='prospect')
    crm_result = {'ok': False, 'error': 'skipped'}
    try:
        from database import get_prospect_by_conversation
        prospect = get_prospect_by_conversation(cid) or {}
        deal_id  = prospect.get('crm_deal_id') or prospect.get('hs_deal_id')
        if deal_id:
            crm_result = _get_crm().move_deal_stage(deal_id, 'replied')
    except Exception as e:
        crm_result = {'ok': False, 'error': str(e)}
    return jsonify({'ok': True, 'crm': crm_result})


# ── Journey ───────────────────────────────────────────────────────────────────

@api.route('/journey')
@login_required
def journey():
    search = request.args.get('search','')
    niche  = request.args.get('niche','')
    stage  = request.args.get('stage','')
    return jsonify(get_journey_list(_uid(), search=search, niche=niche, stage=stage) or [])


@api.route('/journey/<int:pid>')
@login_required
def journey_prospect(pid):
    return jsonify(get_prospect_journey(pid) or {})


@api.route('/journey/<int:pid>/add-event', methods=['POST'])
@login_required
def journey_add_event(pid):
    """Manually add a journey event — e.g. proposal sent, deal closed."""
    data   = request.get_json() or {}
    event  = data.get('event', '').strip()
    icon   = data.get('icon', '📌')
    detail = data.get('detail', '').strip()
    if not event:
        return jsonify({'ok': False, 'error': 'event required'}), 400
    eid = add_journey_event(pid, event, icon, detail)
    return jsonify({'ok': True, 'id': eid})


@api.route('/prospects/<int:pid>/log-reply', methods=['POST'])
@login_required
def prospect_log_reply(pid):
    """
    Log a manual reply pasted in from LinkedIn, Facebook, or any platform
    where we can't read messages automatically.
    Body: { body: str, sender: 'prospect'|'you' }
    """
    data   = request.get_json() or {}
    body   = data.get('body', '').strip()
    sender = data.get('sender', 'prospect')
    if not body:
        return jsonify({'ok': False, 'error': 'body required'}), 400
    msg_id = log_reply(pid, body, sender=sender)
    return jsonify({'ok': True, 'message_id': msg_id})


@api.route('/prospects/<int:pid>/upload-conversation', methods=['POST'])
@login_required
def upload_conversation_screenshot(pid):
    """
    Accept a screenshot of a conversation (base64 or file upload),
    send it to Claude Vision to extract messages, and log them all.

    Accepts JSON: { image: 'data:image/...;base64,...', media_type: 'image/jpeg' }
    OR multipart form-data with field 'image' (file upload from mobile/desktop).

    Returns: { ok: true, messages: [{sender, body}], logged: N }
    """
    import os, json as _json, base64, urllib.request, urllib.error

    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    if not ANTHROPIC_API_KEY:
        return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not configured'}), 503

    # ── Accept image from JSON (data URI) or multipart file upload ──
    image_b64  = None
    media_type = 'image/jpeg'

    if request.content_type and 'multipart' in request.content_type:
        f = request.files.get('image')
        if not f:
            return jsonify({'ok': False, 'error': 'no image file'}), 400
        media_type = f.content_type or 'image/jpeg'
        image_b64  = base64.b64encode(f.read()).decode()
    else:
        data = request.get_json(silent=True) or {}
        raw  = data.get('image', '')
        if raw.startswith('data:'):
            # data URI — strip header
            header, _, b64 = raw.partition(',')
            media_type = header.split(';')[0].replace('data:', '') or 'image/jpeg'
            image_b64  = b64
        else:
            image_b64 = raw
        media_type = data.get('media_type', media_type)

    if not image_b64:
        return jsonify({'ok': False, 'error': 'no image data'}), 400

    # ── Call Claude Vision ──────────────────────────────────────────
    prompt = (
        "This is a screenshot of a direct message conversation. "
        "Extract every message visible. "
        "Return ONLY a JSON array like: "
        '[{"sender":"prospect","body":"..."},{"sender":"you","body":"..."}] '
        "Use \"you\" for the account owner's messages and \"prospect\" for the other person. "
        "If you cannot determine who sent a message, use \"prospect\". "
        "Preserve the exact wording. No preamble, no explanation — JSON only."
    )

    payload = _json.dumps({
        "model":      "claude-sonnet-4-6",
        "max_tokens": 1024,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type":       "base64",
                        "media_type": media_type,
                        "data":       image_b64,
                    }
                },
                {"type": "text", "text": prompt}
            ]
        }]
    }).encode()

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key":         ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "Content-Type":      "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            resp = _json.loads(r.read())
    except urllib.error.HTTPError as e:
        err = e.read().decode(errors='replace')
        return jsonify({'ok': False, 'error': f'Claude API {e.code}: {err[:200]}'}), 502
    except Exception as ex:
        return jsonify({'ok': False, 'error': str(ex)}), 500

    raw_text = resp.get('content', [{}])[0].get('text', '').strip()

    # Strip markdown fences if present
    if raw_text.startswith('```'):
        parts    = raw_text.split('```')
        raw_text = parts[1].lstrip('json').strip() if len(parts) > 1 else raw_text

    try:
        messages = _json.loads(raw_text)
        if not isinstance(messages, list):
            raise ValueError('not a list')
    except Exception:
        return jsonify({'ok': False, 'error': 'Could not parse Claude response', 'raw': raw_text[:300]}), 500

    # ── Log every extracted message ────────────────────────────────
    from database import create_conversation, send_message, add_journey_event
    conv_id = create_conversation(pid)
    logged  = 0
    for msg in messages:
        body   = (msg.get('body') or '').strip()
        sender = msg.get('sender', 'prospect')
        if body:
            send_message(conv_id, sender, body)
            logged += 1

    # One journey event summarising the upload
    if logged:
        preview = next((m['body'] for m in messages if m.get('sender') == 'prospect'), '')
        add_journey_event(
            pid, "Conversation uploaded", "📸",
            f"{logged} messages extracted from screenshot",
            full_message=preview[:500] if preview else None,
        )
        # Mark as replied if prospect has a message
        from database import update_status
        update_status(pid, 'replied')

    return jsonify({'ok': True, 'messages': messages, 'logged': logged})


@api.route('/prospects/<int:pid>/context', methods=['POST'])
@login_required
def prospect_expand_context(pid):
    """
    "Expand Context" button — Hermes reads the Reddit thread and returns a
    3-bullet contextual summary so reps walk into every touch already knowing
    exactly where the prospect stands.

    Flow:
      1. Pull prospect from DB (post_url, post_text, subreddit)
      2. Fetch top Reddit comments via the public JSON API (no auth needed)
      3. Send full thread to Claude Haiku for a 3-bullet summary
      4. Persist summary to context_summary column
      5. Return summary to frontend
    """
    import os as _os, json as _j, urllib.request as _ur, urllib.error as _ue

    try:
        from database import get_prospect, _writer
        from sqlalchemy import text as _t

        p = get_prospect(pid)
        if not p:
            return jsonify({'ok': False, 'error': 'Prospect not found'}), 404

        post_url  = (p.get('post_url') or '').strip()
        post_text = (p.get('post_text') or '').strip()[:1500]
        subreddit = p.get('subreddit', '')
        handle    = p.get('handle', '')

        # ── Step 1: fetch thread comments from Reddit public JSON API ──────────
        thread_comments = ''
        if 'reddit.com' in post_url:
            try:
                json_url = post_url.rstrip('/') + '.json?limit=8&depth=1'
                req_reddit = _ur.Request(
                    json_url,
                    headers={'User-Agent': 'AltusFlow/1.0 context-reader'},
                )
                with _ur.urlopen(req_reddit, timeout=8) as resp:
                    data = _j.loads(resp.read())
                # data[1] = comment listing
                comments = []
                for child in (data[1].get('data', {}).get('children', []) if len(data) > 1 else []):
                    body = child.get('data', {}).get('body', '').strip()
                    author = child.get('data', {}).get('author', '')
                    if body and author and author != 'AutoModerator':
                        comments.append(f"u/{author}: {body[:400]}")
                thread_comments = '\n'.join(comments[:8])
            except Exception as _re:
                pass  # fall back to post text only

        # ── Step 2: ask Hermes for a contextual summary ────────────────────────
        api_key = _os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not set'}), 503

        thread_block = f"""
ORIGINAL POST by u/{handle} in r/{subreddit}:
{post_text}

TOP COMMENTS IN THE THREAD:
{thread_comments if thread_comments else '(No comments captured — working from post only)'}
""".strip()

        prompt = (
            "You are Hermes, a sales intelligence assistant for a trading coaching business. "
            "Analyze the Reddit thread below and return exactly 3 bullet points for an appointment setter. "
            "Each bullet must be 1 short sentence. Format:\n"
            "• [PAIN] The specific problem they described\n"
            "• [CONTEXT] What the thread discussion revealed (community reaction, their follow-up comments, etc.)\n"
            "• [ANGLE] The single best opening angle for outreach based on this thread\n\n"
            "Return ONLY the 3 bullets. No preamble.\n\n"
            + thread_block
        )

        body = _j.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 220,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()

        req_claude = _ur.Request(
            "https://api.anthropic.com/v1/messages", data=body, method="POST",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
        )
        with _ur.urlopen(req_claude, timeout=15) as resp:
            result = _j.loads(resp.read())

        summary = result['content'][0]['text'].strip()

        # ── Step 3: persist to DB ──────────────────────────────────────────────
        _ensure_context_column()
        with _writer() as conn:
            conn.execute(
                _t("UPDATE prospects SET context_summary=:s WHERE id=:id"),
                {"s": summary, "id": pid},
            )

        return jsonify({'ok': True, 'summary': summary, 'thread_comment_count': len(thread_comments.splitlines())})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/prospects/<int:pid>/dm-log', methods=['POST'])
@login_required
def prospect_dm_log(pid):
    """
    Rep logs that the conversation has moved to DM — this is higher-intent.
    Advances the prospect's journey stage and logs a journey event.

    Body: { note?: str }  (optional rep note about what was said)
    """
    data = request.get_json(silent=True) or {}
    note = (data.get('note') or '').strip()

    try:
        from database import add_journey_event, update_status, _writer
        from sqlalchemy import text as _t

        # Move status to 'replied' if they haven't gone past that yet
        _writer_ctx = _writer()
        with _writer_ctx as conn:
            conn.execute(
                _t("UPDATE prospects SET status='replied' WHERE id=:id AND status NOT IN ('booked','closed_won','closed_lost')"),
                {"id": pid},
            )

        event_id = add_journey_event(
            pid,
            event        = "Moved to DM",
            icon         = "💬",
            detail       = note or "Conversation moved from public thread to private DM — higher intent signal",
            full_message = note or None,
        )

        return jsonify({'ok': True, 'event_id': event_id})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


def _ensure_context_column():
    """Add context_summary column to prospects if not already there."""
    try:
        from database import _writer
        from sqlalchemy import text as _t
        with _writer() as conn:
            conn.execute(_t("ALTER TABLE prospects ADD COLUMN context_summary TEXT"))
    except Exception:
        pass  # column already exists — safe to ignore


# ── Pipeline ──────────────────────────────────────────────────────────────────

@api.route('/pipeline/stages')
@login_required
def pipeline_stages():
    return jsonify(get_pipeline_stages(_uid()) or {})


@api.route('/pipeline/stage', methods=['POST'])
@login_required
def pipeline_stage_update():
    """
    Sync a prospect's pipeline stage to the configured CRM when the dashboard pipeline is updated.
    Body: { prospect_id: int, stage_key: str }
    stage_key: replied | meeting_booked | call_completed | closed_won | closed_lost
    """
    data      = request.get_json() or {}
    pid       = data.get('prospect_id')
    stage_key = data.get('stage_key', '')
    if not pid or not stage_key:
        return jsonify({'ok': False, 'error': 'prospect_id and stage_key required'}), 400
    try:
        prospect = get_prospect_by_id(pid, _uid()) or {}
        deal_id  = prospect.get('crm_deal_id') or prospect.get('hs_deal_id')
        if not deal_id:
            return jsonify({'ok': False, 'error': 'No CRM deal linked to this prospect'})
        result = _get_crm().move_deal_stage(deal_id, stage_key)
        return jsonify(result)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@api.route('/pipeline/daily-chart')
@login_required
def pipeline_daily():
    days = int(request.args.get('days', 14))
    return jsonify(get_daily_chart(_uid(), days=days) or [])


@api.route('/pipeline/subreddit-breakdown')
@login_required
def pipeline_subreddits():
    return jsonify(get_subreddit_breakdown(_uid()) or [])


# ── Analytics ─────────────────────────────────────────────────────────────────

@api.route('/analytics/funnel')
@login_required
def analytics_funnel():
    return jsonify(get_funnel_stats(_uid()) or {})


@api.route('/analytics/metrics')
@login_required
def analytics_metrics():
    return jsonify(get_analytics_metrics(_uid()) or {})


@api.route('/analytics/daily-chart')
@login_required
def analytics_daily():
    return jsonify(get_daily_chart(_uid(), days=14) or [])


@api.route('/analytics/speed-to-touch')
@login_required
def analytics_speed():
    return jsonify(get_speed_to_touch(_uid()) or [])


# ── Budget ────────────────────────────────────────────────────────────────────

@api.route('/budget/summary')
@login_required
def budget_summary():
    return jsonify(get_budget_summary(_uid()) or {})


@api.route('/budget/transactions')
@login_required
def budget_transactions():
    platform  = request.args.get('platform','')
    direction = request.args.get('direction','')
    return jsonify(get_transactions(_uid(), platform=platform, direction=direction) or [])


@api.route('/budget/export-csv')
@login_required
def budget_csv():
    rows = get_transactions(_uid()) or []
    out  = io.StringIO()
    w    = csv.DictWriter(out, fieldnames=['created_at','platform','description','amount','direction','status'])
    w.writeheader(); [w.writerow({k: r.get(k,'') for k in w.fieldnames}) for r in rows]
    return send_file(io.BytesIO(out.getvalue().encode()), mimetype='text/csv',
                     as_attachment=True, download_name='budget.csv')


# ── Compliance (FA/RIA audit log + disclosure template) ───────────────────────

@api.route('/compliance/export-csv')
@login_required
def compliance_export_csv():
    """
    Export all sent messages as a compliance-ready CSV.
    Columns: sent_at, advisor_id, prospect_handle, prospect_platform, niche,
             channel, disclosure_appended, message_sent, replied, outcome,
             icp_score, signal_phrase, post_url.
    """
    try:
        from database import get_sent_log_for_compliance
        rows = get_sent_log_for_compliance(limit=5000)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    fields = [
        'sent_at', 'advisor_id', 'prospect_handle', 'prospect_platform', 'niche',
        'channel', 'disclosure_appended', 'replied', 'outcome',
        'icp_score', 'signal_phrase', 'post_url', 'message_sent',
    ]
    out = io.StringIO()
    w   = csv.DictWriter(out, fieldnames=fields, extrasaction='ignore')
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k, '') for k in fields})

    ts = __import__('datetime').datetime.utcnow().strftime('%Y%m%d_%H%M')
    return send_file(
        io.BytesIO(out.getvalue().encode()),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'compliance_audit_{ts}.csv',
    )


@api.route('/compliance/disclosure', methods=['GET'])
@login_required
def get_disclosure():
    """Return the current disclosure footer template."""
    try:
        from database import get_tenant_setting
        footer = get_tenant_setting('disclosure_footer', '')
    except Exception:
        footer = ''
    return jsonify({'disclosure_footer': footer})


@api.route('/compliance/disclosure', methods=['POST'])
@login_required
def set_disclosure():
    """Save the disclosure footer template. Body: { "disclosure_footer": "..." }"""
    footer = (request.json or {}).get('disclosure_footer', '').strip()
    try:
        from database import set_tenant_setting
        set_tenant_setting('disclosure_footer', footer)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Learning ──────────────────────────────────────────────────────────────────

@api.route('/learning/signal-phrases')
@login_required
def learning_phrases():
    return jsonify(get_signal_phrase_performance(_uid()) or [])


@api.route('/learning/platform-performance')
@login_required
def learning_platforms():
    return jsonify(get_platform_performance(_uid()) or [])


@api.route('/learning/intelligence-brief')
@login_required
def learning_brief():
    try:
        brief = _hermes_brief(_uid())
        return jsonify(brief or None)
    except Exception:
        return jsonify(None)


# ── Calls ─────────────────────────────────────────────────────────────────────

@api.route('/calls')
@login_required
def calls():
    return jsonify(get_all_calls(_uid()) or [])


@api.route('/calls/<int:cid>')
@login_required
def call_detail(cid):
    return jsonify(get_call_by_id(cid) or {})


@api.route('/calls/<int:cid>/notes', methods=['POST'])
@login_required
def call_notes(cid):
    notes = request.json.get('notes', '')
    ok    = save_call_notes(cid, notes)
    if ok:
        try:
            call = get_call_by_id(cid) or {}
            contact_id = call.get('crm_contact_id') or call.get('hs_contact_id')
            deal_id    = call.get('crm_deal_id')    or call.get('hs_deal_id')
            if not contact_id and call.get('prospect_id'):
                prospect   = get_prospect_by_id(call.get('prospect_id'), _uid()) or {}
                contact_id = prospect.get('crm_contact_id') or prospect.get('hs_contact_id')
                deal_id    = deal_id or prospect.get('crm_deal_id') or prospect.get('hs_deal_id')
            if contact_id:
                call['notes'] = notes
                _get_crm().push_call(contact_id, deal_id, call)
        except Exception:
            pass  # Never block call save due to CRM failures
    return jsonify({'ok': bool(ok)})


@api.route('/calls/<int:cid>/link-prospect', methods=['POST'])
@login_required
def call_link(cid):
    pid = request.json.get('prospect_id')
    ok  = link_call_prospect(cid, pid)
    return jsonify({'ok': bool(ok)})


@api.route('/calls/upload', methods=['POST'])
@login_required
def upload_call_recording():
    """Accept an audio/video file, transcribe with Whisper, parse with Hermes, return structured call data."""
    import os as _os, tempfile
    from werkzeug.utils import secure_filename

    if 'file' not in request.files:
        return jsonify({'ok': False, 'error': 'No file provided'}), 400
    f = request.files['file']
    if not f.filename:
        return jsonify({'ok': False, 'error': 'Empty filename'}), 400

    fname = secure_filename(f.filename)
    ext = _os.path.splitext(fname)[1].lower()
    if ext not in {'.mp3', '.mp4', '.m4a', '.wav', '.mov', '.webm', '.ogg', '.aac'}:
        return jsonify({'ok': False, 'error': 'Unsupported format — use mp3, mp4, m4a, wav, mov, or webm'}), 400

    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        f.save(tmp.name)
        tmp_path = tmp.name

    try:
        # ── Transcribe ────────────────────────────────────────────────────────
        transcript_text = ''
        openai_key = _os.environ.get('OPENAI_API_KEY', '')
        if openai_key:
            try:
                import openai as _openai
                oa = _openai.OpenAI(api_key=openai_key)
                with open(tmp_path, 'rb') as audio:
                    result = oa.audio.transcriptions.create(model='whisper-1', file=audio, response_format='text')
                transcript_text = result if isinstance(result, str) else getattr(result, 'text', '')
            except Exception as exc:
                transcript_text = f'[Transcription error: {exc}]'
        else:
            transcript_text = '[Connect OpenAI in Connections to enable transcription]'

        # ── Parse with Claude Haiku ───────────────────────────────────────────
        name = 'Unknown'; niche = 'Unknown'; summary = ''; outcome = 'uploaded'; learnings = []
        anthropic_key = _os.environ.get('ANTHROPIC_API_KEY', '')
        if anthropic_key and transcript_text and not transcript_text.startswith('['):
            try:
                import anthropic as _anthropic, json as _json
                ac = _anthropic.Anthropic(api_key=anthropic_key)
                msg = ac.messages.create(
                    model='claude-haiku-4-5-20251001',
                    max_tokens=512,
                    messages=[{'role': 'user', 'content': (
                        'Parse this call transcript. Return ONLY valid JSON with keys: '
                        'caller_name (string), niche (one of: Financial Advisor, Trading Coach, Recruiter, CRE Broker, MSP, Unknown), '
                        'summary (2-3 sentences), outcome (one of: booked, callback, no_answer, uploaded), '
                        'learnings (array of 3-5 short bullet strings).\n\nTranscript:\n' + transcript_text[:3000]
                    )}]
                )
                raw = msg.content[0].text.strip()
                if raw.startswith('```'):
                    raw = raw.split('\n', 1)[-1].rsplit('```', 1)[0]
                p = _json.loads(raw)
                name = p.get('caller_name', 'Unknown')
                niche = p.get('niche', 'Unknown')
                summary = p.get('summary', '')
                outcome = p.get('outcome', 'uploaded')
                learnings = p.get('learnings', [])
            except Exception:
                pass

        # ── Build transcript lines ────────────────────────────────────────────
        transcript_lines = []
        for line in (transcript_text or '').split('\n'):
            line = line.strip()
            if not line:
                continue
            if ':' in line[:25]:
                sp, txt = line.split(':', 1)
                transcript_lines.append({'speaker': sp.strip(), 'text': txt.strip()})
            else:
                if transcript_lines and transcript_lines[-1]['speaker'] == 'Audio':
                    transcript_lines[-1]['text'] += ' ' + line
                else:
                    transcript_lines.append({'speaker': 'Audio', 'text': line})

        niche_key_map = {
            'Financial Advisor': 'fa', 'Trading Coach': 'tc',
            'Recruiter': 'rc', 'CRE Broker': 'cre', 'MSP': 'msp',
        }
        return jsonify({
            'ok': True,
            'call': {
                'name': name,
                'niche': niche,
                'nicheKey': niche_key_map.get(niche),
                'summary': summary or f'Uploaded recording: {fname}',
                'transcript': transcript_lines or [{'speaker': 'Audio', 'text': transcript_text}],
                'learnings': learnings,
                'outcome': outcome,
                'filename': fname,
                'duration': '—',
            }
        })
    finally:
        try:
            _os.unlink(tmp_path)
        except Exception:
            pass


# ── Reports ───────────────────────────────────────────────────────────────────

@api.route('/reports')
@login_required
def reports():
    return jsonify(get_reports(_uid()) or [])


@api.route('/reports/<int:rid>/download')
@login_required
def report_download(rid):
    path = get_report_path(rid, _uid())
    if not path:
        abort(404)
    return send_file(path, as_attachment=True)


# ── Admin: Clients ─────────────────────────────────────────────────────────────

@api.route('/admin/clients')
@login_required
def admin_clients():
    return jsonify(get_all_clients() or [])


@api.route('/admin/clients', methods=['POST'])
@login_required
def admin_create_client():
    data = request.json or {}
    cid  = create_client(data.get('name',''), data.get('email',''), data.get('niche',''))
    return jsonify({'id': cid})


@api.route('/admin/clients/<int:cid>/impersonate', methods=['POST'])
@login_required
def admin_impersonate(cid):
    session['impersonate_client_id'] = cid
    return jsonify({'ok': True})


# ── Admin: Pods ────────────────────────────────────────────────────────────────

@api.route('/admin/pods')
@login_required
def admin_pods():
    return jsonify(get_pod_statuses() or {})


@api.route('/admin/pods/<slug>/pause', methods=['POST'])
@login_required
def pod_pause(slug):
    try:
        from scheduler import pause_pod
        pause_pod(slug)
    except Exception:
        pass
    return jsonify({'ok': True})


@api.route('/admin/pods/<slug>/resume', methods=['POST'])
@login_required
def pod_resume(slug):
    try:
        from scheduler import resume_pod
        resume_pod(slug)
    except Exception:
        pass
    return jsonify({'ok': True})


@api.route('/admin/pods/<slug>/reset', methods=['POST'])
@login_required
def pod_reset(slug):
    try:
        from scheduler import reset_circuit_breaker
        reset_circuit_breaker(slug)
    except Exception:
        pass
    return jsonify({'ok': True})


@api.route('/admin/pods/<slug>/run-now', methods=['POST'])
@login_required
def pod_run_now(slug):
    try:
        from scheduler import run_pod_now
        run_pod_now(slug)
    except Exception:
        pass
    return jsonify({'ok': True})


@api.route('/admin/pods/<slug>/logs')
@login_required
def pod_logs(slug):
    try:
        from database import get_pod_logs
        return jsonify(get_pod_logs(slug) or [])
    except Exception:
        return jsonify([])


# ── Connections ────────────────────────────────────────────────────────────────

def _conn_get_key(tenant_id, var_name):
    """Read an API key: DB first (decrypted), then os.environ fallback."""
    import os as _os
    if tenant_id and tenant_id != 0:
        try:
            from master_db import get_tenant_config
            from auth import decrypt_token
            raw = get_tenant_config(tenant_id, var_name)
            if raw:
                return decrypt_token(raw) or raw
        except Exception:
            pass
    return _os.environ.get(var_name, '')


def _conn_set_key(tenant_id, var_name, value):
    """Persist an API key to the DB (encrypted) and apply to running process."""
    import os as _os
    _os.environ[var_name] = value
    if tenant_id and tenant_id != 0:
        try:
            from master_db import set_tenant_config
            from auth import encrypt_token
            set_tenant_config(tenant_id, var_name, encrypt_token(value))
        except Exception:
            pass


def _conn_clear_key(tenant_id, var_name):
    """Remove an API key from the DB and running process."""
    import os as _os
    _os.environ.pop(var_name, None)
    if tenant_id and tenant_id != 0:
        try:
            from master_db import set_tenant_config
            set_tenant_config(tenant_id, var_name, None)
        except Exception:
            pass


@api.route('/connections')
@login_required
def connections():
    tid = current_user.tenant_id
    def has(var): return bool(_conn_get_key(tid, var))
    return jsonify({
        'reddit':        has('REDDIT_CLIENT_ID'),
        'twitter':       has('TWITTER_BEARER_TOKEN'),
        'discord':       has('DISCORD_BOT_TOKEN'),
        'apify':         has('APIFY_API_TOKEN'),
        'hubspot':       has('HUBSPOT_TOKEN'),
        'pipedrive':     has('PIPEDRIVE_API_TOKEN'),
        'gohighlevel':   has('GHL_API_KEY'),
        'salesforce':    has('SALESFORCE_CLIENT_ID'),
        'anthropic':     has('ANTHROPIC_API_KEY'),
        'scrapebadger':  has('SCRAPEBADGER_API_KEY'),
        'calendly':      has('CALENDLY_TOKEN'),
        'twilio':        has('TWILIO_ACCOUNT_SID'),
        'openai':        has('OPENAI_API_KEY'),
        'deepgram':      has('DEEPGRAM_API_KEY'),
        'vapi':          has('VAPI_API_KEY'),
        'bland':         has('BLAND_API_KEY'),
        'crm_provider':  _crm_provider(),
    })


# Map of platform slug → primary env var (used for single-field platforms)
_PLATFORM_ENV_VARS = {
    'twitter':      'TWITTER_BEARER_TOKEN',
    'hubspot':      'HUBSPOT_TOKEN',
    'pipedrive':    'PIPEDRIVE_API_TOKEN',
    'gohighlevel':  'GHL_API_KEY',
    'salesforce':   'SALESFORCE_CLIENT_ID',
    'anthropic':    'ANTHROPIC_API_KEY',
    'scrapebadger': 'SCRAPEBADGER_API_KEY',
    'calendly':     'CALENDLY_TOKEN',
    'vapi':         'VAPI_API_KEY',
    'bland':        'BLAND_API_KEY',
    'openai':       'OPENAI_API_KEY',
    'deepgram':     'DEEPGRAM_API_KEY',
    'discord':      'DISCORD_BOT_TOKEN',
    'apify':        'APIFY_API_TOKEN',
    'twilio':       'TWILIO_ACCOUNT_SID',   # primary check key; multi-key save handled below
}

# Multi-key platforms: slug → list of env var names saved in one request
_PLATFORM_MULTI_VARS = {
    'reddit': [
        ('REDDIT_CLIENT_ID',     'Client ID'),
        ('REDDIT_CLIENT_SECRET', 'Client Secret'),
    ],
    'twilio': [
        ('TWILIO_ACCOUNT_SID',  'Account SID'),
        ('TWILIO_AUTH_TOKEN',   'Auth Token'),
        ('TWILIO_PHONE_NUMBER', 'Twilio number'),
        ('MY_CELL_NUMBER',      'Your cell'),
    ],
}


@api.route('/connections/<platform>/key', methods=['POST'])
@login_required
def save_connection_key(platform):
    """
    Save an API key for a platform to the database (encrypted).
    Also updates os.environ so the running process picks it up immediately.
    Body: { key: "value" }  OR  { keys: { "ENV_VAR": "value", ... } }
    """
    tid  = current_user.tenant_id
    body = request.get_json(silent=True) or {}

    if 'keys' in body:
        # Multi-field: { keys: { "REDDIT_CLIENT_ID": "...", ... } }
        allowed = {var for var, _ in _PLATFORM_MULTI_VARS.get(platform, [])}
        if not allowed:
            return jsonify({'ok': False, 'error': f'Platform {platform} does not support multi-key save'}), 400
        pairs = {k: str(v).strip() for k, v in body['keys'].items() if k in allowed and str(v).strip()}
        if not pairs:
            return jsonify({'ok': False, 'error': 'No valid keys provided'}), 400
    else:
        var_name = _PLATFORM_ENV_VARS.get(platform)
        if not var_name:
            return jsonify({'ok': False, 'error': f'Unknown platform: {platform}'}), 400
        key_value = body.get('key', '').strip()
        if not key_value:
            return jsonify({'ok': False, 'error': 'key is required'}), 400
        pairs = {var_name: key_value}

    for var_name, value in pairs.items():
        _conn_set_key(tid, var_name, value)

    return jsonify({'ok': True, 'platform': platform, 'saved': list(pairs.keys())})


@api.route('/connections/<platform>/disconnect', methods=['POST'])
@login_required
def connection_disconnect(platform):
    """Remove the API key for a platform from the database and running process."""
    tid = current_user.tenant_id
    multi = _PLATFORM_MULTI_VARS.get(platform)
    if multi:
        for var_name, _ in multi:
            _conn_clear_key(tid, var_name)
    else:
        var_name = _PLATFORM_ENV_VARS.get(platform)
        if var_name:
            _conn_clear_key(tid, var_name)
    return jsonify({'ok': True})


# ── Settings ───────────────────────────────────────────────────────────────────

@api.route('/settings')
@login_required
def settings_get():
    return jsonify(get_settings(_uid()) or {})


@api.route('/settings', methods=['POST'])
@login_required
def settings_save():
    ok = save_settings(_uid(), request.json or {})
    return jsonify({'ok': bool(ok)})


@api.route('/settings/notifications')
@login_required
def notifs_get():
    return jsonify(get_notification_settings(_uid()) or {})


@api.route('/settings/notifications', methods=['POST'])
@login_required
def notifs_save():
    ok = save_notification_settings(_uid(), request.json or {})
    return jsonify({'ok': bool(ok)})


# ── Team ───────────────────────────────────────────────────────────────────────

@api.route('/team')
@login_required
def team():
    return jsonify(get_team(_uid()) or [])


@api.route('/team/invite', methods=['POST'])
@login_required
def team_invite():
    email = (request.json or {}).get('email','').strip()
    if not email: abort(400)
    ok = invite_team_member(_uid(), email)
    return jsonify({'ok': bool(ok)})


@api.route('/team/<int:mid>', methods=['DELETE'])
@login_required
def team_remove(mid):
    ok = remove_team_member(_uid(), mid)
    return jsonify({'ok': bool(ok)})


# ── Market Pulse ───────────────────────────────────────────────────────────────

@api.route('/market-pulse')
@login_required
def market_pulse():
    """
    Omnichannel market intelligence for the MarketPulseWidget.
    Query params:
      pod    — filter by pod slug (optional)
      source — 'reddit' | 'twitter' | omit for both
    """
    pod_slug = request.args.get('pod') or None
    source   = request.args.get('source') or None
    try:
        from market_pulse import get_market_pulse
        return jsonify(get_market_pulse(pod_slug=pod_slug, source=source))
    except Exception as exc:
        return jsonify({'error': str(exc), 'pain_points': [], 'daily_hook': '', 'competitor_mentions': []}), 500


@api.route('/market-pulse/fetch', methods=['POST'])
@login_required
def market_pulse_fetch():
    """
    On-demand fetch: run SocialConnector for a given source + query and return normalised leads.
    Body: { source: 'twitter'|'reddit', query: str, pod_id: str }
    """
    data    = request.get_json(silent=True) or {}
    source  = data.get('source', 'reddit')
    query   = data.get('query', '').strip()
    pod_id  = data.get('pod_id', '')
    if not query:
        return jsonify({'ok': False, 'error': 'query required'}), 400
    try:
        from social_connector import fetch_leads
        leads = fetch_leads(source=source, query=query, pod_id=pod_id)
        return jsonify({'ok': True, 'source': source, 'count': len(leads), 'leads': leads})
    except Exception as exc:
        return jsonify({'ok': False, 'error': str(exc)}), 500


# ── Topic Intelligence ────────────────────────────────────────────────────────

@api.route('/value-posts/topics')
@login_required
def value_posts_topics():
    """
    Aggregate pain signals from stream prospects over the last 14 days.
    Returns trending topics ranked by frequency with subreddit breakdown
    and an example post snippet — used by the Topic Intelligence panel
    to generate data-driven value posts.
    """
    try:
        from database import _reader
        from sqlalchemy import text as _t

        with _reader() as conn:
            rows = conn.execute(_t("""
                SELECT
                    signal_phrase,
                    COUNT(*)            AS cnt,
                    GROUP_CONCAT(DISTINCT subreddit) AS subreddits,
                    MAX(scraped_at)     AS last_seen,
                    MIN(post_text)      AS example_post
                FROM prospects
                WHERE signal_phrase IS NOT NULL
                  AND signal_phrase != ''
                  AND scraped_at >= datetime('now', '-14 days')
                GROUP BY signal_phrase
                ORDER BY cnt DESC
                LIMIT 12
            """)).fetchall()

        topics = []
        for r in rows:
            subs = [s.strip() for s in (r[2] or '').split(',') if s.strip()]
            topics.append({
                'signal':       r[0],
                'count':        r[1],
                'subreddits':   subs,
                'top_subreddit': subs[0] if subs else 'Daytrading',
                'last_seen':    r[3],
                'example_post': (r[4] or '')[:200],
            })

        # If no real data yet, return realistic demo topics
        if not topics:
            topics = [
                {'signal': 'blown account',          'count': 14, 'subreddits': ['Daytrading', 'Futures'], 'top_subreddit': 'Daytrading',     'last_seen': None, 'example_post': 'Just blew my 3rd account this year. I know what I\'m doing wrong but I keep doing it anyway.'},
                {'signal': 'revenge trading',         'count': 11, 'subreddits': ['Daytrading'],             'top_subreddit': 'Daytrading',     'last_seen': None, 'example_post': 'Lost $800 in the morning and made it back by 2pm but then gave it all back revenge trading into close.'},
                {'signal': 'need a coach',            'count': 9,  'subreddits': ['Daytrading', 'Forex'],    'top_subreddit': 'Daytrading',     'last_seen': None, 'example_post': 'Does anyone actually have a trading coach that was worth it? I\'m considering it but worried about scams.'},
                {'signal': 'consistently losing',     'count': 8,  'subreddits': ['Futures', 'options'],     'top_subreddit': 'Futures',        'last_seen': None, 'example_post': 'I\'ve been trading for 2 years and still not consistently profitable. Starting to think I\'m just not cut out for this.'},
                {'signal': 'emotional trading',       'count': 7,  'subreddits': ['Daytrading'],             'top_subreddit': 'Daytrading',     'last_seen': None, 'example_post': 'My biggest problem is I let emotions control my trades. Up big and get greedy, down and panic sell.'},
                {'signal': 'overtrading',             'count': 6,  'subreddits': ['Daytrading', 'stocks'],   'top_subreddit': 'Daytrading',     'last_seen': None, 'example_post': 'I take 30+ trades a day and I know it\'s a problem but I get bored and just keep clicking.'},
                {'signal': 'trading psychology',      'count': 5,  'subreddits': ['Daytrading', 'Futures'],  'top_subreddit': 'Daytrading',     'last_seen': None, 'example_post': 'Strategy is fine, psychology is killing me. How do you actually fix this?'},
                {'signal': 'quit trading',            'count': 4,  'subreddits': ['Daytrading'],             'top_subreddit': 'Daytrading',     'last_seen': None, 'example_post': 'Seriously considering quitting. Down $12k this year and nothing is clicking.'},
            ]

        return jsonify(topics)
    except Exception as e:
        return jsonify([])


# ── Value Posts (viral data contribution tactic) ──────────────────────────────
# Based on the Avneesh playbook: post free, genuinely useful content in the
# community FIRST. One great post = hundreds of inbound impressions without
# a single cold DM. Reps copy the approved post and paste it manually.

@api.route('/value-posts')
@login_required
def value_posts_list():
    subreddit = request.args.get('subreddit')
    try:
        from database import get_value_posts
        return jsonify(get_value_posts(_uid(), subreddit=subreddit) or [])
    except Exception as e:
        return jsonify([])


@api.route('/value-posts/generate', methods=['POST'])
@login_required
def value_posts_generate():
    """
    Generate a new value post using Hermes + recent stream pain signals.
    Body: { subreddit, type: 'insight_digest'|'resource_post', topic? }
    """
    data      = request.get_json(silent=True) or {}
    subreddit = data.get('subreddit', '').strip()
    post_type = data.get('type', 'insight_digest')
    topic     = data.get('topic', '').strip()

    if not subreddit:
        return jsonify({'ok': False, 'error': 'subreddit required'}), 400

    try:
        from value_post_generator import generate_from_recent_prospects, generate_resource_post
        from database import create_value_post

        if post_type == 'resource_post' and topic:
            result = generate_resource_post(subreddit=subreddit, topic=topic)
        elif data.get('use_intelligence'):
            from value_post_generator import generate_with_outcome_intelligence
            result = generate_with_outcome_intelligence(subreddit=subreddit, client_id=_uid())
        else:
            result = generate_from_recent_prospects(subreddit=subreddit, client_id=_uid())

        if not result:
            return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500

        pid = create_value_post(
            subreddit  = result['subreddit'],
            post_type  = result['type'],
            title      = result['title'],
            body       = result['body'],
            topic      = result.get('topic'),
            signals    = result.get('signals', []),
            post_count = result.get('post_count', 0),
            client_id  = _uid(),
        )
        return jsonify({'ok': True, 'id': pid, **result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/lead-sources/stats')
@login_required
def lead_sources_stats():
    """Aggregate lead volume, reply rate, calls, and closed by source."""
    try:
        from database import _reader
        from sqlalchemy import text as _t
        with _reader() as conn:
            rows = conn.execute(_t("""
                SELECT
                    c.source,
                    COUNT(DISTINCT c.id)                                          AS leads,
                    COUNT(DISTINCT CASE WHEN p.status='replied'   THEN c.id END)  AS replies,
                    COUNT(DISTINCT CASE WHEN p.status='call'      THEN c.id END)  AS calls,
                    COUNT(DISTINCT CASE WHEN p.status='closed'    THEN c.id END)  AS closed,
                    ROUND(AVG(CAST(p.intent_score AS REAL)), 0)                   AS avg_intent
                FROM conversations c
                JOIN prospects p ON p.id = c.prospect_id
                WHERE c.source IS NOT NULL
                GROUP BY c.source
            """)).fetchall()

        stats = []
        for r in rows:
            leads   = r[1] or 0
            replies = r[2] or 0
            stats.append({
                'source':      r[0],
                'leads':       leads,
                'replies':     replies,
                'calls':       r[3] or 0,
                'closed':      r[4] or 0,
                'reply_rate':  round((replies / leads * 100) if leads else 0),
                'avg_intent':  int(r[5]) if r[5] else 0,
            })

        return jsonify(stats if stats else [])
    except Exception as e:
        return jsonify([])


@api.route('/value-posts/generate-batch', methods=['POST'])
@login_required
def value_posts_generate_batch():
    """
    Batch mode: generate value content from top pain signals.
    Body: { count: 5, platform: 'reddit'|'x'|'both' }
    - reddit  → Reddit posts from Reddit prospects
    - x       → X threads from X/Twitter prospects
    - both    → split evenly, half Reddit posts + half X threads
    """
    data     = request.get_json(silent=True) or {}
    count    = min(int(data.get('count', 5)), 8)
    platform = data.get('platform', 'both').lower()

    reddit_count = count if platform == 'reddit' else (0 if platform == 'x' else max(1, count // 2))
    x_count      = count if platform == 'x'      else (0 if platform == 'reddit' else count - reddit_count)

    def _pull_signals(src_platform, n):
        """Pull top pain signals from DB for the given platform."""
        try:
            from database import _reader
            from sqlalchemy import text as _t
            plat_filter = "AND (platform = 'x' OR platform = 'twitter')" if src_platform == 'x' else "AND (platform = 'reddit' OR platform IS NULL)"
            with _reader() as conn:
                rows = conn.execute(_t(f"""
                    SELECT signal_phrase,
                           GROUP_CONCAT(DISTINCT subreddit) AS subs,
                           GROUP_CONCAT(DISTINCT pod_slug)  AS pods,
                           MIN(post_text) AS example
                    FROM prospects
                    WHERE signal_phrase IS NOT NULL AND signal_phrase != ''
                      AND scraped_at >= datetime('now', '-14 days')
                      {plat_filter}
                    GROUP BY signal_phrase
                    ORDER BY COUNT(*) DESC
                    LIMIT :n
                """), {"n": n}).fetchall()
            return [
                {
                    'signal':   r[0],
                    'subreddit': (r[1] or 'Daytrading').split(',')[0].strip(),
                    'pod':      (r[2] or 'daytrading').split(',')[0].strip(),
                    'example':  r[3] or '',
                    'platform': src_platform,
                }
                for r in rows
            ]
        except Exception:
            return []

    REDDIT_DEMO = [
        {'signal': 'blown account',      'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Just blew my 3rd account. I know what I'm doing wrong but I keep doing it.", 'platform': 'reddit'},
        {'signal': 'revenge trading',    'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Lost $800 and then revenge traded it into $2,400 loss by close.", 'platform': 'reddit'},
        {'signal': 'need a coach',       'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Does anyone have a trading coach that was actually worth it?", 'platform': 'reddit'},
        {'signal': 'overtrading',        'subreddit': 'Futures',    'pod': 'futures',    'example': "I take 30+ trades a day and I know it's a problem.", 'platform': 'reddit'},
        {'signal': 'emotional trading',  'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "My biggest problem is letting emotions control my trades.", 'platform': 'reddit'},
        {'signal': 'trading psychology', 'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Strategy is fine, psychology is killing me. How do you fix this?", 'platform': 'reddit'},
        {'signal': 'quit trading',       'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Seriously considering quitting. Down $12k this year.", 'platform': 'reddit'},
        {'signal': 'not profitable yet', 'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Year 1 almost done, still red. When does it click?", 'platform': 'reddit'},
    ]
    X_DEMO = [
        {'signal': 'blown my account day trading',   'pod': 'daytrading',   'example': '"blown my account day trading" — saw this 12x this week on X', 'platform': 'x'},
        {'signal': 'IV crush destroyed my trade',    'pod': 'options',      'example': '"IV crush" destroyed my trade — options traders venting on X', 'platform': 'x'},
        {'signal': 'failed prop firm eval',          'pod': 'futures',      'example': '"failed prop firm eval" — futures traders struggling with consistency', 'platform': 'x'},
        {'signal': 'got liquidated crypto',          'pod': 'crypto',       'example': '"got liquidated" — crypto traders who lost everything in a single move', 'platform': 'x'},
        {'signal': 'breakout failed again',          'pod': 'swing-trading','example': '"breakout failed again" — swing traders frustrated with fakeouts', 'platform': 'x'},
        {'signal': 'trading is rigged',              'pod': 'daytrading',   'example': '"trading is rigged" — traders losing faith after a bad streak', 'platform': 'x'},
        {'signal': 'cant hold winners',              'pod': 'daytrading',   'example': '"cant hold my winners" — cutting profits too early consistently', 'platform': 'x'},
        {'signal': 'stopped out before the move',   'pod': 'swing-trading','example': '"stopped out before the big move" — tight stops getting hunted', 'platform': 'x'},
    ]

    reddit_topics = _pull_signals('reddit', reddit_count) if reddit_count > 0 else []
    x_topics      = _pull_signals('x',      x_count)      if x_count      > 0 else []

    if not reddit_topics and reddit_count > 0:
        reddit_topics = REDDIT_DEMO[:reddit_count]
    if not x_topics and x_count > 0:
        x_topics = X_DEMO[:x_count]

    try:
        from value_post_generator import generate_targeted_post, generate_targeted_x_thread
        from database import create_value_post

        created = []
        errors  = []

        # ── Reddit posts ──────────────────────────────────────────────────────
        for t in reddit_topics:
            try:
                result = generate_targeted_post(
                    signal       = t['signal'],
                    subreddit    = t['subreddit'],
                    example_post = t.get('example', ''),
                )
                if not result:
                    errors.append({'signal': t['signal'], 'platform': 'reddit', 'error': 'generation returned empty'})
                    continue
                pid = create_value_post(
                    subreddit  = result['subreddit'],
                    post_type  = result['type'],
                    title      = result['title'],
                    body       = result['body'],
                    topic      = result.get('topic'),
                    signals    = result.get('signals', []),
                    post_count = 0,
                    client_id  = _uid(),
                )
                created.append({'id': pid, 'signal': t['signal'], 'platform': 'reddit', 'title': result['title']})
            except Exception as e:
                errors.append({'signal': t['signal'], 'platform': 'reddit', 'error': str(e)})

        # ── X threads ─────────────────────────────────────────────────────────
        for t in x_topics:
            try:
                niche = t.get('pod', 'daytrading').replace('-', ' ')
                result = generate_targeted_x_thread(
                    signal       = t['signal'],
                    niche        = niche,
                    example_post = t.get('example', ''),
                )
                if not result:
                    errors.append({'signal': t['signal'], 'platform': 'x', 'error': 'generation returned empty'})
                    continue
                # Store X threads as value posts with type='x_thread', subreddit='x'
                body = '\n\n'.join(result.get('tweets', []))
                pid = create_value_post(
                    subreddit  = 'x',
                    post_type  = 'x_thread',
                    title      = result.get('hook', t['signal'])[:200],
                    body       = body,
                    topic      = t['signal'],
                    signals    = [t['signal']],
                    post_count = 0,
                    client_id  = _uid(),
                )
                created.append({
                    'id':          pid,
                    'signal':      t['signal'],
                    'platform':    'x',
                    'hook':        result.get('hook', ''),
                    'tweet_count': result.get('tweet_count', 6),
                    'title':       result.get('hook', t['signal'])[:120],
                })
            except Exception as e:
                errors.append({'signal': t['signal'], 'platform': 'x', 'error': str(e)})

        return jsonify({'ok': True, 'created': created, 'errors': errors, 'total': len(created)})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/value-posts/<int:pid>', methods=['POST'])
@login_required
def value_post_update(pid):
    """Save edits or update status (draft → approved → posted)."""
    data = request.get_json(silent=True) or {}
    try:
        from database import update_value_post
        ok = update_value_post(
            pid,
            title    = data.get('title'),
            body     = data.get('body'),
            status   = data.get('status'),
            upvotes  = data.get('upvotes'),
            comments = data.get('comments'),
        )
        return jsonify({'ok': ok})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@api.route('/value-posts/hermes-reply-draft', methods=['POST'])
@login_required
def value_post_hermes_reply_draft():
    """
    Hermes drafts a personalized DM opener for someone who commented on a value post.
    Body: { handle, comment_body, post_title, subreddit }
    """
    data         = request.get_json(silent=True) or {}
    handle       = data.get('handle', '').strip()
    comment_body = data.get('comment_body', '').strip()
    post_title   = data.get('post_title', '').strip()
    subreddit    = data.get('subreddit', '').strip()

    if not handle or not comment_body:
        return jsonify({'ok': False, 'error': 'handle and comment_body required'}), 400

    import urllib.request as _ur, json as _j, os as _os
    api_key = _os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        # Return a sensible fallback so the UI still works without a key
        draft = (
            f"Hey u/{handle} — your comment really resonated. "
            f"That's exactly the kind of thing I work through with traders. "
            f"Mind if I share something that might help?"
        )
        return jsonify({'ok': True, 'draft': draft})

    prompt = (
        f"You are Hermes, a cold-outreach expert. A trader commented on a Reddit value post and you need to DM them.\n\n"
        f"Post title: \"{post_title}\"\n"
        f"Subreddit: r/{subreddit}\n"
        f"Their comment: \"{comment_body}\"\n\n"
        f"Write a SHORT, personalized Reddit DM to u/{handle} that:\n"
        f"1. References exactly what they said in their comment — be specific, quote or paraphrase it\n"
        f"2. Validates their pain point naturally — sounds like a real person, not a bot\n"
        f"3. Opens a door without pitching anything — one soft question at the end\n"
        f"4. Is under 280 characters\n"
        f"5. Does NOT start with 'Hey' or 'Hi' — find a more natural entry\n\n"
        f"Return ONLY the message text."
    )

    try:
        body = _j.dumps({
            "model": "claude-haiku-4-5-20251001",
            "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages", data=body, method="POST",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
        )
        with _ur.urlopen(req, timeout=15) as resp:
            draft = _j.loads(resp.read())["content"][0]["text"].strip()
        return jsonify({'ok': True, 'draft': draft})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/value-posts/coach-submit', methods=['POST'])
@login_required
def value_post_coach_submit():
    """
    Coach content panel — two modes:
      mode='expand'  → Hermes rewrites raw content into a polished post; returns preview
      mode='as_is'   → saves the content as a draft post immediately
    Body: { content, title, subreddit, mode }
    """
    data      = request.get_json(silent=True) or {}
    content   = (data.get('content') or '').strip()
    title     = (data.get('title')   or '').strip()
    subreddit = data.get('subreddit', 'Daytrading')
    mode      = data.get('mode', 'as_is')

    if not content:
        return jsonify({'ok': False, 'error': 'content is required'}), 400

    if mode == 'expand':
        from value_post_generator import expand_coach_content
        result = expand_coach_content(content, subreddit, title_hint=title)
        if not result:
            # No API key or parse failure — return graceful placeholder
            result = {
                'title': title or content[:80].split('\n')[0],
                'body':  content,
            }
        return jsonify({'ok': True, 'preview': result})

    # as_is or saving an already-expanded post
    final_title = title or content[:80].split('\n')[0].strip('# ')
    try:
        from database import _writer
        with _writer() as conn:
            conn.execute(
                """INSERT INTO value_posts (client_id, subreddit, title, body, type, status, generated_at)
                   VALUES (:cid, :sub, :title, :body, 'coach_content', 'draft', datetime('now'))""",
                {"cid": _uid(), "sub": subreddit, "title": final_title, "body": content},
            )
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/value-posts/<int:pid>/comments')
@login_required
def value_post_comments(pid):
    """
    Fetch top-level comments for a posted value post from Reddit's public JSON API.
    Returns comment author, text, score, permalink, and created time.
    """
    import urllib.request as _ur, json as _j
    post_url = request.args.get('post_url', '').strip()

    if not post_url:
        try:
            from database import _reader
            from sqlalchemy import text as _t
            with _reader() as conn:
                row = conn.execute(_t("SELECT post_url FROM value_posts WHERE id=:id"), {"id": pid}).fetchone()
                post_url = (row[0] or '') if row else ''
        except Exception:
            pass

    if not post_url:
        return jsonify({'ok': False, 'error': 'No post URL saved yet', 'comments': []})

    json_url = post_url.rstrip('/') + '.json?limit=100&sort=top'
    headers  = {'User-Agent': 'AltusFlow/1.0 (comment-reader)'}
    try:
        req = _ur.Request(json_url, headers=headers)
        with _ur.urlopen(req, timeout=10) as resp:
            raw = _j.loads(resp.read())
        comments = []
        for child in raw[1]['data']['children']:
            c = child.get('data', {})
            if c.get('author') and c['author'] not in ('[deleted]', 'AutoModerator'):
                comments.append({
                    'handle':    c['author'],
                    'body':      c.get('body', ''),
                    'score':     c.get('score', 0),
                    'permalink': 'https://reddit.com' + c.get('permalink', ''),
                    'created':   c.get('created_utc'),
                })
        comments.sort(key=lambda x: x['score'], reverse=True)
        return jsonify({'ok': True, 'comments': comments[:50]})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'comments': []})


@api.route('/value-posts/<int:pid>/check-comments', methods=['POST'])
@login_required
def value_post_check_comments(pid):
    """
    Fetch comments on a posted value post from Reddit's public JSON API.
    Creates a prospect + conversation for each new commenter (source='post_comment').
    Body: { post_url?: str }  — saves URL if provided
    """
    import urllib.request as _ur, json as _j, time as _t
    data     = request.get_json(silent=True) or {}
    post_url = data.get('post_url', '').strip()

    try:
        from database import (
            update_value_post, _reader, prospect_exists,
            add_prospect, create_conversation, add_journey_event
        )
        from sqlalchemy import text as _tx

        # Save URL if provided
        if post_url:
            update_value_post(pid, post_url=post_url)
        else:
            with _reader() as conn:
                row = conn.execute(_tx("SELECT post_url, subreddit FROM value_posts WHERE id=:id"), {"id": pid}).fetchone()
                if row:
                    post_url = row[0] or ''

        if not post_url:
            return jsonify({'ok': False, 'error': 'No post URL — paste the Reddit post URL first'}), 400

        # Fetch Reddit public JSON
        json_url = post_url.rstrip('/') + '.json?limit=100&sort=new'
        headers  = {'User-Agent': 'AltusFlow/1.0 (value-post-comment-tracker)'}
        req      = _ur.Request(json_url, headers=headers)

        try:
            with _ur.urlopen(req, timeout=10) as resp:
                raw = _j.loads(resp.read())
        except Exception as e:
            return jsonify({'ok': False, 'error': f'Reddit fetch failed: {e}. Post may need to be public.'}), 502

        # Parse comments — Reddit JSON structure: [post_data, comments_data]
        comments = []
        try:
            for child in raw[1]['data']['children']:
                c = child.get('data', {})
                if c.get('author') and c['author'] != '[deleted]':
                    comments.append({
                        'handle':    c['author'],
                        'body':      c.get('body', '')[:500],
                        'score':     c.get('score', 0),
                        'permalink': 'https://reddit.com' + c.get('permalink', ''),
                    })
        except Exception:
            return jsonify({'ok': False, 'error': 'Could not parse Reddit comment data'}), 502

        if not comments:
            return jsonify({'ok': True, 'found': 0, 'created': 0, 'message': 'No comments yet'})

        # Get subreddit from post URL
        parts    = post_url.rstrip('/').split('/')
        subreddit = parts[parts.index('r') + 1] if 'r' in parts else ''

        # Get post title for context
        try:
            post_title = raw[0]['data']['children'][0]['data'].get('title', '')
        except Exception:
            post_title = ''

        created = 0
        for c in comments:
            if prospect_exists(c['handle'], 'reddit'):
                continue
            try:
                ppid = add_prospect(
                    handle        = c['handle'],
                    platform      = 'reddit',
                    subreddit     = subreddit,
                    post_text     = c['body'],
                    post_url      = c['permalink'],
                    signal_phrase = 'post_comment',
                    upvote_score  = c['score'],
                    source        = 'post_comment',
                    niche_segment = 'trading-coaches',
                    client_id     = _uid(),
                )
                ctx = {
                    'signal':        'engaged with value post',
                    'post_text':     c['body'],
                    'post_url':      c['permalink'],
                    'post_title':    post_title,
                    'platform':      'reddit',
                    'subreddit':     subreddit,
                    'value_post_id': pid,
                }
                create_conversation(
                    prospect_id    = ppid,
                    platform       = 'reddit',
                    source         = 'post_comment',
                    source_context = ctx,
                    handle         = c['handle'],
                    subreddit      = subreddit,
                )
                add_journey_event(ppid, 'Commented on value post', '💬',
                                  f'Commented on "{post_title[:60]}"')
                created += 1
            except Exception:
                pass

        update_value_post(pid,
                          comments_checked_at=_t.strftime('%Y-%m-%dT%H:%M:%SZ', _t.gmtime()),
                          commenters_found=created)
        return jsonify({'ok': True, 'found': len(comments), 'created': created,
                        'message': f'{created} new prospects added from {len(comments)} comments'})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/value-posts/subreddits')
@login_required
def value_post_subreddits():
    """Return list of subreddits the stream has seen prospects from."""
    try:
        from database import _reader
        from sqlalchemy import text as _text
        with _reader() as conn:
            rows = conn.execute(_text("""
                SELECT DISTINCT subreddit, COUNT(*) as cnt
                FROM prospects
                WHERE subreddit IS NOT NULL AND subreddit != ''
                GROUP BY subreddit ORDER BY cnt DESC LIMIT 20
            """)).fetchall()
        return jsonify([{'subreddit': r[0], 'count': r[1]} for r in rows])
    except Exception:
        return jsonify([])


# ── Value Post Performance ────────────────────────────────────────────────────

@api.route('/value-posts/<int:pid>/performance')
@login_required
def value_post_performance(pid):
    """
    Return engagement funnel metrics for a single value post.
    { comments_pulled, dms_initiated, replies_received, calls_booked, upvotes }
    """
    try:
        from database import get_value_post_performance
        return jsonify(get_value_post_performance(pid))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/value-posts/intelligence')
@login_required
def value_posts_intelligence():
    """
    Return outcome-ranked topic intelligence: which signals drive the most
    replies and calls from value post comments.
    Used by the "What to post next" panel and the outcome-weighted generator.
    """
    try:
        from database import get_post_outcome_intelligence
        data = get_post_outcome_intelligence(client_id=_uid(), limit=20)
        return jsonify({'ok': True, 'data': data})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Conversation Sentiment Shift ──────────────────────────────────────────────

@api.route('/conversations/<int:cid>/sentiment-shift', methods=['POST'])
@login_required
def conversation_sentiment_shift(cid):
    """
    Claude Haiku call: analyse the commenter's tone vs. the original pain signal
    and return a sentiment shift label + one-line explanation + intent score.
    Stores result in conversations.source_context so it's served on next load.
    Body: { comment_body, post_title, signal } (all optional — fetched from DB if absent)
    """
    import urllib.request as _ur, json as _j, os as _os
    data = request.get_json(silent=True) or {}

    # Load from DB if not supplied
    comment_body = data.get('comment_body', '').strip()
    post_title   = data.get('post_title', '').strip()
    signal       = data.get('signal', '').strip()

    if not comment_body or not post_title:
        try:
            from database import _reader
            from sqlalchemy import text as _tx
            with _reader() as conn:
                row = conn.execute(
                    _tx("SELECT source_context FROM conversations WHERE id=:cid"),
                    {"cid": cid},
                ).fetchone()
                if row and row[0]:
                    ctx = _j.loads(row[0])
                    comment_body = comment_body or ctx.get('post_text', '')
                    post_title   = post_title   or ctx.get('post_title', '')
                    signal       = signal       or ctx.get('signal', '')
        except Exception:
            pass

    if not comment_body:
        return jsonify({'ok': False, 'error': 'No comment text available'}), 400

    api_key = _os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        fallback = {
            'label': 'Engaged → Open to conversation',
            'shift': 'They engaged publicly with the content — already warmer than a cold lead.',
            'intent': 55,
        }
        try:
            from database import update_conversation_sentiment
            update_conversation_sentiment(cid, fallback)
        except Exception:
            pass
        return jsonify({'ok': True, 'sentiment': fallback})

    prompt = (
        "You analyse sales conversation sentiment for appointment setters.\n\n"
        f"Original post topic: \"{post_title}\"\n"
        f"Pain signal: \"{signal or 'general community pain'}\"\n"
        f"Their comment: \"{comment_body}\"\n\n"
        "Analyse how this person's tone signals their readiness to buy. Return ONLY valid JSON:\n"
        "{\n"
        '  "label": "short phrase describing the shift, e.g. Passive frustration → Actively seeking solution",\n'
        '  "shift": "one sentence explaining what in their comment reveals this shift",\n'
        '  "intent": <integer 0-100 representing purchase intent>\n'
        "}\n\n"
        "Rules: label must be under 60 chars. shift must be under 120 chars. Be specific — quote their words."
    )

    try:
        body = _j.dumps({
            "model":      "claude-haiku-4-5-20251001",
            "max_tokens": 150,
            "messages":   [{"role": "user", "content": prompt}],
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages", data=body, method="POST",
            headers={
                "x-api-key":           api_key,
                "anthropic-version":   "2023-06-01",
                "content-type":        "application/json",
            },
        )
        with _ur.urlopen(req, timeout=15) as resp:
            raw_text = _j.loads(resp.read())["content"][0]["text"].strip()
        # Strip markdown fences if Claude wraps it
        if raw_text.startswith("```"):
            raw_text = "\n".join(raw_text.split("\n")[1:-1])
        sentiment = _j.loads(raw_text)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    try:
        from database import update_conversation_sentiment
        update_conversation_sentiment(cid, sentiment)
    except Exception:
        pass

    return jsonify({'ok': True, 'sentiment': sentiment})


# ── Creator / Influencer Outreach ─────────────────────────────────────────────
# Trading YouTubers, X accounts, newsletter writers — offer them free access.
# Tracked separately from prospects. These are partnerships, not sales leads.

@api.route('/creator-outreach')
@login_required
def creator_outreach_list():
    try:
        from database import _reader
        from sqlalchemy import text as _text
        _ensure_creator_table()
        with _reader() as conn:
            rows = conn.execute(_text(
                "SELECT * FROM creator_outreach ORDER BY created_at DESC"
            )).fetchall()
        from database import _rows as _r
        return jsonify(_r(rows) if rows else [])
    except Exception:
        return jsonify([])


@api.route('/creator-outreach', methods=['POST'])
@login_required
def creator_outreach_add():
    data = request.get_json(silent=True) or {}
    try:
        _ensure_creator_table()
        from database import _writer as _w
        from sqlalchemy import text as _t
        with _w() as conn:
            conn.execute(_t("""
                INSERT INTO creator_outreach
                    (handle, platform, niche, followers, draft, status, client_id)
                VALUES (:handle, :platform, :niche, :followers, :draft, 'pending_review', :cid)
            """), {
                "handle":    data.get('handle', ''),
                "platform":  data.get('platform', 'reddit'),
                "niche":     data.get('niche', 'trading-coaches'),
                "followers": data.get('followers', 0),
                "draft":     data.get('draft', ''),
                "cid":       _uid(),
            })
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@api.route('/creator-outreach/<int:cid>/draft', methods=['POST'])
@login_required
def creator_draft_generate(cid):
    """Hermes generates a partnership offer for this creator."""
    try:
        _ensure_creator_table()
        from database import _reader, _writer
        from sqlalchemy import text as _t
        import os as _os, json as _j, urllib.request as _ur

        with _reader() as conn:
            row = conn.execute(_t("SELECT * FROM creator_outreach WHERE id=:id"), {"id": cid}).fetchone()
        if not row:
            return jsonify({'ok': False, 'error': 'Not found'}), 404

        handle   = row[1] if isinstance(row, tuple) else row.get('handle', '')
        platform = row[2] if isinstance(row, tuple) else row.get('platform', 'reddit')
        niche    = row[3] if isinstance(row, tuple) else row.get('niche', 'trading-coaches')

        api_key = _os.environ.get('ANTHROPIC_API_KEY', '')
        if not api_key:
            return jsonify({'ok': False, 'error': 'ANTHROPIC_API_KEY not set'})

        prompt = (
            f"Write a short, genuine partnership message to {handle} on {platform}. "
            f"They create content about {niche.replace('-', ' ')}. "
            "We want to offer them free access to a trading coaching program in exchange for honest feedback. "
            "Must sound human and genuine — not a template. Under 180 words. "
            "Return ONLY the message text."
        )
        body = _j.dumps({
            "model": "claude-haiku-4-5-20251001", "max_tokens": 200,
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = _ur.Request(
            "https://api.anthropic.com/v1/messages", data=body, method="POST",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
        )
        with _ur.urlopen(req, timeout=15) as resp:
            draft = _j.loads(resp.read())["content"][0]["text"].strip()

        with _writer() as conn:
            conn.execute(_t("UPDATE creator_outreach SET draft=:d WHERE id=:id"),
                         {"d": draft, "id": cid})

        return jsonify({'ok': True, 'draft': draft})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@api.route('/creator-outreach/<int:cid>', methods=['POST'])
@login_required
def creator_outreach_update(cid):
    data = request.get_json(silent=True) or {}
    try:
        _ensure_creator_table()
        from database import _writer
        from sqlalchemy import text as _t
        from database import _now as _n
        sets = []
        if 'draft'    in data: sets.append("draft=:draft")
        if 'status'   in data: sets.append("status=:status")
        if 'response' in data: sets.append("response=:response")
        if not sets:
            return jsonify({'ok': False, 'error': 'nothing to update'})
        with _writer() as conn:
            conn.execute(_t(f"UPDATE creator_outreach SET {', '.join(sets)} WHERE id=:id"),
                         {**data, "id": cid})
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


def _ensure_creator_table():
    try:
        from database import _writer
        from sqlalchemy import text as _t
        with _writer() as conn:
            conn.execute(_t("""
                CREATE TABLE IF NOT EXISTS creator_outreach (
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    handle     TEXT NOT NULL,
                    platform   TEXT NOT NULL DEFAULT 'reddit',
                    niche      TEXT,
                    followers  INTEGER DEFAULT 0,
                    draft      TEXT,
                    status     TEXT NOT NULL DEFAULT 'pending_review',
                    response   TEXT,
                    client_id  TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """))
    except Exception:
        pass


# ── Live Stream ───────────────────────────────────────────────────────────────

@api.route('/stream/status')
@login_required
def stream_status():
    """Real-time stream health — shown in dashboard topbar."""
    try:
        from stream_watcher import get_stream_status
        return jsonify(get_stream_status())
    except Exception:
        return jsonify({'running': False, 'error': 'stream_watcher not loaded'})


@api.route('/stream/start', methods=['POST'])
@login_required
def stream_start():
    try:
        from stream_watcher import start
        start()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@api.route('/stream/stop', methods=['POST'])
@login_required
def stream_stop():
    try:
        from stream_watcher import stop
        stop()
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


# ── Mod Outreach ───────────────────────────────────────────────────────────────
# These are subreddit moderator introductions — NEVER prospects / sales leads.
# The UI must always show the MOD warning banner.

@api.route('/mod-outreach')
@login_required
def mod_outreach_list():
    try:
        from database import get_mod_outreach
        status = request.args.get('status')
        return jsonify(get_mod_outreach(status=status) or [])
    except Exception as e:
        return jsonify([])


@api.route('/mod-outreach/<int:mid>', methods=['POST'])
@login_required
def mod_outreach_update(mid):
    """Approve (mark sent) or dismiss a mod outreach record."""
    data   = request.get_json(silent=True) or {}
    status = data.get('status', 'sent')
    resp   = data.get('response', '')
    try:
        from database import update_mod_outreach
        ok = update_mod_outreach(mid, status, response=resp)
        return jsonify({'ok': ok})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@api.route('/mod-outreach/<int:mid>/draft', methods=['POST'])
@login_required
def mod_outreach_save_draft(mid):
    """Rep edited the Hermes draft before sending."""
    draft = (request.get_json(silent=True) or {}).get('draft', '')
    try:
        from database import save_mod_outreach_draft
        ok = save_mod_outreach_draft(mid, draft)
        return jsonify({'ok': ok})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


# ── Command Center ────────────────────────────────────────────────────────────

@api.route('/command-center')
@login_required
def command_center_overview():
    """Agency command center — all tenants with aggregate pipeline stats + pod health."""
    import os as _os
    import sqlite3 as _sqlite3

    tenants = []
    try:
        from master_db import get_active_tenants
        tenants = get_active_tenants() or []
    except Exception:
        pass

    result = []
    for t in tenants:
        slug    = t.get('slug', '')
        db_path = _os.path.join('tenants', slug, 'outbound_hunter.db')
        exists  = _os.path.isfile(db_path)
        stats   = {'total': 0, 'pending': 0, 'sent': 0, 'replied': 0, 'booked': 0, 'closed_won': 0}
        last_scan = None

        if exists:
            try:
                with _sqlite3.connect(db_path) as conn:
                    conn.row_factory = _sqlite3.Row
                    row = conn.execute("""
                        SELECT
                            COUNT(*) AS total,
                            SUM(CASE WHEN status IN ('pending_review','new') THEN 1 ELSE 0 END) AS pending,
                            SUM(CASE WHEN status='sent'       THEN 1 ELSE 0 END) AS sent,
                            SUM(CASE WHEN status='replied'    THEN 1 ELSE 0 END) AS replied,
                            SUM(CASE WHEN status='booked'     THEN 1 ELSE 0 END) AS booked,
                            SUM(CASE WHEN status='closed_won' THEN 1 ELSE 0 END) AS closed_won,
                            MAX(scraped_at) AS last_scan
                        FROM prospects
                    """).fetchone()
                    if row:
                        d         = dict(row)
                        last_scan = d.pop('last_scan', None)
                        stats     = {k: (v or 0) for k, v in d.items()}
            except Exception:
                pass

        result.append({
            'slug':         slug,
            'company_name': t.get('company_name', slug),
            'plan':         t.get('plan', 'starter'),
            'is_active':    bool(t.get('is_active', 1)),
            'created_at':   t.get('created_at'),
            'db_exists':    exists,
            'stats':        stats,
            'last_scan':    last_scan,
        })

    # Pod health from orchestrator registry
    pods = []
    try:
        from database import get_all_pod_statuses
        raw = get_all_pod_statuses() or []
        pods = [
            {
                'slug':               p.get('pod_slug'),
                'pod_label':          p.get('pod_label') or p.get('pod_slug'),
                'is_paused':          bool(p.get('is_paused')),
                'circuit_breaker_open': bool(p.get('circuit_breaker_open')),
                'prospects_found_today': p.get('last_found', 0),
                'last_run_at':        p.get('last_run_created'),
                'last_status':        p.get('last_status'),
            }
            for p in raw
        ]
    except Exception:
        pass

    return jsonify({'tenants': result, 'pods': pods})


@api.route('/command-center/run-all', methods=['POST'])
@login_required
def command_center_run_all():
    """Trigger every registered pod immediately."""
    results = {}
    try:
        from scheduler import run_pod_now
        from database import get_all_pod_statuses as _all_pods
        pods  = _all_pods() or []
        slugs = [p.get('pod_slug') for p in pods if p.get('pod_slug')]
        for slug in slugs:
            try:
                run_pod_now(slug)
                results[slug] = 'triggered'
            except Exception as e:
                results[slug] = f'error: {e}'
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e), 'results': results})
    return jsonify({'ok': True, 'triggered': len(results), 'results': results})


# ── Integrations ───────────────────────────────────────────────────────────────

@api.route('/integrations')
@login_required
def integrations_list():
    """Return all saved integrations for this user, merged with the catalog."""
    from integrations import CATALOG
    saved = {r['slug']: r for r in (get_integrations(_uid()) or [])}
    result = []
    for item in CATALOG:
        slug = item['slug']
        row  = saved.get(slug, {})
        result.append({
            **item,
            'enabled': row.get('enabled', False),
            'config':  row.get('config', {}),
        })
    return jsonify(result)


@api.route('/integrations/<slug>', methods=['POST'])
@login_required
def integration_save(slug):
    """Save (upsert) an integration config."""
    data    = request.get_json(silent=True) or {}
    enabled = bool(data.get('enabled', False))
    config  = data.get('config', {})
    ok = save_integration(_uid(), slug, enabled, config)
    return jsonify({'ok': ok})


@api.route('/integrations/<slug>/test', methods=['POST'])
@login_required
def integration_test(slug):
    """Fire a test payload to the configured endpoint."""
    cfg = get_integration(_uid(), slug)
    if not cfg:
        return jsonify({'ok': False, 'error': 'Not configured — save first'})
    try:
        from integrations import _build_payload, _FIRERS
        test_prospect = {
            'id': 0, 'handle': 'test_prospect', 'name': 'Test Prospect',
            'niche': 'trading-coaches', 'platform': 'reddit',
            'icp_score': 9.2, 'post_text': 'This is a test event from AltusFlow.',
            'profile_url': '', 'status': 'approved', 'scraped_at': None,
        }
        payload = _build_payload('prospect.test', test_prospect)
        firer   = _FIRERS.get(slug)
        if not firer:
            return jsonify({'ok': False, 'error': f'No connector built for {slug} yet'})
        firer(cfg.get('config') or {}, payload)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


# ── Inbound webhook (public — no login) ───────────────────────────────────────

@api.route('/webhooks/scrapebadger', methods=['POST'])
def webhook_scrapebadger():
    """
    Scrape Badger webhook — receives high-intent leads from Reddit + X.
    Flexible field mapping: accepts their native payload format.
    No auth key required if SCRAPEBADGER_WEBHOOK_SECRET not set (dev mode).

    Expected fields (all optional except handle/username):
      handle / username / author    — Reddit u/ or X @
      platform                      — 'reddit' | 'twitter' | 'x'
      subreddit                     — subreddit name (Reddit only)
      post_url / url / permalink    — link to the original post
      post_text / text / body / selftext — content of the post
      signal / pain_point / signal_phrase — detected pain signal
      score / upvotes               — post score
      intent_score                  — 0-100 Scrape Badger intent score
    """
    import os, json as _json
    secret = os.environ.get('SCRAPEBADGER_WEBHOOK_SECRET', '')
    if secret:
        given = request.headers.get('X-Scrapebadger-Secret') or request.args.get('secret', '')
        if given != secret:
            return jsonify({'ok': False, 'error': 'unauthorized'}), 401

    data = request.get_json(silent=True) or {}
    # Support both single lead and array of leads
    leads = data if isinstance(data, list) else [data]

    try:
        from database import (
            prospect_exists, add_prospect, create_conversation, add_journey_event
        )
    except ImportError as e:
        return jsonify({'ok': False, 'error': str(e)}), 500

    created = 0
    skipped = 0

    for lead in leads:
        # Flexible field extraction
        handle    = (lead.get('handle') or lead.get('username') or lead.get('author') or '').strip().lstrip('u/').lstrip('@')
        platform  = (lead.get('platform') or 'reddit').lower().replace('twitter', 'x')
        subreddit = (lead.get('subreddit') or '').strip().lstrip('r/')
        post_url  = lead.get('post_url') or lead.get('url') or lead.get('permalink') or ''
        post_text = lead.get('post_text') or lead.get('text') or lead.get('body') or lead.get('selftext') or ''
        signal    = lead.get('signal') or lead.get('pain_point') or lead.get('signal_phrase') or ''
        score     = int(lead.get('score') or lead.get('upvotes') or 0)
        intent    = float(lead.get('intent_score') or 0)

        if not handle:
            skipped += 1
            continue

        if prospect_exists(handle, platform):
            skipped += 1
            continue

        try:
            pid = add_prospect(
                handle         = handle,
                platform       = platform,
                subreddit      = subreddit,
                post_text      = post_text[:2000],
                post_url       = post_url,
                signal_phrase  = signal,
                upvote_score   = score,
                intent_score   = intent,
                source         = 'scrapebadger',
                niche_segment  = 'trading-coaches',
                client_id      = _uid(),
            )
            ctx = {
                'signal':    signal,
                'post_url':  post_url,
                'post_text': post_text[:300],
                'platform':  platform,
                'subreddit': subreddit,
                'score':     score,
                'intent':    intent,
            }
            cid = create_conversation(
                prospect_id    = pid,
                platform       = platform,
                source         = 'scrapebadger',
                source_context = ctx,
                handle         = handle,
                subreddit      = subreddit,
            )
            add_journey_event(pid, 'Scrape Badger lead', '🎯',
                              f'Found on {platform} — signal: "{signal}"')
            created += 1
        except Exception as e:
            skipped += 1

    return jsonify({'ok': True, 'created': created, 'skipped': skipped})


@api.route('/webhooks/inbound/<api_key>', methods=['POST'])
def webhook_inbound(api_key):
    """
    Receive status updates from external tools (Calendly, Zapier, etc.).
    Payload: { event, prospect_handle, platform, note }
    api_key must match INBOUND_WEBHOOK_KEY env var or a stored tenant key.
    """
    import os
    expected = os.environ.get('INBOUND_WEBHOOK_KEY', '')
    if not expected or api_key != expected:
        abort(401)

    data   = request.get_json(silent=True) or {}
    event  = data.get('event', '').strip()
    handle = data.get('prospect_handle', '').strip()
    plat   = data.get('platform', 'reddit').strip()
    note   = data.get('note', '').strip()

    if not event or not handle:
        return jsonify({'ok': False, 'error': 'event and prospect_handle required'}), 400

    # Map event → status + journey label
    _EVENT_MAP = {
        'prospect.replied':    ('replied',    'Replied',      '↩️'),
        'prospect.booked':     ('booked',     'Call booked',  '📅'),
        'prospect.closed_won': ('closed_won', 'Closed won',   '🏆'),
    }

    try:
        from database import get_prospects, update_status, add_journey_event
        matches = [p for p in (get_prospects(limit=500) or [])
                   if p.get('handle') == handle and (not plat or p.get('platform') == plat)]
        if not matches:
            return jsonify({'ok': False, 'error': f'Prospect @{handle} not found'}), 404

        pid = matches[0]['id']
        if event in _EVENT_MAP:
            status, ev_label, icon = _EVENT_MAP[event]
            update_status(pid, status)
            if note:
                add_journey_event(pid, ev_label, icon, note)
        else:
            add_journey_event(pid, event, '📌', note or event)

        return jsonify({'ok': True, 'prospect_id': pid})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Discord Watcher ───────────────────────────────────────────────────────────

@api.route('/discord/channels')
@login_required
def discord_channels_list():
    """Return all configured Discord channels."""
    try:
        from database import get_discord_channels
        channels = get_discord_channels(enabled_only=False)
        return jsonify(channels)
    except Exception as e:
        return jsonify([])


@api.route('/discord/channels', methods=['POST'])
@login_required
def discord_channels_add():
    """
    Add a Discord channel to watch.
    Body: { channel_id, guild_id, guild_name?, channel_name?, pod_slug? }
    If only channel_id is provided, we try to fetch guild_id + name from Discord API.
    """
    data = request.get_json(silent=True) or {}
    channel_id = data.get('channel_id', '').strip()
    if not channel_id:
        return jsonify({'ok': False, 'error': 'channel_id required'}), 400

    guild_id     = data.get('guild_id', '').strip()
    guild_name   = data.get('guild_name', '').strip() or None
    channel_name = data.get('channel_name', '').strip() or None
    pod_slug     = data.get('pod_slug', 'daytrading').strip()

    # Try to auto-populate from Discord API if guild_id missing
    if not guild_id:
        try:
            from discord_watcher import get_channel_info
            info = get_channel_info(channel_id)
            if info:
                guild_id     = info.get('guild_id', '')
                channel_name = channel_name or info.get('name')
        except Exception:
            pass

    if not guild_id:
        return jsonify({'ok': False, 'error': 'guild_id required (or provide a bot token so we can look it up)'}), 400

    try:
        from database import add_discord_channel
        result = add_discord_channel(
            guild_id=guild_id, channel_id=channel_id,
            guild_name=guild_name, channel_name=channel_name,
            pod_slug=pod_slug,
        )
        return jsonify({'ok': bool(result), 'channel': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/discord/channels/<channel_id>', methods=['DELETE'])
@login_required
def discord_channels_remove(channel_id):
    """Remove a Discord channel from the watch list."""
    try:
        from database import remove_discord_channel
        ok = remove_discord_channel(channel_id)
        return jsonify({'ok': ok})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/discord/validate', methods=['POST'])
@login_required
def discord_validate_token():
    """Test that the DISCORD_BOT_TOKEN in .env is valid."""
    try:
        from discord_watcher import validate_connection
        bot_token = (request.get_json(silent=True) or {}).get('bot_token')
        result    = validate_connection(bot_token=bot_token)
        return jsonify(result)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@api.route('/discord/poll', methods=['POST'])
@login_required
def discord_poll_now():
    """Trigger an immediate poll of all enabled Discord channels (admin use)."""
    try:
        from discord_watcher import run_all_polls
        results = run_all_polls()
        total   = sum(r.get('stored', 0) for r in results)
        return jsonify({'ok': True, 'channels_polled': len(results),
                        'total_stored': total, 'results': results})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Lead Attribution ──────────────────────────────────────────────────────────

@api.route('/attribution/link', methods=['POST'])
@login_required
def attribution_create_link():
    """
    Generate a tracked attribution link for a conversation/prospect.
    Body: { prospect_id?, conversation_id?, value_post_id?, pod_slug?, base_url? }
    Returns: { lead_id, tracking_url }
    """
    data = request.get_json(silent=True) or {}
    base_url = data.get('base_url', os.environ.get('SITE_BASE_URL', 'https://altusflow.ai'))

    try:
        from database import create_lead_attribution
        lead_id = create_lead_attribution(
            prospect_id     = data.get('prospect_id'),
            conversation_id = data.get('conversation_id'),
            value_post_id   = data.get('value_post_id'),
            pod_slug        = data.get('pod_slug'),
            source_platform = data.get('source_platform', 'reddit'),
        )
        if not lead_id:
            return jsonify({'ok': False, 'error': 'DB error creating attribution'}), 500

        tracking_url = f"{base_url.rstrip('/')}/?ref=altusflow_dm&lead_id={lead_id}"
        return jsonify({'ok': True, 'lead_id': lead_id, 'tracking_url': tracking_url})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/attribution/click/<lead_id>', methods=['POST'])
def attribution_record_click(lead_id):
    """
    Record a link click. Called by the landing page middleware when
    ?ref=altusflow_dm&lead_id=... is detected. No auth required (public endpoint).
    """
    try:
        from database import record_lead_click
        record_lead_click(lead_id)
        return jsonify({'ok': True})
    except Exception:
        return jsonify({'ok': True})  # Always 200 so landing page doesn't error


@api.route('/attribution/convert', methods=['POST'])
def attribution_record_conversion():
    """
    Record a conversion (signup). Called by your signup endpoint.
    Body: { lead_id, internal_user_id }
    This endpoint should be called server-side (from your auth service),
    not exposed directly to the public — secure with a shared secret in prod.
    """
    data            = request.get_json(silent=True) or {}
    lead_id         = data.get('lead_id', '').strip()
    internal_user_id = data.get('internal_user_id', '').strip()

    if not lead_id or not internal_user_id:
        return jsonify({'ok': False, 'error': 'lead_id and internal_user_id required'}), 400

    try:
        from database import record_lead_conversion
        ok = record_lead_conversion(lead_id, internal_user_id)
        return jsonify({'ok': ok})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/attribution/stats')
@login_required
def attribution_stats():
    """Return conversion funnel stats for the dashboard."""
    pod_slug = request.args.get('pod_slug')
    try:
        from database import get_attribution_stats
        stats = get_attribution_stats(pod_slug=pod_slug)
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/attribution/<lead_id>')
@login_required
def attribution_lookup(lead_id):
    """Look up a single attribution record by lead_id."""
    try:
        from database import get_attribution_by_lead_id
        record = get_attribution_by_lead_id(lead_id)
        if not record:
            return jsonify({'error': 'Not found'}), 404
        return jsonify(record)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Auto-Generate (zero input) ───────────────────────────────────────────────

@api.route('/value-posts/auto-generate', methods=['POST'])
@login_required
def value_posts_auto_generate():
    """
    Fully AI-driven generation — no user input required.
    AI picks the top trending pain signal and writes the content.
    Body: { platform: 'reddit'|'x'|'auto' }
      'auto' → picks whichever platform has stronger recent signals
    Returns: { ok, created: { id, platform, title, signal, subreddit?, tweet_count? } }
    """
    data            = request.get_json(silent=True) or {}
    platform        = data.get('platform', 'auto').lower()
    signal_override = data.get('signal_override', '').strip()
    pod_override    = data.get('pod', '').strip()
    sub_override    = data.get('subreddit', '').strip()

    REDDIT_FALLBACK = [
        {'signal': 'blown account',      'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Just blew my 3rd account. I know what I'm doing wrong but I keep doing it."},
        {'signal': 'revenge trading',    'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Lost $800 then revenge traded it to $2,400 loss by close."},
        {'signal': 'need a coach',       'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Does anyone have a trading coach that was actually worth it?"},
        {'signal': 'overtrading',        'subreddit': 'Futures',    'pod': 'futures',    'example': "I take 30+ trades a day and I know it's a problem."},
        {'signal': 'trading psychology', 'subreddit': 'Daytrading', 'pod': 'daytrading', 'example': "Strategy is fine, psychology is killing me."},
    ]
    X_FALLBACK = [
        {'signal': 'blown my account day trading', 'pod': 'daytrading',   'example': '"blown my account" day trading'},
        {'signal': 'IV crush destroyed my trade',  'pod': 'options',      'example': '"IV crush" destroyed my trade'},
        {'signal': 'failed prop firm eval',        'pod': 'futures',      'example': '"failed prop firm eval" — consistency issues'},
        {'signal': 'got liquidated crypto',        'pod': 'crypto',       'example': '"got liquidated" crypto'},
        {'signal': 'breakout failed again',        'pod': 'swing-trading','example': '"breakout failed" swing trade fakeout'},
    ]

    def _top_signal(src_platform):
        try:
            from database import _reader
            from sqlalchemy import text as _t
            plat_filter = "AND (platform='x' OR platform='twitter')" if src_platform == 'x' else "AND (platform='reddit' OR platform IS NULL)"
            with _reader() as conn:
                row = conn.execute(_t(f"""
                    SELECT signal_phrase,
                           GROUP_CONCAT(DISTINCT subreddit) AS subs,
                           GROUP_CONCAT(DISTINCT pod_slug)  AS pods,
                           MIN(post_text) AS example,
                           COUNT(*) AS cnt
                    FROM prospects
                    WHERE signal_phrase IS NOT NULL AND signal_phrase != ''
                      AND scraped_at >= datetime('now', '-14 days')
                      {plat_filter}
                    GROUP BY signal_phrase
                    ORDER BY cnt DESC
                    LIMIT 1
                """)).fetchone()
            if row:
                return {
                    'signal':   row[0],
                    'subreddit': (row[1] or 'Daytrading').split(',')[0].strip(),
                    'pod':      (row[2] or 'daytrading').split(',')[0].strip(),
                    'example':  row[3] or '',
                    'count':    row[4] or 0,
                    'platform': src_platform,
                }
        except Exception:
            pass
        return None

    # If signal_override provided, build signal_data directly from it
    if signal_override:
        if platform == 'auto':
            platform = 'reddit'
        signal_data = {
            'signal':    signal_override,
            'subreddit': sub_override or 'Daytrading',
            'pod':       pod_override or 'daytrading',
            'example':   '',
            'count':     0,
            'platform':  platform,
        }
    else:
        # Decide platform
        if platform == 'auto':
            r_sig = _top_signal('reddit')
            x_sig = _top_signal('x')
            r_cnt = r_sig['count'] if r_sig else 0
            x_cnt = x_sig['count'] if x_sig else 0
            if r_cnt == 0 and x_cnt == 0:
                import random
                platform = random.choice(['reddit', 'x'])
            else:
                platform = 'reddit' if r_cnt >= x_cnt else 'x'

        signal_data = _top_signal(platform)

        if not signal_data:
            import random
            if platform == 'reddit':
                signal_data = random.choice(REDDIT_FALLBACK)
                signal_data['platform'] = 'reddit'
            else:
                signal_data = random.choice(X_FALLBACK)
                signal_data['platform'] = 'x'

    try:
        from database import create_value_post

        if platform == 'reddit':
            from value_post_generator import generate_targeted_post
            result = generate_targeted_post(
                signal       = signal_data['signal'],
                subreddit    = signal_data.get('subreddit', 'Daytrading'),
                example_post = signal_data.get('example', ''),
            )
            if not result:
                return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500
            pid = create_value_post(
                subreddit      = result['subreddit'],
                post_type      = result['type'],
                title          = result['title'],
                body           = result['body'],
                topic          = result.get('topic'),
                signals        = result.get('signals', []),
                post_count     = 0,
                client_id      = _uid(),
                source_signal  = signal_data['signal'],
                platform       = 'reddit',
                image_prompt   = result.get('image_prompt'),
            )
            created = {
                'id':        pid,
                'platform':  'reddit',
                'signal':    signal_data['signal'],
                'subreddit': result['subreddit'],
                'title':     result['title'],
            }
            if pid:
                try:
                    import telegram_approver as _tg
                    _tg.send_for_review(pid, {**result, 'platform': 'reddit', 'signal': signal_data['signal'], 'source_signal': signal_data['signal']})
                except Exception:
                    pass
            return jsonify({'ok': True, 'created': created})

        else:  # x
            from value_post_generator import generate_targeted_x_thread
            niche  = (pod_override or signal_data.get('pod', 'daytrading')).replace('-', ' ')
            result = generate_targeted_x_thread(
                signal       = signal_data['signal'],
                niche        = niche,
                example_post = signal_data.get('example', ''),
            )
            if not result:
                return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500
            body = '\n\n'.join(result.get('tweets', []))
            hook = result.get('hook', signal_data['signal'])
            pid  = create_value_post(
                subreddit      = 'x',
                post_type      = 'x_thread',
                title          = hook[:200],
                body           = body,
                topic          = signal_data['signal'],
                signals        = [signal_data['signal']],
                post_count     = 0,
                client_id      = _uid(),
                source_signal  = signal_data['signal'],
                platform       = 'x',
                image_prompt   = result.get('image_prompt'),
            )
            created = {
                'id':          pid,
                'platform':    'x',
                'signal':      signal_data['signal'],
                'hook':        hook,
                'tweet_count': result.get('tweet_count', 6),
                'title':       hook[:120],
            }
            if pid:
                try:
                    import telegram_approver as _tg
                    _tg.send_for_review(pid, {**result, 'platform': 'x', 'signal': signal_data['signal'], 'source_signal': signal_data['signal']})
                except Exception:
                    pass
            return jsonify({'ok': True, 'created': created})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Live Signal Feed ──────────────────────────────────────────────────────────

@api.route('/signals/live')
@login_required
def signals_live():
    """
    Live pain signal feed — signals seen in last 48h, sorted by recency.
    Returns: list of { signal, platform, count, last_seen, subreddit, pod_slug, example }
    """
    from datetime import datetime, timedelta
    SIGNAL_DEMO = [
        {'signal': 'blown account day trading',  'platform': 'reddit', 'count': 14, 'last_seen': (datetime.utcnow()-timedelta(hours=2)).isoformat(), 'subreddits': 'Daytrading', 'pods': 'daytrading', 'example': "Just blew my 3rd account. I know what I'm doing wrong but I keep doing it."},
        {'signal': 'revenge trading spiral',     'platform': 'reddit', 'count': 11, 'last_seen': (datetime.utcnow()-timedelta(hours=3)).isoformat(), 'subreddits': 'Daytrading', 'pods': 'daytrading', 'example': 'Lost $800 then revenge traded it to $2,400 loss by close.'},
        {'signal': 'IV crush destroyed trade',   'platform': 'x',      'count':  9, 'last_seen': (datetime.utcnow()-timedelta(hours=1)).isoformat(), 'subreddits': '', 'pods': 'options', 'example': '"IV crush" destroyed my trade — options traders venting'},
        {'signal': 'failed prop firm eval',      'platform': 'x',      'count':  8, 'last_seen': (datetime.utcnow()-timedelta(hours=4)).isoformat(), 'subreddits': '', 'pods': 'futures', 'example': 'Failed my 3rd prop firm eval — same mistake every time'},
        {'signal': 'overtrading problem',        'platform': 'reddit', 'count':  7, 'last_seen': (datetime.utcnow()-timedelta(hours=5)).isoformat(), 'subreddits': 'Futures', 'pods': 'futures', 'example': "I take 30+ trades a day and I know it's a problem."},
        {'signal': 'got liquidated crypto',      'platform': 'x',      'count':  6, 'last_seen': (datetime.utcnow()-timedelta(hours=6)).isoformat(), 'subreddits': '', 'pods': 'crypto', 'example': '"got liquidated" — crypto traders who lost everything'},
        {'signal': 'psychology killing my edge', 'platform': 'reddit', 'count':  5, 'last_seen': (datetime.utcnow()-timedelta(hours=7)).isoformat(), 'subreddits': 'Daytrading', 'pods': 'daytrading', 'example': 'Strategy is fine, psychology is killing me. How do you fix this?'},
        {'signal': 'breakout fakeout again',     'platform': 'x',      'count':  4, 'last_seen': (datetime.utcnow()-timedelta(hours=8)).isoformat(), 'subreddits': '', 'pods': 'swing-trading', 'example': '"breakout failed again" — swing traders frustrated with fakeouts'},
    ]
    try:
        from database import _reader
        from sqlalchemy import text as _t
        with _reader() as conn:
            rows = conn.execute(_t("""
                SELECT
                    signal_phrase,
                    platform,
                    COUNT(*) AS cnt,
                    MAX(scraped_at) AS last_seen,
                    GROUP_CONCAT(DISTINCT subreddit) AS subreddits,
                    GROUP_CONCAT(DISTINCT pod_slug) AS pods,
                    MIN(post_text) AS example
                FROM prospects
                WHERE signal_phrase IS NOT NULL AND signal_phrase != ''
                  AND scraped_at >= datetime('now', '-48 hours')
                GROUP BY signal_phrase, platform
                ORDER BY last_seen DESC
                LIMIT 40
            """)).fetchall()
        if rows:
            results = [
                {
                    'signal':     r[0],
                    'platform':   r[1] or 'reddit',
                    'count':      r[2],
                    'last_seen':  r[3],
                    'subreddits': r[4] or '',
                    'pods':       r[5] or '',
                    'example':    r[6] or '',
                }
                for r in rows
            ]
            return jsonify(results)
        return jsonify(SIGNAL_DEMO)
    except Exception:
        return jsonify(SIGNAL_DEMO)


# ── Value Posts Performance ────────────────────────────────────────────────────

@api.route('/value-posts/performance')
@login_required
def value_posts_performance():
    """Posts with lead attribution."""
    try:
        from database import get_value_posts_performance
        results = get_value_posts_performance(_uid())
        return jsonify(results)
    except Exception:
        return jsonify([])


# ── Approve a Draft ───────────────────────────────────────────────────────────

@api.route('/value-posts/<int:pid>/approve', methods=['POST'])
@login_required
def value_post_approve(pid):
    """Approve a draft → status='approved'."""
    try:
        from database import _writer
        from sqlalchemy import text as _t
        with _writer() as conn:
            conn.execute(_t("""
                UPDATE value_posts SET status='approved'
                WHERE id=:id AND client_id=:cid
            """), {"id": pid, "cid": _uid()})
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── X Thread Generator ────────────────────────────────────────────────────────

@api.route('/value-posts/generate-thread', methods=['POST'])
@login_required
def value_posts_generate_thread():
    """
    Generate a native X thread (5-7 tweets) for a topic.
    Body: { topic, niche?, hook_style? }
    hook_style: 'contrarian' | 'story' | 'list'
    Returns: { ok, thread: { tweets, hook, tweet_count, topic, ... } }
    """
    data       = request.get_json(silent=True) or {}
    topic      = data.get('topic', '').strip()
    niche      = data.get('niche', 'trading').strip()
    hook_style = data.get('hook_style', 'contrarian').strip()

    if not topic:
        return jsonify({'ok': False, 'error': 'topic required'}), 400

    try:
        from value_post_generator import generate_x_thread
        result = generate_x_thread(topic=topic, niche=niche, hook_style=hook_style)
        if not result:
            return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500
        return jsonify({'ok': True, 'thread': result})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/value-posts/save-thread', methods=['POST'])
@login_required
def value_posts_save_thread():
    """
    Save a generated X thread as a draft value post.
    Body: { thread: { hook, tweets, tweet_count, topic?, niche? } }
    Returns: { ok, id }
    """
    data   = request.get_json(silent=True) or {}
    thread = data.get('thread', {})
    tweets = thread.get('tweets', [])
    hook   = thread.get('hook', tweets[0] if tweets else '')
    topic  = thread.get('topic') or thread.get('niche') or 'x thread'

    if not tweets:
        return jsonify({'ok': False, 'error': 'no tweets in thread'}), 400

    try:
        from database import create_value_post
        body = '\n\n'.join(tweets)
        pid  = create_value_post(
            subreddit  = 'x',
            post_type  = 'x_thread',
            title      = hook[:200],
            body       = body,
            topic      = topic,
            signals    = [topic] if topic else [],
            post_count = 0,
            client_id  = _uid(),
        )
        return jsonify({'ok': True, 'id': pid})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/value-posts/expand-to-thread', methods=['POST'])
@login_required
def value_posts_expand_to_thread():
    """
    Expand a coach's raw content into an X thread and save as draft.
    Body: { content, niche? }
    Returns: { ok, thread, id }
    """
    data    = request.get_json(silent=True) or {}
    content = data.get('content', '').strip()
    niche   = data.get('niche', 'trading').strip()

    if not content:
        return jsonify({'ok': False, 'error': 'content required'}), 400

    try:
        from value_post_generator import expand_to_x_thread
        from database import create_value_post
        result = expand_to_x_thread(raw_content=content, niche=niche)
        if not result:
            return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500

        body = '\n\n'.join(result.get('tweets', []))
        hook = result.get('hook', '')
        pid  = create_value_post(
            subreddit  = 'x',
            post_type  = 'x_thread',
            title      = hook[:200],
            body       = body,
            topic      = niche,
            signals    = [],
            post_count = 0,
            client_id  = _uid(),
        )
        return jsonify({'ok': True, 'thread': result, 'id': pid})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Content Results ───────────────────────────────────────────────────────────

@api.route('/value-posts/results')
@login_required
def value_posts_results():
    """Aggregate results for the Results tab — upvotes, comments, leads, best subs."""
    try:
        from database import get_content_results
        return jsonify(get_content_results(_uid()))
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/value-posts/check-duplicate', methods=['POST'])
@login_required
def value_posts_check_duplicate():
    """Check if a new post angle duplicates recent content to the same subreddit."""
    data      = request.get_json(silent=True) or {}
    subreddit = data.get('subreddit', '').strip()
    title     = data.get('title', '').strip()
    topic     = data.get('topic', '').strip()

    if not subreddit:
        return jsonify({'is_duplicate': False, 'risk': 'low', 'reason': 'No subreddit provided.'})
    try:
        from value_post_generator import check_duplicate
        result = check_duplicate(subreddit, title, topic, _uid())
        return jsonify(result)
    except Exception as e:
        return jsonify({'is_duplicate': False, 'risk': 'low', 'reason': str(e)})


@api.route('/value-posts/comment-leads')
@login_required
def value_posts_comment_leads():
    """Comment leads from our posted content."""
    try:
        from database import get_comment_leads
        leads = get_comment_leads(client_id=_uid())
        return jsonify(leads)
    except Exception as e:
        return jsonify([])


# ── Niche Delivery ────────────────────────────────────────────────────────────

@api.route('/delivery/stats')
@login_required
def delivery_stats():
    """Return per-pod lead delivery stats for the NicheDelivery screen."""
    try:
        from database import _reader
        from sqlalchemy import text as _t

        with _reader() as conn:
            rows = conn.execute(_t("""
                SELECT
                    pod_slug,
                    COUNT(*)                                                         AS total_leads,
                    COUNT(CASE WHEN scraped_at >= datetime('now', '-7 days') THEN 1 END)  AS leads_this_week,
                    COUNT(CASE WHEN scraped_at >= datetime('now', '-14 days')
                               AND scraped_at <  datetime('now', '-7 days')  THEN 1 END)  AS leads_last_week,
                    COUNT(CASE WHEN icp_score >= 5 THEN 1 END)                       AS qualified,
                    COUNT(CASE WHEN status IN ('replied','call','closed_won') THEN 1 END) AS sent_to_client,
                    MAX(scraped_at)                                                   AS last_activity,
                    platform                                                          AS top_platform,
                    signal_phrase                                                     AS hot_signal
                FROM prospects
                WHERE pod_slug IS NOT NULL
                GROUP BY pod_slug
                ORDER BY leads_this_week DESC
            """)).fetchall()

        stats = []
        for r in rows:
            stats.append({
                'pod_slug':         r[0],
                'total_leads':      r[1] or 0,
                'leads_this_week':  r[2] or 0,
                'leads_last_week':  r[3] or 0,
                'qualified':        r[4] or 0,
                'sent_to_client':   r[5] or 0,
                'last_delivery':    r[6],
                'top_platform':     r[7],
                'hot_signal':       r[8],
                'label':            r[0].replace('-', ' ').title(),
            })

        return jsonify(stats if stats else [])
    except Exception as e:
        return jsonify([])


@api.route('/delivery/package', methods=['POST'])
@login_required
def delivery_package():
    """
    Mark all qualified, uncontacted prospects for a pod as 'sent to client'.
    This represents the weekly lead package delivery.
    Body: { pod_slug }
    """
    data     = request.get_json(silent=True) or {}
    pod_slug = data.get('pod_slug', '').strip()
    if not pod_slug:
        return jsonify({'ok': False, 'error': 'pod_slug required'}), 400

    try:
        from database import _writer, CLIENT_ID as _cid
        from sqlalchemy import text as _t

        with _writer() as conn:
            result = conn.execute(_t("""
                UPDATE prospects
                SET status = 'packaged', packaged_at = datetime('now')
                WHERE pod_slug = :slug
                  AND client_id = :cid
                  AND icp_score >= 5
                  AND status = 'pending'
            """), {"slug": pod_slug, "cid": _cid})
            affected = result.rowcount if hasattr(result, 'rowcount') else 0

        return jsonify({'ok': True, 'packaged': affected, 'pod_slug': pod_slug})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/delivery/export')
@login_required
def delivery_export():
    """
    Export packaged/qualified prospects as CSV for a given pod.
    Query params: pod_slug, format=csv
    """
    pod_slug = request.args.get('pod_slug', '').strip()
    if not pod_slug:
        return jsonify({'error': 'pod_slug required'}), 400

    try:
        from database import _reader, CLIENT_ID as _cid
        from sqlalchemy import text as _t
        import csv, io

        with _reader() as conn:
            rows = conn.execute(_t("""
                SELECT handle, name, platform, signal_phrase, icp_score,
                       profile_url, post_url, scraped_at, status
                FROM prospects
                WHERE pod_slug = :slug AND client_id = :cid
                  AND icp_score >= 5
                ORDER BY icp_score DESC, scraped_at DESC
                LIMIT 500
            """), {"slug": pod_slug, "cid": _cid}).fetchall()

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(['handle','name','platform','signal','score','profile_url','post_url','scraped_at','status'])
        for r in rows:
            w.writerow(list(r))

        from flask import Response
        return Response(
            buf.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={pod_slug}-leads.csv'},
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ── Reddit Top Posts ───────────────────────────────────────────────────────────

@api.route('/top-posts')
@login_required
def get_top_posts_route():
    """Return stored top posts for a subreddit."""
    sub    = request.args.get('subreddit', '')
    period = request.args.get('period', 'week')
    limit  = int(request.args.get('limit', 20))
    try:
        from database import get_top_posts
        posts = get_top_posts(subreddit=sub or None, client_id=_uid(),
                              period=period, limit=limit)
        return jsonify(posts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/top-posts/refresh', methods=['POST'])
@login_required
def refresh_top_posts():
    """Trigger a fetch of top posts from Reddit for one or more subreddits."""
    body = request.get_json(silent=True) or {}
    sub    = body.get('subreddit', 'Daytrading')
    period = body.get('period', 'week')
    niche  = body.get('niche', '')
    try:
        from reddit_top_posts import refresh_subreddit, refresh_niche
        if niche:
            counts = refresh_niche(niche, period=period, client_id=_uid())
            total  = sum(counts.values())
            return jsonify({'ok': True, 'saved': total, 'by_sub': counts})
        else:
            saved = refresh_subreddit(sub, period=period, client_id=_uid())
            return jsonify({'ok': True, 'saved': saved, 'subreddit': sub})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Content Plan ──────────────────────────────────────────────────────────────

@api.route('/content-plan/generate', methods=['POST'])
@login_required
def generate_content_plan():
    """Generate a 7-day content plan from macro/indicator sheet data."""
    body = request.get_json(silent=True) or {}
    sheet_data = body.get('sheet_data', '').strip()
    if not sheet_data:
        return jsonify({'ok': False, 'error': 'No sheet data provided'}), 400

    subreddits = body.get('subreddits') or ['Daytrading', 'Futures']
    niche      = body.get('niche', 'daytrading')
    days       = int(body.get('days', 7))

    try:
        from content_planner import generate_weekly_plan
        plan = generate_weekly_plan(
            sheet_data = sheet_data,
            subreddits = subreddits,
            niche      = niche,
            days       = days,
            client_id  = _uid(),
        )
        if not plan:
            return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500
        return jsonify({'ok': True, 'plan': plan})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/content-plan')
@login_required
def get_content_plans_route():
    """Return recent content plans."""
    try:
        from database import get_content_plans
        plans = get_content_plans(client_id=_uid(), limit=5)
        return jsonify(plans)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/value-posts/generate-image', methods=['POST'])
@login_required
def generate_post_image():
    """
    Call DALL-E 3 with an image_prompt from an X thread post.
    Returns a base64-encoded PNG so the preview screen can show it inline.

    Body: { "image_prompt": str, "post_id": int (optional) }
    """
    import urllib.request, urllib.error, base64, os
    body = request.get_json(silent=True) or {}
    prompt = (body.get('image_prompt') or '').strip()
    if not prompt:
        return jsonify({'error': 'image_prompt is required'}), 400

    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'OPENAI_API_KEY not configured'}), 503

    platform = (body.get('platform') or 'reddit').lower()
    # X threads: landscape 16:9 fills the feed better; Reddit: square is safer across post types
    dalle_size = '1792x1024' if (platform == 'x' or platform == 'x_thread') else '1024x1024'

    payload = json.dumps({
        'model':   'dall-e-3',
        'prompt':  (
            f"Cinematic, high-quality social media image for a trading post. "
            f"Dark moody background, bold dramatic visual, absolutely no text or words. {prompt}"
        ),
        'n':       1,
        'size':    dalle_size,
        'quality': 'standard',
        'response_format': 'b64_json',
    }).encode()

    try:
        req = urllib.request.Request(
            'https://api.openai.com/v1/images/generations',
            data    = payload,
            headers = {
                'Authorization': f'Bearer {api_key}',
                'Content-Type':  'application/json',
            },
            method = 'POST',
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            result = json.loads(resp.read())

        b64 = result['data'][0]['b64_json']
        revised = result['data'][0].get('revised_prompt', prompt)
        return jsonify({'b64': b64, 'revised_prompt': revised})

    except urllib.error.HTTPError as e:
        err = e.read().decode(errors='replace')
        return jsonify({'error': f'OpenAI {e.code}: {err[:300]}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/value-posts/validate-idea', methods=['POST'])
@login_required
def validate_post_idea():
    """
    Validate the user's own content idea against live community data.
    Returns a scored verdict + best subreddit + refined angle.
    Body: { "idea": str, "platform": "reddit"|"x" }
    """
    body     = request.get_json(silent=True) or {}
    idea     = (body.get('idea') or '').strip()
    platform = (body.get('platform') or 'reddit').lower()
    if not idea:
        return jsonify({'error': 'idea is required'}), 400

    from value_post_generator import validate_and_route_idea
    result = validate_and_route_idea(idea, platform=platform, client_id=_uid())
    if not result:
        return jsonify({'error': 'Validation failed — check ANTHROPIC_API_KEY'}), 500
    return jsonify(result)


@api.route('/value-posts/from-idea', methods=['POST'])
@login_required
def generate_from_idea():
    """
    Generate a full post from a validated idea + chosen subreddit.
    Uses refined_angle as the creative brief. Saves to Queue.
    Body: { "idea": str, "refined_angle": str, "subreddit": str, "platform": "reddit"|"x" }
    """
    body          = request.get_json(silent=True) or {}
    idea          = (body.get('idea')          or '').strip()
    refined_angle = (body.get('refined_angle') or idea).strip()
    subreddit     = (body.get('subreddit')     or 'Daytrading').strip()
    platform      = (body.get('platform')      or 'reddit').lower()

    if not idea:
        return jsonify({'error': 'idea is required'}), 400

    try:
        from database import create_value_post

        if platform == 'reddit':
            from value_post_generator import generate_targeted_post
            result = generate_targeted_post(
                signal       = refined_angle,
                subreddit    = subreddit,
                example_post = '',
            )
            if not result:
                return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500
            pid = create_value_post(
                subreddit     = result['subreddit'],
                post_type     = result['type'],
                title         = result['title'],
                body          = result['body'],
                topic         = refined_angle,
                signals       = [idea],
                post_count    = 0,
                client_id     = _uid(),
                source_signal = idea,
            )
            if pid:
                try:
                    import telegram_approver as _tg
                    _tg.send_for_review(pid, {**result, 'platform': 'reddit', 'signal': idea, 'source_signal': idea})
                except Exception:
                    pass
            return jsonify({'ok': True, 'created': {
                'id':        pid,
                'platform':  'reddit',
                'signal':    idea,
                'subreddit': result['subreddit'],
                'title':     result['title'],
            }})

        else:  # x
            from value_post_generator import generate_targeted_x_thread
            result = generate_targeted_x_thread(
                signal       = refined_angle,
                niche        = 'daytrading',
                example_post = '',
            )
            if not result:
                return jsonify({'ok': False, 'error': 'Generation failed — check ANTHROPIC_API_KEY'}), 500
            body_text = '\n\n'.join(result.get('tweets', []))
            hook      = result.get('hook', refined_angle)
            pid = create_value_post(
                subreddit     = 'x',
                post_type     = 'x_thread',
                title         = hook[:200],
                body          = body_text,
                topic         = refined_angle,
                signals       = [idea],
                post_count    = 0,
                client_id     = _uid(),
                source_signal = idea,
            )
            if pid:
                try:
                    import telegram_approver as _tg
                    _tg.send_for_review(pid, {**result, 'platform': 'x', 'signal': idea, 'source_signal': idea})
                except Exception:
                    pass
            return jsonify({'ok': True, 'created': {
                'id':          pid,
                'platform':    'x',
                'signal':      idea,
                'hook':        hook,
                'tweet_count': result.get('tweet_count', 6),
                'title':       hook[:120],
            }})

    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


@api.route('/value-posts/generate-audio', methods=['POST'])
@login_required
def generate_post_audio():
    """
    Generate a voiceover audio clip via ElevenLabs TTS.
    Converts the post hook/title to speech and returns base64-encoded MP3.

    Body: { "text": str, "voice_id": str (optional) }

    Requires ELEVENLABS_API_KEY in environment.
    Default voice: Adam (pNInz6obpgDQGcFmaJgB) — professional male, works well for trading content.
    Other good voices: Rachel (21m00Tcm4TlvDq8ikWAM), Josh (TxGEqnHWrfWFTfGW9XjX)
    Full list: https://api.elevenlabs.io/v1/voices
    """
    import urllib.request, urllib.error, base64, os
    body    = request.get_json(silent=True) or {}
    text    = (body.get('text') or '').strip()
    voice_id = body.get('voice_id') or os.environ.get('ELEVENLABS_VOICE_ID', 'pNInz6obpgDQGcFmaJgB')

    if not text:
        return jsonify({'error': 'text is required'}), 400
    if len(text) > 2500:
        text = text[:2500]  # stay within free-tier credit sweet spot

    api_key = os.environ.get('ELEVENLABS_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'ELEVENLABS_API_KEY not configured'}), 503

    payload = json.dumps({
        'text':     text,
        'model_id': 'eleven_multilingual_v2',
        'voice_settings': {
            'stability':        0.5,
            'similarity_boost': 0.75,
            'speed':            1.0,
        },
    }).encode()

    try:
        req = urllib.request.Request(
            f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128',
            data    = payload,
            headers = {
                'xi-api-key':   api_key,
                'Content-Type': 'application/json',
                'Accept':       'audio/mpeg',
            },
            method  = 'POST',
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            audio_bytes = resp.read()

        audio_b64 = base64.b64encode(audio_bytes).decode()
        return jsonify({
            'audio_b64':  audio_b64,
            'mime_type':  'audio/mpeg',
            'voice_id':   voice_id,
            'char_count': len(text),
        })

    except urllib.error.HTTPError as e:
        err = e.read().decode(errors='replace')
        return jsonify({'error': f'ElevenLabs {e.code}: {err[:300]}'}), 502
    except Exception as e:
        return jsonify({'error': f'ElevenLabs error: {e}'}), 500


@api.route('/value-posts/voices', methods=['GET'])
@login_required
def list_voices():
    """List available ElevenLabs voices for the account."""
    import urllib.request, os
    api_key = os.environ.get('ELEVENLABS_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'ELEVENLABS_API_KEY not configured'}), 503
    try:
        req = urllib.request.Request(
            'https://api.elevenlabs.io/v1/voices',
            headers={'xi-api-key': api_key},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        voices = [
            {'voice_id': v['voice_id'], 'name': v['name'], 'category': v.get('category', '')}
            for v in data.get('voices', [])
        ]
        return jsonify(voices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api.route('/notify', methods=['POST'])
@login_required
def send_push_notification():
    """
    Send a push notification via ntfy.sh.
    Body: { "title": str, "message": str, "priority": "default"|"high" }

    Requires NTFY_TOPIC in environment (e.g. "altusflow-yourname").
    User installs the ntfy app on their phone and subscribes to the same topic.
    """
    import urllib.request, os
    body = request.get_json(silent=True) or {}
    topic = os.environ.get('NTFY_TOPIC', '')
    if not topic:
        return jsonify({'error': 'NTFY_TOPIC not configured'}), 503

    title   = (body.get('title')   or 'AltusFlow').strip()[:100]
    message = (body.get('message') or 'Your post is ready to review.').strip()[:500]
    priority = body.get('priority', 'default')

    try:
        req = urllib.request.Request(
            f'https://ntfy.sh/{topic}',
            data    = message.encode(),
            method  = 'POST',
            headers = {
                'Title':    title,
                'Priority': priority,
                'Tags':     'bell',
            },
        )
        with urllib.request.urlopen(req, timeout=10):
            pass
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
