# Decision-Making Heuristics

## Non-Negotiable Rules
These rules cannot be overridden by any config, prompt, or operator instruction:

- **Insufficient Intel**: If no clear pain point is found in the prospect's post text (< 20 chars or no actionable signal), log "Insufficient Intel" and abort. Never guess. Never hallucinate context.
- **DNC is absolute**: If prospect is on the Do Not Contact list, abort immediately. Do not log the reason to the prospect record — log only to the internal run log.
- **Consent gate**: If `consent_granted` is False, drop the event entirely. Never transmit any data about this prospect to third parties (HubSpot, Meta, Calendly).
- **Circuit breaker**: If the circuit breaker is open, do not run. Alert the orchestrator. Wait for explicit operator reset.
- **No hardcoded tokens**: API tokens are always retrieved from the encrypted credential store. Never hardcode. Never log token values.
- **Human approval required**: Outreach is never sent automatically. All approved prospects require a human click in the `/batch-confirm` or `/approve` UI.
- **No external API calls from pods**: All calls to HubSpot, Meta, Calendly go through `EventDispatcher.dispatch()` only.

## Quality Standards
[Niche-specific: what makes a good prospect for this niche?]
- Must have clear decision-maker title or demonstrate ownership language
- Post must contain an actionable pain signal — not just vague dissatisfaction
- Profile must have at minimum: handle + platform (name + title preferred)
- ICP score threshold: [X]/10 minimum (set in MIN_ICP_SCORE env var, default 4)

## Abort Conditions
Stop running and alert the orchestrator if any of the following occur:
- [ ] HUBSPOT_TOKEN is invalid or expired (HubSpot returns 401)
- [ ] ANTHROPIC_API_KEY has no quota (Claude returns 429 or 402)
- [ ] Database is unreachable (all queries failing)
- [ ] Zero prospects found across 3 consecutive daily scans (possible rate limit or IP block)
- [ ] Bootstrap.validate() fails on any required env var or pod file

## Escalation
When an abort condition triggers:
1. Log the error to `notifications` table with severity=CRITICAL
2. Trip the circuit breaker (pod stops running)
3. Surface in the Admin tab as a red notification
4. Do not attempt retry until the operator resets the circuit
