# Decision-Making Heuristics — Day Trading Pod

## Non-Negotiable Rules
- **Insufficient Intel**: If no clear pain point in the post (< 20 chars or no trading signal), log "Insufficient Intel" and abort. Never guess.
- **DNC is absolute**: If prospect is on Do Not Contact list, abort immediately.
- **Consent gate**: If `consent_granted` is False, drop the event entirely.
- **Circuit breaker**: If circuit breaker is open, do not run. Wait for operator reset.
- **No hardcoded tokens**: Always retrieve from encrypted credential store.
- **Human approval required**: Outreach never sent automatically. All prospects require human click in UI.
- **No external API calls from pods**: All CRM calls go through EventDispatcher only.

## Quality Standards
A good day trading prospect:
- Posts clearly about a trading pain point (blown account, consistency issue, emotional trading)
- Is an active retail trader (not paper trading bragging, not a vendor promoting a service)
- Has at least: handle + platform + post_text with signal phrase
- Is NOT a trading educator, influencer, or account selling signals
- ICP score threshold: 4/10 minimum (env: MIN_ICP_SCORE)

## Signal Priority (highest to lowest)
1. Mentions blown account, liquidation, or specific $ loss
2. Mentions failing a prop firm eval (FTMO, TopStep, etc.)
3. Asks for mentor or coach directly
4. Describes emotional/revenge trading pattern
5. Reports a losing streak without clear resolution

## Abort Conditions
- ANTHROPIC_API_KEY quota exhausted (429/402)
- REDDIT_CLIENT_ID invalid (PRAW returns 401)
- Database unreachable
- Zero prospects across 3 consecutive scans (possible rate limit)
- Bootstrap.validate() fails

## Escalation
1. Log error to `notifications` table with severity=CRITICAL
2. Trip the circuit breaker
3. Surface in Admin tab as red notification
4. Do not retry until operator resets circuit
