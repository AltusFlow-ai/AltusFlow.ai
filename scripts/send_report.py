"""
send_report.py
Emails the generated PDF to the client via SendGrid.

Required env vars:
  SENDGRID_API_KEY
  CLIENT_EMAIL
  CLIENT_NAME
  REPORT_MONTH
  CLIENT_ID
"""

import os, json, base64, urllib.request, urllib.error, glob, sys

API_KEY      = os.environ["SENDGRID_API_KEY"]
CLIENT_EMAIL = os.environ["CLIENT_EMAIL"]
CLIENT_NAME  = os.environ["CLIENT_NAME"]
REPORT_MONTH = os.environ.get("REPORT_MONTH", "this month")
CLIENT_ID    = os.environ.get("CLIENT_ID", "")

FROM_EMAIL   = "reports@altusflow.ai"
FROM_NAME    = "AltusFlow Reports"
REPLY_TO     = "hello@altusflow.ai"

# Find the generated PDF
pdfs = glob.glob(f"reports/AltusFlow_{CLIENT_ID}_*.pdf")
if not pdfs:
    print("ERROR: No PDF found in reports/. Did generate_report.py run?")
    sys.exit(1)
pdf_path = pdfs[0]
pdf_name = os.path.basename(pdf_path)

with open(pdf_path, "rb") as f:
    pdf_b64 = base64.b64encode(f.read()).decode()

body_html = f"""
<div style="font-family: -apple-system, sans-serif; max-width: 560px; margin: 0 auto; color: #2C2C2A;">
  <div style="background: #2C2C2A; padding: 16px 24px; margin-bottom: 24px;">
    <span style="color: #fff; font-weight: 600; font-size: 14px; letter-spacing: 0.08em;">ALTUSFLOW</span>
    <span style="background: #1D9E75; display: inline-block; width: 6px; height: 6px;
                 border-radius: 50%; margin-left: 6px; vertical-align: middle;"></span>
  </div>

  <p style="font-size: 15px; margin: 0 0 12px;">Hi {CLIENT_NAME},</p>

  <p style="font-size: 14px; color: #5F5E5A; line-height: 1.7; margin: 0 0 16px;">
    Your <strong>{REPORT_MONTH} performance report</strong> is attached.
    It covers all three verticals — Inbound Magnet, Outbound Hunter, and Conversion Engine —
    along with your full pipeline snapshot and a priority action item for next month.
  </p>

  <p style="font-size: 14px; color: #5F5E5A; line-height: 1.7; margin: 0 0 24px;">
    Questions or want to walk through the numbers? Reply to this email and we'll schedule
    a 20-minute review call.
  </p>

  <div style="border-top: 1px solid #D3D1C7; padding-top: 16px; font-size: 12px; color: #888780;">
    AltusFlow.ai — automated by design<br/>
    <a href="https://altusflow.ai" style="color: #1D9E75;">altusflow.ai</a>
  </div>
</div>
"""

payload = {
    "personalizations": [{
        "to": [{"email": CLIENT_EMAIL, "name": CLIENT_NAME}],
        "subject": f"{CLIENT_NAME} · {REPORT_MONTH} Performance Report",
    }],
    "from":     {"email": FROM_EMAIL, "name": FROM_NAME},
    "reply_to": {"email": REPLY_TO},
    "content":  [{"type": "text/html", "value": body_html}],
    "attachments": [{
        "content":     pdf_b64,
        "type":        "application/pdf",
        "filename":    pdf_name,
        "disposition": "attachment",
    }],
}

data = json.dumps(payload).encode()
req  = urllib.request.Request(
    "https://api.sendgrid.com/v3/mail/send",
    data=data,
    headers={
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type":  "application/json",
    },
    method="POST",
)

try:
    with urllib.request.urlopen(req) as r:
        print(f"Email sent to {CLIENT_EMAIL} — status {r.status}")
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"SendGrid error {e.code}: {body}")
    sys.exit(1)
