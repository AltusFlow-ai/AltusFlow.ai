---
name: claude-drafter
version: 1.0.0
description: Generate hyper-personalised outreach messages using Claude API based on exact prospect post text
author: AltusFlow
tools:
  - http_request
permissions:
  - network
inputs:
  - name: prospect
    type: object
    required: true
    properties:
      post_text: string (required — exact post, non-empty)
      name: string
      title: string
      company: string
      platform: string
      niche_slug: string
  - name: niche_context
    type: object
    description: Deal economics and common objections from pod's hunter.py
outputs:
  - name: connection_request
    type: string
    maxLength: 300
  - name: dm
    type: string
    maxLength: 800
  - name: call_opener
    type: string
    description: One sentence to open the discovery call
  - name: confidence_score
    type: float
    description: 0-10 routing confidence from auto_router
---

# Claude Drafter Skill

## Purpose
Generate personalised outreach that references the prospect's exact post text.
This is the core value — the message must feel like a human read their post.

## Critical Rules
- post_text must be non-empty — if empty, return error, never draft a generic message
- Message must open with prospect's exact words or very close paraphrase
- Never mention that post was found via AI scanner
- Never mention price in any message
- Never use exclamation marks
- Connection request must be under 300 characters
- DM must be under 800 characters
- If Claude API returns an error: store draft_error, flag for manual drafting in UI

## Model
`claude-sonnet-4-6` — always. Never substitute a different model.

## API Call Format
Direct HTTP POST — no SDK. As per CLAUDE.md: all Claude calls use `requests.post()`
or `urllib.request.urlopen()` to `https://api.anthropic.com/v1/messages`.

```json
{
  "model": "claude-sonnet-4-6",
  "max_tokens": 1024,
  "messages": [{"role": "user", "content": "[assembled prompt]"}]
}
```

## Prompt Injection
The system prompt includes:
- Niche-specific context (deal economics, common objections)
- AltusFlow brand voice rules
- Character limits
- Output format (JSON only)

## Quality Gate
After drafting, run a quality check:
- Does the message reference the prospect's post? (keyword overlap check)
- Is it under character limit?
- Does it end with a soft CTA?
- If any check fails: flag as needs_review in auto_router, never auto-approve

## Cost Logging
Each Claude API call logs to budget_transactions:
- Platform: Claude API
- Amount: estimated $0.003 per draft (input + output tokens)
- Direction: out
