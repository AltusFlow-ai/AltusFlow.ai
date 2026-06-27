"""
scrapers/niches/recruiters.py
Signal library for the Recruiters niche.

Signal phrases calibrated to find a recruiter's ideal client — companies
and founders posting about hiring pain, failed recruitment, or BD
challenges before they pick up the phone to call an agency.
"""

NICHE_SLUG  = 'recruiters'
NICHE_LABEL = 'Recruiters'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'struggling to hire senior engineers',
    'can not find qualified candidates',
    'talent acquisition challenges growing company',
    'hiring is brutal right now',
    'how do companies find good recruiters',
    'recruitment agency recommendations',
    'retained search firm recommendations',
    'hiring taking too long candidates ghosting',
    'struggling to fill technical roles',
    'executive search firm recommendations',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'HR Professionals Network',
    'Talent Acquisition Leaders',
    'Startup Founders Community',
    'Tech Company Founders',
    'Scale Up Business Owners',
    'Small Business Owners Network',
    'Entrepreneurs Under 40',
    'Business Growth Strategies',
    'Founders and CEOs Network',
    'Operations Leaders Community',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'humanresources',
    'recruiting',
    'jobs',
    'careerguidance',
    'ITCareerQuestions',
    'startups',
    'Entrepreneur',
    'smallbusiness',
    'cscareerquestions',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'struggling to find clients',
    'BD is harder than ever',
    'how do you get retainer clients',
    'pipeline dried up',
    'losing to bigger firms',
    'how to get recruitment clients',
    'struggling to hire',
    'can not find qualified candidates',
    'hiring is brutal',
    'talent acquisition help',
    'recruitment recommendations',
    'how do we find a good recruiter',
    'hiring agency recommendations',
    'candidates keep ghosting',
    'search firm recommendations',
    'failed hire need help',
    'how to find the right recruiter',
    'placement fee worth it',
    'contingency vs retained search',
    'technical recruiting help',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'recruiter', 'talent acquisition', 'staffing', 'headhunter',
    'executive search', 'hr director', 'people ops', 'cto', 'vp engineering',
]

ICP_PROSPECT_KEYWORDS = [
    'hiring', 'candidates', 'talent', 'recruitment', 'search firm',
    'placement', 'headhunter', 'agency', 'HR',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'One new client contract = $10,000–$100,000/year in placement fees. '
    'Single retained search engagement pays for the system multiple times over.'
)

COMMON_OBJECTIONS = (
    'We do most of our BD through existing relationships and LinkedIn direct — '
    'worried about hitting the wrong person at the wrong time.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
PLATFORM_WEIGHT = {'linkedin': 0.45, 'facebook': 0.25, 'reddit': 0.15, 'twitter': 0.15}
