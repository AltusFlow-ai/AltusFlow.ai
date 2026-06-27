# Decision-Making Heuristics — Crypto Trading Pod

## Non-Negotiable Rules
- **Insufficient Intel**: If no clear crypto pain point, log "Insufficient Intel" and abort.
- **DNC is absolute**: Abort immediately if on Do Not Contact list.
- **Consent gate**: Drop event if `consent_granted` is False.
- **Circuit breaker**: Do not run if open.
- **Human approval required**: Never auto-send.
- **No direct CRM calls**: All external calls via EventDispatcher.

## Quality Standards
A good crypto prospect:
- Posts about a specific loss event (liquidation, rug, panic sell) or ongoing emotional struggle
- Is a retail trader/holder (not a project founder, VC, or exchange employee)
- Has: handle + platform + post_text with crypto-specific signal
- NOT promoting a token, NFT, or their own signal channel
- NOT asking for investment advice (compliance risk) — looking for trading coaching
- ICP score threshold: 4/10 minimum

## Signal Priority
1. Liquidation or margin call on a crypto exchange
2. Bag holding and emotional attachment to a losing position
3. Describes panic selling the bottom or FOMO into a pump
4. Asks for crypto trading mentor or risk management help
5. Expresses fear/confusion about bear market cycles

## Abort Conditions
- ANTHROPIC_API_KEY quota exhausted
- REDDIT_CLIENT_ID invalid
- Database unreachable
- Zero prospects across 3 consecutive scans
- Bootstrap.validate() fails

## Escalation
1. Log to `notifications` table, severity=CRITICAL
2. Trip circuit breaker
3. Surface in Admin tab
4. No retry until operator resets
