"""
scrapers/niches/msps.py
Signal library for the Managed Service Providers (MSPs) niche.

Signal phrases calibrated to find SMB owners and IT managers posting
about IT pain, bad support, or searching for a new technology partner —
before they start Googling or calling providers.

Reddit gets the highest weight because r/msp and r/sysadmin have active
communities with high-signal discussions from both sides of the market.
"""

NICHE_SLUG  = 'msps'
NICHE_LABEL = 'MSPs'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'IT support frustrating small business',
    'managed IT services recommendations',
    'looking for IT partner small business',
    'server down IT support slow response',
    'MSP recommendations small business',
    'cybersecurity help small business',
    'IT infrastructure problems growing company',
    'switching IT provider recommendations',
    'business technology partner needed',
    'cloud migration help recommendations',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Small Business Technology Users',
    'Business Owners Technology Group',
    'SMB Operations Leaders',
    'Office Managers Network',
    'Small Business Owners Network',
    'Entrepreneurs Under 40',
    'Business Growth Strategies',
    'Online Business Owners',
    'Remote Work & Tech Tools for Business',
    'CEO and Business Owners Community',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
# Reddit has the highest weight for MSPs — r/msp and r/sysadmin are highly active
REDDIT_SUBREDDITS = [
    'msp',
    'sysadmin',
    'ITManagers',
    'smallbusiness',
    'entrepreneur',
    'pcmasterrace',
    'homelab',
    'techsupport',
    'cybersecurity',
    'BusinessIntelligence',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'how do MSPs get new clients',
    'struggling with outbound',
    'need to grow beyond referrals',
    'lost another RFP',
    'looking for IT partner',
    'IT support is a nightmare',
    'our current provider isn\'t cutting it',
    'server went down again',
    'how do I find a good MSP',
    'managed IT services recommendations',
    'switching IT providers',
    'IT help desk frustrating',
    'cybersecurity for small business help',
    'cloud migration recommendations',
    'IT infrastructure problems',
    'looking for IT support company',
    'MSP recommendations',
    'technology partner needed',
    'slow IT response time',
    'IT downtime killing productivity',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'msp', 'managed service', 'it provider', 'technology partner',
    'it director', 'cto', 'it manager', 'systems administrator',
    'vp technology', 'head of it',
]

ICP_PROSPECT_KEYWORDS = [
    'IT', 'managed service', 'MSP', 'server', 'cloud', 'cybersecurity',
    'tech support', 'infrastructure', 'downtime', 'sysadmin',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'One new managed services client = $2,000–$10,000/month recurring MRR. '
    'Compounding revenue — every client added raises the floor permanently.'
)

COMMON_OBJECTIONS = (
    'Most of our growth has been referral-based — '
    'worried about brand perception if we do outbound at scale.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
# Reddit gets highest weight — r/msp and r/sysadmin are uniquely high-signal
PLATFORM_WEIGHT = {'linkedin': 0.35, 'facebook': 0.25, 'reddit': 0.40}
