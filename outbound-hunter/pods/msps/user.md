# User Configuration — MSPs Pod

## Client details
- **Company name**: [Set per client — e.g., "Nexus IT Solutions"]
- **Client ID**: [Set per client — e.g., "NIT01"]
- **MSP owner / founder name**: [Set per client — e.g., "Mark Svensson"]
- **HubSpot Portal ID**: [Set per client]
- **HubSpot Sequence ID (sme_prospect)**: [Set per client — IT pain sequence]
- **HubSpot Sequence ID (msp_owner)**: [Set per client — BD/AltusFlow sequence]
- **HubSpot Sequence ID (urgent)**: [Set per client — emergency response sequence]

## Niche context
- **Niche slug**: `msps`
- **Target platform**: Reddit (primary), LinkedIn, Facebook
- **Max approvals per run**: 40
- **Auto-approve threshold**: 9.0

## MSP specialisation
[Set per client — e.g., "Managed IT for professional services firms (law, accounting, financial services) in the Pacific Northwest, 10–100 employees"]

## Deal economics
[Set per client — e.g., "Managed services contract: $150–$300/endpoint/month, average client = $4,500/month"]

## Urgent prospect handling
Security incident prospects (is_urgent=True) require a dedicated rapid-response sequence. The standard sequence is too slow for a business under active attack. Set `HubSpot Sequence ID (urgent)` to a same-day response sequence.

## Notes
Three HubSpot sequences needed per client: standard SME, MSP owner BD (AltusFlow), and urgent/emergency. IT professional abort runs on title — do not remove this check even for niche-specific builds.
