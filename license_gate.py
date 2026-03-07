"""
License Gate - Freemium licensing for CLI tools.
30-day full trial, then free tier unless activated with a license key.

Integration:
    from license_gate import LicenseGate
    gate = LicenseGate("toolname")
    gate.check()  # prints trial status
    if gate.is_premium():
        # premium feature
"""

import hashlib
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

TRIAL_DAYS = 30
STORE_URL = "https://tirandev.gumroad.com"


class LicenseGate:
    def __init__(self, tool_name):
        self.tool_name = tool_name
        self.config_dir = Path.home() / f".{tool_name}"
        self.config_dir.mkdir(exist_ok=True)
        self.config_path = self.config_dir / "license.json"
        self.config = self._load()

    def _load(self):
        if self.config_path.exists():
            try:
                return json.loads(self.config_path.read_text())
            except Exception:
                pass
        # First run - start trial
        config = {
            "installed": datetime.now().isoformat(),
            "license_key": "",
            "activated": False
        }
        self._save(config)
        return config

    def _save(self, config=None):
        if config:
            self.config = config
        self.config_path.write_text(json.dumps(self.config, indent=2))

    def _validate_key(self, key):
        """Validate a license key. Uses hash-based validation."""
        if not key:
            return False
        # Key format: TOOL-XXXX-XXXX-XXXX
        prefix = self.tool_name.upper().replace("-", "")[:6]
        expected_hash = hashlib.sha256(f"{prefix}:{key.split('-')[1] if '-' in key else ''}:pro".encode()).hexdigest()[:8]
        parts = key.split('-')
        if len(parts) >= 4:
            return parts[-1].lower() == expected_hash.lower() or self._check_universal(key)
        return self._check_universal(key)

    def _check_universal(self, key):
        """Check if it's a valid universal key pattern."""
        if not key:
            return False
        h = hashlib.sha256(f"income-center:{key}".encode()).hexdigest()
        return h[:4] == key[-4:] if len(key) > 4 else False

    def trial_days_left(self):
        installed = datetime.fromisoformat(self.config["installed"])
        elapsed = (datetime.now() - installed).days
        return max(TRIAL_DAYS - elapsed, 0)

    def is_trial_active(self):
        return self.trial_days_left() > 0

    def is_premium(self):
        """Check if user has premium access (trial or activated)."""
        if self.config.get("activated"):
            return True
        return self.is_trial_active()

    def activate(self, key):
        """Activate with a license key."""
        if self._validate_key(key):
            self.config["license_key"] = key
            self.config["activated"] = True
            self._save()
            return True
        return False

    def check(self, silent=False):
        """Check and display license status. Call at tool startup."""
        if self.config.get("activated"):
            if not silent:
                print(f"[{self.tool_name}] Premium activated")
            return "premium"

        days = self.trial_days_left()
        if days > 0:
            if not silent:
                print(f"[{self.tool_name}] Trial: {days} days remaining (all features unlocked)")
            return "trial"
        else:
            if not silent:
                print(f"[{self.tool_name}] Free tier - upgrade for premium features: {STORE_URL}")
            return "free"

    def require_premium(self, feature_name="This feature"):
        """Gate a premium feature. Returns True if allowed, prints upgrade msg if not."""
        if self.is_premium():
            return True
        print(f"\n  {feature_name} requires Premium.")
        print(f"  Upgrade at: {STORE_URL}")
        print(f"  Then run: {self.tool_name} --activate YOUR-KEY\n")
        return False

    def handle_activate_flag(self, args=None):
        """Handle --activate CLI flag."""
        import argparse
        if args and hasattr(args, 'activate') and args.activate:
            if self.activate(args.activate):
                print(f"Premium activated! All features unlocked.")
                return True
            else:
                print(f"Invalid license key.")
                return False
        return None

    @staticmethod
    def add_activate_arg(parser):
        """Add --activate argument to an argparse parser."""
        parser.add_argument('--activate', help='Activate premium with license key', metavar='KEY')
