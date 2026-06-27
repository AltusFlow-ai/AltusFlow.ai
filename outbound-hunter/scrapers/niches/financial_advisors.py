"""
scrapers/niches/financial_advisors.py
Signal library for the Financial Advisors niche.

Signal phrases and groups are calibrated to find the financial advisor's
ideal prospect — people actively posting about needing wealth guidance,
retirement planning, or investment advice.

AltusFlow runs this niche on behalf of financial advisor clients.
"""

NICHE_SLUG  = 'financial-advisors'
NICHE_LABEL = 'Financial Advisors'

# ── LinkedIn search queries ────────────────────────────────────────────────────
# Finds wealth management prospects posting pain signals
LINKEDIN_QUERIES = [
    'need financial advisor recommendations',
    'looking for wealth management advice',
    'retirement planning help where do I start',
    'how do I find a good financial advisor',
    'investment advice overwhelmed where to start',
    'inherited money what to do with it',
    'financial planning for high earners',
    'AUM portfolio management recommendations',
    'CFP financial planner recommendations needed',
    'how to grow wealth investments advice',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
# Groups where financial advisor prospects hang out
FACEBOOK_GROUPS = [
    'Financial Independence',
    'Personal Finance Community',
    'Bogleheads',
    'Early Retirement Now Community',
    'Wealth Building Strategies',
    'High Income Earners Network',
    'Entrepreneurs Finance Club',
    'Personal Finance Advice & Help',
    'FIRE Movement - Financial Independence Retire Early',
    'Investing for Beginners',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'personalfinance',
    'financialindependence',
    'investing',
    'CFP',
    'financialplanning',
    'inheritance',
    'Bogleheads',
    'ChubbyFIRE',
    'fatFIRE',
    'HENRYfinance',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
# Exact phrases to match in posts — sourced from niche landing page
SIGNAL_PHRASES = [
    'pipeline dried up',
    'struggling to find qualified clients',
    'how do you get new AUM clients',
    'growing my practice',
    'lead gen for financial advisors',
    'need financial advice',
    'looking for a financial advisor',
    'how do I find a financial advisor',
    'wealth management recommendations',
    'retirement planning help',
    'what should I do with my money',
    'investment advice needed',
    'inherited money',
    'overwhelmed by finances',
    'need help with investments',
    'financial planner recommendations',
    'CFP recommendations',
    'how to invest',
    'growing my wealth',
    'portfolio management help',
]

# ── ICP keywords (for niche-aware scoring in qualify.py) ──────────────────────
ICP_TITLE_KEYWORDS = [
    'financial advisor', 'financial planner', 'wealth manager',
    'investment advisor', 'ria', 'cfp', 'aum',
    'retirement planner', 'portfolio manager',
]

ICP_PROSPECT_KEYWORDS = [
    'retirement', 'invest', 'wealth', 'portfolio', 'inheritance',
    'savings', 'financial independence', 'fire', 'advisor',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'One new AUM client = $5,000–$50,000 in annual management fees. '
    'The system pays for itself with a single converted prospect.'
)

COMMON_OBJECTIONS = (
    'We already get clients through referrals — '
    'not sure we need a more systematic approach right now.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
# Allocates Apify compute credits: higher weight = more frequent scanning
PLATFORM_WEIGHT = {'linkedin': 0.35, 'facebook': 0.25, 'reddit': 0.25, 'twitter': 0.15}
