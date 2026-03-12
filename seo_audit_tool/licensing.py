"""
Licensing and tier management for SEO Audit Tool.

Model:
- 30-day full-feature trial on first use
- After trial: Free tier (limited) + Premium (license key from Gumroad)
"""

import json
import os
import time
from pathlib import Path

PRODUCT_NAME = "seo-audit-tool"
TRIAL_DAYS = 30
LICENSE_STORE = Path.home() / ".seo-audit-tool" / "license.json"

# Tier limits
FREE_LIMITS = {
    "max_pages": 1,
    "report_formats": ["html"],
    "competitor_analysis": False,
    "full_site_crawl": False,
}

PREMIUM_LIMITS = {
    "max_pages": None,  # unlimited
    "report_formats": ["html", "json", "pdf"],
    "competitor_analysis": True,
    "full_site_crawl": True,
}


def _ensure_store():
    LICENSE_STORE.parent.mkdir(parents=True, exist_ok=True)
    if not LICENSE_STORE.exists():
        data = {
            "first_run": time.time(),
            "license_key": None,
            "tier": "trial",
        }
        LICENSE_STORE.write_text(json.dumps(data, indent=2))
    return json.loads(LICENSE_STORE.read_text())


def _save_store(data):
    LICENSE_STORE.parent.mkdir(parents=True, exist_ok=True)
    LICENSE_STORE.write_text(json.dumps(data, indent=2))


def get_tier():
    """Return current tier: 'trial', 'free', or 'premium'."""
    data = _ensure_store()

    if data.get("license_key") and data.get("tier") == "premium":
        return "premium"

    first_run = data.get("first_run", time.time())
    elapsed_days = (time.time() - first_run) / 86400

    if elapsed_days <= TRIAL_DAYS:
        return "trial"

    return "free"


def get_limits():
    """Return the feature limits for the current tier."""
    tier = get_tier()
    if tier in ("trial", "premium"):
        return PREMIUM_LIMITS.copy()
    return FREE_LIMITS.copy()


def activate_license(key):
    """Activate a premium license key."""
    if not key or not key.strip():
        return False, "License key cannot be empty."

    # NOTE: needs real Gumroad license verification API call
    data = _ensure_store()
    data["license_key"] = key.strip()
    data["tier"] = "premium"
    _save_store(data)
    return True, "License activated. Premium features unlocked."


def deactivate_license():
    """Remove the current license key."""
    data = _ensure_store()
    data["license_key"] = None
    data["tier"] = "free"
    _save_store(data)
    return True, "License deactivated."


def get_status():
    """Return a dict with full licensing status."""
    data = _ensure_store()
    tier = get_tier()
    first_run = data.get("first_run", time.time())
    elapsed_days = (time.time() - first_run) / 86400
    trial_remaining = max(0, TRIAL_DAYS - elapsed_days)

    return {
        "product": PRODUCT_NAME,
        "tier": tier,
        "trial_days_remaining": round(trial_remaining, 1) if tier == "trial" else 0,
        "license_key": bool(data.get("license_key")),
        "limits": get_limits(),
    }


def check_limit(feature, value=None):
    """Check if a feature/value is allowed under the current tier."""
    limits = get_limits()

    if feature == "max_pages" and value is not None:
        max_val = limits.get("max_pages")
        if max_val is not None and value > max_val:
            return False, (
                f"Free tier limited to {max_val} page(s). "
                f"Upgrade to Premium for full site crawl: https://tirandev.gumroad.com"
            )

    if feature == "report_format" and value is not None:
        allowed = limits.get("report_formats", [])
        if value not in allowed:
            return False, (
                f"Report format '{value}' requires Premium. "
                f"Free tier supports: {', '.join(allowed)}. "
                f"Upgrade: https://tirandev.gumroad.com"
            )

    if feature == "competitor_analysis":
        if not limits.get("competitor_analysis"):
            return False, (
                "Competitor analysis requires Premium. "
                "Upgrade: https://tirandev.gumroad.com"
            )

    if feature == "full_site_crawl":
        if not limits.get("full_site_crawl"):
            return False, (
                "Full site crawl requires Premium. "
                "Upgrade: https://tirandev.gumroad.com"
            )

    return True, "OK"
