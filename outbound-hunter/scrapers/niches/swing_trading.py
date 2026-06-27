"""
scrapers/niches/swing_trading.py
Signal library for the Swing Trading niche.

Swing traders hold 2–14 days, use technical and macro analysis, and tend to be
working professionals — higher disposable income, lower time-per-day for trading.
AltusFlow posts weekly setups, sector rotation content, and momentum breakdowns.
"""

NICHE_SLUG  = 'swing-trading'
NICHE_LABEL = 'Swing Trading'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'swing trading coach mentor',
    'learning swing trading need help',
    'consistently profitable swing trader mentor',
    'swing trading education recommendations',
    'technical analysis swing trading mentor',
    'stock market swing trading coaching',
    'momentum trading coaching help',
    'swing trader accountability coach',
    'how to find good swing trading setups',
    'position sizing swing trading help',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Swing Traders Community',
    'Stock Market Swing Traders',
    'Technical Analysis Traders',
    'Momentum Traders Network',
    'Breakout Traders Community',
    'Swing Trading Strategies',
    'Chart Patterns Trading Community',
    'Active Stock Traders',
    'Growth Stock Traders',
    'Options and Swing Trading',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'swingtrading',
    'stocks',
    'StockMarket',
    'Trading',
    'investing',
    'SecurityAnalysis',
    'stocksandtrading',
    'ValueInvesting',
    'options',
    'Daytrading',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'keep buying breakouts that fail',
    'can\'t find good setups',
    'how do you screen for swing trades',
    'losing on most of my setups',
    'buy the breakout sell the news',
    'getting shaken out before the move',
    'stop too tight',
    'how do you manage overnight risk',
    'earnings destroyed my trade',
    'sector rotation confusion',
    'market keeps reversing on me',
    'holding through chop',
    'when to cut losses',
    'averaging down on swings',
    'position sizing help',
    'risk management swing trading',
    'can\'t stay consistent',
    'overtrading swing positions',
    'not sure when to take profits',
    'missing the big moves',
    'how to pick entries for swing trades',
    'trailing stop strategy needed',
    'chart pattern failures',
    'breakouts not following through',
    'market too random lately',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'swing trader', 'technical analyst', 'momentum trader',
    'breakout trader', 'position trader', 'part-time trader',
]

ICP_PROSPECT_KEYWORDS = [
    'swing', 'breakout', 'setup', 'momentum', 'chart', 'pattern',
    'resistance', 'support', 'ema', 'macd', 'rsi', 'volume',
    'earnings', 'catalyst', 'sector', 'watchlist', 'hold',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'Swing trading clients are often working professionals — '
    'they have income and can invest in coaching. One client = $3,000–$10,000 annually. '
    'They trade less frequently but higher stakes per trade, '
    'making discipline and setup selection critical pain points.'
)

COMMON_OBJECTIONS = (
    'I just need a better screener and more patience — '
    'not sure a coach will fix what\'s essentially a market timing problem.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
PLATFORM_WEIGHT = {'linkedin': 0.15, 'facebook': 0.10, 'reddit': 0.45, 'twitter': 0.30}
