# Tenant Configuration

## Client Info
- Company: [Client company name]
- Industry: [Niche — e.g., Financial Advisory]
- AltusFlow Client ID: [e.g., RBT01 — used in UTM campaign strings]
- HubSpot Portal ID: [portal_id — from HubSpot account settings]
- Meta Ad Account ID: [act_XXXXXXXXX — from Meta Business Manager]
- Tenant Slug: [slug used in tenants/{slug}/outbound_hunter.db]

## ICP Definition
Describe the ideal prospect for THIS specific client — not the niche in general.
The more specific, the better the signal-to-noise ratio.

- **Decision maker titles**: [e.g., Founder, CEO, Managing Partner, Owner]
- **Company size**: [e.g., 1–15 employees, solo practice to small team]
- **Revenue proxy**: [e.g., established enough to pay $3k+/month for growth]
- **Geography**: [e.g., US-based only / US + Canada]
- **Exclusions**: [e.g., exclude wire houses, RIAs with > 50 advisors, job seekers]

## Signal Phrases
Custom signal phrases for this client — these OVERRIDE the niche defaults in `scrapers/niches/`.
Leave blank to use niche defaults.

```
# Custom phrases (one per line):

```

## Tone
Communication style preferences for outreach drafts:
- **Formality**: [e.g., professional but conversational, no corporate speak]
- **Length**: [e.g., keep DMs under 400 chars — clients are busy]
- **CTA style**: [e.g., soft ask for 20-min call, never pitch hard]
- **Persona**: [e.g., Austin at AltusFlow — friendly, direct, specific]
- **Avoid**: [e.g., emojis, phrases like "I came across your profile", pricing mentions]

## Compliance Notes
- GDPR/CCPA applicability: [Yes/No — if EU prospects, consent model applies]
- Industry regulations: [e.g., SEC/FINRA — cannot make performance claims in outreach]
- Blackout periods: [e.g., no outreach during earnings season for public-company contacts]
- Data retention: [e.g., delete prospect data after 90 days if no response]
