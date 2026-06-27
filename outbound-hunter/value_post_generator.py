"""
value_post_generator.py — AI-powered content generation for trading coach niches.

Uses Claude directly via HTTP (no anthropic package).
All prompts enforce a specific, non-AI-sounding voice with zero filler.
"""

import os
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

_CLAUDE_URL     = "https://api.anthropic.com/v1/messages"
_CLAUDE_VERSION = "2023-06-01"
_MODEL          = "claude-sonnet-4-6"

# Phrases that make posts sound AI-generated or generic — banned from all output
_BANNED = [
    "It's important to note", "As a reminder", "In conclusion", "To summarize",
    "I hope this helps", "feel free to", "I want to emphasize", "Remember that",
    "I've been trading for", "As a seasoned trader", "In the world of trading",
    "Let's dive in", "Let's explore", "Let's break this down", "delve into",
    "First and foremost", "At the end of the day", "Game changer", "Level up",
    "Navigating the", "It goes without saying", "Without a doubt",
    "I'd like to share", "I want to start by", "community", "insights to share",
]

_REDDIT_SYSTEM = (
    "You are a profitable day trader who posts in trading subreddits because you genuinely want the "
    "community to improve — not to sell anything. Your posts get saved because they're dense with "
    "specific, actionable observations. You write in plain, direct language: short paragraphs, bold "
    "for key points, specific numbers and scenarios. You never mention coaching, services, DMs, or links. "
    "You never write vague generalisations. Every sentence earns its place. "
    "BANNED phrases you never use: " + "; ".join(_BANNED)
)

_X_SYSTEM = (
    "You are a profitable trader with a sharp, direct voice on X. Your threads go viral because "
    "every tweet delivers one concrete idea — no filler, no hedging, no platitudes. "
    "You use real trader language: specific P&L numbers, actual ticker scenarios, the exact words "
    "traders use when a trade is going wrong. You never hashtag. You never self-promote. "
    "BANNED phrases you never use: " + "; ".join(_BANNED[:12])
)


def _call_claude(prompt: str, max_tokens: int = 1400, system: str = None) -> str | None:
    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return None
    try:
        import urllib.request as _ur
        payload = {
            "model":      _MODEL,
            "max_tokens": max_tokens,
            "messages":   [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        body = json.dumps(payload).encode()
        req  = _ur.Request(
            _CLAUDE_URL, data=body, method="POST",
            headers={
                "x-api-key":         api_key,
                "anthropic-version": _CLAUDE_VERSION,
                "content-type":      "application/json",
            },
        )
        with _ur.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read())["content"][0]["text"].strip()
    except Exception as e:
        log.warning(f"[value_post] claude error: {e}")
        return None


def generate_insight_digest(subreddit: str, pain_signals: list[str], post_count: int = 0) -> dict | None:
    """
    Weekly roundup: the real patterns showing up in this community right now.
    Written as genuine community value — no pitch, no links.
    """
    signals_text = '\n'.join(f'- {s}' for s in pain_signals[:20]) if pain_signals else '- general trading struggles'

    prompt = f"""Subreddit: r/{subreddit}
Posts scanned this week: {post_count}

Pain signals pulled from real posts:
{signals_text}

Write a weekly insight post. Requirements:

TITLE: Must be specific and curiosity-driven based on the DOMINANT pattern above.
Do NOT write "What I'm seeing in r/{subreddit} this week" — that's overused.
Good title formats:
- "[Number] accounts I've watched blow up this week followed the same 4 steps"
- "The [specific pattern] is destroying more accounts this week than any bad setup"
- "Why r/{subreddit} keeps making the same $2,000 mistake on [specific scenario]"

BODY: Cover 3–4 specific patterns. For each:
- Name it precisely ("The 9:31 FOMO trade" not "poor entry timing")
- Give a concrete example with specific numbers ("$400 loss → doubled size → $1,200 loss in 12 minutes")
- Explain the psychological root cause in one sentence
- Give ONE specific, actionable fix for this week — not "journal more", something you can do in the next trade

End with a single question that pulls in comments from traders who've lived this exact experience.

RULES:
- Zero self-promotion, no DMs, no links, no "I offer coaching"
- No filler sentences — every sentence must carry information
- Short paragraphs. Use **bold** for section labels and key points.
- Write like you're the most knowledgeable person in this community, not like a bot

Format: Title on line 1, blank line, then body. Return ONLY the post."""

    prompt += "\n\nAlso write an image_prompt: a single striking visual concept for this post — a real trading scenario, annotated chart moment, or specific emotional scene. Under 60 words. No text overlays. Append on the LAST line as: IMAGE_PROMPT: <description>"

    content = _call_claude(prompt, max_tokens=1600, system=_REDDIT_SYSTEM)
    if not content:
        return None

    image_prompt = ''
    if 'IMAGE_PROMPT:' in content:
        parts = content.rsplit('IMAGE_PROMPT:', 1)
        content = parts[0].strip()
        image_prompt = parts[1].strip()

    lines = content.strip().split('\n', 1)
    title = lines[0].strip().lstrip('# ').strip()
    body  = lines[1].strip() if len(lines) > 1 else content

    return {
        'type':         'insight_digest',
        'subreddit':    subreddit,
        'title':        title,
        'body':         body,
        'signals':      pain_signals[:20],
        'post_count':   post_count,
        'image_prompt': image_prompt,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def generate_resource_post(subreddit: str, topic: str, niche: str = 'trading-coaches') -> dict | None:
    """
    Free resource post — the "save this" format.
    Checklists, frameworks, breakdowns traders bookmark and share.
    """
    prompt = f"""Subreddit: r/{subreddit}
Topic: {topic}

Write a resource post that traders will save and share for months.

TITLE: Must make traders think "I needed this." Be specific.
Bad: "A guide to better trading psychology"
Good: "The 7-point checklist I run before every trade that stopped my revenge trading cold"

BODY requirements:
- Deliver a structured resource: numbered list, checklist, decision tree, or breakdown
- Every point must be concrete and specific — real numbers, real scenarios, named patterns
- Use **bold** for each key point or item label
- Include at least one counterintuitive insight that makes traders think "I never thought of it that way"
- If it's a list, each item should have 2-3 sentences of explanation — not just a one-liner
- Length: substantial enough to deserve being saved (aim for 350-500 words in body)

End with an open question that invites traders to share their version or experience.

RULES: No self-promotion. No links. No "DM me". No filler.

Format: Title on line 1, blank line, body. Return ONLY the post.

Also write an image_prompt on the LAST line: a striking visual concept — annotated checklist, chart moment, or trading scenario. Under 60 words. No text overlays. Format: IMAGE_PROMPT: <description>"""

    content = _call_claude(prompt, max_tokens=1700, system=_REDDIT_SYSTEM)
    if not content:
        return None

    image_prompt = ''
    if 'IMAGE_PROMPT:' in content:
        parts = content.rsplit('IMAGE_PROMPT:', 1)
        content = parts[0].strip()
        image_prompt = parts[1].strip()

    lines = content.strip().split('\n', 1)
    title = lines[0].strip().lstrip('# ').strip()
    body  = lines[1].strip() if len(lines) > 1 else content

    return {
        'type':         'resource_post',
        'subreddit':    subreddit,
        'topic':        topic,
        'title':        title,
        'body':         body,
        'image_prompt': image_prompt,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def generate_targeted_post(signal: str, subreddit: str, example_post: str = '') -> dict | None:
    """
    Value post laser-focused on one specific pain signal.
    Used by batch generation and signal-triggered auto-generate.
    """
    example_section = (
        f'\nReal post from this community that triggered this signal:\n"{example_post}"\n'
        if example_post else ''
    )

    prompt = f"""Subreddit: r/{subreddit}
Pain signal to address: "{signal}"
{example_section}
Write a Reddit post targeting traders experiencing exactly this problem.

TITLE: Name this exact pain in a way that makes traders think "this is about me."
Don't be generic. Make it specific to "{signal}".
Examples:
- "If you've ever {signal} and doubled down, read this before your next trade"
- "Why {signal} keeps happening — and the one rule that actually stops it"

BODY structure:
1. Open by describing the exact experience — what it feels like, the inner monologue, the specific moment it happens. Make traders feel seen in the first 2 sentences.
2. Explain WHY this pattern happens. The psychological or structural root cause. Be specific.
3. Give 3–4 concrete, actionable insights around this exact problem. Each insight should:
   - Reference a specific scenario or number traders will recognise
   - Be something a trader can implement in their very next session
4. End with a discussion question that draws out comments from traders fighting this exact battle.

RULES:
- Zero self-promotion, no DMs, no links, no coaching references
- Use specific numbers and scenarios — not vague language
- Short paragraphs, **bold** for key points
- Write like you've been in this exact situation

Format: Title on line 1, blank line, body. Return ONLY the post.

Also write an image_prompt on the LAST line: a striking visual for this post — a specific trading scenario, chart pattern, or emotional moment. Under 60 words. No text. Format: IMAGE_PROMPT: <description>"""

    content = _call_claude(prompt, max_tokens=1500, system=_REDDIT_SYSTEM)
    if not content:
        return None

    image_prompt = ''
    if 'IMAGE_PROMPT:' in content:
        parts = content.rsplit('IMAGE_PROMPT:', 1)
        content = parts[0].strip()
        image_prompt = parts[1].strip()

    lines = content.strip().split('\n', 1)
    title = lines[0].strip().lstrip('# ').strip()
    body  = lines[1].strip() if len(lines) > 1 else content

    return {
        'type':         'insight_digest',
        'subreddit':    subreddit,
        'topic':        signal,
        'title':        title,
        'body':         body,
        'signals':      [signal],
        'image_prompt': image_prompt,
        'generated_at': datetime.now(timezone.utc).isoformat(),
    }


def generate_targeted_x_thread(signal: str, niche: str = 'trading', example_post: str = '') -> dict | None:
    """
    6-tweet X thread laser-targeted at one pain signal.
    Also returns image_prompt for automated visual generation.
    """
    example_section = (
        f'\nReal community post that surfaced this signal: "{example_post}"\n'
        if example_post else ''
    )

    prompt = f"""Pain signal to address: "{signal}"
Niche: {niche} trading
{example_section}
Write a 6-tweet X thread. Each tweet must stand alone.

Tweet 1 (hook): Open by naming this exact experience with a punchy, scroll-stopping line.
Format options: "X traders I watch did [signal] this week. Here's what they all had in common."
Or start with the specific moment: "You're down $800. You tell yourself one more trade will fix it."
Under 240 chars. Make the reader think "this is me."

Tweets 2–5: One concrete, specific insight per tweet on this exact problem.
- Use real numbers and scenarios: "down 3R", "ES gaps up 8 points", "$400 turned into $1,800 loss in 11 minutes"
- Each tweet must be dense — no filler sentences
- Under 260 chars each

Tweet 6 (engagement): Ask a specific question that gets replies from people who've experienced this.
Not "thoughts?" — something specific: "What's the exact thought that runs through your head at that moment?"
Under 200 chars.

RULES: No hashtags. No self-promotion. No "DM me". No "thread below". Each tweet complete on its own.

Also write an image_prompt: a concise description for an AI image generator of a visual that would stop the scroll for this thread. Should be a striking, real-feeling trading scenario — not generic stock photos. Under 60 words.

Return ONLY valid JSON, no markdown fences:
{{"hook": "tweet 1 text", "tweets": ["t1","t2","t3","t4","t5","t6"], "image_prompt": "..."}}"""

    text = _call_claude(prompt, max_tokens=1200, system=_X_SYSTEM)
    if not text:
        return None

    return _parse_x_thread_json(text, topic=signal, niche=niche)


def generate_x_thread(topic: str, niche: str = 'trading', hook_style: str = 'contrarian') -> dict | None:
    """
    Generate a 6-tweet X thread. hook_style: 'contrarian' | 'story' | 'list'
    Also returns image_prompt for visual generation.
    """
    hooks = {
        'contrarian': 'Open with a bold statement that directly contradicts what most traders believe. Make it specific — name the belief and why it\'s wrong.',
        'story':      'Open with a 1–2 sentence micro-story about a specific trader in a specific moment. Real and cinematic: "I watched a trader turn $3k into $140 in 4 trades this morning. Here\'s exactly how."',
        'list':       'Open with a numbered promise: "7 things profitable [niche] traders do that nobody talks about:" — then deliver on it.',
    }

    prompt = f"""Topic: "{topic}"
Niche: {niche} trading

{hooks.get(hook_style, hooks['contrarian'])}

Write a 6-tweet thread:
Tweet 1 (hook): The opener. Under 240 chars. Must make a profitable trader stop scrolling.
Tweets 2–5: Each delivers ONE sharp, specific insight on "{topic}". Concrete numbers. Real scenarios. Under 260 chars.
Tweet 6 (CTA): A specific question that invites replies. Under 200 chars.

Rules: No hashtags. No self-promotion. Specific numbers over vague language. Dense over padded.

Also write an image_prompt: a vivid description for an AI image generator of a striking visual for tweet 1.
Think: a real trading scenario, a specific emotional moment, something that stops the scroll.
Under 60 words.

Return ONLY valid JSON, no markdown fences:
{{"hook": "tweet 1 text", "tweets": ["t1","t2","t3","t4","t5","t6"], "image_prompt": "..."}}"""

    text = _call_claude(prompt, max_tokens=1200, system=_X_SYSTEM)
    if not text:
        return None

    return _parse_x_thread_json(text, topic=topic, niche=niche, hook_style=hook_style)


def expand_to_x_thread(raw_content: str, niche: str = 'trading') -> dict | None:
    """
    Expand a coach's raw note or trade recap into a 6-tweet X thread.
    Preserves their authentic voice and specific insights.
    """
    prompt = f"""A {niche} trading coach wrote this raw note or recap:

{raw_content}

Turn it into a 6-tweet X thread. Preserve their specific numbers, scenarios, and insights — do NOT genericise or dilute.

Tweet 1 (hook): Distil their core insight into the most scroll-stopping version. Under 240 chars.
Tweets 2–5: Each expands one specific point from their content. Keep their language. Under 260 chars.
Tweet 6: Open question that invites their audience to respond. Under 200 chars.

Rules: No hashtags. No "DM me". Their voice, not a generic trading voice. Dense, not padded.

Also write an image_prompt: a vivid description for an AI image generator of a visual that matches the core theme.
Under 60 words.

Return ONLY valid JSON, no markdown fences:
{{"hook": "tweet 1 text", "tweets": ["t1","t2","t3","t4","t5","t6"], "image_prompt": "..."}}"""

    text = _call_claude(prompt, max_tokens=1200, system=_X_SYSTEM)
    if not text:
        return None

    return _parse_x_thread_json(text, topic='coach_content', niche=niche)


def expand_coach_content(raw_content: str, subreddit: str, title_hint: str = '') -> dict | None:
    """
    Expand a coach's raw note into a polished Reddit post that keeps their voice.
    """
    title_line = f'\nTitle direction from coach: "{title_hint}"' if title_hint else ''

    prompt = f"""A trading coach wrote this raw note or thought:

{raw_content}
{title_line}

Subreddit: r/{subreddit}

Expand and structure it into a complete, polished Reddit post. Keep their specific insights and voice — do NOT genericise.

TITLE: Specific and curiosity-driven. Based on their actual insight, not a generic spin.

BODY:
- Structure their raw content into clear sections with **bold** headers
- Expand their insights with concrete examples and specific numbers where it fits their point
- Keep their authentic perspective — don't dilute or soften their observations
- End with a single discussion question

RULES: No self-promotion. No links. No DMs. Zero filler. Every sentence earns its place.

Respond with valid JSON only, no markdown fences:
{{"title": "...", "body": "..."}}"""

    text = _call_claude(prompt, max_tokens=1400, system=_REDDIT_SYSTEM)
    if not text:
        return None

    try:
        clean = text.strip().lstrip('`').rstrip('`')
        if clean.startswith('json'):
            clean = clean[4:].strip()
        result = json.loads(clean)
        return {
            'type':         'coach_content',
            'subreddit':    subreddit,
            'title':        result.get('title', '').strip(),
            'body':         result.get('body',  '').strip(),
            'generated_at': datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.warning(f"[value_post] expand_coach_content parse error: {e} — raw: {text[:200]}")
        return None


_CANDIDATE_SUBS = [
    'Daytrading', 'Futures', 'swingtrading', 'options',
    'Scalping', 'StockMarket', 'thetagang', 'CryptoCurrency',
]


def validate_and_route_idea(
    idea: str,
    platform: str = 'reddit',
    client_id: str = None,
) -> dict | None:
    """
    Takes the user's raw content idea and:
    1. Checks it against top-performing posts in candidate subreddits
    2. Cross-references active pain signals
    3. Scores specificity, gap, and pain alignment
    4. Recommends the best subreddit and a refined angle

    Returns a verdict dict or None on failure.
    """
    # Pull top post context for candidate subs
    top_ctx_parts = []
    try:
        from reddit_top_posts import get_top_post_context
        for sub in _CANDIDATE_SUBS[:6]:
            c = get_top_post_context(sub, client_id=client_id, limit=3)
            if c:
                top_ctx_parts.append(c)
    except Exception:
        pass
    top_ctx = "\n\n".join(top_ctx_parts)

    # Pull recent pain signals from DB
    signal_ctx = ""
    try:
        from database import _reader
        from sqlalchemy import text as _t
        with _reader() as conn:
            rows = conn.execute(_t("""
                SELECT signal_phrase, COUNT(*) as cnt,
                       MIN(post_text) as example,
                       GROUP_CONCAT(DISTINCT subreddit) as subs
                FROM prospects
                WHERE signal_phrase IS NOT NULL AND signal_phrase != ''
                  AND scraped_at >= datetime('now', '-14 days')
                GROUP BY signal_phrase
                ORDER BY cnt DESC
                LIMIT 12
            """)).fetchall()
        if rows:
            lines = ["Active pain signals in monitored communities (last 14 days):"]
            for r in rows:
                ex = (r[2] or '')[:100]
                lines.append(f'  [{r[1]}x] "{r[0]}" — e.g. "{ex}"')
            signal_ctx = "\n".join(lines)
    except Exception:
        pass

    platform_label = "X (Twitter) thread" if platform == 'x' else "Reddit value post"
    candidates = ", ".join(f"r/{s}" for s in _CANDIDATE_SUBS)

    prompt = f"""You are evaluating whether a trader's content idea will perform well as a {platform_label} in trading communities.

USER'S IDEA:
"{idea}"

{f"WHAT'S CURRENTLY WINNING ENGAGEMENT:{chr(10)}{top_ctx}" if top_ctx else ""}

{signal_ctx if signal_ctx else ""}

CANDIDATE SUBREDDITS TO CHOOSE FROM: {candidates}

Evaluate this idea on 4 dimensions:

1. PAIN ALIGNMENT — Does this address a real, active pain traders are experiencing right now?
2. SPECIFICITY — Is the angle specific enough to earn saves and comments, or too generic?
3. GAP ANALYSIS — Is this topic overcovered in top posts right now, or is there a clear opening?
4. AUDIENCE FIT — Which single subreddit from the candidates fits this idea best, and why specifically?

Then write a refined angle: a sharpened version of their idea that is more specific, more likely to get traction, and directly addresses a named pain.

Return ONLY valid JSON, no markdown:
{{
  "score": <0-100 integer>,
  "verdict": "strong" | "refine" | "skip",
  "verdict_reason": "<one punchy sentence explaining the verdict>",
  "best_subreddit": "<subreddit name only, no r/ prefix>",
  "subreddit_reason": "<why this sub specifically over the others>",
  "pain_alignment": "<1-2 sentences — does real community data back this up?>",
  "specificity_note": "<1-2 sentences — what's sharp, what's too vague>",
  "gap_note": "<1-2 sentences — is there room for this right now?>",
  "refined_angle": "<their idea sharpened into a specific, actionable post direction>"
}}"""

    text = _call_claude(prompt, max_tokens=900, system=_REDDIT_SYSTEM)
    if not text:
        return None

    try:
        clean = text.strip().lstrip('`').rstrip('`')
        if clean.startswith('json'):
            clean = clean[4:].strip()
        return json.loads(clean)
    except Exception as e:
        log.warning(f"[validate_idea] parse error: {e} — raw: {text[:200]}")
        return None


def generate_with_outcome_intelligence(subreddit: str, client_id: str = None) -> dict | None:
    """
    Generate using outcome data — picks the highest-converting signal and writes
    a fresh post on it from a new angle. Falls back to recent prospects.
    """
    try:
        from database import get_post_outcome_intelligence, CLIENT_ID as _cid
        cid  = client_id or _cid
        data = get_post_outcome_intelligence(client_id=cid, limit=20)
    except Exception as e:
        log.warning(f"[value_post] outcome intelligence fetch error: {e}")
        data = []

    if not data:
        return generate_from_recent_prospects(subreddit, client_id)

    perf_lines = []
    for d in data[:10]:
        topic = d.get('topic') or (d.get('signals') or [''])[0] or d.get('title', '')[:60]
        if not topic:
            continue
        perf_lines.append(
            f'  • "{topic}" → {d["comments_pulled"]} comments, {d["dms_initiated"]} DMs, '
            f'{d["replies_received"]} replies, {d["calls_booked"]} calls ({d["reply_rate"]}% reply rate)'
        )

    if not perf_lines:
        return generate_from_recent_prospects(subreddit, client_id)

    best         = data[0]
    anchor_topic = best.get('topic') or (best.get('signals') or [''])[0] or ''
    perf_block   = '\n'.join(perf_lines)

    prompt = f"""r/{subreddit} — content performance data (ranked by discovery calls booked):

{perf_block}

Best-performing topic: "{anchor_topic}"

Write a NEW post on this topic from a fresh angle — go one level deeper, tackle a sub-problem, or take a contrarian view on a common assumption about this pain.

Do NOT repeat the angle of the previous post. Do NOT reference any data or previous posts.

TITLE: Specific, curiosity-driven, different from any previous angle on "{anchor_topic}".

BODY: Dense, specific, actionable. 3–4 patterns or insights. Real numbers. No filler.
End with a discussion question targeting traders dealing with this exact pain.

RULES: Zero self-promotion. No DMs. No links. Write like the most credible trader in this community.

Format: Title on line 1, blank line, body. Return ONLY the post."""

    content = _call_claude(prompt, max_tokens=1400, system=_REDDIT_SYSTEM)
    if not content:
        return generate_from_recent_prospects(subreddit, client_id)

    lines = content.strip().split('\n', 1)
    title = lines[0].strip().lstrip('# ').strip()
    body  = lines[1].strip() if len(lines) > 1 else content

    winning_signals = best.get('signals') or ([best.get('topic')] if best.get('topic') else [])

    return {
        'type':                 'insight_digest',
        'subreddit':            subreddit,
        'title':                title,
        'body':                 body,
        'topic':                anchor_topic,
        'signals':              winning_signals,
        'post_count':           0,
        'generated_at':         datetime.now(timezone.utc).isoformat(),
        'intelligence_source':  'outcome_weighted',
    }


def generate_from_recent_prospects(subreddit: str, client_id: str = None) -> dict | None:
    """
    Auto-generate an insight digest using pain signals from recent prospects.
    """
    try:
        from database import CLIENT_ID as _cid
        from sqlalchemy import text
        from database import _reader

        cid = client_id or _cid

        with _reader() as conn:
            rows = conn.execute(text("""
                SELECT signal_phrase, post_text, platform, subreddit
                FROM prospects
                WHERE client_id = :cid
                  AND signal_phrase IS NOT NULL
                  AND signal_phrase != ''
                  AND scraped_at >= datetime('now', '-14 days')
                ORDER BY scraped_at DESC
                LIMIT 50
            """), {"cid": cid}).fetchall()

        signals = []
        for row in rows:
            phrase = row[0] if hasattr(row, '__getitem__') else getattr(row, 'signal_phrase', '')
            if phrase and phrase not in signals:
                signals.append(phrase)

        return generate_insight_digest(
            subreddit    = subreddit,
            pain_signals = signals,
            post_count   = len(rows),
        )

    except Exception as e:
        log.warning(f"[value_post] generate_from_recent_prospects error: {e}")
        return generate_insight_digest(subreddit=subreddit, pain_signals=[], post_count=0)


# ── Internal helpers ──────────────────────────────────────────────────────────

def rewrite_with_feedback(post: dict, feedback: str) -> dict | None:
    """
    Rewrite a post based on the user's plain-text feedback from Telegram.
    Preserves platform, subreddit, signal. Returns updated post dict or None.
    """
    platform = (post.get('platform') or 'reddit').lower()

    if platform == 'x':
        tweets  = post.get('tweets') or []
        if not tweets and post.get('body'):
            tweets = [t.strip() for t in post['body'].split('\n\n') if t.strip()]
        thread_text = '\n'.join(f"Tweet {i+1}: {t}" for i, t in enumerate(tweets))

        prompt = f"""Original X thread:
{thread_text}

User feedback: "{feedback}"

Rewrite the thread incorporating this feedback exactly. Keep 6 tweets. Keep specific numbers and scenarios.

Return ONLY valid JSON:
{{"hook": "tweet 1 text", "tweets": ["t1","t2","t3","t4","t5","t6"], "image_prompt": "{post.get('image_prompt','')}"}}"""

        text = _call_claude(prompt, max_tokens=1200, system=_X_SYSTEM)
        if not text:
            return None
        result = _parse_x_thread_json(text, topic=post.get('topic', ''), niche='daytrading')
        if result:
            result['platform']     = 'x'
            result['signal']       = post.get('signal') or post.get('source_signal') or post.get('topic', '')
            result['source_signal'] = post.get('source_signal', '')
        return result

    else:
        prompt = f"""Original Reddit post:
TITLE: {post.get('title', '')}
BODY:
{post.get('body', '')}

User feedback: "{feedback}"

Rewrite the post incorporating this feedback. Keep the same structure and tone — just apply the requested changes.
Keep every sentence earning its place. No filler.

Return ONLY valid JSON:
{{"title": "...", "body": "..."}}"""

        text = _call_claude(prompt, max_tokens=1500, system=_REDDIT_SYSTEM)
        if not text:
            return None
        try:
            clean = text.strip().lstrip('`').rstrip('`')
            if clean.startswith('json'):
                clean = clean[4:].strip()
            result = json.loads(clean)
            return {
                **post,
                'title': result.get('title', post.get('title', '')).strip(),
                'body':  result.get('body',  post.get('body',  '')).strip(),
            }
        except Exception as e:
            log.warning(f"[rewrite] parse error: {e}")
            return None


def _parse_x_thread_json(text: str, topic: str, niche: str, hook_style: str = None) -> dict | None:
    """Parse Claude's JSON response for X thread functions."""
    try:
        clean = text.strip().lstrip('`').rstrip('`')
        if clean.startswith('json'):
            clean = clean[4:].strip()
        result = json.loads(clean)
        tweets = result.get('tweets', [])
        if not tweets:
            return None

        n = len(tweets)
        numbered = []
        for i, t in enumerate(tweets):
            t = t.strip()
            if 0 < i < n - 1:
                suffix = f" {i+1}/{n}"
                if len(t) + len(suffix) <= 280:
                    t = t + suffix
            numbered.append(t)

        out = {
            'type':          'x_thread',
            'topic':         topic,
            'niche':         niche,
            'hook':          result.get('hook', numbered[0] if numbered else ''),
            'tweets':        numbered,
            'tweet_count':   len(numbered),
            'image_prompt':  result.get('image_prompt', ''),
            'generated_at':  datetime.now(timezone.utc).isoformat(),
        }
        if hook_style:
            out['hook_style'] = hook_style
        return out

    except Exception as e:
        log.warning(f"[value_post] x thread parse error: {e} — raw: {text[:200]}")
        return None


def check_duplicate(subreddit: str, title: str, topic: str,
                     client_id: str = None) -> dict:
    """
    Check whether a similar post was already sent to this subreddit recently.
    Returns: {is_duplicate: bool, risk: 'low'|'medium'|'high', reason: str, recent_similar: str}
    """
    import database as _db
    recent = _db.get_recent_posts_for_subreddit(
        client_id or 'default', subreddit, days=14
    )
    if not recent:
        return {"is_duplicate": False, "risk": "low", "reason": "No recent posts to this subreddit."}

    # Build context of recent titles + topics
    recent_summary = "\n".join(
        f"- \"{r.get('title','')[:100]}\" (topic: {r.get('topic') or r.get('source_signal','')[:60]})"
        for r in recent[:8]
    )

    prompt = f"""We are about to post to r/{subreddit}.

New post title: "{title[:200]}"
New post topic/angle: "{topic[:200]}"

Recent posts we already sent to this subreddit (last 14 days):
{recent_summary}

Is the new post covering materially the same angle as any of the above?
Consider angle, not just keywords. Same angle = same takeaway for the reader.

Respond JSON only:
{{"is_duplicate": true or false, "risk": "low" or "medium" or "high", "reason": "one sentence", "most_similar": "title of the most similar post, or empty string"}}"""

    text = _call_claude(prompt, max_tokens=200, system="Respond with JSON only.")
    if not text:
        return {"is_duplicate": False, "risk": "low", "reason": "Could not check."}
    try:
        clean = text.strip().lstrip('`').rstrip('`')
        if clean.startswith('json'):
            clean = clean[4:].strip()
        result = json.loads(clean)
        return {
            "is_duplicate": bool(result.get("is_duplicate")),
            "risk":         result.get("risk", "low"),
            "reason":       result.get("reason", ""),
            "most_similar": result.get("most_similar", ""),
        }
    except Exception as e:
        log.warning(f"[check_duplicate] parse error: {e}")
        return {"is_duplicate": False, "risk": "low", "reason": "Parse error."}
