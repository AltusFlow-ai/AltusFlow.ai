"""
scrapers/niches/__init__.py
Central loader for all niche signal libraries.

Usage:
    from scrapers.niches import get_niche, ALL_NICHES, PLATFORM_WEIGHTS

    niche = get_niche('msps')
    print(niche.SIGNAL_PHRASES)
    print(niche.PLATFORM_WEIGHT)

    for n in ALL_NICHES:
        print(n.NICHE_SLUG, n.LINKEDIN_QUERIES)
"""

from . import (
    financial_advisors,
    business_coaches,
    recruiters,
    commercial_real_estate,
    msps,
    altusflow_own,
    daytrading,
    futures_trading,
    swing_trading,
    crypto,
    options_trading,
)

# ── Registry ──────────────────────────────────────────────────────────────────

ALL_NICHES = [
    financial_advisors,
    business_coaches,
    recruiters,
    commercial_real_estate,
    msps,
    altusflow_own,
    daytrading,
    futures_trading,
    swing_trading,
    crypto,
    options_trading,
]

_NICHE_MAP = {n.NICHE_SLUG: n for n in ALL_NICHES}

# ── Public API ────────────────────────────────────────────────────────────────

def get_niche(slug):
    """
    Return the niche module for the given slug, or None if not found.
    Example: get_niche('msps') → scrapers.niches.msps module
    """
    return _NICHE_MAP.get(slug)


def get_all_slugs():
    """Return list of all registered niche slugs."""
    return list(_NICHE_MAP.keys())


def get_signal_phrases(slug):
    """Return SIGNAL_PHRASES for a niche slug, or [] if not found."""
    n = _NICHE_MAP.get(slug)
    return n.SIGNAL_PHRASES if n else []


def get_linkedin_queries(slug):
    """Return LINKEDIN_QUERIES for a niche slug, or [] if not found."""
    n = _NICHE_MAP.get(slug)
    return n.LINKEDIN_QUERIES if n else []


def get_facebook_groups(slug):
    """Return FACEBOOK_GROUPS for a niche slug, or [] if not found."""
    n = _NICHE_MAP.get(slug)
    return n.FACEBOOK_GROUPS if n else []


def get_reddit_subreddits(slug):
    """Return REDDIT_SUBREDDITS for a niche slug, or [] if not found."""
    n = _NICHE_MAP.get(slug)
    return n.REDDIT_SUBREDDITS if n else []


def get_platform_weight(slug, platform):
    """
    Return the platform weight (0.0–1.0) for a niche/platform combo.
    Falls back to equal weighting if niche not found.
    """
    n = _NICHE_MAP.get(slug)
    if n and hasattr(n, 'PLATFORM_WEIGHT'):
        return n.PLATFORM_WEIGHT.get(platform, 0.33)
    return 0.33


# ── Platform weights dict (for orchestrator allocation) ───────────────────────
PLATFORM_WEIGHTS = {n.NICHE_SLUG: n.PLATFORM_WEIGHT for n in ALL_NICHES}
