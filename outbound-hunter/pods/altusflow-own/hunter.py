"""
pods/altusflow-own/hunter.py
AltusFlowOwnHunter — prospects for AltusFlow itself across all 5 target niches.

Key differences from client pods:
  - Checks HubSpot before qualifying (abort if already a contact)
  - Stricter confidence threshold: 9.5 (auto-approve threshold, not ICP score)
  - Combined signal phrases from all 5 niches
  - Messages represent AltusFlow brand — higher quality bar
  - Min ICP score to qualify: 8 (vs 4 for other pods)
  - client_id = 'ALT00' on all HubSpot pushes
"""

import os
import sys
import json

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.BaseHunter import BaseHunter

# ── AltusFlow own-prospecting constants ───────────────────────────────────────
CONFIDENCE_THRESHOLD_AUTO_APPROVE = 9.5
MIN_ICP_SCORE                     = 8

# ── Combined signal phrases from all 5 niches ─────────────────────────────────
_FA_SIGNALS = [
    "pipeline dried up financial advisor",
    "how do financial advisors get clients",
    "struggling to find qualified clients advisor",
    "lead gen for financial advisors",
    "growing my advisory practice",
    "aum not growing",
    "book of business not growing",
    "prospecting as an advisor",
    "referrals drying up advisor",
    "independent ria growth",
]

_COACH_SIGNALS = [
    "how do coaches get clients",
    "coaching business lead generation",
    "struggling to fill my coaching calendar",
    "my coaching program is not selling",
    "how to market my coaching business",
    "coach lead gen",
    "coaching revenue stuck",
]

_RECRUITER_SIGNALS = [
    "how do recruiters get more clients",
    "recruitment agency business development",
    "struggling with bd as a recruiter",
    "growing my staffing agency",
    "how to get retainer clients recruiter",
    "recruiter outbound strategy",
]

_CRE_SIGNALS = [
    "cre lead generation",
    "how do commercial real estate brokers get clients",
    "deal flow slow commercial real estate",
    "cre business development",
    "commercial real estate marketing",
    "how to get more listings",
    "commercial broker lead gen",
]

_MSP_SIGNALS = [
    "how do msps get clients",
    "msp lead generation",
    "growing my managed services business",
    "msp marketing strategy",
    "outbound for msps",
    "msp bd help",
    "how to grow an msp",
]

_ALL_SIGNAL_PHRASES = (
    _FA_SIGNALS + _COACH_SIGNALS + _RECRUITER_SIGNALS +
    _CRE_SIGNALS + _MSP_SIGNALS
)

# ── Target niche identifiers (prospect MUST be in one of these) ───────────────
_TARGET_NICHE_TITLES = [
    # Financial advisors
    "financial advisor", "ria", "wealth manager", "financial planner", "cfp",
    # Business coaches
    "business coach", "executive coach", "life coach", "leadership coach",
    # Recruiters
    "recruiter", "staffing", "talent acquisition", "headhunter",
    # CRE
    "commercial real estate", "cre broker", "real estate broker", "commercial broker",
    # MSPs
    "managed services", "msp", "it services", "it company",
]

# ── Competitor / wrong audience markers ──────────────────────────────────────
_COMPETITOR_SIGNALS = [
    "marketing agency",
    "digital marketing agency",
    "lead generation agency",
    "outbound agency",
    "demand generation agency",
    "growth agency",
    "sales development",
    "sdr agency",
]


class AltusFlowOwnHunter(BaseHunter):
    """
    AltusFlow's own prospecting pod — finds clients across all five target niches.

    Stricter than client pods:
      - HubSpot check before qualify (abort if already a contact)
      - Min ICP score 8 (not 4)
      - Auto-approve confidence threshold 9.5 (not 9.0)
      - Messages represent AltusFlow brand — not a client
    """

    POD_SLUG  = "altusflow-own"
    POD_LABEL = "AltusFlow Own Prospecting"

    def __init__(self, run_id=None, user_id=None, pod_config=None):
        config = pod_config or {
            "slug":    self.POD_SLUG,
            "label":   self.POD_LABEL,
            "user_id": user_id or "ALT00",
            "run_id":  run_id,
        }
        super().__init__(config)

        from scrapers.niches import get_niche
        self._niche = get_niche(self.POD_SLUG)
        if not self._niche:
            raise RuntimeError(f"Niche module '{self.POD_SLUG}' not found in scrapers.niches registry.")

    # ── scan() — all platforms, LinkedIn primary ──────────────────────────────

    def scan(self) -> list:
        """LinkedIn primary, then Facebook, then Reddit."""
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

        self._log(f"scan complete — {len(raw)} raw prospects for AltusFlow own pipeline")
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

    # ── qualify() — HubSpot check + strict threshold + niche gate ────────────

    def qualify(self, prospect: dict) -> tuple:
        """
        Enforces AltusFlow's own prospecting rules:
          1. Abort if already in HubSpot
          2. Abort if not in a target niche
          3. Abort if competitor/agency
          4. Delegate scoring with min threshold of 8
        """
        post_text = (prospect.get("post_text") or "").lower()
        title     = (prospect.get("title") or "").lower()
        bio       = (prospect.get("name")     or "").lower()

        # 1. HubSpot existing contact check (fail open — don't block on network errors)
        if self._is_in_hubspot(prospect):
            return (0, "Already in HubSpot CRM — skip to avoid duplicate outreach")

        # 2. Must be in one of the 5 target niches
        in_target_niche = any(s in title or s in bio for s in _TARGET_NICHE_TITLES)
        niche_signal    = any(phrase in post_text for phrase in _ALL_SIGNAL_PHRASES)
        if not in_target_niche and not niche_signal:
            return (0, "Not in a target niche — AltusFlow only prospects in 5 defined verticals")

        # 3. Abort if competitor (marketing agency, lead gen agency, etc.)
        if any(s in title or s in bio or s in post_text for s in _COMPETITOR_SIGNALS):
            return (0, "Competitor / marketing agency — out of scope for AltusFlow own prospecting")

        # 4. Score with standard scorer, then apply strict threshold
        from qualify import score_prospect
        score, notes = score_prospect(prospect, niche_module=self._niche)

        if score < MIN_ICP_SCORE:
            return (0, f"Score {score} below AltusFlow own-prospecting threshold ({MIN_ICP_SCORE})")

        # Tag for HubSpot push with AltusFlow's own client_id
        prospect["client_id"] = "ALT00"

        return score, notes

    def _is_in_hubspot(self, prospect: dict) -> bool:
        """
        Search HubSpot for an existing contact matching this prospect.
        Returns False (fail open) if HubSpot is unavailable.
        """
        name   = prospect.get("name", "")
        handle = prospect.get("handle", "")
        if not (name or handle):
            return False

        try:
            # Get token from encrypted store, fall back to env var
            token = ""
            try:
                from budget import get_connection_token
                from auth import decrypt_token
                enc   = get_connection_token("hubspot")
                token = decrypt_token(enc) if enc else ""
            except Exception:
                pass
            if not token:
                token = os.environ.get("HUBSPOT_TOKEN", "")
            if not token:
                return False

            # Search by first name token
            search_term = (name.split()[0] if name else handle)[:50]
            body = json.dumps({
                "filterGroups": [{
                    "filters": [{
                        "propertyName": "firstname",
                        "operator":     "CONTAINS_TOKEN",
                        "value":        search_term,
                    }]
                }],
                "limit": 1,
            }).encode()

            import urllib.request as _ur
            req = _ur.Request(
                "https://api.hubapi.com/crm/v3/objects/contacts/search",
                data=body,
                headers={
                    "Authorization":  f"Bearer {token}",
                    "Content-Type":   "application/json",
                },
                method="POST",
            )
            with _ur.urlopen(req, timeout=5) as r:
                data = json.loads(r.read())
                return int(data.get("total", 0)) > 0

        except Exception as e:
            self._log(f"HubSpot existence check failed (fail open): {e}", level="warning")
            return False  # Fail open — don't block on network error

    def inject_niche_context(self, prospect: dict) -> dict:
        prospect["_niche_label"]       = "AltusFlow Target Niche"
        prospect["_deal_economics"]    = "AltusFlow retainer = $2,000–$5,000/month"
        prospect["_common_objections"] = "We already have a marketing agency"
        prospect["_brand_voice"]       = (
            "Direct, specific, referencing their exact post. "
            "Represents Austin at AltusFlow.ai. Never sounds automated. "
            "Never mention that you found them via AI or a scanner. "
            "Sound like a human who genuinely read their post."
        )
        return prospect

    def strip_niche_context(self, prospect: dict) -> dict:
        for k in ("_niche_label", "_deal_economics", "_common_objections", "_brand_voice"):
            prospect.pop(k, None)
        return prospect
