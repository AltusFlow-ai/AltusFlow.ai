"""
crm/__init__.py
CRM router — returns the active adapter based on the CRM_PROVIDER env var.

Set CRM_PROVIDER in .env.local to one of:
  hubspot       — HubSpot (default)
  gohighlevel   — GoHighLevel / GHL
  pipedrive     — Pipedrive
  salesforce    — Salesforce (requires OAuth setup)
  none          — disable CRM sync

Each client gets their own .env.local with CRM_PROVIDER set to their CRM.
"""
import os

_provider = os.environ.get("CRM_PROVIDER", "hubspot").lower().strip()

# Map provider names to adapter class paths (lazy-loaded to avoid import errors
# when a provider's dependencies or env vars aren't configured)
_PROVIDERS = {
    "hubspot":      ("crm.hubspot_adapter", "HubSpotAdapter"),
    "gohighlevel":  ("crm.gohighlevel",     "GoHighLevelAdapter"),
    "ghl":          ("crm.gohighlevel",     "GoHighLevelAdapter"),
    "pipedrive":    ("crm.pipedrive",        "PipedriveAdapter"),
    "salesforce":   ("crm.salesforce",       "SalesforceAdapter"),
}


def get_adapter():
    """Return the active CRM adapter instance. Falls back to NullAdapter on any error."""
    entry = _PROVIDERS.get(_provider)
    if entry is None:
        from crm.base import NullAdapter
        return NullAdapter()
    module_path, class_name = entry
    try:
        import importlib
        mod = importlib.import_module(module_path)
        return getattr(mod, class_name)()
    except Exception as e:
        print(f"[CRM] Failed to load adapter '{_provider}': {e} — falling back to NullAdapter")
        from crm.base import NullAdapter
        return NullAdapter()


def active_provider() -> str:
    """Return the configured CRM provider name."""
    return _provider
