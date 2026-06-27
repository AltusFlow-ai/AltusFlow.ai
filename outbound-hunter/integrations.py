"""
integrations.py — Connector layer for AltusFlow outbound-hunter.

Fired from database hooks whenever a prospect status changes.
All calls are best-effort: never raises, never blocks the main flow.

Adding a new native connector:
  1. Add an entry to CATALOG
  2. Write a _fire_<slug>(config, payload) function
  3. Register it in _FIRERS
"""

import json
import sys
import hmac
import hashlib
import urllib.request
import urllib.error
from datetime import datetime, timezone


# ── Event types ───────────────────────────────────────────────────────────────

WEBHOOK_EVENTS = [
    'prospect.detected',
    'prospect.approved',
    'prospect.sent',
    'prospect.replied',
    'prospect.booked',
    'prospect.closed_won',
    'prospect.closed_lost',
]


# ── Integration catalog (mirrors frontend CATALOG in Settings.jsx) ────────────

CATALOG = [
    {
        'slug':         'webhook_outbound',
        'name':         'Outbound Webhook',
        'icon':         '🔗',
        'badge':        'Universal',
        'badge_color':  '#1d9e75',
        'description':  'POST prospect events to any URL. Works with Zapier, Make, n8n, or your own server.',
        'category':     'universal',
        'fields': [
            {'key': 'webhook_url', 'label': 'Webhook URL',      'type': 'url',      'placeholder': 'https://hooks.zapier.com/hooks/catch/...', 'required': True},
            {'key': 'secret',      'label': 'Signing Secret',   'type': 'password', 'placeholder': 'Optional — requests signed with HMAC-SHA256'},
        ],
        'event_filter': True,
    },
    {
        'slug':         'hubspot',
        'name':         'HubSpot',
        'icon':         '🟠',
        'badge':        'CRM',
        'badge_color':  '#ff7a59',
        'description':  'Sync contacts to HubSpot CRM and enroll in email sequences (Sales Hub Pro required for sequences).',
        'category':     'crm',
        'fields': [
            {'key': 'api_key',     'label': 'Private App Token',  'type': 'password', 'placeholder': 'pat-na1-...', 'required': True},
            {'key': 'sequence_id', 'label': 'Sequence ID',        'type': 'text',     'placeholder': 'Optional — auto-enroll on approval'},
            {'key': 'pipeline_id', 'label': 'Deal Pipeline ID',   'type': 'text',     'placeholder': 'Optional — create deals automatically'},
        ],
        'event_filter': False,
    },
    {
        'slug':         'gmail',
        'name':         'Gmail / SMTP',
        'icon':         '📧',
        'badge':        'Email',
        'badge_color':  '#4285f4',
        'description':  'Send email touches as part of your sequence using Gmail or any SMTP provider.',
        'category':     'email',
        'fields': [
            {'key': 'smtp_user',  'label': 'Gmail Address',  'type': 'email',    'placeholder': 'you@gmail.com',       'required': True},
            {'key': 'smtp_pass',  'label': 'App Password',   'type': 'password', 'placeholder': 'xxxx xxxx xxxx xxxx', 'required': True},
            {'key': 'from_name',  'label': 'From Name',      'type': 'text',     'placeholder': 'Your Name'},
            {'key': 'smtp_host',  'label': 'SMTP Host',      'type': 'text',     'placeholder': 'smtp.gmail.com (default)'},
            {'key': 'smtp_port',  'label': 'Port',           'type': 'text',     'placeholder': '587 (default)'},
        ],
        'event_filter': False,
    },
    {
        'slug':         'calendly',
        'name':         'Calendly',
        'icon':         '📅',
        'badge':        'Calendar',
        'badge_color':  '#006bff',
        'description':  'Auto-log bookings as "Call booked" journey events when prospects schedule via Calendly.',
        'category':     'calendar',
        'fields': [
            {'key': 'signing_key', 'label': 'Webhook Signing Key', 'type': 'password', 'placeholder': 'From Calendly → Integrations → Webhooks', 'required': True},
            {'key': 'event_type',  'label': 'Event Type UUID',     'type': 'text',     'placeholder': 'Optional — filter to one meeting type'},
        ],
        'event_filter': False,
    },
    {
        'slug':         'apollo',
        'name':         'Apollo.io',
        'icon':         '🚀',
        'badge':        'Email',
        'badge_color':  '#3b5bdb',
        'description':  'Enroll approved prospects in an Apollo sequence automatically.',
        'category':     'email',
        'fields': [
            {'key': 'api_key',     'label': 'API Key',      'type': 'password', 'placeholder': 'From Apollo → Settings → API Keys', 'required': True},
            {'key': 'sequence_id', 'label': 'Sequence ID',  'type': 'text',     'placeholder': 'Optional — default sequence'},
        ],
        'event_filter': False,
    },
    {
        'slug':         'instantly',
        'name':         'Instantly',
        'icon':         '⚡',
        'badge':        'Email',
        'badge_color':  '#f59f00',
        'description':  'Push prospects to an Instantly campaign when they reach "sent" status.',
        'category':     'email',
        'fields': [
            {'key': 'api_key',     'label': 'API Key',     'type': 'password', 'placeholder': 'From Instantly → Settings → API', 'required': True},
            {'key': 'campaign_id', 'label': 'Campaign ID', 'type': 'text',     'placeholder': 'Target campaign ID'},
        ],
        'event_filter': False,
    },
    {
        'slug':         'lemlist',
        'name':         'Lemlist',
        'icon':         '🍋',
        'badge':        'Email',
        'badge_color':  '#fab005',
        'description':  'Add leads to a Lemlist campaign on approval.',
        'category':     'email',
        'fields': [
            {'key': 'api_key',     'label': 'API Key',     'type': 'password', 'placeholder': 'From Lemlist → Settings → Integrations', 'required': True},
            {'key': 'campaign_id', 'label': 'Campaign ID', 'type': 'text',     'placeholder': 'Target campaign'},
        ],
        'event_filter': False,
    },
    {
        'slug':         'gohighlevel',
        'name':         'GoHighLevel',
        'icon':         '🏆',
        'badge':        'CRM',
        'badge_color':  '#7048e8',
        'description':  'Sync contacts and pipeline stages to a GHL sub-account.',
        'category':     'crm',
        'fields': [
            {'key': 'api_key',     'label': 'API Key',      'type': 'password', 'placeholder': 'Agency or location API key', 'required': True},
            {'key': 'location_id', 'label': 'Location ID',  'type': 'text',     'placeholder': 'Sub-account location ID'},
            {'key': 'pipeline_id', 'label': 'Pipeline ID',  'type': 'text',     'placeholder': 'Optional — create opportunities'},
        ],
        'event_filter': False,
    },
    {
        'slug':         'slack',
        'name':         'Slack',
        'icon':         '💬',
        'badge':        'Notify',
        'badge_color':  '#4a154b',
        'description':  'Post Slack notifications when prospects reply, book calls, or close won.',
        'category':     'notify',
        'fields': [
            {'key': 'webhook_url', 'label': 'Incoming Webhook URL', 'type': 'url', 'placeholder': 'https://hooks.slack.com/services/...', 'required': True},
        ],
        'event_filter': True,
    },
]


# ── Payload builder ───────────────────────────────────────────────────────────

def _build_payload(event_type, prospect):
    return {
        "event":     event_type,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "prospect": {
            "id":          prospect.get("id"),
            "handle":      prospect.get("handle"),
            "name":        prospect.get("name"),
            "niche":       prospect.get("niche") or prospect.get("niche_segment"),
            "platform":    prospect.get("platform"),
            "icp_score":   prospect.get("icp_score"),
            "post_text":   (prospect.get("post_text") or "")[:500],
            "profile_url": prospect.get("profile_url"),
            "status":      prospect.get("status"),
            "scraped_at":  prospect.get("scraped_at"),
        },
        "meta": {"source": "altusflow"},
    }


# ── HTTP helper ───────────────────────────────────────────────────────────────

def _post_json(url, payload, extra_headers=None):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'AltusFlow-Webhook/1.0')
    for k, v in (extra_headers or {}).items():
        req.add_header(k, v)
    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.status


# ── Native firers ─────────────────────────────────────────────────────────────

def _fire_webhook(config, payload):
    url = (config or {}).get('webhook_url', '').strip()
    if not url:
        return
    headers = {}
    secret = (config or {}).get('secret', '').strip()
    if secret:
        sig = hmac.new(secret.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        headers['X-AltusFlow-Signature'] = f'sha256={sig}'
    _post_json(url, payload, headers)


def _fire_slack(config, payload):
    url = (config or {}).get('webhook_url', '').strip()
    if not url:
        return
    event = payload.get('event', '')
    p     = payload.get('prospect', {})
    score = p.get('icp_score')
    score_str = f" · ICP {score}" if score else ""
    text = f"*AltusFlow* `{event}` — *{p.get('handle')}* ({p.get('niche')}{score_str})"
    if p.get('post_text'):
        text += f'\n> {p["post_text"][:200]}'
    _post_json(url, {"text": text})


# Stubs for native connectors — wired when the integration is built out
def _fire_hubspot(config, payload):
    pass  # TODO: upsert contact + optional sequence enroll


def _fire_apollo(config, payload):
    pass  # TODO: add contact to sequence


def _fire_instantly(config, payload):
    pass  # TODO: add lead to campaign


def _fire_lemlist(config, payload):
    pass  # TODO: add lead to campaign


def _fire_gohighlevel(config, payload):
    pass  # TODO: upsert contact + opportunity


def _fire_gmail(config, payload):
    pass  # TODO: queue SMTP send via sequence engine


def _fire_calendly(config, payload):
    pass  # Calendly pushes to us (inbound webhook) — nothing to fire outbound


_FIRERS = {
    'webhook_outbound': _fire_webhook,
    'slack':            _fire_slack,
    'hubspot':          _fire_hubspot,
    'apollo':           _fire_apollo,
    'instantly':        _fire_instantly,
    'lemlist':          _fire_lemlist,
    'gohighlevel':      _fire_gohighlevel,
    'gmail':            _fire_gmail,
    'calendly':         _fire_calendly,
}


# ── Public entry point ────────────────────────────────────────────────────────

def notify_integrations(advisor_id, event_type, prospect):
    """
    Fire all enabled integrations for this advisor. Best-effort — never raises.
    Called from database.update_status() and database.mark_prospect_sent().
    """
    try:
        from database import get_integrations
        configs = get_integrations(advisor_id) or []
    except Exception:
        return

    if not configs:
        return

    payload = _build_payload(event_type, prospect)

    for cfg in configs:
        if not cfg.get('enabled'):
            continue
        slug   = cfg.get('slug', '')
        config = cfg.get('config') or {}
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except Exception:
                config = {}

        allowed = config.get('events')
        if allowed and isinstance(allowed, list) and event_type not in allowed:
            continue

        firer = _FIRERS.get(slug)
        if not firer:
            continue
        try:
            firer(config, payload)
        except Exception as e:
            print(f"[integrations] {slug} fire error: {e}", file=sys.stderr)
