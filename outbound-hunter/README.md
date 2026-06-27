# AltusFlow Outbound Hunter

Scans X/Twitter and LinkedIn daily for finance prospects posting pain signals.
Drafts hyper-personalised outreach using their exact post text via Claude API.
You review, approve, and send. Every prospect's post is stored so you can reference it on calls.

---

## Setup (one-time, ~20 minutes)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Add your API keys
```bash
cp .env.example .env
```
Open `.env` and fill in:
- `ANTHROPIC_API_KEY` — console.anthropic.com → API Keys
- `TWITTER_BEARER_TOKEN` — developer.twitter.com (Basic plan $100/mo or Academic Research)
- `APIFY_API_TOKEN` — console.apify.com → Settings → Integrations

### 3. Initialise the database
```bash
python database.py
```

### 4. Run the hunter
```bash
python main.py              # full run (Twitter + LinkedIn)
python main.py --twitter    # Twitter only
python main.py --linkedin   # LinkedIn only
```

### 5. Open the review UI
```bash
python app.py
```
Open http://localhost:5000 in your browser.

---

## Daily workflow

1. Run `python main.py` (or let the scheduler do it at 8 AM)
2. Open http://localhost:5000
3. Review each prospect — read their exact post, tweak the message if needed
4. Click Approve for the ones you want to reach out to
5. Click Export CSV to get your queue
6. Send the messages manually on LinkedIn/X (copy-paste from the queue)
7. After sending, mark as Sent in the UI

---

## On discovery calls

Every prospect's exact post text is stored in the database. Before any call, open the prospect's record and you'll have:
- Their exact words from the post
- The date they posted it
- The platform
- Their title and company

Use this on the call: "Hey [Name] — I saw your post on [date] where you said [exact quote]. That's exactly the kind of thing we solve..."

---

## Scheduling (Windows Task Scheduler)

1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 8:00 AM
4. Action: Start a program
5. Program: `python`
6. Arguments: `C:\path\to\outbound-hunter\main.py`
7. Start in: `C:\path\to\outbound-hunter\`

---

## File structure

```
outbound-hunter/
├── main.py              — orchestrator (run this)
├── app.py               — review UI + admin routes (run this separately)
├── orchestrator.py      — pod orchestrator (opt-in via USE_POD_ORCHESTRATOR=true)
├── database.py          — SQLite storage (pod tables, DNC, dispatched events)
├── qualify.py           — ICP scoring
├── drafter.py           — Claude API message generation
├── core/
│   ├── BaseHunter.py    — parent class all pod hunters extend
│   ├── EventDispatcher.py — consent gate, PII hashing, HubSpot/Meta/Calendly dispatch
│   └── DNC.py           — DNC scrubber (per-user and global)
├── pods/
│   ├── _template/       — copy this to build a new pod (do not run directly)
│   ├── financial-advisors/
│   ├── business-coaches/
│   ├── recruiters/
│   ├── commercial-real-estate/
│   ├── msps/
│   └── altusflow-own/
├── scrapers/
│   ├── linkedin.py      — LinkedIn via Apify
│   ├── facebook.py      — Facebook Groups via Apify
│   ├── reddit.py        — Reddit via Apify
│   └── niches/          — per-niche keyword/ICP config modules
├── templates/
│   ├── digest.html      — review dashboard UI
│   └── admin_pods.html  — pod admin UI (/admin/pods)
├── exports/
│   └── queue.csv        — approved prospects (auto-generated)
├── .env.example         — API key template
├── .env                 — your keys (never commit this)
└── requirements.txt
```

---

## Deploying a New Pod

Follow these 10 steps to add a new niche pod to the factory. The entire process takes about 30 minutes using the `_template/` pod as a starting point.

### Step 1 — Create the pod directory

```bash
cp -r pods/_template/ pods/your-niche-name/
```

Use a lowercase hyphenated slug that matches the niche module in `scrapers/niches/`. Example: `financial-advisors`, `msps`, `commercial-real-estate`.

### Step 2 — Register the niche module

Open `scrapers/niches/__init__.py`. Confirm your niche slug exists in `_NICHE_MAP`. If not, create `scrapers/niches/your_niche.py` with at minimum:

```python
NICHE_SLUG     = "your-niche-name"
NICHE_LABEL    = "Human Readable Name"
PLATFORM_WEIGHT = {"linkedin": 0.5, "facebook": 0.4, "reddit": 0.3}
SEARCH_QUERIES  = ["pain signal 1", "pain signal 2"]
```

Then add it to `ALL_NICHES` in `__init__.py`.

### Step 3 — Write the hunter.py

Create `pods/your-niche-name/hunter.py` by extending `BaseHunter`:

```python
from core.BaseHunter import BaseHunter

class YourNicheHunter(BaseHunter):
    POD_SLUG = "your-niche-name"

    def scan(self) -> list:
        # call scrapers.linkedin/facebook/reddit run_niche_search()
        ...

    def qualify(self, prospect: dict) -> tuple:
        # enforce niche-specific abort conditions first
        # then: from qualify import score_prospect; return score_prospect(...)
        ...
```

Key rules:
- `qualify()` returns `(0, reason_string)` to abort, or `(score, notes)` to pass through
- Call `from qualify import score_prospect` as the final step — never rewrite scoring logic
- Never call external APIs (HubSpot, Apify) directly in `qualify()` — except for the AltusFlow Own pod's HubSpot dedup check

### Step 4 — Write bootstrap.py

Copy `pods/financial-advisors/bootstrap.py` verbatim, change only `POD_SLUG`. Run it standalone to verify all 5 checks pass before proceeding:

```bash
python pods/your-niche-name/bootstrap.py
```

### Step 5 — Write heartbeat.py

Copy `pods/financial-advisors/heartbeat.py`, change `POD_SLUG` and the hunter import line:

```python
from hunter import YourNicheHunter
hunter = YourNicheHunter(run_id=run_id)
```

### Step 6 — Fill in the config files

Edit these five files with niche-specific content:

| File | What to change |
|------|---------------|
| `identity.md` | Who you're looking for, who you're NOT looking for, ICP profile |
| `soul.md` | Example of a perfect qualifying post, abort conditions explained, message tone |
| `tasks.json` | `schedule` (cron), `max_approvals_per_run`, `platforms_priority`, search queries |
| `tools.json` | Platform priorities, rate limits, HubSpot/Calendly config |
| `user.md` | Client name, Client ID, HubSpot portal/sequence IDs, deal economics |

### Step 7 — Write pod-specific tests

Add at least one test to `test_factory.py` that verifies the pod's primary abort condition works:

```python
def test_your_niche_hunter_rejects_[abort_condition](self):
    # Load hunter via importlib (handles hyphenated dir names)
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "your_hunter",
        os.path.join(_ROOT, "pods", "your-niche-name", "hunter.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    mock_niche = _make_mock_niche("your-niche-name")
    with patch("scrapers.niches.get_niche", return_value=mock_niche):
        spec.loader.exec_module(mod)
    hunter = mod.YourNicheHunter.__new__(mod.YourNicheHunter)
    hunter._niche = mock_niche
    hunter.run_id = "test"
    # Assert abort condition...
```

### Step 8 — Run the full test suite

```bash
python test_factory.py -v
```

All 24 existing tests plus your new test(s) must pass before deploying.

### Step 9 — Enable the pod orchestrator

Set `USE_POD_ORCHESTRATOR=true` in your `.env`. Start the app:

```bash
python app.py
```

Navigate to `/admin/pods` and confirm your new pod appears with status "Running" (or "not_run" if it hasn't fired yet).

### Step 10 — Trigger a test run

From `/admin/pods/your-niche-name`, click **Run Now**. Watch the run history table populate. Confirm:

- [ ] Pod appears in `/admin/pods` grid
- [ ] `bootstrap.validate()` passes (check logs if not)
- [ ] `heartbeat.status()` returns valid data contract JSON
- [ ] Abort conditions fire correctly on test prospects
- [ ] Qualified prospects appear in the review dashboard
- [ ] HubSpot push works for a manually approved prospect

---

## Pod admin UI

When `USE_POD_ORCHESTRATOR=true` and `ADMIN_EMAIL` is set, the pod admin panel is available at:

```
/admin/pods                    — all pods grid view
/admin/pods/{slug}             — pod detail + run history
```

Actions available per pod:
- **Pause / Resume** — stop a pod from running on schedule
- **Reset** — clear circuit breaker after fixing a root cause
- **Run Now** — trigger an immediate run outside the schedule

Access requires the request to come from the `ADMIN_EMAIL` address (checked via Flask session).

---

## Circuit breaker behaviour

Each pod has a circuit breaker that opens after **3 consecutive errors**. When open:
- The pod stops running until an operator calls Reset
- An alert is sent (configure `error_logger.py` for Slack/email)
- The pod status shows "Circuit Open" in the admin UI

The high-volume guard is a separate protection: if any single run auto-approves **more than 50 prospects**, the circuit opens immediately and the run status is marked `paused_high_volume`. This prevents a misconfigured query from flooding a client's HubSpot.

To reset either condition: `/admin/pods/{slug}` → **Reset**.

---

## Architecture Overview

AltusFlow Outbound Hunter uses a pod-based factory architecture.

```
outbound-hunter/
├── core/
│   ├── BaseHunter.py       — parent class all pods inherit
│   ├── EventDispatcher.py  — ALL data egress passes through here
│   └── DNC.py              — global do not contact registry
├── pods/
│   ├── _template/          — 7-file template for new pods
│   ├── financial-advisors/ — FA niche pod
│   ├── business-coaches/   — coach niche pod
│   ├── recruiters/         — recruiter niche pod
│   ├── commercial-real-estate/ — CRE niche pod
│   ├── msps/               — MSP niche pod
│   └── altusflow-own/      — AltusFlow's own prospecting
├── skills/
│   ├── apify-scraper/      — OpenClaw skill for Apify
│   ├── hubspot-crm/        — OpenClaw skill for HubSpot
│   ├── claude-drafter/     — OpenClaw skill for Claude API
│   └── meta-audiences/     — OpenClaw skill for Meta
├── orchestrator.py         — master controller
├── app.py                  — Flask web UI
└── test_factory.py         — test suite (29+ tests)
```

### Data flow

```
Platform post → Scraper → BaseHunter.pre_flight_check() → qualify() → draft()
     ↓                          ↓ (DNC block)
EventDispatcher ──────── consent check ──── PII hash ──── HubSpot / Meta push
     ↓                                                           ↓
dispatched_events (dedup)                              prospects table
```

---

## How the EventDispatcher protects your data

Every piece of data leaving the system — to HubSpot, Meta, Apify —
passes through EventDispatcher. It:

1. **Checks `consent_granted`** — drops event if False, never transmits
2. **SHA-256 hashes all PII** before any external API call
3. **Generates a deterministic event_id** (UUID5) to prevent duplicate pushes
4. **Logs every dispatched event** with timestamp for audit trail

No pod may call an external API directly. Everything goes through `dispatch()`.

---

## Adding a Client to an Existing Pod

To run the Financial Advisors pod for a new client:

1. Open `pods/financial-advisors/user.md`
2. Update the client fields (Company name, Client ID, HubSpot portal/sequence IDs)
3. The pod now prospects for that client
4. Restart the app — the pod picks up the new config on next heartbeat

To run **multiple clients simultaneously on the same niche**: create a second pod directory:

```bash
cp -r pods/financial-advisors/ pods/financial-advisors-clientb/
```

Then update `pods/financial-advisors-clientb/user.md` with the second client's details and `tasks.json` with a different run schedule to avoid rate limit collisions.

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Claude API for drafting |
| `HUBSPOT_TOKEN` | Yes | Default HubSpot token (agency) |
| `APIFY_API_TOKEN` | Yes | Default Apify token (agency) |
| `REDDIT_CLIENT_ID` | Yes | Reddit PRAW API |
| `REDDIT_CLIENT_SECRET` | Yes | Reddit PRAW API |
| `REDDIT_USER_AGENT` | Yes | e.g. `AltusFlowHunter/1.0` |
| `META_ACCESS_TOKEN` | Optional | Meta Custom Audience sync |
| `META_AD_ACCOUNT_ID` | Optional | Meta ad account |
| `ALERT_WEBHOOK_URL` | Optional | Slack/Make alert destination |
| `USE_POD_ORCHESTRATOR` | Optional | `true` = orchestrator, `false` = legacy scheduler |
| `SECRET_KEY` | Yes | Fernet encryption for stored tokens |
| `DATABASE_URL` | Yes (prod) | PostgreSQL connection string |
| `ADMIN_EMAIL` | Yes | Email address that can access `/admin/pods/*` |
| `TWILIO_ACCOUNT_SID` | Optional | Call recording |
| `TWILIO_AUTH_TOKEN` | Optional | Call recording |
| `OPENAI_API_KEY` | Optional | Whisper transcription |

---

## Troubleshooting Common Issues

**Pod shows as 'error' in /admin/pods:**
1. Click pod name → view last run logs
2. Check `error_log` field for specific error
3. Common causes: API token expired, Apify credits exhausted, HubSpot rate limit
4. Fix the underlying issue → click Reset → pod resumes

**Circuit breaker tripped:**
1. Check the alert webhook for error details
2. Fix the root cause (usually an expired API token or rate limit)
3. Go to `/admin/pods/[slug]` → **Reset**
4. Monitor next run carefully

**Prospects not appearing in batch confirm:**
1. Check `/admin/pods/[slug]/logs` — were prospects found?
2. If found but not appearing: check auto_router confidence scores
3. Scores below 4 are auto-skipped — check `qualify()` logic in pod
4. Check DNC list — prospect may be blocked

**HubSpot push failing:**
1. Check `dispatched_events` table for error details
2. Verify `HUBSPOT_TOKEN` has `crm.objects.contacts.write` permission
3. Check if all 7 custom properties exist in the portal
4. Retry button in batch confirm UI re-attempts the push

**AltusFlow own pod not qualifying anyone:**
1. Check that `HUBSPOT_TOKEN` is set — HubSpot dedup check fails open (passes through) if token is missing, but logs a warning
2. Min score is 8 (vs 4 for client pods) — check scoring in `qualify.py`
3. Confirm prospects are in one of the 5 target niches — niche gate is strict

---

## Running on Windows (local mode)

Reddit-only launch mode — no Railway, no cloud, runs on your machine.

### Quick start

Double-click **`start-altusflow.bat`** in the project root.

App starts at [http://localhost:5000](http://localhost:5000)
Reddit scanner runs at **6:00 AM** daily.
Digest email (if configured) sends at **6:30 AM**.

### First-time setup

```bat
cd C:\Users\ghhoc\Projects\AltusFlow\outbound-hunter
python -m venv venv
venv\Scripts\pip install -r requirements.txt
copy .env.local .env
```

Fill in `.env`: `ANTHROPIC_API_KEY`, `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `HUBSPOT_TOKEN`, `SECRET_KEY`, `FLASK_SECRET`.

```bat
venv\Scripts\python database.py       # initialise DB
venv\Scripts\python create_admin.py   # create login account
```

### Daily workflow

| Time | What happens |
|------|-------------|
| 6:00 AM | Reddit scanner runs automatically |
| 6:30 AM | Digest email sent (if configured) |
| ~6:15 AM | Open http://localhost:5000 to review |

1. Go to **Batch Confirm** tab — auto-approved prospects (score 9+)
2. Click **Approve all 7+ ⚡** for one-click batch push to HubSpot
3. Review remaining pending cards manually
4. Click **Export CSV** to download approved queue for manual outreach

### Option 2 — Auto-start with Windows Task Scheduler

Start the app automatically each morning without opening anything.

1. Press `Windows + R` → type `taskschd.msc` → Enter
2. Click **Create Basic Task** → Name: `AltusFlow Hunter` → Next
3. Trigger: **Daily** → Start time: **5:50 AM** (10 min before scanner runs) → Next
4. Action: **Start a program** → Next
5. Program/script: `C:\Users\ghhoc\Projects\AltusFlow\start-altusflow.bat`
6. Finish → OK

The app starts at 5:50 AM, scanner runs at 6:00 AM, open http://localhost:5000 at 6:15 AM to review results.

### Activating more platforms (when ready)

| Platform | Add to .env | What unlocks |
|----------|-------------|-------------|
| `APIFY_API_TOKEN` | After first client | LinkedIn + Facebook scraping |
| `META_ACCESS_TOKEN` | When Meta ads are live | Custom Audience sync |
| `VAPI_API_KEY` + `TWILIO_*` | When voice is activated | Morgan AI receptionist |
| `SENDGRID_API_KEY` or `SMTP_*` + `DIGEST_EMAIL_TO` | Any time | Daily email digest |

No code changes needed — each platform activates automatically when its key is present.

---

## OpenClaw Integration (Future)

When ready to integrate OpenClaw (at 5+ pods running in production):

1. Install OpenClaw gateway: `npm install -g @openclaw/gateway`
2. Start gateway: `openclaw gateway start`
3. Register skills: `openclaw skills install ./skills/`
4. Update `orchestrator.py` to route through OpenClaw gateway instead of direct Python calls
5. Each pod's `tools.json` already defines the allowed tools — OpenClaw enforces these

The `skills/` directory contains SKILL.md files ready for OpenClaw:

| Skill | File | Purpose |
|-------|------|---------|
| apify-scraper | `skills/apify-scraper/SKILL.md` | LinkedIn/Facebook/Reddit scraping via Apify |
| hubspot-crm | `skills/hubspot-crm/SKILL.md` | Contact upsert, deals, notes |
| claude-drafter | `skills/claude-drafter/SKILL.md` | Personalised message generation |
| meta-audiences | `skills/meta-audiences/SKILL.md` | Custom Audience sync for retargeting |

No code changes needed to the pods themselves when OpenClaw is connected — the hunter.py and heartbeat.py files remain unchanged. Only `orchestrator.py` gains a thin routing layer to call skills via the OpenClaw gateway instead of direct Python imports.
