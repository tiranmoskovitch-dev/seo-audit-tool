"""Tests for the licensing module."""

from unittest.mock import patch

import pytest

from seo_audit_tool.licensing import (
    activate_license,
    check_limit,
    get_limits,
    get_status,
    get_tier,
)


@pytest.fixture(autouse=True)
def temp_license_store(tmp_path):
    store = tmp_path / "license.json"
    with patch("seo_audit_tool.licensing.LICENSE_STORE", store):
        yield store


def test_first_run_is_trial():
    assert get_tier() == "trial"


def test_trial_has_premium_limits():
    limits = get_limits()
    assert limits["max_pages"] is None
    assert limits["full_site_crawl"] is True


def test_activate_license():
    ok, _ = activate_license("test-key")
    assert ok is True
    assert get_tier() == "premium"


def test_check_limit_pages_free():
    with patch("seo_audit_tool.licensing.get_tier", return_value="free"):
        allowed, _ = check_limit("max_pages", 1)
        assert allowed is True
        allowed, msg = check_limit("max_pages", 5)
        assert allowed is False


def test_check_limit_report_format_free():
    with patch("seo_audit_tool.licensing.get_tier", return_value="free"):
        allowed, _ = check_limit("report_format", "html")
        assert allowed is True
        allowed, _ = check_limit("report_format", "json")
        assert allowed is False


def test_get_status():
    status = get_status()
    assert status["product"] == "seo-audit-tool"
    assert "limits" in status
