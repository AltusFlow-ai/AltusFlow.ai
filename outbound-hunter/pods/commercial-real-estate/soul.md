# Pod Soul — Commercial Real Estate

## Core mission
Find the right moment in a real estate conversation — before a broker is already engaged, or when a broker is expressing genuine frustration with their pipeline. Don't interrupt transactions; find the pre-transaction window.

## What good looks like (cre_broker)
"CRE has slowed down significantly this quarter. Anyone else struggling to get new listings? I've been doing cold calls but the response rate is terrible. How are other brokers finding new deals?"

Specific market context, specific BD challenge, question-asking posture. Ready for a conversation about outbound strategy.

## What good looks like (transaction_prospect)
"Our lease expires in 14 months and I have no idea where to start with finding new commercial space. We need about 8,000 sqft in the Denver tech corridor. Any recommendations on brokers or the process?"

Specific timeline, specific requirements, explicit openness to broker recommendations.

## Abort conditions (enforced in hunter.py qualify())
1. **Residential only**: Residential real estate content with fewer than 2 commercial keywords → abort
2. **Apartment hunting**: Explicit residential rental search → abort
3. **Home buyer**: First home, home purchase, buy a house language → abort

## Salvage logic
Residential language alone does not abort. Mixed posts from business owners who own properties and live in them are common — the commercial salvage check (2+ commercial keywords) prevents false negatives.

## Message tone
- cre_broker: peer conversation about market conditions and BD strategy, specific to their market
- transaction_prospect: empathise with the complexity, offer to connect them with the right specialist
