"""
scrapers/niches/options_trading.py
Signal library for the Options Trading niche.

Options traders include retail degens (0DTE, yolo), income traders (theta/wheel),
and hedgers. Very distinct communities: r/options vs r/thetagang vs r/wallstreetbets.
AltusFlow posts educational breakdowns on Greeks, strategy selection, and risk management.
"""

NICHE_SLUG  = 'options'
NICHE_LABEL = 'Options Trading'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'options trading mentor coach',
    'learning options trading coaching',
    'theta gang wheel strategy coaching',
    'options trading education help',
    'consistently profitable options trader mentor',
    'selling options income strategy coaching',
    'options trading psychology mentor',
    'SPX 0DTE trading coaching help',
    'iron condor covered calls coaching',
    'options risk management mentor',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Options Traders Community',
    'Theta Gang Traders',
    'Wheel Strategy Traders',
    'Options Income Traders',
    'Stock Options Trading Community',
    'Covered Call Traders',
    'Iron Condor Traders Network',
    'SPX Options Traders',
    'Options Education Hub',
    'Retail Options Traders',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'options',
    'thetagang',
    'stocks',
    'wallstreetbets',
    'Optionstraders',
    'investing',
    'StockMarket',
    'Daytrading',
    'algotrading',
    'SecurityAnalysis',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'theta decay killing me',
    'assignment risk confused',
    'lost everything on calls',
    'options expired worthless again',
    '0DTE blew up account',
    'don\'t understand the Greeks',
    'IV crush destroyed my trade',
    'earnings play lost badly',
    'rolling options confused',
    'when to close vs let expire',
    'covered calls capped my gains',
    'wheel strategy not working',
    'don\'t know how to hedge',
    'wrong strike selection',
    'buying options always lose',
    'selling options scared of assignment',
    'credit spread blew out',
    'iron condor loss',
    'delta neutral confused',
    'can\'t manage positions',
    'extrinsic value help',
    'options too complex',
    'how to size option trades',
    'need options mentor',
    'volatility skew confusion',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'options trader', 'theta trader', 'wheel trader', 'premium seller',
    'options income', 'derivatives trader', 'vol trader',
]

ICP_PROSPECT_KEYWORDS = [
    'call', 'put', 'strike', 'expiry', 'greek', 'delta', 'theta',
    'vega', 'gamma', 'iv', 'premium', 'spread', 'condor', 'butterfly',
    'covered call', 'cash secured', 'assignment', 'wheel', '0dte',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'Options traders often have substantial accounts and are actively losing to IV crush, '
    'assignment errors, and poor strategy selection. One coaching client = $4,000–$15,000 '
    'annually. Income-focused options traders (wheel/theta) are the highest LTV — '
    'they trade monthly and compound coaching value over time.'
)

COMMON_OBJECTIONS = (
    'I think I just need more experience selling premium — '
    'not sure a coach can help with something I need to learn by doing.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
PLATFORM_WEIGHT = {'linkedin': 0.10, 'facebook': 0.10, 'reddit': 0.50, 'twitter': 0.30}
