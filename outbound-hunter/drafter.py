"""
drafter.py
Uses the Claude API to generate hyper-personalised outreach messages.
The prospect's EXACT post text is passed into the prompt — this is the firepower.

Each prospect gets:
  - connection_request  (under 300 chars, LinkedIn connection note)
  - dm                  (under 500 chars, LinkedIn DM or X DM)
  - call_opener         (1-2 sentences for the discovery call opener)
  - cta_url             (UTM-tagged link to altusflow.ai, stored in DB)

The CTA link in every message carries UTM parameters so the attribution
chain is closed: signal post → outreach → website visit → chat → booked call.
"""

import os
import re
import json
import urllib.request
import urllib.error

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
MODEL             = "claude-sonnet-4-6"
CLIENT_ID         = os.environ.get("CLIENT_ID", "ALT00")
SITE_URL          = os.environ.get("SITE_URL", "https://altusflow.ai")
SENDER_NAME       = os.environ.get("SENDER_NAME", "Austin")
SENDER_COMPANY    = os.environ.get("SENDER_COMPANY", "AltusFlow.ai")


# ── UTM helpers ───────────────────────────────────────────────────────────────

def _slugify(text, max_len=50):
    """Convert signal phrase to URL-safe slug."""
    slug = re.sub(r"[^a-z0-9\s-]", "", text.lower())
    slug = re.sub(r"\s+", "-", slug.strip())
    slug = re.sub(r"-+", "-", slug)
    return slug[:max_len].rstrip("-")


def build_cta_url(signal_phrase, platform="linkedin", client_id=None):
    """
    Build a UTM-tagged CTA URL for the outreach message.

    Convention: [CLIENT-ID]_OH_outbound / [platform] / [phrase-slug]
    This closes the attribution chain in HubSpot when the prospect
    visits the website after receiving outreach.
    """
    cid      = client_id or CLIENT_ID
    slug     = _slugify(signal_phrase or "growth")
    medium   = platform.lower() if platform else "linkedin"
    campaign = f"{cid}_OH_outbound"
    return (
        f"{SITE_URL}/"
        f"?utm_source=outbound"
        f"&utm_medium={medium}"
        f"&utm_campaign={campaign}"
        f"&utm_content={slug}"
    )


# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = f"""You are writing Reddit and X/Twitter outreach messages for {SENDER_NAME} at {SENDER_COMPANY}.

AltusFlow builds automated growth systems for high-value B2B businesses — three components:
1. A custom-trained AI assistant on their website that qualifies leads and books calls 24/7
2. Meta Ads funnels that turn cold traffic into booked calls
3. An outbound AI that scans Reddit and X for prospects actively signalling intent

Your job: write TWO pieces of outreach that reference the prospect's exact post and lead them toward a 20-minute discovery call.

PIECE 1 — PUBLIC COMMENT (post this as a reply to their thread/tweet before any DM):
- Adds genuine value to the conversation — answer their question or validate their pain
- Sounds like a helpful community member, not a salesperson
- DO NOT pitch AltusFlow directly — just show expertise and empathy
- End with ONE soft question that invites them to continue the conversation
- Reddit comments: 2-4 sentences, conversational, platform-native
- X replies: under 250 characters, punchy
- No links, no CTA URL in the comment

PIECE 2 — DIRECT MESSAGE (send after they engage with the comment, or cold):
- Open by referencing their EXACT words — must feel specific, not generic
- One sentence on what AltusFlow does relevant to their pain
- Soft CTA: suggest a 20-minute call, never pitch hard. Include the CTA link near the end.
- Under 300 characters for Reddit DMs. Under 280 for X DMs.
- No emojis. No corporate speak. Sound like a real person.
- Never mention price. Never say "I noticed" or "I came across your profile."
- Start with "Hey [First Name] —" if name is known, otherwise skip the opener

RULES FOR BOTH:
- Reference their EXACT signal phrase or a close paraphrase
- Never hallucinate context not in their post
- Write for the platform (Reddit = casual/community, X = punchy/direct)

OUTPUT: Return a JSON object with exactly these keys:
{
  "public_comment": "helpful public reply to their post — no CTA link, adds value, ends with a question",
  "dm": "under 300 char DM with CTA link near the end",
  "call_opener": "1-2 sentences to open the discovery call referencing their specific post"
}
Return ONLY the JSON. No preamble, no explanation."""


def draft_message(prospect):
    """
    Generate personalised outreach for a prospect.
    Returns dict with 'connection_request', 'dm', 'call_opener', and 'cta_url' keys.
    """
    signal_phrase = prospect.get("signal_phrase") or ""
    platform      = prospect.get("platform") or "linkedin"
    cta_url       = build_cta_url(signal_phrase, platform=platform)

    if not ANTHROPIC_API_KEY:
        placeholder = "[API key not set — add ANTHROPIC_API_KEY to Railway env vars]"
        return {
            "public_comment": placeholder,
            "dm":             placeholder,
            "call_opener":    placeholder,
            "cta_url":        cta_url,
        }

    first_name = (prospect.get("name") or "there").split()[0]
    title      = prospect.get("title") or "professional"
    company    = prospect.get("company") or "your company"
    post_text  = prospect.get("post_text") or ""

    # Niche context injected by main.py before drafting
    niche_label  = prospect.get("_niche_label")
    deal_econ    = prospect.get("_deal_economics", "")
    objection    = prospect.get("_common_objections", "")
    niche_block  = ""
    if niche_label:
        niche_block = (
            f"\nNiche context (use to sharpen the message):\n"
            f"- Who they are: {niche_label}\n"
            f"- Deal economics: {deal_econ}\n"
            f"- Main objection to pre-empt: {objection}\n"
        )

    outreach_method = prospect.get("outreach_method", "direct")
    reddit_username = prospect.get("reddit_username") or prospect.get("handle", "")
    platform_label  = platform

    if outreach_method == "reddit_dm" or platform_label == "reddit":
        platform_note = (
            f"\nIMPORTANT: This is Reddit outreach to u/{reddit_username}. "
            "public_comment = a helpful reply to their thread (2-4 sentences, no link). "
            "dm = the Reddit DM body (under 300 chars, casual tone, include CTA link). "
            "Reference their subreddit and post naturally."
        )
        platform_label = "reddit"
    elif platform_label in ("twitter", "x"):
        platform_note = (
            "\nIMPORTANT: This is X/Twitter outreach. "
            "public_comment = a reply to their tweet (under 250 chars, punchy, no link). "
            "dm = the X DM (under 280 chars, include CTA link near the end)."
        )
        platform_label = "x"
    else:
        platform_note = ""

    user_prompt = f"""Write outreach for this prospect. Include this exact CTA link in the DM only: {cta_url}

Name: {first_name}
Platform: {platform_label}
Signal phrase that matched: "{signal_phrase}"
{niche_block}
Their exact post:
"{post_text}"
{platform_note}
public_comment: helpful reply to their post, no CTA link, ends with a question.
dm: opens with direct reference to their post, CTA link near the end, under 300 chars.
call_opener: 1-2 sentences to open the discovery call referencing their specific post."""

    payload = {
        "model":      MODEL,
        "max_tokens": 600,
        "system":     SYSTEM_PROMPT,
        "messages":   [{"role": "user", "content": user_prompt}],
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
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read())

        text_raw = data["content"][0]["text"].strip()

        # Strip markdown fences if Claude wraps in ```json
        if text_raw.startswith("```"):
            parts = text_raw.split("```")
            text_raw = parts[1]
            if text_raw.startswith("json"):
                text_raw = text_raw[4:]
        text_raw = text_raw.strip()

        result = json.loads(text_raw)
        result["cta_url"] = cta_url
        _append_disclosure(result)
        return result

    except Exception as e:
        fallback = (
            f"Hey {first_name} — saw your post about {post_text[:60]}... "
            f"we help with exactly this. Worth 20 mins? {cta_url}"
        )
        draft = {
            "connection_request": fallback[:300],
            "dm":                 fallback[:500],
            "call_opener":        f"Hey {first_name}, I read your post about {post_text[:80]}...",
            "cta_url":            cta_url,
            "error":              str(e),
        }
        _append_disclosure(draft)
        return draft


def _append_disclosure(draft: dict):
    """
    If a disclosure footer is configured in tenant_settings, append it to the
    'dm' field. Marks draft['disclosure_appended'] = True so the audit log
    can record it accurately.
    """
    try:
        from database import get_tenant_setting
        footer = get_tenant_setting('disclosure_footer', '')
        if footer and footer.strip():
            draft['dm'] = (draft.get('dm') or '') + '\n\n' + footer.strip()
            draft['disclosure_appended'] = True
            return
    except Exception:
        pass
    draft['disclosure_appended'] = False


def draft_batch(prospects):
    """Draft messages for a list of prospects. Adds drafted_message, call_opener, cta_url."""
    for p in prospects:
        result = draft_message(p)
        p["drafted_message"] = result.get("dm", "")
        # public_comment is stored in call_opener — the Prospects UI reads call_opener
        # for the "Public comment" / "Reply on X" tab
        p["call_opener"]     = result.get("public_comment", "") or result.get("call_opener", "")
        p["cta_url"]         = result.get("cta_url", "")
        p["draft_error"]     = result.get("error", "")
    return prospects


if __name__ == "__main__":
    test_prospect = {
        "name":          "Sarah Chen",
        "title":         "Founder — Retirement Planning Advisor",
        "company":       "Chen Financial Group",
        "post_text":     "Anyone else struggling to find qualified clients in this market? My pipeline has completely dried up the last 6 weeks and I'm not sure what's working anymore for lead gen as a financial advisor.",
        "platform":      "linkedin",
        "signal_phrase": "pipeline dried up",
    }
    cta = build_cta_url(test_prospect["signal_phrase"], platform=test_prospect["platform"])
    print(f"CTA URL: {cta}\n")
    result = draft_message(test_prospect)
    print("Connection request:")
    print(result.get("connection_request", ""))
    print(f"\nDM ({len(result.get('dm',''))} chars):")
    print(result.get("dm", ""))
    print("\nCall opener:")
    print(result.get("call_opener", ""))
