# Decision-Making Heuristics — Futures Trading Pod

## Non-Negotiable Rules
- **Insufficient Intel**: If no clear pain point (< 20 chars or no futures signal), log "Insufficient Intel" and abort.
- **DNC is absolute**: Abort immediately if on Do Not Contact list.
- **Consent gate**: Drop event if `consent_granted` is False.
- **Circuit breaker**: Do not run if open. Wait for operator reset.
- **Human approval required**: Never auto-send outreach.
- **No direct CRM calls**: All external calls via EventDispatcher.

## Quality Standards
A good futures prospect:
- Posts about a specific futures instrument (ES, NQ, MNQ, crude, gold)
- Mentions a concrete pain: prop eval fail, stopped out on key level, account blowup
- Is a retail trader (not a CTA, fund, or vendor)
- Has at least: handle + platform + post_text with signal
- NOT posting to sell signals, promote a room, or recruit affiliates
- ICP score threshold: 4/10 minimum

## Signal Priority
1. Failed prop firm evaluation (FTMO, TopStep, Apex, etc.)
2. Account liquidation or margin call in futures
3. Asks specifically for futures mentor/coach
4. Describes being "wicked out" or "stopped out on every entry"
5. Expresses confusion about ES/NQ behavior, FOMC, or news events

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
