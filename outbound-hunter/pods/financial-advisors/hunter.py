"""
pods/financial-advisors/hunter.py
FinancialAdvisorHunter — first production pod.

Extends BaseHunter. Delegates ALL scraping to the existing scrapers in
scrapers/linkedin.py, scrapers/facebook.py, scrapers/reddit.py.
Delegates ALL scoring to qualify.py.

No logic is duplicated — existing code remains the source of truth.
This class is a thin coordinator layer, not a rewrite.
"""

import os
import sys

# Ensure outbound-hunter root is on sys.path when this file is run directly
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.BaseHunter import BaseHunter


class FinancialAdvisorHunter(BaseHunter):
    """
    Niche pod for the Financial Advisors vertical.

    Scans LinkedIn, Facebook, and Reddit for wealth management professionals
    posting pain signals about lead generation, pipeline dryup, and client
    acquisition — then qualifies, drafts, and routes them through the pipeline.

    Platform weights (from scrapers/niches/financial_advisors.py):
      LinkedIn: 0.40   Facebook: 0.35   Reddit: 0.25
    """

    POD_SLUG  = "financial-advisors"
    POD_LABEL = "Financial Advisors"

    def __init__(self, run_id=None, user_id=None, pod_config=None):
        """
        Args:
          run_id      — current scan_runs.id (set by caller after start_scan_run)
          user_id     — tenant slug for multi-tenant deployments
          pod_config  — override the default config dict (for orchestrator use)
        """
        config = pod_config or {
            "slug":    self.POD_SLUG,
            "label":   self.POD_LABEL,
            "user_id": user_id,
            "run_id":  run_id,
        }
        super().__init__(config)

        # Load the existing niche module — signal phrases, ICP keywords,
        # platform weights, and deal economics all live in the niche module.
        # Never duplicate this data here.
        from scrapers.niches import get_niche
        self._niche = get_niche(self.POD_SLUG)
        if not self._niche:
            raise RuntimeError(
                f"Niche module '{self.POD_SLUG}' not found in scrapers.niches registry. "
                "Ensure scrapers/niches/financial_advisors.py is present and registered in __init__.py."
            )

    # ── scan() — delegates to existing scrapers ───────────────────────────────

    def scan(self) -> list:
        """
        Scrape all configured platforms for the financial-advisors niche.

        Platform selection and volume are controlled by PLATFORM_WEIGHT in
        scrapers/niches/financial_advisors.py — never hardcoded here.
        Returns a list of raw prospect dicts (not yet scored, deduped, or drafted).
        """
        if self.cost_save_mode:
            self._log("Cost Save Mode active — Reddit only (free). Skipping LinkedIn and Facebook.")
            return self._scan_reddit()

        weights  = self._niche.PLATFORM_WEIGHT
        base_max = int(os.environ.get("MAX_PER_PLATFORM", "15"))
        raw      = []

        if weights.get("linkedin", 0) > 0:
            li_max = max(5, int(base_max * weights["linkedin"] / 0.5))
            raw.extend(self._scan_linkedin(li_max))

        if weights.get("facebook", 0) > 0:
            raw.extend(self._scan_facebook())

        if weights.get("reddit", 0) > 0:
            raw.extend(self._scan_reddit())

        self._log(f"scan complete — {len(raw)} raw prospects from all platforms")
        return raw

    def _scan_linkedin(self, max_per_query: int) -> list:
        self._log(f"LinkedIn scan (max {max_per_query}/query)...")
        try:
            from scrapers.linkedin import run_niche_search
            return run_niche_search(self.POD_SLUG, max_per_query=max_per_query, run_id=self.run_id)
        except Exception as e:
            self._log(f"LinkedIn scraper failed: {type(e).__name__}: {e}", level="warning")
            return []

    def _scan_facebook(self) -> list:
        self._log("Facebook scan...")
        try:
            from scrapers.facebook import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Facebook scraper failed: {type(e).__name__}: {e}", level="warning")
            return []

    def _scan_reddit(self) -> list:
        self._log("Reddit scan...")
        try:
            from scrapers.reddit import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Reddit scraper failed: {type(e).__name__}: {e}", level="warning")
            return []

    # ── qualify() — delegates to existing qualify.py ──────────────────────────

    def qualify(self, prospect: dict) -> tuple:
        """
        Score a single prospect using the niche-aware ICP scorer.
        Delegates to qualify.score_prospect() — no logic duplication.
        Returns (score: int, notes: str).
        """
        from qualify import score_prospect
        return score_prospect(prospect, niche_module=self._niche)

    # ── Niche context for drafter ─────────────────────────────────────────────

    def inject_niche_context(self, prospect: dict) -> dict:
        """
        Inject niche-specific context keys consumed by drafter.draft_message().
        Mirrors main.py process_prospects() step 5.
        """
        prospect["_niche_label"]       = getattr(self._niche, "NICHE_LABEL", self.POD_LABEL)
        prospect["_deal_economics"]    = getattr(self._niche, "DEAL_ECONOMICS", "")
        prospect["_common_objections"] = getattr(self._niche, "COMMON_OBJECTIONS", "")
        return prospect

    def strip_niche_context(self, prospect: dict) -> dict:
        """Strip private context keys before DB insert."""
        for k in ("_niche_label", "_deal_economics", "_common_objections"):
            prospect.pop(k, None)
        return prospect
