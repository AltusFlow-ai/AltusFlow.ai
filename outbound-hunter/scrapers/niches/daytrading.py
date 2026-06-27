"""
scrapers/niches/daytrading.py
Signal library for the Day Trading niche.

AltusFlow posts in r/Daytrading and related communities under a trading educator
persona. Comments on those posts become warm leads — people who already know
the account is credible. One day trader client = $3,000–$12,000 in annual coaching.
"""

NICHE_SLUG  = 'daytrading'
NICHE_LABEL = 'Day Trading'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'day trading coach mentor recommendations',
    'learning to day trade consistently profitable',
    'day trading psychology help',
    'stuck losing money day trading need help',
    'day trader accountability partner mentor',
    'trading mentor recommendations day trading',
    'how to become consistently profitable trader',
    'day trading education course recommendations',
    'prop firm trading mentorship',
    'futures day trading coaching help',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Day Traders Community',
    'Futures Trading Community',
    'Day Trading Strategies',
    'Forex Traders Community',
    'Stock Market Day Traders',
    'Trading Psychology Mastery',
    'Prop Firm Traders',
    'Emini Futures Traders',
    'NQ Day Traders',
    'Active Traders Network',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'Daytrading',
    'stocks',
    'StockMarket',
    'Trading',
    'FuturesTrading',
    'algotrading',
    'PropFirmTrading',
    'stocksandtrading',
    'Daytraders',
    'trading212',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'blown my account',
    'keep losing money',
    'can\'t find consistency',
    'revenge trading',
    'overtrading',
    'FOMO trading',
    'blew up account',
    'how do you become consistently profitable',
    'emotional trading',
    'can\'t stick to my plan',
    'losing streak',
    'need a mentor',
    'trading psychology problems',
    'keep making the same mistakes',
    'how long until profitable',
    'losing my savings trading',
    'day trading is impossible',
    'stop loss hunting',
    'when will I be consistent',
    'taking bad trades',
    'chasing entries',
    'don\'t know why I keep losing',
    'undisciplined trading',
    'averaging down',
    'can\'t read price action',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'day trader', 'daytrader', 'futures trader', 'prop trader',
    'trading student', 'retail trader', 'algo trader',
]

ICP_PROSPECT_KEYWORDS = [
    'trade', 'chart', 'setup', 'entry', 'stop loss', 'profit',
    'account', 'broker', 'candlestick', 'price action', 'nq', 'es',
    'spy', 'qqq', 'scalp', 'momentum', 'consistency',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'One day trading coaching client = $3,000–$12,000 in annual fees. '
    'Most traders try for 6–18 months solo before seeking a mentor — '
    'catching them at that frustration point is the highest-converting moment.'
)

COMMON_OBJECTIONS = (
    'I can figure this out on my own, I just need more screen time — '
    'not sure I need to pay for coaching right now.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
# Reddit + X dominate the trading retail community
PLATFORM_WEIGHT = {'linkedin': 0.10, 'facebook': 0.10, 'reddit': 0.50, 'twitter': 0.30}
