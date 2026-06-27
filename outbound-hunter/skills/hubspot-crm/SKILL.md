---
name: hubspot-crm
version: 1.0.0
description: Create and update contacts, deals, notes, and properties in HubSpot CRM
author: AltusFlow
tools:
  - http_request
permissions:
  - network
inputs:
  - name: operation
    type: string
    enum: [upsert_contact, create_deal, add_note, update_deal_stage, get_contact]
    required: true
  - name: payload
    type: object
    required: true
  - name: portal_id
    type: string
    required: true
outputs:
  - name: contact_id
    type: string
  - name: deal_id
    type: string
  - name: success
    type: boolean
  - name: error
    type: string
---

# HubSpot CRM Skill

## Purpose
All HubSpot operations from any pod route through this skill.
No pod may call HubSpot directly — all calls go through EventDispatcher first.

## Critical Rules
- Never call HubSpot with unhashed PII — EventDispatcher hashes before this skill runs
- If CONTACT_EXISTS error on create: switch to update operation automatically
- If HubSpot returns 429: wait 10s, retry once, then log warning
- Always return hubspot_contact_id and store in prospects table
- Portal ID comes from pod's user.md — never hardcoded

## Required Properties on Every Contact Push
All 7 AltusFlow custom properties must be populated:
- altusflow_lead_source_vertical
- altusflow_client_portal_id
- altusflow_lead_qualified_status
- altusflow_ai_chat_score
- altusflow_first_touch_campaign
- altusflow_outbound_trigger_phrase (exact post text — truncated to 500 chars)
- altusflow_meeting_booked_date (null until meeting booked)

## Intelligence Note Format
Every approved prospect gets a HubSpot note with this structure:
```
ALTUSFLOW INTEL NOTE — [date]
Platform: [platform]
Post Date: [post_date]
Signal Phrase Matched: [signal_phrase]
Prospect's Exact Words: "[post_text — first 500 chars]"
ICP Score: [score]/10
Confidence: [confidence]
Pod: [pod_slug]
```

## Error Handling
- 401 Unauthorized: log critical, alert admin, do not retry
- 429 Rate limit: wait 10s, retry once
- 500 Server error: log warning, queue for retry in 5 minutes
- Missing required property: log error, do not push partial record

## Retry Queue
Failed pushes are stored in a retry queue — attempt again on next heartbeat run.
After 3 failed attempts: escalate to critical alert.
