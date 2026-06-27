"""
pods/business-coaches/hunter.py
BusinessCoachHunter — scans for business owners and entrepreneurs who need coaching.

Key abort conditions enforced in qualify():
  - Post author appears to be a coach seeking clients → "Wrong side of market"
  - Post is about coaching certification → abort
  - Promotional post advertising their own services → abort
  - Revenue signals suggest < $100k/year → low priority, never auto-approve

All scraping and base scoring delegates to existing scrapers/qualify.py.
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.BaseHunter import BaseHunter

# ── Phrases that indicate the post author IS a coach, not a coaching client ──
_WRONG_SIDE_PHRASES = [
    "looking for coaching clients",
    "enrolling new clients",
    "my coaching program",
    "my coaching business",
    "build my coaching practice",
    "attract coaching clients",
    "my 1:1 coaching",
    "opening spots in my program",
    "dm me to work with me",
    "book a discovery call",
    "apply to work with me",
    "spaces available in my program",
]

# ── Phrases indicating the post is about getting coaching credentials ─────────
_CERTIFICATION_PHRASES = [
    "coaching certification",
    "become a coach",
    "icf certification",
    "acc certification",
    "pcc certification",
    "coach training program",
    "getting certified as a coach",
    "life coach certification",
]

# ── Promotional post markers ──────────────────────────────────────────────────
_PROMO_PHRASES = [
    "limited spots",
    "spots available",
    "dms are open",
    "link in bio",
    "free discovery call",
    "swipe up",
    "check out my freebie",
    "grab my free guide",
    "doors are open",
]

# ── Low-revenue / side-hustle markers (flag, don't auto-approve) ─────────────
_LOW_REVENUE_PHRASES = [
    "side hustle",
    "side gig",
    "part-time business",
    "just started my business",
    "brand new business",
    "startup of one",
    "solopreneur just starting",
]


class BusinessCoachHunter(BaseHunter):
    """
    Niche pod for the Business Coaches vertical.

    Scans Facebook Groups, Reddit, and LinkedIn for business owners and
    entrepreneurs posting about coaching needs, revenue plateaus, and
    lead generation struggles.
    """

    POD_SLUG  = "business-coaches"
    POD_LABEL = "Business Coaches and Consultants"

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

    # ── scan() — delegates to existing scrapers ───────────────────────────────

    def scan(self) -> list:
        """
        Facebook Groups first (most candid), then Reddit, then LinkedIn.
        Platform priority mirrors tasks.json: facebook → reddit → linkedin.
        """
        if self.cost_save_mode:
            self._log("Cost Save Mode active — Reddit only (free). Skipping Facebook and LinkedIn.")
            return self._scan_reddit()

        weights  = self._niche.PLATFORM_WEIGHT
        base_max = int(os.environ.get("MAX_PER_PLATFORM", "15"))
        raw      = []

        # Facebook Groups (priority 1 — most candid signal for this niche)
        if weights.get("facebook", 0) > 0:
            raw.extend(self._scan_facebook())

        # Reddit (priority 2 — anonymous = honest pain expression)
        if weights.get("reddit", 0) > 0:
            raw.extend(self._scan_reddit())

        # LinkedIn (priority 3)
        if weights.get("linkedin", 0) > 0:
            li_max = max(5, int(base_max * weights["linkedin"] / 0.5))
            raw.extend(self._scan_linkedin(li_max))

        self._log(f"scan complete — {len(raw)} raw prospects")
        return raw

    def _scan_facebook(self) -> list:
        self._log("Facebook Groups scan...")
        try:
            from scrapers.facebook import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Facebook scan failed: {type(e).__name__}: {e}", level="warning")
            return []

    def _scan_reddit(self) -> list:
        self._log("Reddit scan...")
        try:
            from scrapers.reddit import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Reddit scan failed: {type(e).__name__}: {e}", level="warning")
            return []

    def _scan_linkedin(self, max_per_query: int) -> list:
        self._log(f"LinkedIn scan (max {max_per_query}/query)...")
        try:
            from scrapers.linkedin import run_niche_search
            return run_niche_search(self.POD_SLUG, max_per_query=max_per_query, run_id=self.run_id)
        except Exception as e:
            self._log(f"LinkedIn scan failed: {type(e).__name__}: {e}", level="warning")
            return []

    # ── qualify() — niche-specific abort conditions + delegate ────────────────

    def qualify(self, prospect: dict) -> tuple:
        """
        Enforce business-coaches abort conditions before delegating to the scorer.

        Returns (0, reason_string) on abort.
        Returns (score, notes) from qualify.score_prospect() otherwise.
        """
        post_text = (prospect.get("post_text") or "").lower()
        title     = (prospect.get("title") or "").lower()
        bio       = (prospect.get("name") or "").lower()

        # Abort: author IS a coach selling coaching (wrong side of market)
        if any(phrase in post_text for phrase in _WRONG_SIDE_PHRASES):
            return (0, "Wrong side of market — coach seeking clients, not a client seeking coaching")

        # Secondary check: bio/title suggests they are a coach
        coach_bio_signals = ["business coach", "life coach", "executive coach", "leadership coach",
                             "mindset coach", "success coach", "career coach"]
        if any(s in title or s in bio for s in coach_bio_signals):
            # Only abort if the post is promotional — coaches can also post pain
            if any(phrase in post_text for phrase in _PROMO_PHRASES):
                return (0, "Coach posting promotional content — wrong side of market")

        # Abort: post is about getting coaching credentials
        if any(phrase in post_text for phrase in _CERTIFICATION_PHRASES):
            return (0, "Coaching certification content — out of scope")

        # Abort: pure promotional post (no pain signal)
        promo_hits = sum(1 for p in _PROMO_PHRASES if p in post_text)
        if promo_hits >= 2:
            return (0, "Promotional post — out of scope")

        # Flag low-revenue signals — score and pass through but mark low priority
        if any(phrase in post_text for phrase in _LOW_REVENUE_PHRASES):
            prospect["_low_revenue_flag"] = True

        from qualify import score_prospect
        score, notes = score_prospect(prospect, niche_module=self._niche)

        # Low-revenue prospects: cap score at 7 to prevent auto-approval
        if prospect.get("_low_revenue_flag") and score > 7:
            score = 7
            notes = (notes or "") + " [Low-revenue flag: score capped at 7, manual review required]"

        return score, notes

    def inject_niche_context(self, prospect: dict) -> dict:
        prospect["_niche_label"]       = getattr(self._niche, "NICHE_LABEL", self.POD_LABEL)
        prospect["_deal_economics"]    = getattr(self._niche, "DEAL_ECONOMICS",
                                                  "One coaching engagement = $5,000–$50,000")
        prospect["_common_objections"] = getattr(self._niche, "COMMON_OBJECTIONS",
                                                  "I already tried coaching and it didn't work")
        return prospect

    def strip_niche_context(self, prospect: dict) -> dict:
        for k in ("_niche_label", "_deal_economics", "_common_objections", "_low_revenue_flag"):
            prospect.pop(k, None)
        return prospect
