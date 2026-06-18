/**
 * AltusFlow.ai — AI Sales Assistant v2
 * Full business bible: pricing, tiers, objection handling, HubSpot capture.
 */
(function () {
  'use strict';

  // ── Config ──────────────────────────────────────────────────────────────────
  const HUBSPOT_PORTAL_ID = '246530361';
  const ALTUSFLOW_CLIENT_ID = 'ALT00';

  // ── Quick action buttons ────────────────────────────────────────────────────
  const QUICK_ACTIONS = [
    { label: 'What does AltusFlow do?',   intent: 'overview' },
    { label: 'Is this right for me?',      intent: 'icp' },
    { label: 'AI-powered websites',       intent: 'websites' },
    { label: 'Meta ads & funnels',        intent: 'ads' },
    { label: 'Outbound lead sourcing',    intent: 'outbound' },
    { label: 'Book a strategy call',      intent: 'contact' },
  ];

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

  // ── Intent matching ─────────────────────────────────────────────────────────
  const INTENT_PATTERNS = [
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
    if (RESPONSES[intentOrText]) return RESPONSES[intentOrText];
    const intent = matchIntent(intentOrText);
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

  function incrementScore(intent) {
    const highValue = ['pricing', 'contact', 'process', 'objection_price', 'objection_burned'];
    if (highValue.includes(intent)) chatScore = Math.min(chatScore + 2, 10);
    else chatScore = Math.min(chatScore + 1, 10);
  }

  function pushToHubSpot(email, name) {
    // HubSpot identify via tracking cookie
    const _hsq = (window._hsq = window._hsq || []);
    _hsq.push(['identify', {
      email,
      firstname:                       name || '',
      altusflow_lead_source_vertical:  'Conversion Engine',
      altusflow_client_portal_id:      ALTUSFLOW_CLIENT_ID,
      altusflow_lead_qualified_status: chatScore >= 7 ? 'AI-Qualified' : 'Unqualified',
      altusflow_ai_chat_score:         String(chatScore),
    }]);
    _hsq.push(['trackPageView']);

    // Also fire window.__altusflowCapture if the full integration is wired
    if (typeof window.__altusflowCapture === 'function') {
      window.__altusflowCapture({
        email,
        firstName: name || '',
        chatScore,
        triggerPhrase: '',
      });
    }
  }

  function askForEmail(addMessageFn) {
    if (capturedEmail || awaitingEmail) return;
    if (chatScore >= 4) {
      awaitingEmail = true;
      setTimeout(() => {
        addMessageFn(`Before I go further — what's the best email to send you a personalised systems analysis? I can pull together a tailored breakdown based on what we've discussed.`, 'bot');
      }, 800);
    }
  }

  function handleEmailCapture(text, addMessageFn) {
    const emailRegex = /[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}/;
    const match = text.match(emailRegex);
    if (match) {
      capturedEmail = match[0];
      awaitingEmail = false;
      pushToHubSpot(capturedEmail, capturedName);
      addMessageFn(`Got it — I've noted ${capturedEmail}. Our team will follow up with a personalised analysis within 1 business day.\n\nIn the meantime, <a href="#contact" class="chat-cta-link">fill out the full intake form here</a> to speed up your strategy call booking.`, 'bot');
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
    QUICK_ACTIONS.forEach(({ label, intent }) => {
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
