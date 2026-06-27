# User Configuration — Recruiters Pod

## Client details
- **Company name**: [Set per client — e.g., "Apex Talent Partners"]
- **Client ID**: [Set per client — e.g., "ATP01"]
- **Recruiter / founder name**: [Set per client — e.g., "James Thornton"]
- **HubSpot Portal ID**: [Set per client]
- **HubSpot Sequence ID (agency_owner)**: [Set per client — BD conversation]
- **HubSpot Sequence ID (hiring_manager)**: [Set per client — talent conversation]

## Niche context
- **Niche slug**: `recruiters`
- **Target platform**: LinkedIn (primary), Facebook, Reddit
- **Max approvals per run**: 35
- **Auto-approve threshold**: 9.0

## Specialisation
[Set per client — e.g., "SaaS engineering roles in Series A/B startups"]

## Deal economics
[Set per client — e.g., "20% of first-year salary, average placement $14k per hire"]

## Notes
Two HubSpot sequences are needed per client: one for agency_owner prospects (AltusFlow's own BD context), one for hiring_manager prospects (the recruiter's target client). Ensure `prospect_type` is correctly tagged before HubSpot push — the sequences have completely different messaging.
