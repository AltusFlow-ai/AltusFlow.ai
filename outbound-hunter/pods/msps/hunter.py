"""
pods/msps/hunter.py
MSPHunter — scans for business owners with IT pain (prospects for MSP clients)
and MSP owners with BD struggles (AltusFlow direct prospects).

Key abort conditions:
  - IT professional posting (not a business owner) → abort
  - Software development / coding post → abort
  - IT staff job listing → abort

Key behaviour:
  - Tags prospect_type: 'msp_owner' | 'sme_prospect'
  - Security incidents (ransomware, breach) flagged as is_urgent=True
  - Reddit is the primary signal source — highest volume, most candid
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.BaseHunter import BaseHunter

# ── IT professional title abort signals ──────────────────────────────────────
_IT_PROFESSIONAL_TITLES = [
    "software engineer",
    "software developer",
    "sysadmin",
    "system administrator",
    "systems administrator",
    "devops engineer",
    "site reliability engineer",
    "sre",
    "network engineer",
    "it engineer",
    "it technician",
    "helpdesk technician",
    "it support specialist",
    "security engineer",
    "cloud architect",
    "database administrator",
    "dba",
    "programmer",
    "developer",
    "data engineer",
    "machine learning engineer",
]

# ── Coding/dev content abort signals ─────────────────────────────────────────
_CODING_PHRASES = [
    "pull request",
    "git commit",
    "stack overflow",
    "debugging my code",
    "python script",
    "api endpoint",
    "rest api",
    "kubernetes",
    "docker container",
    "my github",
    "open source project",
    "javascript framework",
]

# ── IT job listing abort signals ──────────────────────────────────────────────
_IT_JOB_LISTING = [
    "hiring it staff",
    "looking for a sysadmin",
    "senior software engineer wanted",
    "it position available",
    "job opening it",
    "junior developer needed",
]

# ── Security incident signals (urgent — prioritise these) ─────────────────────
_SECURITY_SIGNALS = [
    "ransomware",
    "data breach",
    "got hacked",
    "phishing attack",
    "cybersecurity incident",
    "malware",
    "our systems were compromised",
    "crypto locker",
    "ransom demand",
]

# ── SME prospect signals (IT pain — client of MSP) ───────────────────────────
_SME_SIGNALS = [
    "our it support is terrible",
    "looking for a better managed services provider",
    "tired of surprise it bills",
    "it company ghosted us",
    "current it guy is leaving",
    "anyone recommend a good msp",
    "managed services provider recommendations",
    "it support nightmare",
    "cybersecurity help",
    "our systems keep going down",
    "it problems",
    "unreliable it support",
    "frustrated with our msp",
    "need a new it provider",
    "it costs out of control",
]

# ── MSP owner BD signals (AltusFlow direct prospect) ─────────────────────────
_MSP_OWNER_SIGNALS = [
    "how do msps get new clients",
    "struggling with outbound msp",
    "need to grow beyond referrals msp",
    "lost another rfp",
    "msp business development",
    "how to market managed services",
    "msp lead generation",
    "growing my msp",
    "client acquisition msp",
    "msp marketing strategy",
    "how do i get more msp clients",
    "outbound for managed services",
]


class MSPHunter(BaseHunter):
    """
    Niche pod for IT Managed Service Providers.

    Reddit is the primary signal source (highest volume of unguarded SME pain).
    Two prospect types:
      sme_prospect — business owners with IT pain (prospects for MSP clients)
      msp_owner    — MSP owners with BD pain (AltusFlow direct prospects)
    Security incidents are flagged as urgent for immediate review.
    """

    POD_SLUG  = "msps"
    POD_LABEL = "IT Managed Service Providers"

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

    # ── scan() — Reddit primary for this niche ────────────────────────────────

    def scan(self) -> list:
        """Reddit first (highest signal for IT pain), LinkedIn second, Facebook third."""
        if self.cost_save_mode:
            self._log("Cost Save Mode active — Reddit only (free). Skipping LinkedIn and Facebook.")
            return self._scan_reddit()

        weights  = self._niche.PLATFORM_WEIGHT
        base_max = int(os.environ.get("MAX_PER_PLATFORM", "15"))
        raw      = []

        if weights.get("reddit", 0) > 0:
            raw.extend(self._scan_reddit())

        if weights.get("linkedin", 0) > 0:
            li_max = max(5, int(base_max * weights["linkedin"] / 0.5))
            raw.extend(self._scan_linkedin(li_max))

        if weights.get("facebook", 0) > 0:
            raw.extend(self._scan_facebook())

        self._log(f"scan complete — {len(raw)} raw prospects")
        return raw

    def _scan_reddit(self) -> list:
        self._log("Reddit scan (primary)...")
        try:
            from scrapers.reddit import run_niche_search
            return run_niche_search(self.POD_SLUG, run_id=self.run_id)
        except Exception as e:
            self._log(f"Reddit scan failed: {e}", level="warning")
            return []

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

    # ── qualify() — IT professional abort + urgency flagging + type tagging ──

    def qualify(self, prospect: dict) -> tuple:
        """
        Abort on IT professional posts, coding content, IT job listings.
        Flag security incidents as urgent. Tag prospect_type.
        """
        post_text = (prospect.get("post_text") or "").lower()
        title     = (prospect.get("title") or "").lower()

        # Abort: IT professional in title (not a business owner)
        if any(t in title for t in _IT_PROFESSIONAL_TITLES):
            return (0, "IT professional in title — looking for business owners, not IT staff")

        # Abort: coding/dev content (wrong community)
        if any(phrase in post_text for phrase in _CODING_PHRASES):
            return (0, "Coding/development content — out of scope for MSP niche")

        # Abort: IT staff job listing
        if any(phrase in post_text for phrase in _IT_JOB_LISTING):
            return (0, "IT job listing — out of scope")

        # Flag security incidents as urgent
        if any(s in post_text for s in _SECURITY_SIGNALS):
            prospect["is_urgent"]   = True
            prospect["signal_type"] = "security_incident"
            self._log(f"URGENT: security incident signal in post from {prospect.get('handle', '?')}")

        # Tag prospect_type
        msp_owner_hits = sum(1 for p in _MSP_OWNER_SIGNALS if p in post_text)
        prospect["prospect_type"] = "msp_owner" if msp_owner_hits > 0 else "sme_prospect"

        from qualify import score_prospect
        score, notes = score_prospect(prospect, niche_module=self._niche)

        # Boost urgent security incidents (they need help NOW)
        if prospect.get("is_urgent") and score >= 4:
            score = min(score + 2, 10)
            notes = (notes or "") + " [URGENT: security incident — prioritise review]"

        return score, notes

    def inject_niche_context(self, prospect: dict) -> dict:
        ptype = prospect.get("prospect_type", "sme_prospect")
        prospect["_niche_label"]       = getattr(self._niche, "NICHE_LABEL", self.POD_LABEL)
        prospect["_deal_economics"]    = getattr(self._niche, "DEAL_ECONOMICS",
                                                  "MSP contract = $2k–$15k/month recurring" if ptype == "sme_prospect"
                                                  else "Outbound retainer = $2k–$5k/month")
        prospect["_common_objections"] = getattr(self._niche, "COMMON_OBJECTIONS",
                                                  "Our current IT company has been with us for years")
        return prospect

    def strip_niche_context(self, prospect: dict) -> dict:
        for k in ("_niche_label", "_deal_economics", "_common_objections"):
            prospect.pop(k, None)
        return prospect
