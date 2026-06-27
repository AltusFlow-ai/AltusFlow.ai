"""
pods/commercial-real-estate/hunter.py
CREHunter — scans for commercial real estate brokers (AltusFlow prospects)
and business owners/investors with real estate transaction needs.

Key abort conditions:
  - Residential real estate language → abort
  - Apartment hunting / home buying → abort
  - Single-family language with no commercial context → abort

Key behaviour:
  - Tags each qualified prospect with prospect_type:
      'cre_broker'            — BD pain (AltusFlow direct prospect)
      'transaction_prospect'  — real estate transaction need (prospect for broker client)
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.BaseHunter import BaseHunter

# ── Residential abort signals ─────────────────────────────────────────────────
_RESIDENTIAL_PHRASES = [
    "looking for an apartment",
    "apartment hunting",
    "renting a house",
    "first home",
    "home buyer",
    "buy a house",
    "home purchase",
    "single family home",
    "single-family",
    "residential real estate",
    "my condo",
    "my apartment",
    "looking for a rental",
    "landlord issues",
    "rent is too high",
]

# ── Commercial context salvage keywords (prevent false residential aborts) ────
_COMMERCIAL_SALVAGE = [
    "commercial", "office space", "retail", "industrial", "warehouse",
    "multifamily", "mixed-use", "nnn", "triple net", "cap rate",
    "1031", "sale-leaseback", "tenant improvement", "ground lease",
]

# ── CRE broker BD signals (AltusFlow direct prospect) ────────────────────────
_BROKER_SIGNALS = [
    "deal flow is slow",
    "how are brokers generating leads",
    "cre business development",
    "commercial real estate marketing",
    "how do you get new listings",
    "losing deals to other brokers",
    "growing my brokerage",
    "need more listing leads",
    "commercial broker lead generation",
    "struggling to find buyers",
    "cre broker prospecting",
    "bd for commercial real estate",
]

# ── Transaction prospect signals (need space / doing a deal) ─────────────────
_TRANSACTION_SIGNALS = [
    "lease is up",
    "lease expiring",
    "1031 exchange",
    "downsizing our office",
    "looking at our first commercial property",
    "sale-leaseback",
    "need more space for our business",
    "office lease expiring",
    "looking to buy commercial property",
    "commercial space recommendations",
    "need a warehouse",
    "need office space",
    "expanding our operations",
    "need industrial space",
    "retail space for our business",
]


class CREHunter(BaseHunter):
    """
    Niche pod for the Commercial Real Estate Brokers vertical.

    Two prospect types:
      cre_broker           — brokers with deal-flow/BD pain (AltusFlow prospects)
      transaction_prospect — businesses with real estate transaction needs
    """

    POD_SLUG  = "commercial-real-estate"
    POD_LABEL = "Commercial Real Estate Brokers"

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
            raise RuntimeError(f"Niche module '{self.POD_SLUG}' not found in scrapers.niches registry.")

    # ── scan() — LinkedIn primary, Facebook + Reddit secondary ───────────────

    def scan(self) -> list:
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

        self._log(f"scan complete — {len(raw)} raw prospects")
        return raw

    def _scan_linkedin(self, max_per_query: int) -> list:
        try:
            from scrapers.linkedin import run_niche_search
            return run_niche_search(self.POD_SLUG, max_per_query=max_per_query, run_id=self.run_id)
        except Exception as e:
            self._log(f"LinkedIn scan failed: {e}", level="warning")
            return []

    def _scan_facebook(self) -> list:
        try:
            from scrapers.facebook import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Facebook scan failed: {e}", level="warning")
            return []

    def _scan_reddit(self) -> list:
        try:
            from scrapers.reddit import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Reddit scan failed: {e}", level="warning")
            return []

    # ── qualify() — residential abort + prospect_type tagging ────────────────

    def qualify(self, prospect: dict) -> tuple:
        """
        Abort on residential real estate content.
        Tag each passing prospect with prospect_type before scoring.
        """
        post_text = (prospect.get("post_text") or "").lower()
        title     = (prospect.get("title") or "").lower()

        # Check for residential language — with commercial salvage check
        residential_hits = [p for p in _RESIDENTIAL_PHRASES if p in post_text]
        if residential_hits:
            # See if there's enough commercial context to salvage
            commercial_hits = sum(1 for s in _COMMERCIAL_SALVAGE if s in post_text)
            if commercial_hits < 2:
                return (0, f"Residential real estate content ({residential_hits[0]!r}) — out of scope")

        # Tag prospect_type
        broker_hits  = sum(1 for p in _BROKER_SIGNALS      if p in post_text)
        tx_hits      = sum(1 for p in _TRANSACTION_SIGNALS  if p in post_text)

        broker_title_signals = ["cre broker", "commercial broker", "commercial real estate agent",
                                  "investment sales", "leasing agent", "tenant rep"]
        broker_title_hits = sum(1 for s in broker_title_signals if s in title)

        prospect["prospect_type"] = (
            "cre_broker" if (broker_hits + broker_title_hits) >= tx_hits
            else "transaction_prospect"
        )

        from qualify import score_prospect
        return score_prospect(prospect, niche_module=self._niche)

    def inject_niche_context(self, prospect: dict) -> dict:
        ptype = prospect.get("prospect_type", "transaction_prospect")
        prospect["_niche_label"]       = getattr(self._niche, "NICHE_LABEL", self.POD_LABEL)
        prospect["_deal_economics"]    = getattr(self._niche, "DEAL_ECONOMICS",
                                                  "Transaction commission = $20k–$200k" if ptype == "transaction_prospect"
                                                  else "Outbound retainer = $2k–$5k/month")
        prospect["_common_objections"] = getattr(self._niche, "COMMON_OBJECTIONS",
                                                  "I have an existing broker relationship")
        return prospect

    def strip_niche_context(self, prospect: dict) -> dict:
        for k in ("_niche_label", "_deal_economics", "_common_objections"):
            prospect.pop(k, None)
        return prospect
