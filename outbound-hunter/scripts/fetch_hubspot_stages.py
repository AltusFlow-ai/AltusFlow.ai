#!/usr/bin/env python3
"""
scripts/fetch_hubspot_stages.py
Fetch all HubSpot deal pipeline and stage IDs so they can be pasted into .env.

Usage:
  cd outbound-hunter
  python scripts/fetch_hubspot_stages.py

Requires HUBSPOT_TOKEN to be set in the environment or .env.local.
"""

import os
import json
import urllib.request
import urllib.error
import sys

try:
    from dotenv import load_dotenv
    load_dotenv(".env.local")
    load_dotenv(".env")
except ImportError:
    pass

TOKEN = os.environ.get("HUBSPOT_TOKEN", "")
if not TOKEN:
    print("ERROR: HUBSPOT_TOKEN is not set.")
    print("Set it in .env.local or export HUBSPOT_TOKEN=pat-na1-... and re-run.")
    sys.exit(1)

req = urllib.request.Request(
    "https://api.hubapi.com/crm/v3/pipelines/deals",
    headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
except urllib.error.HTTPError as e:
    body = e.read().decode(errors="replace")
    print(f"HubSpot API error {e.code}: {body[:400]}")
    sys.exit(1)
except Exception as ex:
    print(f"Request failed: {ex}")
    sys.exit(1)

pipelines = data.get("results", [])
if not pipelines:
    print("No deal pipelines found in this HubSpot portal.")
    sys.exit(0)

print("\n" + "=" * 60)
print("  HubSpot Deal Pipeline / Stage IDs")
print("=" * 60)

env_lines = []
for pipeline in pipelines:
    pid   = pipeline.get("id", "")
    label = pipeline.get("label", "Unnamed Pipeline")
    print(f"\nPipeline: {label}")
    print(f"  ID: {pid}")
    env_lines.append(f"\n# Pipeline: {label}")
    env_lines.append(f"HUBSPOT_PIPELINE_ID={pid}")

    for stage in pipeline.get("stages", []):
        sid        = stage.get("id", "")
        slabel     = stage.get("label", "Unnamed Stage")
        display_order = stage.get("displayOrder", "?")
        print(f"    Stage [{display_order}] {slabel}: {sid}")
        env_lines.append(f"# Stage: {slabel}")
        env_lines.append(f"# HUBSPOT_STAGE_???_ID={sid}")

print("\n" + "=" * 60)
print("  Copy-paste block for .env")
print("=" * 60)
print("\n".join(env_lines))
print()
print("Tip: Set HUBSPOT_STAGE_1_ID to the first stage ID (e.g. 'New Lead').")
print("     Set HUBSPOT_STAGE_MEETING_BOOKED_ID to the 'Meeting Booked' stage ID.")
