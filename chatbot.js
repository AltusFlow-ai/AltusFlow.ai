/**
 * AltusFlow.ai — AI Sales Assistant v2
 * Full business bible: pricing, tiers, objection handling, HubSpot capture.
 */
(function () {
  'use strict';

  // ── Config ──────────────────────────────────────────────────────────────────
  const HUBSPOT_PORTAL_ID = '246530361';
  const ALTUSFLOW_CLIENT_ID = 'ALT00';

  // ── Niche data ───────────────────────────────────────────────────────────────
  const NICHE_DATA = {
    'financial-advisors': {
      label: 'financial advisors', short: 'advisors',
      signals: ['"pipeline dried up"', '"struggling to find qualified clients"', '"how do you get new AUM clients"', '"growing my practice"', '"lead gen for financial advisors"'],
      deal: 'one new AUM client = $5,000–$50,000 in annual fees',
      examplePost: 'A prospect posted: "Looking for ideas on how to grow my advisory practice beyond referrals. Cold outreach feels off-brand but I need to fill the pipeline."',
      exampleReply: '"Hi James — saw your post about practice growth. We built a system specifically for advisors that finds prospects already asking about wealth management — and gets your name in front of them before they Google anyone. Worth 15 minutes?"',
      industry: 'financial advisory',
      keywords: [/financial advis|wealth manag|\baum\b|advisory practice|financial plann/i],
    },
    'business-coaches': {
      label: 'business coaches', short: 'coaches',
      signals: ['"struggling to get clients"', '"how do coaches get clients"', '"my calendar is empty"', '"tired of chasing leads"', '"word of mouth not enough"'],
      deal: 'one new client engagement = $5,000–$50,000',
      examplePost: 'A prospect posted: "Honest question — how are business coaches actually getting new clients right now? My referral pipeline has dried up and I\'m not sure what to do."',
      exampleReply: '"Hi Sarah — saw your post about client acquisition. We built a system that finds business owners publicly posting about needing a coach — and gets your outreach to them first. Worth a quick call?"',
      industry: 'business coaching',
      keywords: [/business coach|coaching client|coaching business|life coach|executive coach/i],
    },
    'recruiters': {
      label: 'recruiters', short: 'recruiters',
      signals: ['"struggling to find clients"', '"BD is harder than ever"', '"how do you get retainer clients"', '"pipeline dried up"', '"losing to bigger firms"'],
      deal: 'one new client contract = $10,000–$100,000/year in placement fees',
      examplePost: 'A prospect posted: "Business development as a recruiter is brutal right now. Anyone successfully adding new clients in this market? What\'s actually working?"',
      exampleReply: '"Hi Mike — saw your post about BD. We built a system that scans for companies posting about hiring challenges before they start calling agencies — and gets your message in first. Worth 15 minutes?"',
      industry: 'recruitment',
      keywords: [/recruit|staffing|placement fee|talent acquisition|headhunt|executive search/i],
    },
    'commercial-real-estate': {
      label: 'CRE brokers', short: 'CRE',
      signals: ['"deal flow is slow"', '"struggling to find qualified buyers"', '"how do you generate leads in CRE"', '"market is tough"', '"need more listings"'],
      deal: 'one closed deal = $50,000–$500,000 in commission',
      examplePost: 'A prospect posted: "Market has been brutally slow. Anyone doing anything creative for deal flow? I have three solid listings sitting right now."',
      exampleReply: '"Hi David — saw your post about deal flow. We built a system for CRE professionals that surfaces decision makers posting about slow markets — so you\'re in the conversation before they start making calls. Worth 15 minutes?"',
      industry: 'commercial real estate',
      keywords: [/commercial real estate|\bcre\b|deal flow|listings|commercial propert/i],
    },
    'msps': {
      label: 'MSPs', short: 'MSPs',
      signals: ['"how do MSPs get new clients"', '"struggling with outbound"', '"need to grow beyond referrals"', '"lost another RFP"', '"looking for IT partner"'],
      deal: 'one new managed services client = $2,000–$10,000/month recurring',
      examplePost: 'A prospect posted: "Had our server go down for 6 hours yesterday. Current IT support took 4 hours just to call us back. Anyone had luck switching MSPs?"',
      exampleReply: '"Hi Sarah — saw your post about the server outage. We work with MSPs that want to reach clients like this before they start Googling IT support. Want to see how it works?"',
      industry: 'managed IT services',
      keywords: [/\bmsp\b|managed service|it support|it provider|managed it|cybersecurity.*business/i],
    },
  };

  function detectNicheFromText(text) {
    for (const [slug, data] of Object.entries(NICHE_DATA)) {
      if (data.keywords.some((p) => p.test(text))) return slug;
    }
    return null;
  }

  function setNiche(slug) {
    if (slug && NICHE_DATA[slug]) {
      currentNiche = slug;
      sessionStorage.setItem('altusflow_niche', slug);
    }
  }

  // ── Quick action buttons ────────────────────────────────────────────────────
  const QUICK_ACTIONS = [
    { label: 'What does AltusFlow do?',   intent: 'overview' },
    { label: 'Is this right for me?',      intent: 'icp' },
    { label: 'AI-powered websites',       intent: 'websites' },
    { label: 'Meta ads & funnels',        intent: 'ads' },
    { label: 'Outbound lead sourcing',    intent: 'outbound' },
    { label: 'Book a strategy call',      intent: 'contact' },
  ];

  function getQuickActions() {
    if (currentNiche && NICHE_DATA[currentNiche]) {
      const nd = NICHE_DATA[currentNiche];
      return [
        { label: `How does this work for ${nd.short}?`, intent: 'niche_how_it_works' },
        { label: 'What signals do you scan for?',       intent: 'niche_signals' },
        { label: 'Show me an example',                  intent: 'niche_example' },
        ...QUICK_ACTIONS,
      ];
    }
    return QUICK_ACTIONS;
  }

  // ── Full response bible ─────────────────────────────────────────────────────
  const RESPONSES = {

    greeting: `Hey! 👋 I'm the AltusFlow AI assistant — here to help you understand how we build fully automated growth engines for high-value businesses.

**I can help with:**
• Our 3-Vertical Growth Ecosystem (websites, ads, outbound)
• Pricing and what's included in each tier
• Whether AltusFlow is the right fit for you
• Booking a free strategy call

What would you like to know?`,

    overview: `**AltusFlow.ai** builds fully automated growth engines for high-value businesses.

We solve the "leaky bucket" problem — where you spend on traffic but lose deals because your website can't sell 24/7.

Our **3-Vertical Growth Ecosystem** works as one integrated pipeline:

1. **The Conversion Engine** — Premium website + native 24/7 AI chat that qualifies leads and books meetings while you sleep
2. **The Inbound Magnet** — Meta Ads and psychological sales funnels that turn cold clicks into booked calls
3. **The Outbound Hunter** — AI that scans LinkedIn and social for buyers actively mentioning problems you solve, then drafts hyper-personalized pitches

Everything flows into one HubSpot CRM with automated reporting. You get a branded performance dashboard and a PDF report on the 1st of every month — zero manual work on your end.

Which area would you like to dive into?`,

    pricing: `Investment depends entirely on your situation — and honestly, quoting a number before understanding your business would be doing you a disservice.

What we've found is that every client has a different combination of gaps. Some need all three verticals from day one. Others start with one and scale into the rest as results come in.

**The right answer requires a 30-minute conversation** where we map your current setup, identify the highest-impact lever first, and show you exactly what ROI looks like for your specific numbers.

No generic quote sheet. No pressure. Just a straight diagnosis.

<a href="#contact" class="chat-cta-link">→ Book your free strategy call</a>`,

    websites: `**The Conversion Engine** — Premium AI-Powered Websites

Every AltusFlow website ships with a **custom-trained AI chat assistant** built in — not a bolt-on widget. It knows your offers, handles objections, and books meetings 24/7.

**What it does:**
• Answers questions in ~3 seconds, around the clock
• Qualifies leads with smart follow-up questions
• Books meetings directly into your calendar
• Handles objections while your team sleeps

**Why it matters:** Most websites are passive brochures. A prospect lands at 7 PM Saturday, can't get an answer, and books your competitor by Monday morning. The Conversion Engine stops that leak permanently.

**Includes:** HubSpot CRM integration, UTM attribution, live dashboard, monthly reporting.

Want to know how it connects with ads and outbound? Just ask.`,

    ads: `**The Inbound Magnet** — Meta Ads & Sales Funnels

Stop burning budget on generic ads that drive clicks but not calls.

**What we build:**
• Targeted Meta (Facebook & Instagram) campaigns for your ideal buyer
• TOF → MOF → RTG funnel structure (cold traffic → warm → retarget)
• Landing pages wired into your AI chat for instant qualification
• UTM tracking so you know exactly which ad booked which call
• Weekly AI-reviewed performance — underperforming ads flagged automatically

**How it connects:** Traffic from ads lands on your AltusFlow website where the AI qualifies and books — no lead falls through.

**Ad spend is managed by you directly** — we handle strategy, setup, and optimization oversight.

Want to know how outbound works alongside this?`,

    outbound: `**The Outbound Hunter** — Intent-Based Lead Sourcing

While your website and ads capture inbound demand, the Outbound Hunter finds buyers **actively signaling intent right now.**

**How it works:**
• AI scans LinkedIn, X/Twitter, and social networks daily
• Identifies prospects posting about problems your business solves — things like "pipeline dried up," "ads aren't converting," "can't find quality leads"
• Drafts hyper-personalized outreach tied to their exact signal phrase
• You review and approve — no spray-and-pray

**This is the highest-ROI vertical for most clients** because you're reaching people at the exact moment they're feeling the pain you solve.

**Included in the Ecosystem tier.** Want to see the full pricing?`,

    process: `**How AltusFlow works — from leaky bucket to growth engine:**

**Step 1 — Strategy call (free)**
We map your biggest revenue leaks and identify which verticals will have the highest impact first.

**Step 2 — Build the Conversion Engine**
Your premium website and AI chat go live. HubSpot CRM is set up and connected.

**Step 3 — Launch the Inbound Magnet**
Meta campaigns go live. UTM tracking ties every lead back to the exact ad that generated it.

**Step 4 — Deploy the Outbound Hunter**
AI starts scanning for intent signals. Personalized pitches are drafted for your review daily.

**Step 5 — Automated reporting**
Live dashboard goes live. Monthly PDF report lands in your inbox on the 1st of every month. Zero manual work.

**Onboarding timeline:** Most clients are fully live within 2 weeks of signing.

Ready to map this to your business? <a href="#contact" class="chat-cta-link">Book your free strategy call →</a>`,

    objection_price: `Totally fair — and the honest answer is we don't quote investment until we understand your situation.

What we do know is that the system typically **replaces 3–4 tools and agencies** most businesses are already paying for separately. For most clients the math works out significantly in their favour once we map it out.

The only way to give you a real number is a 30-minute call where we look at your current setup, identify the gaps, and show you what the ROI actually looks like for your business specifically.

No pressure. No pitch deck. Just a straight conversation.

<a href="#contact" class="chat-cta-link">→ Book your free strategy call</a>`,

    objection_existing: `Great question — **we work with what you have.**

**If you have a website:** We don't replace it. We add the AI chat widget and lead capture on top. Two lines of code. Your site stays exactly as it is.

**If you have a CRM (Salesforce, Pipedrive, etc.):** We sit alongside it. HubSpot handles the AltusFlow reporting layer, and we mirror contacts into your existing CRM via a simple integration. You keep your workflow, we add the automation and reporting on top.

**If you have a Meta Ads account:** We plug into it. We add our campaign structure and UTM taxonomy — your account, your spend, our strategy.

Nothing gets ripped out. Everything gets upgraded.

Want to talk through your specific setup? <a href="#contact" class="chat-cta-link">Book a call →</a>`,

    objection_burned: `That's one of the most common things we hear — and it's fair.

Here's what makes AltusFlow different:

**You own everything.** The CRM data, the ad account, the website. If you leave, you take it all with you. We never hold your assets hostage.

**Standardised delivery.** We don't do bespoke custom projects that go over budget and timeline. We deploy proven templates, apply your branding, and hand you the keys. Scope is defined before we start.

**Automated accountability.** You get a live dashboard and a monthly report with real numbers — not a PDF we wrote ourselves. The data comes straight from HubSpot, not from us.

**No long lock-in.** 3-month initial term, then month-to-month. If we're not delivering, you can leave.

<a href="#contact" class="chat-cta-link">→ Let's talk about what went wrong before and how we'd handle it differently</a>`,

    objection_diy: `You absolutely could build this yourself — here's the honest answer:

The tech exists. HubSpot, Meta Ads, LinkedIn outreach tools, website builders — all available. A skilled team could assemble it in 3–6 months.

**What you're actually buying from AltusFlow:**
• A proven architecture that's already built and tested
• Templates that deploy in days, not months
• Integrations that already work — no debugging
• Ongoing optimization without hiring a team

**The real question is:** what's your team's time worth, and what's the cost of the 3–6 months you're not generating leads while building?

Most clients find the math isn't close. But if you want to explore it, happy to talk through exactly what's involved.

<a href="#contact" class="chat-cta-link">→ Book a call and we'll be straight with you</a>`,

    integration: `**The unfair advantage: one integrated pipeline**

Most businesses buy disconnected tools. AltusFlow clients get **three systems that share data in real time:**

• **Ads → Website:** Campaign traffic lands on conversion-optimised pages with instant AI qualification
• **Chat → Outbound:** Buying signals from your chatbot inform who to target outbound
• **Outbound → Funnels:** Warm prospects hit funnels that already know their pain points
• **Everything → HubSpot:** Every lead, every source, every stage tracked in one CRM
• **HubSpot → Report:** Automated monthly PDF with KPIs, deltas, and recommendations

The result: you're not managing three vendors. You're running one growth engine that works while you sleep.

Which vertical matters most for your business right now?`,

    problem: `**The Leaky Bucket** — sound familiar?

You spend thousands on traffic every month. The pipeline fills up… then nothing happens.

**Common leaks:**
• Website is a passive brochure — can't answer questions at 7 PM Saturday
• Sales team follows up 3 days later — lead already booked a competitor
• Ads drive clicks but landing pages don't convert
• SDRs spend hours on manual research instead of closing

**Every unanswered question, every slow response, every missed after-hours inquiry is revenue pouring out.**

The fix: turn your website into an active, 24/7 automated sales pipeline. Three systems, one CRM, zero manual work.

What's your biggest bottleneck right now — website, ads, or outbound?`,

    icp: `**Who AltusFlow is built for:**

**Best fit:**
• B2B professional services, agencies, consultants, SaaS, financial advisory, IT services
• Revenue $2M–$100M (sweet spot: $5M–$30M)
• Marketing spend $3,000+/month
• Decision-makers: Founder, CEO, CMO, VP Sales, Head of Growth

**Pain signals we look for (need 2+):**
• Traffic without conversion — leaky bucket
• No 24/7 chat on website
• After-hours leads going unanswered
• Low ad ROI / high cost per booked call
• SDRs spending 10+ hours/week on manual research

**Not a fit:**
• Low-ticket e-commerce only
• Businesses under 10 employees with no marketing budget
• Anyone looking for custom bespoke dev work

Does that sound like you? <a href="#contact" class="chat-cta-link">Let's map your gaps →</a>`,

    contact: `**Let's map your revenue gaps — free, 30 minutes.**

Here's what we cover on the call:
• Where your biggest leaks are right now
• Which of the 3 verticals will have the highest impact first
• What the system looks like for your specific business
• Exact investment and timeline

No pitch deck. No hard sell. Just a straight conversation about whether this makes sense for you.

<a href="#contact" class="chat-cta-link">→ Book your free strategy call</a>

Or fill out the form below and we'll reach out within 1 business day.`,

    who: `**AltusFlow is built for high-value B2B businesses** where one booked call equals significant revenue — and losing a lead hurts.

**Great fit:**
• B2B services, agencies, consultants, SaaS
• Companies spending $3k+/month on marketing with weak conversion
• Teams that can't respond to leads 24/7
• Sales leaders tired of SDRs doing manual LinkedIn research

**Not ideal for:**
• Low-ticket e-commerce
• Businesses that don't rely on calls or meetings to close

Does that sound like you? Tell me your industry and I'll share what's most relevant.`,

    lead_sourcing_specialist: `**How the Outbound Hunter sources leads:**

**1. Signal detection** — AI scans LinkedIn, X/Twitter, and social daily for ICP prospects posting about problems you solve. Trigger phrases like "pipeline dried up," "ads aren't converting," "can't find quality leads."

**2. Qualification** — Every prospect must pass:
• Revenue >$2M or marketing spend >$3k/month
• Decision-maker is Founder, C-level, or VP
• Active on social in last 30 days or recent trigger event (funding, new hire, product launch)
• Verified LinkedIn or website

**3. Personalization** — Each qualified lead gets a 1-sentence hook tied to their exact signal:
• "Saw you posted about lead gen struggles last week…"
• "Just hired an SDR — our intent engine replaces the manual research…"
• "Running Meta ads but site has no chat — we plug that leak…"

**4. Delivery** — Pitched sequences delivered to your CRM for review. You approve and send. No spray-and-pray.

This is what we build for clients. Want it running for your pipeline?

<a href="#contact" class="chat-cta-link">→ Book your free strategy call</a>`,

    thanks: `You're welcome! If anything else comes up — pricing, how the system works, or whether you're a good fit — just ask.

When you're ready: <a href="#contact" class="chat-cta-link">book your free strategy call here</a>.`,

    fallback: `Good question. Here's what I can tell you for sure:

AltusFlow.ai builds **integrated growth engines** — not disconnected tools. Our 3 verticals:

1. **AI-powered websites** with native 24/7 chat
2. **Meta ads & sales funnels** for inbound
3. **Intent-based lead sourcing** for outbound

Could you rephrase, or tap one of the quick buttons below? For a detailed answer tailored to your business, <a href="#contact" class="chat-cta-link">book a free strategy call</a> and our team will map your gaps personally.`,
  };

  // ── Niche-aware dynamic responses ────────────────────────────────────────────
  const NICHE_RESPONSES = {
    niche_how_it_works: () => {
      const nd = currentNiche && NICHE_DATA[currentNiche];
      if (!nd) return RESPONSES.outbound;
      return `**How the Outbound Hunter works for ${nd.label}:**

Every morning the system scans LinkedIn, Facebook, and Instagram for ${nd.label} — or their ideal clients — posting pain signals that match what you solve.

**The three steps:**

1. **Scan** — AI searches daily for signal phrases your prospects actually use (see "What signals do you scan for?" for the full list)

2. **Score** — Every result is reviewed for fit. Is this a decision maker? Is the pain real and actionable? Low-confidence results are filtered silently.

3. **Send** — A personalised message is drafted that references their exact post. You review it, click confirm, it goes into HubSpot. Under 2 minutes per lead.

**The economics:** ${nd.deal}.

The system runs every day. It finds people who are already thinking about the problem you solve — and gets your name in front of them first.

Want to see a real example? <a href="#contact" class="chat-cta-link">Or book a 15-minute call →</a>`;
    },

    niche_results: () => {
      const nd = currentNiche && NICHE_DATA[currentNiche];
      if (!nd) return RESPONSES.process;
      return `**What to expect from the Outbound Hunter for ${nd.label}:**

Results depend on your market size, geography, and how quickly you follow up — but here's the honest picture:

**Week 1–2:** Setup, niche calibration, first batch of signals reviewed and confirmed by you.

**Week 3+:** Daily queue of qualified prospects, personalised messages ready for your approval.

**The key metric isn't volume — it's timing.** You're reaching people at the exact moment they're feeling the pain you solve. That changes the conversation entirely.

**The real ROI math:** ${nd.deal}. The system costs a fraction of that. It runs every day. Every client you close from a signal post is pure return on a fixed investment.

Want to map this to your specific numbers?

<a href="#contact" class="chat-cta-link">→ Book a 30-minute strategy call</a>`;
    },

    niche_example: () => {
      const nd = currentNiche && NICHE_DATA[currentNiche];
      if (!nd) return RESPONSES.lead_sourcing_specialist;
      return `**Here's what it looks like in practice for ${nd.label}:**

**The signal post we found:**
${nd.examplePost}

**The message we drafted:**
${nd.exampleReply}

You review it, edit if needed, click confirm. Under 2 minutes. It goes into HubSpot — lead tracked, touchpoint logged.

**Why this works:** The outreach references their exact post. It's not cold. It's not generic. It shows up when the pain is front of mind.

Want to see this running for your pipeline? <a href="#contact" class="chat-cta-link">Book a discovery call →</a>`;
    },

    niche_signals: () => {
      const nd = currentNiche && NICHE_DATA[currentNiche];
      if (!nd) return RESPONSES.lead_sourcing_specialist;
      const signalList = nd.signals.map((s) => `• ${s}`).join('\n');
      return `**The signal phrases we scan for — ${nd.label}:**

${signalList}

The system also catches variations and adjacent language. If someone is publicly expressing the pain you solve — in any form — the scanner is designed to surface it.

**What happens after a signal is found:**
AI scores the post for fit (decision-maker level, pain specificity, recency) and only surfaces high-confidence results. You never see the noise — just the qualified queue.

Want to see what a full drafted message looks like? Just say "show me an example."

<a href="#contact" class="chat-cta-link">Or book a call to see it live →</a>`;
    },
  };

  // ── Intent matching ─────────────────────────────────────────────────────────
  const INTENT_PATTERNS = [
    { intent: 'niche_how_it_works',  patterns: [/how (does|do) (this|it) work for|how.*work.*for (my|us|our)|specific to (my|our) (industry|niche|business)/i] },
    { intent: 'niche_results',       patterns: [/what (result|outcome|return|roi)|how many leads|how fast|what (can|should) i expect|what.*result/i] },
    { intent: 'niche_example',       patterns: [/show me (an?|the)?\s*(example|sample)|example (outreach|message|post|pitch)|what does (it look like|a message look like)/i] },
    { intent: 'niche_signals',       patterns: [/what (signal|trigger|phrase|keyword)|what (do you|does it) scan for|what are you looking for|how do you find (them|prospects|leads)/i] },
    { intent: 'greeting',            patterns: [/^(hi|hello|hey|yo|good\s*(morning|afternoon|evening)|sup)\b/i, /^howdy/i] },
    { intent: 'thanks',              patterns: [/thank/i, /\bthanks\b/i, /appreciate/i, /helpful/i] },
    { intent: 'contact',             patterns: [/book|call|demo|meeting|schedule|talk to|speak with|contact|get started|sign up|strategy|consult/i] },
    { intent: 'pricing',             patterns: [/pric(e|ing)|cost|how much|budget|invest|afford|package|plan|\$\d/i] },
    { intent: 'objection_price',     patterns: [/too expensive|can't afford|tight budget|recession|cut.*spend|expensive/i] },
    { intent: 'objection_existing',  patterns: [/already have|existing (website|crm|hubspot|salesforce|pipedrive)|won't replace|keep my/i] },
    { intent: 'objection_burned',    patterns: [/burned|bad experience|last agency|didn't work|waste.*money|disappointed/i] },
    { intent: 'objection_diy',       patterns: [/do it (myself|ourselves|in.?house)|build it|our (team|dev)|hire internally/i] },
    { intent: 'websites',            patterns: [/website|web\s*site|chatbot|chat\s*bot|ai\s*chat|conversion engine|landing page|storefront|brochure/i] },
    { intent: 'ads',                 patterns: [/meta|facebook|instagram|ad[s]?|funnel|inbound|ppc|campaign|click/i] },
    { intent: 'outbound',            patterns: [/outbound|linkedin|sdr|prospect|outreach|cold|social network|hunter|intent/i] },
    { intent: 'lead_sourcing_specialist', patterns: [/lead sourc|find leads|source leads|personalization|trigger event|signal/i] },
    { intent: 'icp',                 patterns: [/ideal (customer|client)|\bicp\b|target (audience|market)|who is (this|it) for|good fit|right for me/i] },
    { intent: 'integration',         patterns: [/integrat|connect|work together|pipeline|ecosystem|unfair advantage|autonomous|24\/7/i] },
    { intent: 'process',             patterns: [/how (does|do) it work|how long|timeline|process|step|onboard|get started/i] },
    { intent: 'problem',             patterns: [/leaky bucket|leak|losing (revenue|deal|lead)|problem|bottleneck|challenge|struggle/i] },
    { intent: 'who',                 patterns: [/who (is this|do you work with|are your clients)|b2b|saas|agency|consult/i] },
    { intent: 'overview',            patterns: [/what (is|does) altusflow|tell me about|what do you (do|offer)|services|about you/i] },
  ];

  function matchIntent(text) {
    const normalized = text.trim().toLowerCase();
    for (const { intent, patterns } of INTENT_PATTERNS) {
      if (patterns.some((p) => p.test(normalized))) return intent;
    }
    return null;
  }

  function getResponse(intentOrText) {
    if (NICHE_RESPONSES[intentOrText]) return NICHE_RESPONSES[intentOrText]();
    if (RESPONSES[intentOrText]) return RESPONSES[intentOrText];
    const intent = matchIntent(intentOrText);
    if (intent && NICHE_RESPONSES[intent]) return NICHE_RESPONSES[intent]();
    return RESPONSES[intent] || RESPONSES.fallback;
  }

  function formatMessage(text) {
    return text
      .replace(/\*\*(.+?)\*\*/g, '<strong class="text-white font-medium">$1</strong>')
      .replace(/\n/g, '<br>')
      .replace(/• /g, '<span class="text-accent-light">•</span> ');
  }

  // ── HubSpot lead capture ────────────────────────────────────────────────────
  // Collects email mid-conversation and pushes to HubSpot via tracking API
  let capturedEmail = null;
  let capturedName  = null;
  let awaitingEmail = false;
  let chatScore     = 0;
  let currentNiche  = null;

  function incrementScore(intent) {
    const highValue = ['pricing', 'contact', 'process', 'objection_price', 'objection_burned'];
    if (highValue.includes(intent)) chatScore = Math.min(chatScore + 2, 10);
    else chatScore = Math.min(chatScore + 1, 10);
  }

  function pushToHubSpot(email, name) {
    const qualifiedStatus = chatScore >= 7 ? 'AI-Qualified' : 'Unqualified';

    // Client-side HubSpot identify (cookied sessions)
    const _hsq = (window._hsq = window._hsq || []);
    _hsq.push(['identify', {
      email,
      firstname:                       name || '',
      altusflow_lead_source_vertical:  'Conversion Engine',
      altusflow_client_portal_id:      ALTUSFLOW_CLIENT_ID,
      altusflow_lead_qualified_status: qualifiedStatus,
      altusflow_ai_chat_score:         String(chatScore),
    }]);
    _hsq.push(['trackPageView']);

    // Server-side backup — resilient against ad blockers (~40% of B2B traffic)
    const nameParts = (name || '').trim().split(/\s+/);
    fetch('/api/hubspot/contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        email,
        firstName: nameParts[0] || '',
        lastName:  nameParts.slice(1).join(' '),
        utm: {
          altusflow_vertical:              'Conversion Engine',
          altusflow_client_id:             ALTUSFLOW_CLIENT_ID,
          altusflow_ai_chat_score:         chatScore,
          altusflow_lead_qualified_status: qualifiedStatus,
          altusflow_first_touch_campaign:  'AI Chat',
        },
      }),
    }).catch(() => {});

    if (typeof window.__altusflowCapture === 'function') {
      window.__altusflowCapture({ email, firstName: name || '', chatScore, triggerPhrase: '' });
    }
  }

  function askForEmail(addMessageFn) {
    if (capturedEmail || awaitingEmail) return;
    if (chatScore >= 4) {
      awaitingEmail = true;
      const nd = currentNiche && NICHE_DATA[currentNiche];
      const ask = nd
        ? `Before I go further — **what's the best email to send you a breakdown of how this works for ${nd.label} specifically?** (Your name too, so it doesn't land like a newsletter)`
        : `Before I go further — **what's your name and best email?** I'll put together a personalised systems analysis based on what we've discussed.`;
      setTimeout(() => { addMessageFn(ask, 'bot'); }, 800);
    }
  }

  function handleEmailCapture(text, addMessageFn) {
    const emailRegex = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/;
    const match = text.match(emailRegex);
    if (match) {
      capturedEmail = match[0];
      awaitingEmail = false;
      // Extract name from the text — anything that isn't the email address
      const nameCandidate = text.replace(emailRegex, '').replace(/[,\s]+/g, ' ').trim();
      if (nameCandidate && nameCandidate.length > 1 && nameCandidate.length < 60) {
        capturedName = nameCandidate;
      }
      pushToHubSpot(capturedEmail, capturedName);
      const greeting = capturedName ? `Thanks, ${capturedName.split(' ')[0]}!` : 'Got it!';
      addMessageFn(`${greeting} Our team will follow up at ${capturedEmail} within 1 business day.\n\nIn the meantime, <a href="#contact" class="chat-cta-link">fill out the full intake form here</a> to speed up your strategy call booking.`, 'bot');
      return true;
    }
    return false;
  }

  // ── DOM refs ────────────────────────────────────────────────────────────────
  let panel, messagesEl, inputEl, toggleBtn, closeBtn, sendBtn, quickActionsEl;

  function scrollToBottom() {
    requestAnimationFrame(() => { messagesEl.scrollTop = messagesEl.scrollHeight; });
  }

  function addMessage(content, role) {
    const wrap   = document.createElement('div');
    wrap.className = role === 'user' ? 'flex justify-end' : 'flex justify-start';
    const bubble = document.createElement('div');
    if (role === 'user') {
      bubble.className = 'max-w-[85%] rounded-2xl rounded-br-md bg-accent px-4 py-3 text-sm leading-relaxed text-white';
      bubble.textContent = content;
    } else {
      bubble.className = 'max-w-[90%] rounded-2xl rounded-bl-md glass px-4 py-3 text-sm leading-relaxed text-zinc-300';
      bubble.innerHTML = formatMessage(content);
      bubble.querySelectorAll('a.chat-cta-link').forEach((link) => {
        link.addEventListener('click', () => closePanel());
      });
    }
    wrap.appendChild(bubble);
    messagesEl.appendChild(wrap);
    scrollToBottom();
  }

  function showTyping() {
    const el = document.createElement('div');
    el.id = 'chat-typing';
    el.className = 'flex justify-start';
    el.innerHTML = `<div class="glass flex items-center gap-1.5 rounded-2xl rounded-bl-md px-4 py-3">
      <span class="chat-typing-dot"></span>
      <span class="chat-typing-dot" style="animation-delay:0.15s"></span>
      <span class="chat-typing-dot" style="animation-delay:0.3s"></span>
    </div>`;
    messagesEl.appendChild(el);
    scrollToBottom();
    return el;
  }

  function removeTyping() { document.getElementById('chat-typing')?.remove(); }

  function botReply(intentOrText, isIntent) {
    const intent = isIntent ? intentOrText : matchIntent(intentOrText);
    if (intent) incrementScore(intent);
    const typing = showTyping();
    const delay  = 600 + Math.random() * 400;
    setTimeout(() => {
      removeTyping();
      addMessage(getResponse(intentOrText), 'bot');
      renderQuickActions();
      askForEmail(addMessage);
    }, delay);
  }

  function handleUserMessage(text) {
    const trimmed = text.trim();
    if (!trimmed) return;
    addMessage(trimmed, 'user');
    inputEl.value  = '';
    sendBtn.disabled = true;
    quickActionsEl.innerHTML = '';

    // Update niche from message keywords if not already set
    if (!currentNiche) {
      const detected = detectNicheFromText(trimmed);
      if (detected) setNiche(detected);
    }

    // Check if awaiting email
    if (awaitingEmail) {
      const handled = handleEmailCapture(trimmed, addMessage);
      if (handled) {
        setTimeout(() => { sendBtn.disabled = false; inputEl.focus(); }, 1200);
        return;
      }
    }

    botReply(trimmed, false);
    setTimeout(() => { sendBtn.disabled = false; inputEl.focus(); }, 1200);
  }

  function renderQuickActions() {
    quickActionsEl.innerHTML = '';
    getQuickActions().forEach(({ label, intent }) => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'chat-quick-btn shrink-0 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-xs font-medium text-zinc-300 transition hover:border-accent/30 hover:bg-accent/10 hover:text-white';
      btn.textContent = label;
      btn.addEventListener('click', () => {
        addMessage(label, 'user');
        quickActionsEl.innerHTML = '';
        incrementScore(intent);
        const typing = showTyping();
        setTimeout(() => {
          removeTyping();
          addMessage(getResponse(intent), 'bot');
          renderQuickActions();
          askForEmail(addMessage);
        }, 700);
      });
      quickActionsEl.appendChild(btn);
    });
  }

  function openPanel()  {
    panel.classList.remove('hidden');
    panel.classList.add('chat-panel-open');
    toggleBtn.classList.add('hidden');
    inputEl.focus();
  }

  function closePanel() {
    panel.classList.remove('chat-panel-open');
    panel.classList.add('hidden');
    toggleBtn.classList.remove('hidden');
  }

  function init() {
    panel          = document.getElementById('chat-panel');
    messagesEl     = document.getElementById('chat-messages');
    inputEl        = document.getElementById('chat-input');
    toggleBtn      = document.getElementById('chat-toggle');
    closeBtn       = document.getElementById('chat-close');
    sendBtn        = document.getElementById('chat-send');
    quickActionsEl = document.getElementById('chat-quick-actions');

    if (!panel) return;

    // Detect niche: sessionStorage → URL path
    (function () {
      const stored = sessionStorage.getItem('altusflow_niche');
      if (stored && NICHE_DATA[stored]) { currentNiche = stored; return; }
      const match = window.location.pathname.match(/\/for\/([^/]+)/);
      if (match && NICHE_DATA[match[1]]) setNiche(match[1]);
    })();

    toggleBtn.addEventListener('click', openPanel);
    closeBtn.addEventListener('click', closePanel);
    sendBtn.addEventListener('click', () => handleUserMessage(inputEl.value));
    inputEl.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleUserMessage(inputEl.value); }
    });
    inputEl.addEventListener('input', () => { sendBtn.disabled = !inputEl.value.trim(); });

    // Welcome message on first open
    let welcomed = false;
    toggleBtn.addEventListener('click', () => {
      if (!welcomed) {
        welcomed = true;
        setTimeout(() => { addMessage(RESPONSES.greeting, 'bot'); renderQuickActions(); }, 300);
      }
    });

    // Auto-open from hero CTA
    document.querySelectorAll('a[href="#chatbot-demo"]').forEach((link) => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        openPanel();
        if (!welcomed) {
          welcomed = true;
          setTimeout(() => { addMessage(RESPONSES.greeting, 'bot'); renderQuickActions(); }, 300);
        }
        document.getElementById('chatbot-demo')?.scrollIntoView({ behavior: 'smooth' });
      });
    });

    // Proactive trigger — auto-open after 15s if visitor hasn't engaged (once per session)
    if (!sessionStorage.getItem('af_chat_triggered')) {
      setTimeout(() => {
        if (panel.classList.contains('chat-panel-open')) return;
        sessionStorage.setItem('af_chat_triggered', '1');
        openPanel();
        if (!welcomed) {
          welcomed = true;
          const nd = currentNiche && NICHE_DATA[currentNiche];
          const proactiveMsg = nd
            ? `Hey 👋 — I see you're exploring how AltusFlow works for **${nd.label}**. What would you like to know first?`
            : `Hey 👋 — quick question: **what's your biggest growth bottleneck right now?** Website conversions, ad performance, or finding qualified leads?`;
          setTimeout(() => { addMessage(proactiveMsg, 'bot'); renderQuickActions(); }, 400);
        }
      }, 15000);
    }

    // Load HubSpot tracking pixel
    if (HUBSPOT_PORTAL_ID && !document.getElementById('hs-script')) {
      const s  = document.createElement('script');
      s.id     = 'hs-script';
      s.src    = `//js.hs-scripts.com/${HUBSPOT_PORTAL_ID}.js`;
      s.async  = true;
      s.defer  = true;
      document.head.appendChild(s);
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
