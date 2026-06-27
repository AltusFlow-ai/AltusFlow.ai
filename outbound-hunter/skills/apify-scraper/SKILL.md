---
name: apify-scraper
version: 1.0.0
description: Fetch structured prospect intelligence from LinkedIn, Facebook Groups, and Reddit via Apify actors
author: AltusFlow
tools:
  - http_request
  - file_write
  - wait
permissions:
  - network
inputs:
  - name: platform
    type: string
    enum: [linkedin, facebook, reddit]
    required: true
  - name: query
    type: string
    required: true
  - name: niche_slug
    type: string
    required: true
  - name: max_results
    type: integer
    default: 20
outputs:
  - name: prospects
    type: array
    description: Array of prospect objects with post_text, handle, profile_url, post_date
  - name: run_cost
    type: float
    description: Apify compute cost in USD for budget logging
  - name: insufficient_intel_count
    type: integer
    description: Number of results dropped due to no clear pain point
---

# Apify Scraper Skill

## Purpose
Fetch social media posts matching niche signal phrases using Apify actors.
Results must contain a clear pain point to proceed — never hallucinate missing context.

## Critical Rules
- If a result contains no clear pain point: increment insufficient_intel_count, skip result
- Never pass a result to the drafter if post_text is empty or under 20 characters
- Always retrieve run_cost after actor completion for budget logging
- Rate limit: max 10 actor runs per hour per platform

## Actors Used
- LinkedIn: apify/linkedin-post-search-scraper
- Facebook Groups: apify/facebook-groups-scraper
- Reddit: Use PRAW directly (free API) — do not use Apify for Reddit

## Input Validation
Before running any actor:
1. Confirm APIFY_API_TOKEN exists in encrypted store
2. Confirm niche_slug matches an active pod
3. Confirm platform is in allowed_tools for this pod

## Output Contract
Every result must have:
- post_text: string (non-empty, min 20 chars)
- handle: string
- profile_url: string
- post_date: ISO8601 string
- platform: string
- signal_phrase: string (which phrase triggered this result)
- niche_slug: string

If any required field is missing: drop the result, log as insufficient_intel.

## Error Handling
- Actor timeout (>180s): log critical error, return empty array, do not retry immediately
- HTTP 429 rate limit: wait 60s, retry once, then log warning and return empty array
- HTTP 401 invalid token: log critical error, alert admin, do not retry
- Any other error: log with suggested_fix, return empty array

## Budget Logging
After every actor run call:
```
GET https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_TOKEN}
```
Extract: `stats.computeUnits` → multiply by $0.25 to get USD cost.
Pass cost to EventDispatcher for budget_transactions logging.
