"""
main.py
Outbound Hunter — 5-niche parallel pipeline orchestrator.

Each niche runs as an independent agent in a thread:
  1. Load niche library (queries, signal phrases, platform weights)
  2. Check niche-level pause state — skip if paused
  3. Run scrapers weighted by PLATFORM_WEIGHT
  4. Registry check — skip handles in 90-day cooldown (before scoring)
  5. ICP scoring (qualify.py)
  6. Dedup against DB
  7. Draft with Claude API — niche context injected into prompt
  8. Insert — niche_segment mandatory, reject if missing
  9. Add to global registry (cooldown starts now)
 10. Route (auto_router) — auto_approved / pending / auto_skipped
 11. Log platform stats

All 5 niche agents run concurrently via ThreadPoolExecutor. No asyncio.

Usage:
    python main.py                      # all active niches
    python main.py --niche msps         # single niche only
    python main.py --draft-only         # re-draft pending prospects missing messages
"""

import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dotenv import load_dotenv

load_dotenv()

from database import (
    init_db, insert_prospect, prospect_exists, log_search_run,
    start_scan_run, complete_scan_run, get_pending, update_status,
    check_registry, add_to_registry, is_niche_paused, log_platform_stat,
    CLIENT_ID,
)
from qualify      import filter_by_min_score
from drafter      import draft_batch
from auto_router  import route_batch
from error_logger import log_pipeline_error, CRITICAL, WARNING

MIN_ICP_SCORE = int(os.environ.get("MIN_ICP_SCORE", "4"))


# ── Active niche resolution ───────────────────────────────────────────────────

def _get_active_niches():
    """Read ACTIVE_NICHES env var. Returns all niches if blank."""
    from scrapers.niches import get_all_slugs
    raw = os.environ.get("ACTIVE_NICHES", "").strip()
    if raw:
        return [s.strip() for s in raw.split(",") if s.strip()]
    return get_all_slugs()


# ── Per-platform scraper wrappers ─────────────────────────────────────────────

def _run_linkedin_niche(niche_slug, run_id, max_per_query=10):
    if not os.environ.get("APIFY_API_TOKEN"):
        print(f"[{niche_slug}] Apify not configured — Reddit only mode")
        return []
    from scrapers.linkedin import run_niche_search
    print(f"\n[{niche_slug}] LinkedIn search (max {max_per_query}/query)...")
    try:
        return run_niche_search(niche_slug, max_per_query=max_per_query, run_id=run_id)
    except Exception as e:
        log_pipeline_error(
            run_id, "linkedin_scraper",
            f"[{niche_slug}] LinkedIn scraper failed: {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []


def _run_facebook_niche(niche_slug, run_id):
    if not os.environ.get("APIFY_API_TOKEN"):
        return []  # already logged by _run_linkedin_niche
    from scrapers.facebook import run_niche_search
    print(f"\n[{niche_slug}] Facebook search...")
    try:
        return run_niche_search(niche_slug, run_id=run_id)
    except Exception as e:
        log_pipeline_error(
            run_id, "facebook_scraper",
            f"[{niche_slug}] Facebook scraper failed: {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []


def _run_reddit_niche(niche_slug, run_id):
    from scrapers.reddit import run_niche_search
    print(f"\n[{niche_slug}] Reddit search...")
    try:
        return run_niche_search(niche_slug, run_id=run_id)
    except Exception as e:
        log_pipeline_error(
            run_id, "reddit_scraper",
            f"[{niche_slug}] Reddit scraper failed: {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []


def _run_twitter_niche(niche_slug, run_id):
    if not os.environ.get("TWITTER_BEARER_TOKEN"):
        print(f"[{niche_slug}] TWITTER_BEARER_TOKEN not set — X/Twitter skipped")
        return []
    from scrapers.twitter import run_niche_search
    print(f"\n[{niche_slug}] X/Twitter search...")
    try:
        return run_niche_search(niche_slug, run_id=run_id)
    except Exception as e:
        log_pipeline_error(
            run_id, "twitter_scraper",
            f"[{niche_slug}] X/Twitter scraper failed: {type(e).__name__}: {e}",
            CRITICAL,
        )
        return []


# ── Core pipeline ─────────────────────────────────────────────────────────────

def process_prospects(raw_prospects, niche_slug, run_id=None, niche_module=None):
    """
    Qualify, registry-check, dedup, draft, insert, and route a batch.
    niche_slug is mandatory — prospects missing it are logged and rejected.

    Returns (qualified_count, stored_count, routing_counts).
    """
    empty = 0, 0, {}

    if not raw_prospects:
        return empty

    label = niche_slug or "unknown"
    print(f"\n[{label}] {len(raw_prospects)} raw prospects to process...")

    # ── 0. Enforce niche_segment on every record ──────────────────────────────
    valid = []
    for p in raw_prospects:
        p.setdefault("niche_segment", niche_slug)
        p.setdefault("niche", niche_slug)
        if not p.get("niche_segment"):
            log_pipeline_error(
                run_id, "pipeline",
                f"[{label}] Prospect '{p.get('handle','?')}' missing niche_segment — skipped.",
                WARNING,
            )
            continue
        valid.append(p)

    if not valid:
        return empty

    # ── 1. Global registry check (before scoring — avoids wasting Claude calls) ─
    not_in_cooldown = []
    for p in valid:
        if check_registry(p["handle"], p["platform"]):
            print(f"  [{label}] Registry: skipping {p['handle']} (90-day cooldown active)")
        else:
            not_in_cooldown.append(p)

    print(f"[{label}] {len(not_in_cooldown)} not in cooldown (of {len(valid)})")

    if not not_in_cooldown:
        return empty

    # ── 2. ICP scoring ────────────────────────────────────────────────────────
    try:
        qualified = filter_by_min_score(
            not_in_cooldown, min_score=MIN_ICP_SCORE, niche_module=niche_module
        )
    except Exception as e:
        log_pipeline_error(
            run_id, "qualify",
            f"[{label}] ICP scoring crashed: {type(e).__name__}: {e}",
            CRITICAL,
        )
        return empty

    # ── 3. Apply Reddit ICP boosts (post-score adjustment) ───────────────────
    for p in qualified:
        boost = p.pop("_reddit_icp_boost", 0)
        notes = p.pop("_reddit_boost_notes", [])
        if boost:
            p["icp_score"] = min(10, (p.get("icp_score") or 0) + boost)
            if notes:
                extra = " | ".join(notes)
                p["icp_notes"] = (
                    ((p.get("icp_notes") or "") + " | " + extra).strip(" |")
                )

    print(f"[{label}] {len(qualified)} passed ICP >= {MIN_ICP_SCORE}")

    # ── 4. Dedup against DB ───────────────────────────────────────────────────
    new_prospects = []
    for p in qualified:
        try:
            if not prospect_exists(p["handle"], p["platform"]):
                new_prospects.append(p)
            else:
                print(f"  [{label}] Dedup: skipping existing {p['handle']}")
        except Exception as e:
            log_pipeline_error(
                run_id, "database",
                f"[{label}] Dedup check failed for {p.get('handle','?')}: {e}",
                WARNING,
            )

    if not new_prospects:
        log_search_run(label, "all", len(raw_prospects), len(qualified), 0)
        return len(qualified), 0, {}

    # ── 5. Inject niche context for drafter ──────────────────────────────────
    if niche_module:
        for p in new_prospects:
            p["_niche_label"]         = getattr(niche_module, "NICHE_LABEL", label)
            p["_deal_economics"]      = getattr(niche_module, "DEAL_ECONOMICS", "")
            p["_common_objections"]   = getattr(niche_module, "COMMON_OBJECTIONS", "")

    # ── 6. Draft personalised outreach via Claude API ─────────────────────────
    print(f"[{label}] Drafting {len(new_prospects)} messages via Claude API...")
    try:
        drafted = draft_batch(new_prospects)
    except Exception as e:
        log_pipeline_error(
            run_id, "drafter",
            f"[{label}] draft_batch crashed: {type(e).__name__}: {e}",
            CRITICAL,
            suggested_fix=(
                "Verify ANTHROPIC_API_KEY is set and has quota. "
                "Run with --draft-only to retry drafting."
            ),
        )
        drafted = new_prospects  # Store anyway; re-draft later

    # ── 7. Insert to DB + add to global registry ──────────────────────────────
    stored_prospects = []
    for p in drafted:
        # Strip private niche context keys — not persisted
        for k in ("_niche_label", "_deal_economics", "_common_objections"):
            p.pop(k, None)
        try:
            p["id"] = insert_prospect(p)
            add_to_registry(p["handle"], p["platform"], niche_slug)
            stored_prospects.append(p)
            print(f"  [{label}] Stored: {p.get('name','?')} ({p['handle']}) — ICP {p.get('icp_score',0)}/10")
        except Exception as e:
            log_pipeline_error(
                run_id, "database",
                f"[{label}] Failed to insert {p.get('handle','?')}: {type(e).__name__}: {e}",
                WARNING,
            )

    if not stored_prospects:
        log_search_run(label, "all", len(raw_prospects), len(qualified), 0)
        return len(qualified), 0, {}

    # ── 8. AI confidence routing ──────────────────────────────────────────────
    print(f"\n[{label}] Routing {len(stored_prospects)} prospects...")
    try:
        routing_counts = route_batch(stored_prospects, run_id=run_id)
    except Exception as e:
        log_pipeline_error(
            run_id, "auto_router",
            f"[{label}] route_batch crashed: {type(e).__name__}: {e}",
            WARNING,
            suggested_fix=(
                "All prospects kept as 'pending' — no data lost. "
                "Verify ANTHROPIC_API_KEY is valid."
            ),
        )
        routing_counts = {
            "auto_approved": 0,
            "pending":       len(stored_prospects),
            "auto_skipped":  0,
        }

    print(
        f"[{label}] Routing: {routing_counts.get('auto_approved',0)} auto-approved | "
        f"{routing_counts.get('pending',0)} pending | "
        f"{routing_counts.get('auto_skipped',0)} skipped"
    )

    # ── 9. Log stats ──────────────────────────────────────────────────────────
    platform = stored_prospects[0].get("platform", "unknown") if stored_prospects else "unknown"
    avg_icp  = (
        sum(p.get("icp_score") or 0 for p in stored_prospects) / len(stored_prospects)
        if stored_prospects else 0.0
    )
    log_platform_stat(platform, niche_slug, len(raw_prospects), len(qualified), avg_icp)
    log_search_run(label, "all", len(raw_prospects), len(qualified), len(stored_prospects))

    return len(qualified), len(stored_prospects), routing_counts


# ── Niche agent ───────────────────────────────────────────────────────────────

def _run_niche_agent(niche_slug, run_id):
    """
    Full pipeline for one niche. Runs all three platform scrapers weighted by
    PLATFORM_WEIGHT, then processes prospects through the core pipeline.
    Returns result dict: {found, qualified, stored, routing}.
    """
    from scrapers.niches import get_niche

    niche = get_niche(niche_slug)
    if not niche:
        log_pipeline_error(
            run_id, "pipeline",
            f"Unknown niche slug '{niche_slug}' — skipping.",
            WARNING,
        )
        return {"found": 0, "qualified": 0, "stored": 0, "routing": {}}

    if is_niche_paused(niche_slug):
        print(f"\n[{niche_slug}] Niche is paused — skipping.")
        return {"found": 0, "qualified": 0, "stored": 0, "routing": {}}

    print(f"\n{'─'*42}")
    print(f"  NICHE AGENT: {niche_slug}")
    print(f"{'─'*42}")

    weights  = niche.PLATFORM_WEIGHT
    base_max = int(os.environ.get("MAX_PER_PLATFORM", "15"))
    raw      = []

    # Run platforms proportional to PLATFORM_WEIGHT
    # Weight of 0.50 = full base_max; lower weights scale down proportionally
    if weights.get("linkedin", 0) > 0:
        li_max = max(5, int(base_max * weights["linkedin"] / 0.5))
        raw.extend(_run_linkedin_niche(niche_slug, run_id, max_per_query=li_max))

    if weights.get("facebook", 0) > 0:
        raw.extend(_run_facebook_niche(niche_slug, run_id))

    if weights.get("reddit", 0) > 0:
        raw.extend(_run_reddit_niche(niche_slug, run_id))

    if weights.get("twitter", 0) > 0:
        raw.extend(_run_twitter_niche(niche_slug, run_id))

    found = len(raw)
    q, s, routing = process_prospects(raw, niche_slug, run_id=run_id, niche_module=niche)

    print(f"\n[{niche_slug}] Agent done — {found} found | {q} qualified | {s} stored")
    return {"found": found, "qualified": q, "stored": s, "routing": routing}


# ── Draft-only mode ───────────────────────────────────────────────────────────

def _run_draft_only(run_id):
    """Re-draft pending prospects that are missing their outreach message."""
    pending_no_msg = [p for p in get_pending() if not p.get("drafted_message")]
    print(f"Re-drafting {len(pending_no_msg)} pending prospects with no message...")

    if not pending_no_msg:
        print("Nothing to re-draft.")
        complete_scan_run(run_id, found=0, drafted=0, status="complete")
        return

    try:
        drafted = draft_batch(pending_no_msg)
        for p in drafted:
            update_status(p["id"], "pending", p.get("drafted_message", ""))
        print(f"Done. Re-drafted {len(drafted)} messages.")
        complete_scan_run(run_id, found=len(pending_no_msg), drafted=len(drafted), status="complete")
    except Exception as e:
        log_pipeline_error(
            run_id, "drafter",
            f"--draft-only re-draft failed: {type(e).__name__}: {e}",
            CRITICAL,
        )
        complete_scan_run(run_id, found=len(pending_no_msg), drafted=0, status="failed")


# ── Entrypoint ────────────────────────────────────────────────────────────────

def main():
    args       = sys.argv[1:]
    draft_only = "--draft-only" in args

    # --niche <slug> runs a single niche
    niche_flag = None
    if "--niche" in args:
        idx = args.index("--niche")
        if idx + 1 < len(args):
            niche_flag = args[idx + 1]

    print("=" * 42)
    print("  ALTUSFLOW OUTBOUND HUNTER")
    print("=" * 42)

    init_db()
    run_id = start_scan_run(client_id=CLIENT_ID)
    print(f"  Scan run: #{run_id}")

    if draft_only:
        print("  Mode: draft-only")
        print()
        _run_draft_only(run_id)
        return

    niches = [niche_flag] if niche_flag else _get_active_niches()
    print(f"  Mode: {len(niches)} niche agent(s) — {', '.join(niches)}")
    print()

    total_found     = 0
    total_qualified = 0
    total_stored    = 0
    total_routing   = {"auto_approved": 0, "pending": 0, "auto_skipped": 0}

    try:
        with ThreadPoolExecutor(max_workers=min(len(niches), 6)) as executor:
            futures = {
                executor.submit(_run_niche_agent, slug, run_id): slug
                for slug in niches
            }
            for future in as_completed(futures):
                slug = futures[future]
                try:
                    result = future.result()
                    total_found     += result["found"]
                    total_qualified += result["qualified"]
                    total_stored    += result["stored"]
                    for k in total_routing:
                        total_routing[k] += result["routing"].get(k, 0)
                except Exception as e:
                    log_pipeline_error(
                        run_id, "pipeline",
                        f"Niche agent '{slug}' raised unhandled exception: {type(e).__name__}: {e}",
                        CRITICAL,
                    )

        complete_scan_run(
            run_id,
            found=total_found,
            qualified=total_qualified,
            drafted=total_stored,
            status="complete",
        )

    except Exception as e:
        log_pipeline_error(
            run_id, "pipeline",
            f"Orchestrator-level failure: {type(e).__name__}: {e}",
            CRITICAL,
        )
        complete_scan_run(
            run_id,
            found=total_found,
            qualified=total_qualified,
            drafted=total_stored,
            status="failed",
        )

    # ── Summary ───────────────────────────────────────────────────────────────
    print(f"\n{'='*42}")
    print(f"  Run #{run_id} complete.")
    print(f"  Niches scanned:  {', '.join(niches)}")
    print(f"  Raw found:       {total_found}")
    print(f"  Qualified:       {total_qualified}")
    print(f"  Stored:          {total_stored}")
    print(f"  Auto-approved:   {total_routing['auto_approved']}")
    print(f"  Pending review:  {total_routing['pending']}")
    print(f"  Auto-skipped:    {total_routing['auto_skipped']}")
    if total_routing["auto_approved"] > 0:
        print(f"  >> Open /batch-confirm to one-click confirm.")
    if total_routing["pending"] > 0:
        print(f"  >> Open / to review {total_routing['pending']} pending prospect(s).")
    print(f"{'='*42}\n")


if __name__ == "__main__":
    main()
