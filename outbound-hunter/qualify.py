"""
qualify.py
ICP scoring engine for the Outbound Hunter.

Two-pass scoring:
  Pass 1 — keyword scoring (fast, no API cost):
    Niche title match  (title / company)    0–3 pts
    Niche keyword hit  (post text)          0–2 pts   (bonus when niche module provided)
    Decision-maker title                    0–3 pts
    Post intent strength                    0–2 pts
    Post contains a question                  +1
    Full profile data quality                 +1
    Total possible uncapped:               12
    Cap applied:                           10

  Pass 2 — AI intent scoring (Claude, optional):
    Applied AFTER keyword filtering to avoid burning tokens on junk.
    Set AI_SCORING_ENABLED=true in .env to activate.
    Claude returns a 1–10 score + brief reasoning.
    Final score = max(keyword_score, ai_score) — AI can only improve the score,
    never punish a keyword match it missed context for.
    AI reasoning is appended to icp_notes.
"""

import json
import os
import re
import urllib.request

ANTHROPIC_API_KEY  = os.environ.get('ANTHROPIC_API_KEY', '')
AI_SCORING_ENABLED = os.environ.get('AI_SCORING_ENABLED', 'false').lower() == 'true'
AI_SCORING_MODEL   = os.environ.get('AI_SCORING_MODEL', 'claude-haiku-4-5-20251001')

# ── Universal decision-maker signals ─────────────────────────────────────────

DECISION_MAKER_TITLES = [
    'founder', 'co-founder', 'owner', 'ceo', 'president', 'principal',
    'managing director', 'managing partner', 'director', 'head of',
    'partner', 'vp', 'vice president',
]

# ── Universal high-intent phrases ─────────────────────────────────────────────

HIGH_INTENT_PHRASES = [
    'pipeline', 'lead gen', 'leads', 'clients', 'marketing', 'ads',
    'growing', 'struggling', 'need more', 'how do', 'anyone know',
    'recommendations', 'help', 'advice', 'working for you',
    'booked calls', 'appointments', 'members', 'community',
    'slow', 'dried up', 'dry up', 'not working', 'hard to find',
    'where do i', 'what do you use', 'looking for',
]

# ── Generic industry fallback (used when no niche module is passed) ───────────

_GENERIC_INDUSTRY_KEYWORDS = [
    # Finance
    'financial advisor', 'financial planner', 'wealth manager', 'investment advisor',
    'broker', 'brokerage', 'retirement', 'fund manager', 'portfolio manager',
    'cfa', 'cfp', 'ria', 'insurance', 'estate planning',
    # Coaches / consultants
    'coach', 'consultant', 'coaching practice', 'business coach',
    # Recruiters / staffing
    'recruiter', 'staffing', 'talent acquisition', 'executive search', 'headhunter',
    # CRE
    'commercial real estate', 'cre broker', 'property management', 'leasing agent',
    # MSPs
    'managed services', 'msp', 'it provider', 'managed it',
]

# ── Negative signals ──────────────────────────────────────────────────────────

NEGATIVE_SIGNALS = [
    'hiring', 'job posting', 'we are hiring', 'open position',
    'congratulations', 'just passed', 'certification passed',
    'happy to announce', 'excited to share my new role',
]


def score_prospect(prospect, niche_module=None):
    """
    Score a prospect dict 1-10. Returns (score: int, notes: str).

    Pass niche_module for niche-specific ICP weighting. Without it, falls back
    to generic industry keyword matching (original behaviour).
    """
    score = 0
    notes = []

    title_lower   = (prospect.get('title')    or '').lower()
    company_lower = (prospect.get('company')  or '').lower()
    post_lower    = (prospect.get('post_text') or '').lower()

    # ── Negative signals — hard disqualify ───────────────────────────────────
    for neg in NEGATIVE_SIGNALS:
        if neg in post_lower:
            return 0, f"Disqualified: '{neg}' in post — not a pain signal"

    # ── Niche industry match on title / company (0–3 pts) ────────────────────
    if niche_module and hasattr(niche_module, 'ICP_TITLE_KEYWORDS'):
        title_keywords = niche_module.ICP_TITLE_KEYWORDS
    else:
        title_keywords = _GENERIC_INDUSTRY_KEYWORDS

    industry_hit = next(
        (kw for kw in title_keywords if kw in title_lower or kw in company_lower),
        None,
    )

    if industry_hit:
        score += 3
        notes.append(f"Niche title match: '{industry_hit}'")
    else:
        score += 1
        notes.append("No niche title match — relying on post signal")

    # ── Niche keyword hit in post text (0–2 bonus pts) ───────────────────────
    # Only applied when a niche module with ICP_PROSPECT_KEYWORDS is provided.
    if niche_module and hasattr(niche_module, 'ICP_PROSPECT_KEYWORDS'):
        prospect_kws = niche_module.ICP_PROSPECT_KEYWORDS
        post_hits    = [kw for kw in prospect_kws if kw in post_lower]
        if len(post_hits) >= 3:
            score += 2
            notes.append(f"Strong niche post signal: {post_hits[:3]}")
        elif post_hits:
            score += 1
            notes.append(f"Niche post signal: {post_hits[:2]}")

    # ── Decision-maker title (0–3 pts) ───────────────────────────────────────
    dm_hit = next((dm for dm in DECISION_MAKER_TITLES if dm in title_lower), None)
    if dm_hit:
        score += 3
        notes.append(f"Decision maker: '{dm_hit}' in title")
    else:
        score += 1
        notes.append("Title not clearly decision-maker")

    # ── Post intent strength (0–2 pts) ───────────────────────────────────────
    intent_hits = [p for p in HIGH_INTENT_PHRASES if p in post_lower]
    if len(intent_hits) >= 3:
        score += 2
        notes.append(f"Strong intent: {len(intent_hits)} intent phrases")
    elif intent_hits:
        score += 1
        notes.append(f"Moderate intent: {len(intent_hits)} intent phrase(s)")
    else:
        notes.append("Low post intent")

    # ── Post asks a question (+1) ─────────────────────────────────────────────
    if '?' in (prospect.get('post_text') or ''):
        score += 1
        notes.append("Post asks a question — actively seeking help")

    # ── Full profile data quality (+1) ───────────────────────────────────────
    if prospect.get('name') and prospect.get('company'):
        score += 1
        notes.append("Full profile available")

    return min(score, 10), ' | '.join(notes)


def score_with_ai(prospect, niche_description: str = "") -> tuple[int, str]:
    """
    Call Claude to evaluate a prospect's post for true buying intent.
    Returns (score: int 1-10, reasoning: str).

    Uses Haiku by default (cheap, fast). Skips and returns (0, "") on any error
    so it never blocks the pipeline.
    """
    if not ANTHROPIC_API_KEY:
        return 0, ""

    post_text = (prospect.get('post_text') or '')[:1000]
    title     = prospect.get('title', '')
    company   = prospect.get('company', '')
    platform  = prospect.get('platform', 'unknown')

    niche_context = f"\nTarget niche: {niche_description}" if niche_description else ""

    prompt = f"""You are an outbound sales qualifier. Rate this social media post for buying intent from 1-10.
{niche_context}

Poster: {title} at {company} (platform: {platform})
Post:
"{post_text}"

Scoring guide:
1-3  = Not a buyer signal (generic, congratulatory, hiring post, off-topic)
4-5  = Weak signal (mentions the space but no active pain)
6-7  = Moderate signal (clear challenge, not yet urgent)
8-9  = Strong signal (active pain, seeking solutions, decision-maker)
10   = Perfect fit (explicit ask for what we sell, decision-maker, urgent)

Respond with ONLY a JSON object:
{{"score": <int 1-10>, "reasoning": "<one short sentence>"}}"""

    payload = {
        "model":      AI_SCORING_MODEL,
        "max_tokens": 80,
        "messages":   [{"role": "user", "content": prompt}],
    }

    try:
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers={
                "x-api-key":         ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "Content-Type":      "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())
        raw = data["content"][0]["text"].strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()
        parsed = json.loads(raw)
        score     = max(1, min(10, int(parsed.get("score", 5))))
        reasoning = parsed.get("reasoning", "")
        return score, reasoning
    except Exception:
        return 0, ""


def filter_by_min_score(prospects, min_score=4, niche_module=None):
    """
    Pass 1: keyword-score all prospects, drop those below min_score.
    Pass 2: AI-score the survivors (only if AI_SCORING_ENABLED=true in .env).
    Final icp_score = max(keyword, ai) capped at 10.
    """
    niche_description = getattr(niche_module, 'NICHE_DESCRIPTION', '') if niche_module else ''

    qualified = []
    for p in prospects:
        kw_score, kw_notes = score_prospect(p, niche_module=niche_module)
        p['icp_score'] = kw_score
        p['icp_notes'] = kw_notes

        if kw_score < min_score:
            continue

        if AI_SCORING_ENABLED and ANTHROPIC_API_KEY:
            ai_score, ai_reason = score_with_ai(p, niche_description)
            if ai_score:
                final_score = min(10, max(kw_score, ai_score))
                ai_note = f"AI intent: {ai_score}/10 — {ai_reason}" if ai_reason else f"AI intent: {ai_score}/10"
                p['icp_score'] = final_score
                p['icp_notes'] = kw_notes + ' | ' + ai_note
                p['ai_intent_score'] = ai_score

        qualified.append(p)
    return qualified


if __name__ == '__main__':
    from scrapers.niches import get_niche

    tests = [
        ('financial-advisors', {
            'name': 'Sarah Chen', 'title': 'Founder & CFP',
            'company': 'Chen Financial Group', 'platform': 'linkedin',
            'post_text': (
                "Anyone know a good lead gen strategy for financial advisors? "
                "My pipeline has dried up and I'm struggling to find qualified clients."
            ),
        }),
        ('msps', {
            'name': 'Marcus Lee', 'title': 'IT Manager',
            'company': 'Acme Corp', 'platform': 'reddit',
            'post_text': (
                "We're evaluating managed services providers — any recommendations "
                "for MSPs that handle 200-seat environments well?"
            ),
        }),
        ('recruiters', {
            'name': 'Jessica Tran', 'title': 'Executive Recruiter',
            'company': 'Tran Staffing Solutions', 'platform': 'linkedin',
            'post_text': (
                "LinkedIn is getting saturated. Anyone finding success reaching "
                "candidates elsewhere? My lead gen pipeline has slowed to a crawl."
            ),
        }),
        ('business-coaches', {
            'name': 'Alex Rivera', 'title': 'Business Coach & Consultant',
            'company': 'Rivera Coaching', 'platform': 'facebook',
            'post_text': (
                "Struggling to fill my coaching calendar this quarter. "
                "Anyone recommend a good client acquisition strategy for coaches?"
            ),
        }),
        ('commercial-real-estate', {
            'name': 'Dana Kim', 'title': 'Commercial Real Estate Broker',
            'company': 'Kim Commercial Group', 'platform': 'linkedin',
            'post_text': (
                "Deal flow has been slow. How are other CRE brokers generating "
                "qualified buyer leads right now? The market is tough."
            ),
        }),
    ]

    for slug, prospect in tests:
        niche = get_niche(slug)
        score, notes = score_prospect(prospect, niche_module=niche)
        print(f"\n[{slug}] {prospect['name']} ({prospect['title']}) — {score}/10")
        for note in notes.split(' | '):
            print(f"  {note}")
