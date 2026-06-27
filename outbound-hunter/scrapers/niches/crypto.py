"""
scrapers/niches/crypto.py
Signal library for the Crypto Trading niche.

Crypto traders span retail spot holders, altcoin traders, DeFi participants,
and crypto derivatives traders. High volume of pain signals across Reddit and X.
AltusFlow posts risk management, cycle analysis, and emotional discipline content.
"""

NICHE_SLUG  = 'crypto'
NICHE_LABEL = 'Crypto Trading'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'crypto trading mentor coach',
    'bitcoin trading education coaching',
    'altcoin trading mentor recommendations',
    'cryptocurrency trading help mentor',
    'crypto portfolio management coaching',
    'blockchain trading education',
    'defi trading strategy coaching',
    'crypto technical analysis mentor',
    'bitcoin trading consistently profitable mentor',
    'crypto trading psychology coaching',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Cryptocurrency Traders Community',
    'Bitcoin Trading Strategies',
    'Altcoin Traders Network',
    'Crypto Day Traders',
    'DeFi Traders Community',
    'Crypto Technical Analysis',
    'Cryptocurrency Investment Community',
    'Bitcoin Ethereum Crypto Traders',
    'Crypto Trading Signals Community',
    'Blockchain Traders Network',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'CryptoCurrency',
    'Bitcoin',
    'ethereum',
    'CryptoMarkets',
    'altcoin',
    'SatoshiStreetBets',
    'defi',
    'CryptoTrading',
    'BitcoinBeginners',
    'solana',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'wrecked by altcoins',
    'bag holding',
    'buy high sell low',
    'got liquidated',
    'margin call',
    'rug pulled',
    'lost everything in crypto',
    'panic sold the bottom',
    'FOMO into a pump',
    'can\'t stop gambling on alts',
    'overleveraged and scared',
    'how do you take profits',
    'never know when to sell',
    'portfolio down 80 percent',
    'crypto PTSD',
    'emotional crypto decisions',
    'how do you manage crypto risk',
    'position sizing crypto',
    'how to survive a bear market',
    'altseason strategy needed',
    'can\'t stop looking at charts',
    'sleep deprived from crypto',
    'gambling problem with crypto',
    'how to stop buying tops',
    'DCA strategy not working for me',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'crypto trader', 'bitcoin trader', 'defi trader', 'altcoin trader',
    'crypto investor', 'web3', 'blockchain', 'crypto enthusiast',
]

ICP_PROSPECT_KEYWORDS = [
    'bitcoin', 'eth', 'btc', 'sol', 'altcoin', 'defi', 'wallet',
    'exchange', 'binance', 'coinbase', 'leverage', 'liquidation',
    'pump', 'dump', 'bag', 'portfolio', 'staking', 'yield',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'Crypto traders often have significant portfolio value despite poor risk management. '
    'One coaching client = $2,000–$8,000 annually. '
    'Emotional trading cycles in crypto create recurring coaching demand — '
    'bear markets drive demand for education; bull markets drive demand for execution.'
)

COMMON_OBJECTIONS = (
    'Crypto moves on fundamentals and whale manipulation — '
    'not sure a trading coach can help with something this unpredictable.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
# X (Twitter) is the dominant crypto community platform
PLATFORM_WEIGHT = {'linkedin': 0.05, 'facebook': 0.10, 'reddit': 0.40, 'twitter': 0.45}
