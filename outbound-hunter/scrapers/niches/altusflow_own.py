"""
scrapers/niches/altusflow_own.py
Signal library for AltusFlow's own business development.

This niche is for finding practitioners (financial advisors, business coaches,
recruiters, CRE brokers, MSPs) who are struggling with their own BD and
could benefit from the AltusFlow Growth Ecosystem.

Unlike the other niches, the signal phrases here are the PRACTITIONER's pain
(struggling to grow their practice) — not their clients' pain.
"""

NICHE_SLUG  = 'altusflow-own'
NICHE_LABEL = 'AltusFlow Own BD'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'marketing agency struggling to find clients',
    'financial advisor lead generation struggling',
    'business coach how to get clients',
    'recruiter BD is hard finding clients',
    'MSP how to get new clients outbound',
    'commercial real estate broker deal flow slow',
    'professional services lead generation struggling',
    'B2B service business need more clients',
    'agency growth strategy need help',
    'consultant how to get more clients',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
# Groups where our target clients (agency owners, advisors, etc.) hang out
FACEBOOK_GROUPS = [
    'Marketing Agency Owners',
    'Recruitment Agency Owners Network',
    'MSP Business Owners',
    'Financial Advisor Growth Community',
    'Business Coaches & Consultants',
    'Independent Financial Advisors',
    'IT Managed Services Professionals',
    'Commercial Real Estate Professionals',
    'Agency Owners Community',
    'Professional Services Business Growth',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
# Two target segments: financial advisors/RIAs and trading coaches
REDDIT_SUBREDDITS = [
    # Financial advisors / RIAs
    'financialplanning', 'CFP', 'personalfinance', 'financialindependence',
    'investing', 'FinancialAdvisors', 'wealthmanagement',
    # Trading coaches / community leaders
    'Daytrading', 'StockMarket', 'options', 'Forex', 'algotrading',
    'trading', 'Bogleheads',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
# Financial advisor pain: practitioners struggling with their own BD
# Trading coach pain: traders who need mentorship / community
SIGNAL_PHRASES = [
    # Financial advisors — advisor BD pain
    'how do financial advisors get new clients',
    'pipeline dried up advisor',
    'struggling to find qualified clients',
    'marketing as a financial advisor',
    'referrals have slowed down',
    'how do advisors grow their book',
    'fee-only advisor lead generation',
    'RIA business development',
    # Financial advisors — prospect signals (people who need an advisor)
    'just sold my business need financial advisor',
    'inherited money need advisor',
    'retiring soon need financial planning',
    'net worth milestone need wealth manager',
    'how do I find a fee-only advisor',
    # Trading coaches — traders who need help
    'looking for a trading community',
    'want to learn to trade properly',
    'been trading alone spinning my wheels',
    'profitable some months blow it up next',
    'need trading mentor',
    'paper trading ready to go live scared',
    'trading psychology help',
    'anyone recommend a trading community',
    'tired of trading alone',
    'looking for trading accountability',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'founder', 'owner', 'ceo', 'managing director', 'principal',
    'financial advisor', 'business coach', 'recruiter', 'broker',
    'msp', 'managed service', 'agency owner',
]

ICP_PROSPECT_KEYWORDS = [
    'agency', 'practice', 'firm', 'clients', 'pipeline',
    'BD', 'business development', 'marketing', 'lead gen',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'AltusFlow engagement = $3,000–$8,000/month retainer. '
    'The 3-vertical ecosystem replaces 3-4 tools and often a full-time BD hire.'
)

COMMON_OBJECTIONS = (
    'We\'ve tried agencies before and they didn\'t deliver — '
    'not sure this is different from what we\'ve already tried.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
PLATFORM_WEIGHT = {'linkedin': 0.35, 'facebook': 0.25, 'reddit': 0.25, 'twitter': 0.15}
