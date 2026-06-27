"""
scrapers/niches/futures_trading.py
Signal library for the Futures Trading niche.

ES, NQ, MNQ, MES, crude oil, gold — futures traders have a specific vocabulary
and very specific pain signals. Higher ticket clients than general daytrading.
AltusFlow posts educational content in r/FuturesTrading as a trading educator persona.
"""

NICHE_SLUG  = 'futures'
NICHE_LABEL = 'Futures Trading'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'futures trading mentor coach',
    'NQ ES futures trading help',
    'consistently profitable futures trader mentor',
    'futures trading education coaching',
    'emini futures coaching mentorship',
    'prop firm futures trader mentor',
    'CME futures trading coach recommendations',
    'futures trading psychology coaching',
    'micro futures trading mentor',
    'index futures trading education help',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Futures Trading Community',
    'Emini Futures Traders',
    'ES NQ Futures Traders',
    'CME Futures Traders',
    'Prop Firm Traders',
    'Micro Futures Traders',
    'Futures Trading Strategies',
    'Index Futures Day Traders',
    'Crude Oil Gold Futures Traders',
    'Trading Psychology Masters',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'FuturesTrading',
    'emini',
    'Trading',
    'Daytrading',
    'algotrading',
    'PropFirmTrading',
    'stocks',
    'FinancialCareers',
    'investing',
    'StockMarket',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'keep getting stopped out',
    'NQ eating my account',
    'can\'t pass the prop firm eval',
    'failed prop firm challenge',
    'blown my futures account',
    'chop killing me',
    'getting wicked out',
    'news spike blew my trade',
    'struggling with overnight holds',
    'how do you handle overnight gaps',
    'ES too choppy lately',
    'can\'t trade NQ consistently',
    'micro futures losing streak',
    'need a futures mentor',
    'can\'t read the tape',
    'volume profile not working',
    'market profile help needed',
    'how do you trade around FOMC',
    'news events destroying my trades',
    'scalping ES not working',
    'MNQ account blowup',
    'commissions eating profits',
    'sizing issues in futures',
    'can\'t control leverage',
    'futures trading psychology struggling',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'futures trader', 'emini trader', 'prop trader', 'cme',
    'es trader', 'nq trader', 'micro futures', 'index futures',
]

ICP_PROSPECT_KEYWORDS = [
    'es', 'nq', 'mnq', 'mes', 'emini', 'cme', 'futures', 'prop firm',
    'tick', 'contract', 'rollover', 'expiry', 'overnight', 'vix',
    'fomc', 'market profile', 'volume profile', 'tape reading',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'Futures traders face leverage 20–50x — one bad week can erase months of gains. '
    'One coaching client = $5,000–$20,000 annually. Prop firm failure rate >90% '
    'creates a constant stream of traders needing guidance after costly resets.'
)

COMMON_OBJECTIONS = (
    'I just need to study more price action and market profile — '
    'not sure I need a coach vs. just more screen time and backtesting.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
PLATFORM_WEIGHT = {'linkedin': 0.10, 'facebook': 0.10, 'reddit': 0.50, 'twitter': 0.30}
