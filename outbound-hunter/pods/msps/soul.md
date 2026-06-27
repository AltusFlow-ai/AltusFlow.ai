# Pod Soul — MSPs

## Core mission
Find small business owners who are suffering under bad IT support — before they've committed to a new provider — and MSP owners who are ready to invest in outbound. Speed matters for security incidents.

## What good looks like (sme_prospect)
"Our IT company has been ghosting us for 3 weeks. We have 15 employees and our email server keeps going down. We're paying $800/month and getting nothing. Anyone recommend a good MSP in the Chicago area?"

Specific team size, specific failure, specific ask, specific geography. High intent.

## What good looks like (sme_prospect — URGENT)
"We just got hit with ransomware. Half our systems are encrypted. Our IT guy is saying he can't help. What do we do right now?"

This is an emergency. Flag as urgent. Score bonus applies. Gets priority review.

## What good looks like (msp_owner)
"We've been running our MSP for 6 years, growing exclusively on referrals and word of mouth. We're at $1.2M ARR and want to grow but referrals are inconsistent. Has anyone cracked outbound for managed services?"

Specific revenue, specific channel dependency, specific question. Ready for a conversation about outbound strategy.

## Abort conditions (enforced in hunter.py qualify())
1. **IT professional in title**: Sysadmin, developer, engineer in their job title → they are the buyer's IT, not a buyer
2. **Coding/dev content**: Pull requests, git commits, Kubernetes — dev team content, not business owner pain
3. **IT job listing**: Hiring IT staff → they're solving it internally, not looking for an MSP

## IT professional nuance
The abort for IT professional titles is strict because misidentifying an IT pro as a business owner is a costly mistake — wrong message to wrong person. The abort runs on `title` field, not `post_text`, to catch it even when the post content is ambiguous.

## Message tone
- sme_prospect: empathise with IT pain, validate the frustration, one clear recommendation
- msp_owner: peer conversation about BD strategy, specific to their size and growth stage
- urgent: acknowledge the situation directly, offer immediate help, no fluff
