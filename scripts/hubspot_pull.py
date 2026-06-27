"""
hubspot_pull.py
Pulls all data needed for the AltusFlow monthly PDF report from HubSpot.
Outputs a report_data.json file consumed by generate_report.py.

Required env vars:
  HUBSPOT_TOKEN   — HubSpot private app token
  CLIENT_ID       — e.g. RBT01
  CLIENT_NAME     — e.g. Redbox Talent
  REPORT_MONTH    — e.g. June 2025  (auto-set by GitHub Actions if not provided)
"""

import os, json, datetime, sys
import urllib.request, urllib.parse, urllib.error

# ── Config ─────────────────────────────────────────────────────────────────────
TOKEN       = os.environ["HUBSPOT_TOKEN"]
CLIENT_ID   = os.environ.get("CLIENT_ID",    "RBT01")
CLIENT_NAME = os.environ.get("CLIENT_NAME",  "Redbox Talent")

now = datetime.date.today().replace(day=1)          # first of current month
prev = (now - datetime.timedelta(days=1)).replace(day=1)

REPORT_MONTH = os.environ.get(
    "REPORT_MONTH",
    now.strftime("%B %Y")   # e.g. "June 2025"
)

# month window as epoch-ms (HubSpot filter format)
def month_range(d):
    start = int(datetime.datetime(d.year, d.month, 1).timestamp() * 1000)
    if d.month == 12:
        end_dt = datetime.datetime(d.year + 1, 1, 1)
    else:
        end_dt = datetime.datetime(d.year, d.month + 1, 1)
    end = int(end_dt.timestamp() * 1000)
    return start, end

THIS_START, THIS_END   = month_range(now)
PREV_START, PREV_END   = month_range(prev)

BASE = "https://api.hubapi.com"
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type":  "application/json",
}

# ── HTTP helpers ───────────────────────────────────────────────────────────────
def hs_post(path, payload):
    url  = BASE + path
    data = json.dumps(payload).encode()
    req  = urllib.request.Request(url, data=data, headers=HEADERS, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def hs_get(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

# ── Query helpers ──────────────────────────────────────────────────────────────
ALTUS_VERTICAL   = "altusflow_lead_source_vertical"
ALTUS_PORTAL     = "altusflow_client_portal_id"
ALTUS_QUAL       = "altusflow_lead_qualified_status"
ALTUS_TRIGGER    = "altusflow_outbound_trigger_phrase"
ALTUS_MTG_DATE   = "altusflow_meeting_booked_date"

PIPELINE_STAGES = [
    "New Lead — Unworked",
    "AI Qualified — Awaiting Human Review",
    "Meeting Booked",
    "Meeting Held — Proposal Sent",
    "Closed Won",
    "Closed Lost — Nurture",
]

def search_contacts(start_ms, end_ms):
    """All contacts created for this client in the given window."""
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "createdate",       "operator": "BETWEEN",    "highValue": str(end_ms),   "value": str(start_ms)},
                {"propertyName": ALTUS_PORTAL,       "operator": "EQ",         "value": CLIENT_ID},
            ]
        }],
        "properties": ["createdate", ALTUS_VERTICAL, ALTUS_QUAL,
                       ALTUS_TRIGGER, ALTUS_MTG_DATE, "firstname", "lastname",
                       "company", "hs_lead_status"],
        "limit": 200,
    }
    results = []
    after   = None
    while True:
        if after:
            payload["after"] = after
        resp = hs_post("/crm/v3/objects/contacts/search", payload)
        results.extend(resp.get("results", []))
        paging = resp.get("paging", {}).get("next", {})
        after  = paging.get("after")
        if not after:
            break
    return results

def search_deals(start_ms, end_ms):
    """All deals created for this client in the given window."""
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": "createdate",  "operator": "BETWEEN", "highValue": str(end_ms), "value": str(start_ms)},
                {"propertyName": ALTUS_PORTAL,  "operator": "EQ",      "value": CLIENT_ID},
            ]
        }],
        "properties": ["dealname", "dealstage", "amount", "closedate",
                       "createdate", ALTUS_VERTICAL, ALTUS_PORTAL],
        "limit": 200,
    }
    results = []
    after   = None
    while True:
        if after:
            payload["after"] = after
        resp = hs_post("/crm/v3/objects/deals/search", payload)
        results.extend(resp.get("results", []))
        paging = resp.get("paging", {}).get("next", {})
        after  = paging.get("after")
        if not after:
            break
    return results

def get_all_open_deals():
    """All open deals for pipeline snapshot (not window-filtered)."""
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": ALTUS_PORTAL, "operator": "EQ", "value": CLIENT_ID},
                {"propertyName": "dealstage",  "operator": "NOT_IN",
                 "values": ["Closed Won", "Closed Lost — Nurture"]},
            ]
        }],
        "properties": ["dealstage", "amount", ALTUS_VERTICAL],
        "limit": 200,
    }
    results = []
    after   = None
    while True:
        if after:
            payload["after"] = after
        resp = hs_post("/crm/v3/objects/deals/search", payload)
        results.extend(resp.get("results", []))
        paging = resp.get("paging", {}).get("next", {})
        after  = paging.get("after")
        if not after:
            break
    return results

def get_outbound_recent(limit=10):
    """Most recent Outbound Hunter contacts with trigger phrases."""
    payload = {
        "filterGroups": [{
            "filters": [
                {"propertyName": ALTUS_PORTAL,   "operator": "EQ",            "value": CLIENT_ID},
                {"propertyName": ALTUS_VERTICAL, "operator": "EQ",            "value": "Outbound Hunter"},
                {"propertyName": ALTUS_TRIGGER,  "operator": "HAS_PROPERTY"},
            ]
        }],
        "properties": ["firstname", "lastname", "company", "jobtitle",
                       ALTUS_TRIGGER, "hs_lead_status", "createdate"],
        "sorts": [{"propertyName": "createdate", "direction": "DESCENDING"}],
        "limit": limit,
    }
    resp = hs_post("/crm/v3/objects/contacts/search", payload)
    return resp.get("results", [])

# ── Calculation helpers ────────────────────────────────────────────────────────
def safe_div(a, b):
    return round(a / b * 100, 1) if b else 0

def delta_str(curr, prev_val, fmt=None):
    if prev_val == 0:
        return ("—", "flat")
    diff = curr - prev_val
    pct  = round(diff / prev_val * 100)
    sign = "+" if pct >= 0 else ""
    if fmt == "pct":
        pts = round(curr - prev_val, 1)
        sign2 = "+" if pts >= 0 else ""
        return (f"{sign2}{pts}pts", "up" if pts >= 0 else "down")
    return (f"{sign}{pct}%", "up" if pct >= 0 else "down")

# ── Main ───────────────────────────────────────────────────────────────────────
def main():
    print(f"Pulling HubSpot data for {CLIENT_NAME} ({CLIENT_ID}) — {REPORT_MONTH}")

    this_contacts = search_contacts(THIS_START, THIS_END)
    prev_contacts = search_contacts(PREV_START, PREV_END)
    this_deals    = search_deals(THIS_START, THIS_END)
    prev_deals    = search_deals(PREV_START, PREV_END)
    open_deals    = get_all_open_deals()
    outbound_rows = get_outbound_recent(10)

    # ── KPI calculations ──────────────────────────────────────────────────────
    leads_this = len(this_contacts)
    leads_prev = len(prev_contacts)

    def stage_count(deals, stage_name):
        return sum(1 for d in deals
                   if d["properties"].get("dealstage","").strip().lower()
                      == stage_name.strip().lower())

    booked_this  = stage_count(this_deals, "Meeting Booked")
    booked_prev  = stage_count(prev_deals, "Meeting Booked")
    held_this    = stage_count(this_deals, "Meeting Held — Proposal Sent")
    closed_this  = stage_count(this_deals, "Closed Won")
    closed_prev  = stage_count(prev_deals, "Closed Won")

    show_rate_this = safe_div(held_this,   booked_this)
    show_rate_prev_held = stage_count(prev_deals, "Meeting Held — Proposal Sent")
    show_rate_prev = safe_div(show_rate_prev_held, booked_prev)

    close_rate_this = safe_div(closed_this, held_this)
    close_rate_prev_closed = stage_count(prev_deals, "Closed Won")
    close_rate_prev = safe_div(close_rate_prev_closed,
                               stage_count(prev_deals, "Meeting Held — Proposal Sent"))

    def closed_value(deals):
        total = 0
        for d in deals:
            if d["properties"].get("dealstage","").strip().lower() == "closed won":
                try: total += float(d["properties"].get("amount") or 0)
                except: pass
        return total

    rev_this = closed_value(this_deals)
    rev_prev = closed_value(prev_deals)

    open_pipeline_val = sum(
        float(d["properties"].get("amount") or 0) for d in open_deals
    )

    # CAC: simple placeholder if no ad spend tracked in HubSpot
    # Replace with actual ad spend property if available
    cac_this = round(rev_this / closed_this, 0) if closed_this else 0
    cac_prev = round(rev_prev / closed_prev, 0) if closed_prev else 0

    ld, ld_dir = delta_str(leads_this, leads_prev)
    cd, cd_dir = delta_str(booked_this, booked_prev)
    sd, sd_dir = delta_str(show_rate_this, show_rate_prev, fmt="pct")
    cld, cld_dir = delta_str(close_rate_this, close_rate_prev, fmt="pct")
    cacd, cacd_dir = delta_str(cac_this, cac_prev)
    pipd, pipd_dir = delta_str(open_pipeline_val,
                               sum(float(d["properties"].get("amount") or 0)
                                   for d in get_all_open_deals()), )

    kpis = [
        ("Leads captured",  str(leads_this),           ld,   ld_dir),
        ("Calls booked",    str(booked_this),           cd,   cd_dir),
        ("Show rate",       f"{show_rate_this}%",       sd,   sd_dir),
        ("Close rate",      f"{close_rate_this}%",      cld,  cld_dir),
        ("Avg. CAC",        f"${int(cac_this):,}",      cacd, cacd_dir),
        ("Open pipeline",   f"${int(open_pipeline_val):,}", pipd, pipd_dir),
    ]

    # ── Vertical breakdown ────────────────────────────────────────────────────
    def vert_count(contacts, vert_name):
        return sum(1 for c in contacts
                   if c["properties"].get(ALTUS_VERTICAL,"") == vert_name)

    im_leads = vert_count(this_contacts, "Inbound Magnet")
    oh_leads = vert_count(this_contacts, "Outbound Hunter")
    ce_leads = vert_count(this_contacts, "Conversion Engine")

    # ── Pipeline snapshot ─────────────────────────────────────────────────────
    stage_map = {
        "New Lead — Unworked":               "New lead",
        "AI Qualified — Awaiting Human Review": "AI qualified",
        "Meeting Booked":                    "Call booked",
        "Meeting Held — Proposal Sent":      "Meeting held",
        "Closed Won":                        "Closed won",
    }
    pipeline_snapshot = []
    all_this_deals_open = get_all_open_deals()
    for hs_name, display_name in stage_map.items():
        n = sum(1 for d in all_this_deals_open
                if d["properties"].get("dealstage","").strip() == hs_name)
        if hs_name == "Closed Won":
            n = closed_this
        pipeline_snapshot.append((display_name, n))

    # ── Funnel ────────────────────────────────────────────────────────────────
    # Cold traffic & ad clicks require Meta Ads integration; use placeholders
    # that you can replace with actual ad API data later
    funnel = [
        ("Cold traffic",  leads_this * 55),   # placeholder ratio
        ("Ad clicks",     leads_this * 3),
        ("Leads",         leads_this),
        ("Calls booked",  booked_this),
        ("Closed won",    closed_this),
    ]

    # ── Outbound recent activity ──────────────────────────────────────────────
    outbound_activity = []
    for row in outbound_rows:
        p = row["properties"]
        name = f"{p.get('firstname','')} {p.get('lastname','')}".strip() or "Unknown"
        company = p.get("company","")
        title   = p.get("jobtitle","")
        trigger = p.get(ALTUS_TRIGGER,"")[:60]
        status  = p.get("hs_lead_status","Open")
        outbound_activity.append({
            "name":    name,
            "company": company,
            "title":   title,
            "trigger": trigger,
            "status":  status,
        })

    # ── Assemble output ───────────────────────────────────────────────────────
    output = {
        "client_name":   CLIENT_NAME,
        "client_id":     CLIENT_ID,
        "month":         REPORT_MONTH,
        "prepared_by":   "AltusFlow.ai",
        "kpis":          kpis,
        "pipeline":      pipeline_snapshot,
        "funnel":        funnel,
        "vertical_leads": {
            "Inbound Magnet":    im_leads,
            "Outbound Hunter":   oh_leads,
            "Conversion Engine": ce_leads,
        },
        "close_rate_dir": cld_dir,
        "close_rate_val": f"{close_rate_this}%",
        "close_rate_delta": cld,
        "outbound_activity": outbound_activity,
        "raw": {
            "leads_this":  leads_this,
            "leads_prev":  leads_prev,
            "closed_this": closed_this,
            "rev_this":    rev_this,
        }
    }

    out_path = os.environ.get("DATA_OUTPUT_PATH", "reports/report_data.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Data written to {out_path}")
    print(f"  Leads: {leads_this}  |  Booked: {booked_this}  |  Closed: {closed_this}")

if __name__ == "__main__":
    main()
