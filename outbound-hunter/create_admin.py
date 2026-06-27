"""
create_admin.py
Bootstrap script — run once after deploying to create the first tenant + admin user.

  python create_admin.py

What it does:
  1. Initialises master.db (tenants, users, tenant_config tables)
  2. Creates a new tenant record
  3. Creates an admin user for that tenant
  4. Creates the tenant's DB directory and initialises the outbound_hunter schema

Run for each new client you onboard:
  python create_admin.py
  > Tenant slug: client-acme
  > Company name: Acme Financial
  > Plan: starter
  > Admin email: owner@acme.com
  > Admin password: xxxxxxxx
"""

import os
import sys
import getpass


def main():
    print()
    print("=" * 52)
    print("  AltusFlow — Create Tenant & Admin User")
    print("=" * 52)
    print()

    # Initialise master DB
    from master_db import (
        init_master_db, create_tenant, create_user,
        get_tenant_by_slug,
    )
    init_master_db()

    # ── Tenant details ────────────────────────────────────────────────────────
    slug = input("Tenant slug (lowercase, hyphens OK — e.g. acme-financial): ").strip().lower()
    slug = slug.replace(" ", "-")
    if not slug:
        print("✗ Slug cannot be empty.")
        sys.exit(1)

    if get_tenant_by_slug(slug):
        print(f"✗ Tenant '{slug}' already exists. Use a different slug.")
        sys.exit(1)

    company_name = input("Company name: ").strip()
    if not company_name:
        print("✗ Company name cannot be empty.")
        sys.exit(1)

    plan = input("Plan [starter / pro / agency] (default: starter): ").strip().lower() or "starter"
    if plan not in ("starter", "pro", "agency"):
        print(f"✗ Unknown plan '{plan}'. Defaulting to starter.")
        plan = "starter"

    # ── Admin user ────────────────────────────────────────────────────────────
    email = input("Admin email: ").strip().lower()
    if not email or "@" not in email:
        print("✗ Invalid email.")
        sys.exit(1)

    while True:
        password  = getpass.getpass("Admin password (min 8 chars): ")
        password2 = getpass.getpass("Confirm password: ")
        if password != password2:
            print("  Passwords do not match — try again.")
            continue
        if len(password) < 8:
            print("  Password must be at least 8 characters — try again.")
            continue
        break

    print()

    # ── Create records ────────────────────────────────────────────────────────
    tenant_id = create_tenant(slug, company_name, plan)
    print(f"✓ Tenant '{slug}' created (id={tenant_id})")

    create_user(tenant_id, email, password, role="admin")
    print(f"✓ Admin user '{email}' created")

    # ── Initialise tenant DB ──────────────────────────────────────────────────
    tenant_dir = os.path.join("tenants", slug)
    os.makedirs(tenant_dir, exist_ok=True)

    import database
    database.set_tenant_slug(slug)
    database.init_db()
    print(f"✓ Tenant database initialised at {tenant_dir}/outbound_hunter.db")

    print()
    print("=" * 52)
    print(f"  Done!")
    print(f"  Start the app and log in at /login")
    print(f"  Email:    {email}")
    print(f"  Tenant:   {slug} ({company_name})")
    print("=" * 52)
    print()


if __name__ == "__main__":
    main()
