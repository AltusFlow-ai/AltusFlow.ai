"""
pods/recruiters/hunter.py
RecruiterHunter — scans for recruitment agency owners (AltusFlow prospects)
and hiring managers posting pain (prospects for recruiter clients).

Key abort conditions:
  - Job seeker posts → abort immediately
  - Job listing posts → abort
  - Layoff/fired language → abort (wrong emotional state for this conversation)

Key behaviour:
  - Tags each qualified prospect with prospect_type:
      'agency_owner'    — BD pain signals (AltusFlow direct prospect)
      'hiring_manager'  — talent acquisition pain (prospect for recruiter client)
  - Agency owner prospects scored higher — primary acquisition target
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.BaseHunter import BaseHunter

# ── Job seeker abort signals ──────────────────────────────────────────────────
_JOB_SEEKER_PHRASES = [
    "looking for a job",
    "open to work",
    "seeking new opportunities",
    "laid off",
    "just got fired",
    "recently let go",
    "resume help",
    "interview tips",
    "job search",
    "need a job",
    "unemployed",
    "open to opportunities",
    "#opentowork",
    "career change help",
    "anyone hiring",
]

# ── Job listing abort signals ─────────────────────────────────────────────────
_JOB_LISTING_PHRASES = [
    "we are hiring",
    "now hiring",
    "job opening",
    "job opportunity",
    "position available",
    "roles available",
    "we have an opening",
    "apply now",
    "send your cv",
    "send your resume",
    "full job description",
]

# ── Layoff/fired language → wrong emotional state ─────────────────────────────
_LAYOFF_PHRASES = [
    "just got laid off",
    "just got fired",
    "company went under",
    "startup folded",
    "just got let go",
    "my company is closing",
]

# ── Agency owner BD signals (AltusFlow direct prospect) ──────────────────────
_AGENCY_OWNER_SIGNALS = [
    "how do recruiters get clients",
    "bd is harder than ever",
    "how do you get retainer clients",
    "pipeline dried up",
    "losing to bigger firms",
    "recruitment agency growth",
    "business development recruiting",
    "how to get more clients as a recruiter",
    "growing my staffing agency",
    "recruitment business development",
    "agency owner struggling",
    "how to grow a recruiting firm",
    "outbound for recruiters",
    "client acquisition recruiting",
    "contingency to retained",
]

# ── Hiring manager signals (prospect for recruiter client) ────────────────────
_HIRING_MANAGER_SIGNALS = [
    "struggling to find senior engineers",
    "last three hires did not work out",
    "looking for a recruiter who specialises",
    "headcount is growing need help",
    "tried a big agency did not work",
    "need a boutique recruiter",
    "talent acquisition help",
    "hiring is broken",
    "we need to hire fast",
    "bad hire cost us",
    "recruiter recommendations",
    "how to find good talent",
    "our hiring process is broken",
    "talent shortage in",
    "struggling to fill roles",
]


class RecruiterHunter(BaseHunter):
    """
    Niche pod for the Recruiters and Staffing Agencies vertical.

    Two prospect types are discovered and tagged:
      agency_owner   — recruitment agency owners with BD pain (AltusFlow prospects)
      hiring_manager — business leaders with talent acquisition pain
                       (prospects for recruiter clients)
    """

    POD_SLUG  = "recruiters"
    POD_LABEL = "Recruitment and Staffing Agencies"

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

    # ── scan() — LinkedIn primary for this niche ──────────────────────────────

    def scan(self) -> list:
        """LinkedIn primary (hiring managers and agency owners both active there)."""
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
        self._log(f"LinkedIn scan (max {max_per_query}/query)...")
        try:
            from scrapers.linkedin import run_niche_search
            return run_niche_search(self.POD_SLUG, max_per_query=max_per_query, run_id=self.run_id)
        except Exception as e:
            self._log(f"LinkedIn scan failed: {type(e).__name__}: {e}", level="warning")
            return []

    def _scan_facebook(self) -> list:
        self._log("Facebook scan...")
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

    # ── qualify() — abort conditions + prospect_type tagging ─────────────────

    def qualify(self, prospect: dict) -> tuple:
        """
        Abort on job seeker / job listing / layoff posts.
        Tag each passing prospect with prospect_type before scoring.
        """
        post_text = (prospect.get("post_text") or "").lower()
        title     = (prospect.get("title") or "").lower()

        # Hard abort: job seeker
        if any(phrase in post_text for phrase in _JOB_SEEKER_PHRASES):
            return (0, "Job seeker post — wrong audience")

        # Hard abort: job listing
        if any(phrase in post_text for phrase in _JOB_LISTING_PHRASES):
            return (0, "Job listing — out of scope")

        # Hard abort: layoff / fired
        if any(phrase in post_text for phrase in _LAYOFF_PHRASES):
            return (0, "Layoff/fired content — wrong emotional context for outreach")

        # Tag prospect_type based on which signal category has stronger match
        agency_hits  = sum(1 for p in _AGENCY_OWNER_SIGNALS  if p in post_text)
        hiring_hits  = sum(1 for p in _HIRING_MANAGER_SIGNALS if p in post_text)

        # Also use title to break ties
        agency_title_signals  = ["recruiter", "staffing", "headhunter", "talent acquisition lead",
                                   "recruiting director", "agency owner", "founder"]
        hiring_title_signals  = ["cto", "coo", "ceo", "vp of engineering", "head of people",
                                   "operations manager", "hiring manager", "people ops"]

        agency_title_hits = sum(1 for s in agency_title_signals if s in title)
        hiring_title_hits = sum(1 for s in hiring_title_signals if s in title)

        agency_score = agency_hits + agency_title_hits
        hiring_score = hiring_hits + hiring_title_hits

        prospect["prospect_type"] = "agency_owner" if agency_score >= hiring_score else "hiring_manager"

        from qualify import score_prospect
        return score_prospect(prospect, niche_module=self._niche)

    def inject_niche_context(self, prospect: dict) -> dict:
        ptype = prospect.get("prospect_type", "hiring_manager")
        prospect["_niche_label"]       = getattr(self._niche, "NICHE_LABEL", self.POD_LABEL)
        prospect["_deal_economics"]    = getattr(self._niche, "DEAL_ECONOMICS",
                                                  "Placement fee = $15k–$40k per hire" if ptype == "hiring_manager"
                                                  else "Outbound retainer = $2k–$5k/month")
        prospect["_common_objections"] = getattr(self._niche, "COMMON_OBJECTIONS",
                                                  "We tried a big agency and it didn't work")
        return prospect

    def strip_niche_context(self, prospect: dict) -> dict:
        for k in ("_niche_label", "_deal_economics", "_common_objections"):
            prospect.pop(k, None)
        return prospect
