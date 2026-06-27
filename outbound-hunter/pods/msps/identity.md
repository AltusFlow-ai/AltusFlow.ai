# Pod Identity — MSPs (IT Managed Service Providers)

## What this pod does
Scans Reddit, LinkedIn, and Facebook for two distinct prospect types:
1. **SME prospects** — business owners with IT pain (prospects for MSP clients)
2. **MSP owners** — with BD/growth struggles (AltusFlow direct prospects)

## Prospect types

### sme_prospect
Small and mid-size business owners who are:
- Posting frustration about unreliable IT support
- Looking for MSP recommendations
- Experiencing IT-related downtime or cost overruns
- Had a bad experience with their current IT provider
- Facing a security incident (ransomware, breach, phishing) — flagged URGENT

### msp_owner
MSP founders and owners who are:
- Posting about difficulty growing beyond referrals
- Asking how to do outbound or get more clients
- Losing RFPs to larger players
- Trying to move from break-fix to managed services

## Who we are NOT looking for
- IT professionals (sysadmins, developers, engineers) posting about their work — they ARE the IT, not the buyer
- Software developers posting coding content
- Companies posting IT job listings

## Security incident urgency
When an SME prospect posts about a ransomware attack, data breach, or active phishing, the post is flagged as `is_urgent=True`. These prospects need help immediately — urgency flag triggers priority review regardless of run schedule.

## Platform signal quality
- **Reddit**: Highest volume for IT pain — r/smallbusiness owners post candidly about IT frustrations
- **LinkedIn**: MSP owner BD pain and business leader IT frustrations
- **Facebook**: MSP professional groups and small business communities
