"""
Hermes AI — DM suggestion engine powering the Reply Center.

Auto-send gate: Hermes will NOT auto-send until it has drafted messages for
50 conversations. This gives it enough examples to calibrate tone before
operating without supervision. The counter is stored in scheduler_state and
unlocks automatically. Owners can manually disable auto-send any time.

Claude API called via urllib.request (no anthropic package required).
"""
import os
import json
import urllib.request

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
_CLAUDE_URL       = "https://api.anthropic.com/v1/messages"
_CLAUDE_VERSION   = "2023-06-01"
_MODEL            = "claude-haiku-4-5-20251001"

LEARNING_THRESHOLD = 50

_SYSTEM = """You are Hermes, an expert cold-outreach copywriter for AltusFlow.
Your only job is to write short, personalised Reddit/X DMs.
Rules:
- Under 300 characters unless explicitly asked for longer.
- Sound like a real person, never a bot.
- Reference the prospect's specific post or pain point directly.
- End with a soft, non-pushy CTA (Calendly link at end only when relevant).
- Return ONLY the message text — no quotes, no explanation, no preamble."""

_SOURCE_CONTEXT = {
    'scrapebadger': "This is a HIGH-INTENT lead found by Scrape Badger. They explicitly expressed this pain point publicly. Reference what they said directly. Be specific — they'll know you read it.",
    'post_comment':  "This is a WARM lead — they engaged with a value post you wrote. They already know who you are. Lower friction than cold. Acknowledge that their comment resonated and build from there.",
    'creator':       "This is a CREATOR COLLAB lead. Focus on audience overlap and mutual value. Do not pitch your product — pitch the collaboration opportunity.",
    'cold_stream':   "This is a stream-sourced lead. They posted publicly about this struggle. Be empathetic, reference their situation specifically, don't sound salesy.",
}


def _call_claude(prompt: str, max_tokens: int = 400) -> str | None:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        body = json.dumps({
            "model":      _MODEL,
            "max_tokens": max_tokens,
            "system":     _SYSTEM,
            "messages":   [{"role": "user", "content": prompt}],
        }).encode()
        req = urllib.request.Request(
            _CLAUDE_URL, data=body, method="POST",
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": _CLAUDE_VERSION,
                "content-type":      "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())["content"][0]["text"].strip()
    except Exception:
        return None


def get_suggestion(prospect: dict, conversation_history: list, mode: str,
                   source_context: dict = None) -> str | None:
    """
    Return an AI-generated DM suggestion, or None on failure.
    source_context: dict with keys: source, signal, post_text, platform, subreddit
    """
    if not ANTHROPIC_API_KEY:
        return None

    history_text = '\n'.join(
        f"[{m.get('sender','?')}]: {m.get('body','')}"
        for m in (conversation_history or [])[-6:]
    )

    ctx = source_context or {}
    source      = ctx.get('source', 'cold_stream')
    signal      = ctx.get('signal', '')
    post_text   = ctx.get('post_text', '') or prospect.get('post_text', '') or prospect.get('drafted_message', '')
    platform    = ctx.get('platform', 'reddit')
    subreddit   = ctx.get('subreddit', '') or prospect.get('subreddit', '')
    source_note = _SOURCE_CONTEXT.get(source, _SOURCE_CONTEXT['cold_stream'])

    sentiment_shift = ctx.get('sentiment_shift') or {}
    post_title      = ctx.get('post_title', '')

    context_block = ''
    if signal:
        context_block += f"Pain signal detected: \"{signal}\"\n"
    if post_text:
        context_block += f"Their original post: \"{post_text[:400]}\"\n"
    if post_title:
        context_block += f"Value post they commented on: \"{post_title}\"\n"
    if subreddit:
        context_block += f"Community: r/{subreddit}\n"
    if platform:
        context_block += f"Platform: {platform}\n"

    sentiment_block = ''
    if sentiment_shift:
        label  = sentiment_shift.get('label', '')
        shift  = sentiment_shift.get('shift', '')
        intent = sentiment_shift.get('intent', '')
        sentiment_block = (
            f"\nSentiment analysis (Hermes read their comment):\n"
            f"  Tone shift: {label}\n"
            f"  Why: {shift}\n"
            f"  Purchase intent: {intent}%\n"
            f"Use this to calibrate urgency and warmth in your message — "
            f"high intent means you can be more direct.\n"
        )

    prompt = (
        f"Prospect: {'@' if platform == 'x' else 'u/'}{prospect.get('handle', 'unknown')}\n"
        f"Lead source: {source}\n"
        f"Source note: {source_note}\n"
        f"{context_block}"
        f"ICP score: {prospect.get('icp_score', '?')}/10\n"
        f"{sentiment_block}"
        f"Conversation so far:\n{history_text or '(none — this is the first touch)'}\n\n"
        f"Mode: {mode}\n"
        f"Write the next message."
    )

    # Inject proven openers from historical data (Level 2 learning)
    niche = prospect.get('niche_segment') or prospect.get('niche', '')
    try:
        from database import get_winning_opener_patterns
        winners = get_winning_opener_patterns(niche=niche or None, limit=3)
    except Exception:
        winners = []

    if winners:
        examples = '\n'.join(f'  • "{w["body"][:200]}"' for w in winners)
        prompt += (
            f"\n\nOpeners from your history that got replies in this niche:\n{examples}\n"
            f"Study the tone and structure — do not copy, but let them inform your style."
        )

    suggestion = _call_claude(prompt)
    if not suggestion:
        return None

    try:
        from database import increment_hermes_convo_count
        increment_hermes_convo_count()
    except Exception:
        pass

    return suggestion


def should_auto_send(suggestion: str, mode: str, prospect: dict) -> bool:
    if mode != 'full_auto':
        return False
    try:
        from database import hermes_auto_enabled
        if not hermes_auto_enabled():
            return False
    except Exception:
        return False
    return (prospect.get('icp_score') or 0) >= 8


def generate_intelligence_brief(pod_slug: str = None) -> str | None:
    """Generate a market intelligence brief for the command center."""
    try:
        from database import get_market_pulse_data
        data = get_market_pulse_data(pod_slug=pod_slug)
        if not data:
            return None
        signals = '\n'.join(f"- [{d.get('source','')}] {d.get('post_text','')[:120]}" for d in data[:15])
        prompt = (
            f"You are Hermes, AltusFlow's AI analyst. Summarize the following prospect signals "
            f"into a 3-bullet intelligence brief for a sales team. Be specific, cite patterns, "
            f"flag the highest-intent signals. Under 200 words total.\n\nSignals:\n{signals}"
        )
        return _call_claude(prompt, max_tokens=300)
    except Exception:
        return None
