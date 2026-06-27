"""
auto_router.py
AI-confidence scoring and automatic routing for the Outbound Hunter.

After keyword ICP scoring (qualify.py), each prospect is sent to Claude
for a calibrated confidence assessment. The routing decision is authoritative:

  confidence 9-10  ->  auto_approved  (batch-confirm queue, one-click confirm)
  confidence 4-8   ->  pending        (manual exception review)
  confidence 1-3   ->  auto_skipped   (silent, logged to DB, never surfaced)

If Claude is unavailable for any reason, routing degrades gracefully to the
raw keyword ICP score — no prospect is ever lost or silently discarded without
a logged reason.

Prospects with icp_score > 8 trigger a high-value lead notification regardless
of routing outcome. Even if such a prospect lands in 'pending', the founder
is alerted immediately rather than discovering it on the next UI visit.

Future — Closed Won calibration:
  When you have 10+ Closed Won contacts in HubSpot, add them to
  CLOSED_WON_EXAMPLES as dicts. The prompt includes them as few-shot
  calibration examples automatically. No model training required —
  just prompt engineering with your own data.
"""

import os
import json
import urllib.request
import urllib.error

from database import update_routing

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL             = "claude-sonnet-4-6"

# ── Routing thresholds ────────────────────────────────────────────────────────
AUTO_APPROVE_MIN        = 9  # confidence >= 9 -> auto_approved
MANUAL_MIN              = 4  # confidence 4-8  -> pending; <4 -> auto_skipped
HIGH_VALUE_ICP_THRESHOLD = 8  # icp_score > 8 triggers high-value lead notification

# ── Closed Won calibration examples ──────────────────────────────────────────
# Empty now (pre-revenue). Populate once you have Closed Won data in HubSpot.
# Each dict: name, title, company, signal_phrase, post_excerpt (≤100 chars),
#             confidence_score (what you'd rate them in hindsight), outcome
# Example:
# CLOSED_WON_EXAMPLES = [
#     {
#         "title": "Founder & Financial Advisor",
#         "company": "Smith Wealth Management",
#         "signal_phrase": '"pipeline dried up" financial',
#         "post_excerpt": "Anyone know good lead gen for FAs? Pipeline has completely dried up.",
#         "confidence_score": 10,
#         "outcome": "closed_won",
#     },
# ]
CLOSED_WON_EXAMPLES: list = []

# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an AI confidence scorer for AltusFlow.ai, a productized marketing agency
that installs automated growth systems for high-value B2B financial services businesses.

AltusFlow's Ideal Client Profile (ICP):
  Industry:    Financial advisory, wealth management, RIAs, independent broker-dealers,
               financial planning practices, trading education groups
  Role:        Decision maker who controls the marketing budget — Founder, CEO, Managing Partner,
               Principal, Owner, President. NOT a junior employee or associate.
  Company:     Typically 1-15 people (solo practice to small team). Established enough to pay
               $1,500-$5,000/month for growth systems — not someone who just started.
  Core pain:   Struggling to generate qualified leads consistently. Pipeline has dried up.
               Relying only on referrals. Ads not working. Wants more booked discovery calls.

Confidence score calibration (1-10):
  9-10: Decision maker CONFIRMED in title. Finance industry is clear. Post describes a specific,
        actionable pain about lead gen or client acquisition — not a vague complaint. Strong
        profile data (name + title + company all present). This prospect needs exactly what
        AltusFlow offers. These scores should be rare — only reserve 9-10 for obvious fits.
  7-8:  Likely a good fit. One material factor is ambiguous (seniority not fully confirmed,
        company size unknown, or pain signal is indirect but plausible).
  4-6:  Could be a fit but meaningful uncertainty. Wrong-level title, generic post unrelated
        to lead gen, or very thin profile data.
  1-3:  Probably wrong audience. Not a decision maker, not in financial services, or the post
        is clearly not about growth/client acquisition pain.

IMPORTANT: Routing boundaries are hard. Use these exactly:
  confidence >= 9  ->  routing_decision must be "auto_approved"
  confidence 4-8   ->  routing_decision must be "pending"
  confidence 1-3   ->  routing_decision must be "auto_skipped"

Return ONLY valid JSON with exactly these three keys. No preamble, no explanation, no markdown:
{
  "confidence_score": <integer 1-10>,
  "routing_decision": "<auto_approved|pending|auto_skipped>",
  "reason": "<one concise sentence — the single most important factor driving this score>"
}"""


def _build_prompt(prospect):
    """Build the user-turn prompt for a single prospect."""
    has_name    = bool(prospect.get("name"))
    has_title   = bool(prospect.get("title"))
    has_company = bool(prospect.get("company"))
    profile_completeness = f"{sum([has_name, has_title, has_company])}/3 fields present"

    lines = [
        "Score this prospect:",
        "",
        f"Platform:              {prospect.get('platform', 'unknown')}",
        f"Niche:                 {prospect.get('niche', 'unknown')}",
        f"Name:                  {prospect.get('name') or '(not available)'}",
        f"Title:                 {prospect.get('title') or '(not available)'}",
        f"Company:               {prospect.get('company') or '(not available)'}",
        f"Profile completeness:  {profile_completeness}",
        f"Keyword ICP score:     {prospect.get('icp_score', 0)}/10 (rule-based pre-filter)",
        f"ICP notes:             {prospect.get('icp_notes') or '(none)'}",
        f"Signal phrase matched: \"{prospect.get('signal_phrase', '')}\"",
        "",
        "Their exact post:",
        f"\"{prospect.get('post_text', '')}\"",
    ]

    if CLOSED_WON_EXAMPLES:
        lines.append("")
        lines.append("Calibration reference — previous Closed Won contacts:")
        for ex in CLOSED_WON_EXAMPLES[:5]:
            lines.append(
                f"  [{ex.get('outcome','closed_won')}] "
                f"{ex.get('title','')} at {ex.get('company','')} | "
                f"signal: \"{ex.get('signal_phrase','')}\" | "
                f"post: \"{ex.get('post_excerpt','')}\" | "
                f"rated: {ex.get('confidence_score','')}/10"
            )

    return "\n".join(lines)


def _call_claude(prospect):
    """
    Make one Claude API call for a prospect.
    Returns (confidence_score: int, routing_decision: str, reason: str)
    or None if the call fails for any reason.
    """
    if not ANTHROPIC_API_KEY:
        return None

    payload = {
        "model":      MODEL,
        "max_tokens": 200,
        "system":     _SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": _build_prompt(prospect)}],
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
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read())

        raw = data["content"][0]["text"].strip()

        # Strip markdown code fences if Claude wraps the JSON
        if raw.startswith("```"):
            parts = raw.split("```")
            raw   = parts[1].lstrip("json").strip()

        result   = json.loads(raw)
        score    = max(1, min(10, int(result["confidence_score"])))
        decision = str(result["routing_decision"]).strip()
        reason   = str(result.get("reason", "")).strip()

        # Enforce routing boundaries — correct any drift in Claude's output
        if score >= AUTO_APPROVE_MIN:
            decision = "auto_approved"
        elif score >= MANUAL_MIN:
            decision = "pending"
        else:
            decision = "auto_skipped"

        return score, decision, reason

    except (KeyError, ValueError, json.JSONDecodeError) as e:
        # Claude returned something we couldn't parse — treat as failure
        return None

    except Exception:
        return None


def _deterministic_fallback(icp_score):
    """
    Keyword-score-based routing when Claude is unavailable.
    Coarser than LLM scoring but guarantees no prospect is silently lost.
    All prospects routed this way land in 'pending' unless score is extreme.
    """
    if icp_score >= AUTO_APPROVE_MIN:
        return icp_score, "auto_approved", "Fallback routing: keyword ICP score >= 9 (Claude API unavailable)"
    elif icp_score >= MANUAL_MIN:
        return icp_score, "pending",       "Fallback routing: keyword ICP score 4-8 (Claude API unavailable)"
    else:
        return icp_score, "auto_skipped",  "Fallback routing: keyword ICP score < 4 (Claude API unavailable)"


def route_prospect(prospect, run_id=None):
    """
    Score and route a single prospect.

    - Calls Claude for confidence score + routing decision
    - Falls back to deterministic keyword scoring if Claude fails
    - Writes routing result to DB (requires prospect['id'] to be set)
    - Updates prospect dict in-place with confidence_score / confidence_reason / routing_decision
    - Fires high-value lead notification if icp_score > HIGH_VALUE_ICP_THRESHOLD
    - Returns routing_decision string

    Never raises.
    """
    from error_logger import log_pipeline_error, log_high_value_lead, WARNING

    prospect_id = prospect.get("id")
    name        = prospect.get("name") or prospect.get("handle") or "Unknown"

    # ── Score ─────────────────────────────────────────────────────────────────
    result = _call_claude(prospect)

    if result is not None:
        confidence, decision, reason = result
    else:
        if ANTHROPIC_API_KEY:
            # Key is set but call still failed — log as warning
            log_pipeline_error(
                run_id, "auto_router",
                f"Claude API call failed for '{name}' — falling back to keyword ICP score.",
                WARNING,
            )
        confidence, decision, reason = _deterministic_fallback(prospect.get("icp_score", 0))

    # ── Update prospect dict in-place ─────────────────────────────────────────
    prospect["confidence_score"]  = confidence
    prospect["confidence_reason"] = reason
    prospect["routing_decision"]  = decision

    # ── Persist to DB ─────────────────────────────────────────────────────────
    if prospect_id:
        update_routing(prospect_id, confidence, reason, decision)

    # ── High-value lead alert ─────────────────────────────────────────────────
    # Triggered by keyword ICP score > 8, regardless of routing outcome.
    # A high-ICP prospect routed to 'pending' still deserves immediate attention.
    if prospect.get("icp_score", 0) > HIGH_VALUE_ICP_THRESHOLD:
        log_high_value_lead(run_id, prospect)

    return decision


def route_batch(prospects, run_id=None):
    """
    Route a list of prospects through the AI confidence scorer.

    Prospects must already be inserted into the DB so that prospect['id']
    is populated (main.py is responsible for this).

    Updates each prospect dict in-place.
    Returns a counts dict: {"auto_approved": N, "pending": N, "auto_skipped": N}
    """
    counts = {"auto_approved": 0, "pending": 0, "auto_skipped": 0}

    for prospect in prospects:
        name     = prospect.get("name") or prospect.get("handle") or "?"
        decision = route_prospect(prospect, run_id=run_id)
        counts[decision] = counts.get(decision, 0) + 1

        status_label = {
            "auto_approved": "AUTO-APPROVED",
            "pending":       "PENDING REVIEW",
            "auto_skipped":  "AUTO-SKIPPED",
        }.get(decision, decision.upper())

        print(
            f"  [{status_label}] {name} "
            f"(ICP {prospect.get('icp_score','?')}/10, "
            f"Confidence {prospect.get('confidence_score','?')}/10)"
        )

    return counts
