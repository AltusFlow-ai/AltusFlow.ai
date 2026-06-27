"""
scrapers/niches/commercial_real_estate.py
Signal library for the Commercial Real Estate niche.

Signal phrases calibrated to find CRE decision makers posting about
slow deal flow, struggling pipelines, and market challenges — before
they pick up the phone and start calling advisors.
"""

NICHE_SLUG  = 'commercial-real-estate'
NICHE_LABEL = 'Commercial Real Estate'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'commercial real estate deal flow slow',
    'CRE broker struggling to find qualified buyers',
    'commercial real estate market tough',
    'need more listings commercial property',
    'commercial real estate lead generation',
    'CRE investment opportunities looking',
    'commercial property buyer looking',
    'office space industrial looking to lease',
    'commercial real estate advisor recommendations',
    'transaction volume down CRE market',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Real Estate Investors Network',
    'Commercial Real Estate Professionals',
    'Business Owners Community',
    'Entrepreneurs in Business Real Estate',
    'Real Estate Investment Strategies',
    'Commercial Property Investors',
    'CRE Investors and Brokers',
    'Business Owners - Office & Commercial Space',
    'Real Estate Networking Group',
    'Property Investment Community',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'CommercialRealEstate',
    'realestateinvesting',
    'smallbusiness',
    'entrepreneur',
    'realestate',
    'investing',
    'REBubble',
    'AskCommercialRealEstate',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'deal flow is slow',
    'struggling to find qualified buyers',
    'how do you generate leads in CRE',
    'market is tough',
    'need more listings',
    'transaction volume down',
    'looking for investment opportunities',
    'how do CRE brokers prospect',
    'commercial real estate advisor recommendations',
    'looking for commercial space',
    'need to find office space',
    'looking to buy commercial property',
    'how do I find a commercial real estate broker',
    'industrial space for lease recommendations',
    'retail space looking to expand',
    'CRE market slow',
    'deal pipeline dried up',
    'struggling to close CRE deals',
    'commercial real estate marketing',
    'how to find buyers for commercial property',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'broker', 'commercial real estate', 'cre', 'leasing agent',
    'property manager', 'real estate investor', 'principal',
    'managing broker', 'investment sales',
]

ICP_PROSPECT_KEYWORDS = [
    'commercial', 'cre', 'broker', 'listing', 'deal flow',
    'lease', 'acquisition', 'investment property', 'office space',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'One closed deal = $50,000–$500,000 in commission. '
    'The system runs daily and finds decision makers at the exact moment they\'re in-market.'
)

COMMON_OBJECTIONS = (
    'CRE is relationship-driven — not sure a digital prospecting system fits '
    'how we build trust in this market.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
PLATFORM_WEIGHT = {'linkedin': 0.45, 'facebook': 0.35, 'reddit': 0.20}
