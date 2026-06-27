"""
scrapers/niches/business_coaches.py
Signal library for the Business Coaches niche.

Signal phrases and groups are calibrated to find the business coach's
ideal prospect — founders, operators, and solopreneurs actively posting
about needing strategic help, accountability, or a growth partner.
"""

NICHE_SLUG  = 'business-coaches'
NICHE_LABEL = 'Business Coaches'

# ── LinkedIn search queries ────────────────────────────────────────────────────
LINKEDIN_QUERIES = [
    'looking for a business coach recommendations',
    'need executive coach struggling to grow',
    'business coaching where to start',
    'accountability partner entrepreneur needed',
    'small business growth coach recommendations',
    'how to scale my business advice needed',
    'founder overwhelmed need help',
    'solopreneur struggling to grow',
    'business mentor recommendations',
    'leadership coach for founders',
]

# ── Facebook groups ───────────────────────────────────────────────────────────
FACEBOOK_GROUPS = [
    'Entrepreneurs Under 40',
    'Small Business Owners Network',
    'Female Founders',
    'Business Growth Strategies',
    'Startup Founders Community',
    'Online Business Owners',
    'Solopreneur Success',
    'Coaches and Consultants Community',
    'The Entrepreneur Life',
    'Online Entrepreneurs & Business Owners',
]

# ── Reddit subreddits ─────────────────────────────────────────────────────────
REDDIT_SUBREDDITS = [
    'smallbusiness',
    'Entrepreneur',
    'entrepreneur',
    'startups',
    'AskEntrepreneurs',
    'Business',
    'selfemployed',
    'Freelancers',
    'cofounder',
]

# ── Signal phrases ────────────────────────────────────────────────────────────
SIGNAL_PHRASES = [
    'struggling to get clients',
    'how do coaches get clients',
    'my calendar is empty',
    'tired of chasing leads',
    'word of mouth not enough',
    'looking for a business coach',
    'need a coach',
    'overwhelmed as a founder',
    'stuck in my business',
    'need accountability',
    'how do I scale',
    'business advice needed',
    'no idea how to grow',
    'struggling to grow my business',
    'need mentorship',
    'business mentor recommendations',
    'executive coach recommendations',
    'how to get unstuck in business',
    'need help with strategy',
    'small business advice',
]

# ── ICP keywords ──────────────────────────────────────────────────────────────
ICP_TITLE_KEYWORDS = [
    'business coach', 'executive coach', 'life coach', 'leadership coach',
    'consultant', 'advisor', 'mentor', 'founder', 'solopreneur',
]

ICP_PROSPECT_KEYWORDS = [
    'founder', 'business owner', 'entrepreneur', 'startup',
    'scale', 'grow', 'strategy', 'coach', 'accountability',
]

# ── Pre-call brief data ───────────────────────────────────────────────────────
DEAL_ECONOMICS = (
    'One new coaching engagement = $5,000–$50,000. '
    'The system fills the calendar without the founder doing manual outreach.'
)

COMMON_OBJECTIONS = (
    'I build my practice through referrals and content — '
    'not sure cold outreach fits my brand.'
)

# ── Platform weighting ────────────────────────────────────────────────────────
PLATFORM_WEIGHT = {'linkedin': 0.30, 'facebook': 0.45, 'reddit': 0.25}
