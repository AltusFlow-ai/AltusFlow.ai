# User Configuration — AltusFlow Own Prospecting Pod

## Company
- **Company name**: AltusFlow.ai
- **Client ID**: ALT00
- **Contact name**: Austin [Last name]
- **HubSpot Portal ID**: 246530361
- **HubSpot Sequence ID**: [Set — AltusFlow's own prospect sequence]

## Niche context
- **Niche slug**: `altusflow-own`
- **Target platform**: LinkedIn (primary), Facebook, Reddit
- **Max approvals per run**: 20
- **Auto-approve threshold**: 9.5 (stricter than all client pods)
- **Min ICP score**: 8

## Target niches
All five AltusFlow verticals:
- financial-advisors
- business-coaches
- recruiters
- commercial-real-estate
- msps

## Deal economics
AltusFlow outbound retainer: $2,000–$5,000/month per client

## Brand voice
Direct. Human. Specific. Austin is not an "outbound rep" in these messages — he's a professional who genuinely read the post and has a specific reason for reaching out. Every message must reference something specific from the prospect's post. Never sound automated.

## HubSpot dedup
This pod always runs `_is_in_hubspot()` before scoring. Portal 246530361. Anyone already in CRM is skipped automatically. This prevents double-outreach from other team members or past campaigns.

## Notes
This pod feeds Austin's personal calendar, not a client pipeline. Volume is intentionally low — 20 max approvals per run. It is better to send 3 great messages than 15 mediocre ones.
