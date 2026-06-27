# Decision-Making Heuristics — Options Trading Pod

## Non-Negotiable Rules
- **Insufficient Intel**: If no clear options-specific pain point (no mention of Greeks, strategy, or specific loss event), log "Insufficient Intel" and abort.
- **DNC is absolute**: Abort immediately if on Do Not Contact list.
- **Consent gate**: Drop event if `consent_granted` is False.
- **Circuit breaker**: Do not run if open.
- **Human approval required**: Never auto-send.
- **No direct CRM calls**: All external calls via EventDispatcher.

## Quality Standards
A good options prospect:
- Posts about a specific options loss or confusion (not just "I lost money")
- Uses options vocabulary: strike, expiry, IV, Greeks, premium, spread, assignment
- Is a retail trader (not a market maker, fund, or registered advisor)
- Has: handle + platform + post_text with options-specific signal
- NOT asking for specific trade recommendations (compliance risk)
- ICP score threshold: 4/10 minimum

## Signal Priority (two sub-segments to capture)

**Theta/Income traders (higher LTV):**
1. Wheel strategy not working as expected
2. Assignment confusion (covered calls, CSPs)
3. Managing losers on credit spreads
4. Iron condor blowout during vol spike

**Retail degens (high volume, lower LTV):**
1. 0DTE account blowup
2. IV crush destroyed an earnings play
3. Bought calls/puts that expired worthless repeatedly
4. Asks "why do I always buy tops?"

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
