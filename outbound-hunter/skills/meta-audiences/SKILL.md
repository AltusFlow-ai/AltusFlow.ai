---
name: meta-audiences
version: 1.0.0
description: Push approved prospects to Meta Custom Audiences for retargeting and lookalike building
author: AltusFlow
tools:
  - http_request
permissions:
  - network
inputs:
  - name: prospects
    type: array
    description: Array of approved prospects — PII already hashed by EventDispatcher
  - name: audience_name
    type: string
    description: Target audience name e.g. 'AltusFlow Hunter — Financial Advisors'
  - name: ad_account_id
    type: string
    required: true
outputs:
  - name: users_added
    type: integer
  - name: match_rate
    type: float
  - name: audience_id
    type: string
  - name: success
    type: boolean
---

# Meta Custom Audiences Skill

## Purpose
Add Hunter-approved prospects to niche-specific Meta Custom Audiences.
These audiences are significantly warmer than cold targeting — prospects have
already posted about their pain and visited the AltusFlow site.

## Critical Rules
- ALL PII must be SHA-256 hashed before this skill receives it.
  EventDispatcher handles hashing — this skill never receives raw PII.
- One audience per niche per client — naming convention:
  `AltusFlow Hunter — [Niche Label] — [Client ID]`
- If audience does not exist: create it before adding users
- Batch uploads: max 10,000 users per API call
- Never push a prospect with `consent_granted = False`

## Hashed Fields to Send
- `email_hash`: SHA-256 of lowercased, stripped email
- `fn_hash`: SHA-256 of lowercased first name (optional but improves match rate)
- `ln_hash`: SHA-256 of lowercased last name (optional)

## API Endpoint
```
POST https://graph.facebook.com/v18.0/{audience_id}/users
Authorization: Bearer {META_ACCESS_TOKEN}
```

Payload schema:
```json
{
  "payload": {
    "schema": ["EMAIL", "FN", "LN"],
    "data": [["<email_hash>", "<fn_hash>", "<ln_hash>"]]
  }
}
```

## Error Handling
- 190 Invalid token: log critical, alert admin
- 100 Invalid parameter: log error with full payload for debugging
- Rate limit: batch requests, max 1 call per second

## Match Rate Monitoring
Log `match_rate` after every push to budget_transactions metadata.
If match_rate drops below 20%: log warning (data quality issue).
Target match rate: 30–60% for professional audiences.
