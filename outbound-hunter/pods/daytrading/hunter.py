"""
pods/daytrading/hunter.py
DaytradingHunter — scanning for day traders posting pain signals.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.BaseHunter import BaseHunter


class DaytradingHunter(BaseHunter):
    """
    Niche pod for the Day Trading vertical.
    Scans Reddit and X for traders posting about consistency struggles,
    blown accounts, and emotional trading — then routes them through the pipeline.
    Platform weights: Reddit 0.50  Twitter 0.30  LinkedIn 0.10  Facebook 0.10
    """

    POD_SLUG  = "daytrading"
    POD_LABEL = "Day Trading"

    def __init__(self, run_id=None, user_id=None, pod_config=None):
        config = pod_config or {
            "slug":    self.POD_SLUG,
            "label":   self.POD_LABEL,
            "user_id": user_id,
            "run_id":  run_id,
        }
        super().__init__(config)

        from scrapers.niches import get_niche
        self._niche = get_niche(self.POD_SLUG)
        if not self._niche:
            raise RuntimeError(
                f"Niche module '{self.POD_SLUG}' not found in scrapers.niches registry."
            )

    def scan(self) -> list:
        if self.cost_save_mode:
            self._log("Cost Save Mode — Reddit only.")
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
        if weights.get("twitter", 0) > 0:
            raw.extend(self._scan_twitter())

        self._log(f"scan complete — {len(raw)} raw prospects")
        return raw

    def _scan_linkedin(self, max_per_query: int) -> list:
        try:
            from scrapers.linkedin import run_niche_search
            return run_niche_search(self.POD_SLUG, max_per_query=max_per_query, run_id=self.run_id)
        except Exception as e:
            self._log(f"LinkedIn scraper failed: {e}", level="warning")
            return []

    def _scan_facebook(self) -> list:
        try:
            from scrapers.facebook import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Facebook scraper failed: {e}", level="warning")
            return []

    def _scan_twitter(self) -> list:
        try:
            from scrapers.twitter import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Twitter scraper failed: {e}", level="warning")
            return []

    def _scan_reddit(self) -> list:
        try:
            from scrapers.reddit import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Reddit scraper failed: {e}", level="warning")
            return []

    def qualify(self, prospect: dict) -> tuple:
        from qualify import score_prospect
        return score_prospect(prospect, niche_module=self._niche)

    def inject_niche_context(self, prospect: dict) -> dict:
        prospect["_niche_label"]       = getattr(self._niche, "NICHE_LABEL", self.POD_LABEL)
        prospect["_deal_economics"]    = getattr(self._niche, "DEAL_ECONOMICS", "")
        prospect["_common_objections"] = getattr(self._niche, "COMMON_OBJECTIONS", "")
        return prospect

    def strip_niche_context(self, prospect: dict) -> dict:
        for k in ("_niche_label", "_deal_economics", "_common_objections"):
            prospect.pop(k, None)
        return prospect
