# Decision-Making Heuristics — Swing Trading Pod

## Non-Negotiable Rules
- **Insufficient Intel**: If no swing-specific pain point (breakout, overnight, position sizing), log "Insufficient Intel" and abort.
- **DNC is absolute**: Abort immediately if on Do Not Contact list.
- **Consent gate**: Drop event if `consent_granted` is False.
- **Circuit breaker**: Do not run if open.
- **Human approval required**: Never auto-send.
- **No direct CRM calls**: All external calls via EventDispatcher.

## Quality Standards
A good swing trading prospect:
- Posts about holding positions overnight or multi-day with specific problems
- Mentions breakout failures, earnings risk, sector rotation confusion, or trailing stops
- Is a retail part-time trader (has a job, trades on the side)
- Has: handle + platform + actionable signal phrase
- NOT day trading / scalping (different pod), NOT investing long-term
- ICP score threshold: 4/10 minimum

## Signal Priority
1. Describes a specific failed breakout trade with dollar context
2. Asks about managing overnight risk or gap-down scenarios
3. Mentions buying breakouts that immediately reverse
4. Reports inconsistency despite having a "system"
5. Asks for swing setup screeners or mentor

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
