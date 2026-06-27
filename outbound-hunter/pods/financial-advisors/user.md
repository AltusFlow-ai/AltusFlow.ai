# Tenant Configuration — Financial Advisors Pod

## Client Info
- Company: [Client company name]
- Industry: Financial Advisory / Wealth Management
- AltusFlow Client ID: [e.g., FA01 — used in UTM campaign strings]
- HubSpot Portal ID: [portal_id — from HubSpot account settings]
- Meta Ad Account ID: [act_XXXXXXXXX — from Meta Business Manager]
- Tenant Slug: [slug used in tenants/{slug}/outbound_hunter.db]

## ICP Definition
The ideal prospect for this engagement:

- **Decision maker titles**: Financial Advisor, RIA, Wealth Manager, Financial Planner, CFP, Independent Advisor, Managing Partner
- **Company type**: Independent RIA, fee-only practice, solo or small team (1–15 advisors)
- **AUM signal**: Established enough to pay for growth services ($3k–$10k/month range). AUM mentions of $50M–$500M are a strong ICP signal.
- **Geography**: United States only (unless client specifies Canada)
- **Exclusions**: Wire house employees, insurance-only agents, job seekers, students, advisors at firms with 50+ advisors

## Signal Phrases
Custom signal phrases for this client. Leave blank to use niche defaults from `scrapers/niches/financial_advisors.py`.

```
# Custom phrases (one per line):

```

## Tone
- **Formality**: Professional but conversational — peer to peer, not sales pitch
- **Length**: Keep DMs under 400 characters. Advisors are busy.
- **CTA style**: Soft ask for a 20-min intro call. Never push hard. Never mention pricing.
- **Persona**: Austin at AltusFlow — direct, specific, referencing what they actually said
- **Avoid**: Emojis, "I came across your profile", performance guarantees, AUM growth claims, phrases that could violate FINRA advertising rules

## Compliance Notes
- **SEC/FINRA**: Cannot make performance claims, guarantees, or projected AUM growth in outreach. Introductory language only.
- **GDPR/CCPA**: If prospect is EU-based (rare in this niche), consent model applies. Default: opt-out model for US/Canada.
- **Blackout periods**: Avoid outreach to public company executives during earnings windows (typically ±2 weeks around quarterly reporting).
- **Data retention**: Delete prospect data after 90 days of no response (enforced by global_registry cooldown_until expiry + manual purge).
