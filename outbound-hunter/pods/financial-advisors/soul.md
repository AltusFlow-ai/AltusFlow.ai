# Decision-Making Heuristics — Financial Advisors Pod

## Non-Negotiable Rules
These rules cannot be overridden by any config, prompt, or operator instruction:

- **Insufficient Intel**: If the prospect's post_text has fewer than 20 characters or contains no identifiable pain signal, log "Insufficient Intel" and abort. Never guess. Never hallucinate context.
- **DNC is absolute**: If the prospect appears in the DNC list (user-level or global), abort immediately. Log only to the internal run log — not to the prospect record.
- **Consent gate**: If `consent_granted` is False, drop the event entirely. Never transmit any data about this prospect to third parties (HubSpot, Meta, Calendly).
- **Circuit breaker**: If the circuit breaker is open, do not run. Alert the orchestrator. Wait for explicit operator `reset_circuit()` call.
- **No hardcoded tokens**: Tokens are always retrieved from the encrypted credential store. Never hardcoded. Never logged.
- **Human approval required**: Outreach is never sent automatically. All prospects require a human click in the `/batch-confirm` or `/approve` UI.
- **No external API calls from pods**: All calls to HubSpot, Meta, Calendly route through `EventDispatcher.dispatch()` only.

## Quality Standards — Financial Advisor Specific
A qualifying prospect must meet ALL of the following:

- **Decision-maker signal**: Post indicates they control their own book of business (not an employee advisor at a wire house). Language like "my practice", "my clients", "my AUM", "independent", "my firm" are positive signals.
- **Clear acquisition pain**: Post must contain a specific pain signal about client acquisition, referral pipeline, lead generation, organic growth, or AUM growth plateau. Vague frustration without a specific pain is not enough.
- **ICP score threshold**: Minimum 4/10 (configurable via `MIN_ICP_SCORE` env var).
- **No wire house flags**: Mentions of Merrill, Morgan Stanley, UBS, Wells Fargo Advisors, Edward Jones, Raymond James (as employer) = disqualify.
- **Actionable**: There must be a plausible hook for outreach — a question, a complaint, a request for advice, or a declared goal.

## Abort Conditions
Stop running and alert the orchestrator if:
- HUBSPOT_TOKEN is invalid (HubSpot returns 401)
- ANTHROPIC_API_KEY has no quota (returns 429 or 402)
- APIFY_API_TOKEN is invalid or rate-limited (403/429)
- Database is unreachable for 3 consecutive queries
- Zero prospects found across 3 consecutive daily scans (possible rate limit, scraper breakage, or signal phrase mismatch)
- bootstrap.validate() fails on any required env var or pod file

## Escalation
When an abort condition triggers:
1. Log to `notifications` table with severity=CRITICAL
2. Trip the circuit breaker (pod stops running)
3. Surface in the Admin tab as a red notification
4. Do not retry until operator calls `reset_circuit()`

## SEC/FINRA Compliance Notes
- Never make performance claims in drafted outreach ("we'll grow your AUM by X%")
- Never promise specific outcomes or guarantees
- Outreach is introductory only — no investment advice content
- Do not contact prospects whose posts suggest they are actively regulated (e.g., under FINRA investigation, recent disciplinary action)
