"""T008: Tests for configuration parsing.

Tests the config parser at src/pcp_pmda_unifi/config.py.
Validates INI parsing, defaults, validation rules, env var overrides,
and controller NAME constraints per the configuration contract.
"""

import os

import pytest

from pcp_pmda_unifi.config import parse_config


# ---------------------------------------------------------------------------
# Happy-path parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestParseValidConfig:
    """parse_config returns a well-formed config object from valid INI text."""

    def test_single_controller(self, sample_config):
        """Single [controller:main] section is parsed with correct values."""
        cfg = parse_config(sample_config)

        assert cfg.global_settings.poll_interval == 30
        assert cfg.global_settings.max_clients == 1000
        assert cfg.global_settings.grace_period == 300
        assert cfg.global_settings.enable_dpi is False

        assert len(cfg.controllers) == 1
        ctrl = cfg.controllers["main"]
        assert ctrl.url == "https://192.168.1.1"
        assert ctrl.api_key == "test-api-key-12345"
        assert ctrl.sites == ["all"]
        assert ctrl.is_udm is True
        assert ctrl.verify_ssl is False

    def test_multi_controller(self, sample_multi_controller_config):
        """Multiple [controller:*] sections are each parsed independently."""
        cfg = parse_config(sample_multi_controller_config)

        assert len(cfg.controllers) == 2
        assert "hq" in cfg.controllers
        assert "branch" in cfg.controllers

        hq = cfg.controllers["hq"]
        assert hq.url == "https://10.0.0.1"
        assert hq.sites == ["all"]
        assert hq.is_udm is True

        branch = cfg.controllers["branch"]
        assert branch.url == "https://10.1.0.1"
        assert branch.sites == ["warehouse", "office"]
        assert branch.is_udm is False
        # Per-controller poll_interval override
        assert branch.poll_interval == 60


# ---------------------------------------------------------------------------
# Required-field validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMissingRequiredFields:
    """parse_config raises ValueError when required fields are absent."""

    def test_missing_url_raises(self):
        ini = """\
[global]
poll_interval = 30

[controller:main]
api_key = some-key
"""
        with pytest.raises(ValueError, match="(?i)url"):
            parse_config(ini)

    def test_missing_api_key_raises(self):
        ini = """\
[global]
poll_interval = 30

[controller:main]
url = https://192.168.1.1
"""
        with pytest.raises(ValueError, match="(?i)api_key"):
            parse_config(ini)


# ---------------------------------------------------------------------------
# Numeric-bound validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNumericBounds:
    """Numeric fields that violate min/max constraints raise ValueError."""

    def test_poll_interval_below_minimum_raises(self):
        ini = """\
[global]
poll_interval = 5

[controller:main]
url = https://192.168.1.1
api_key = some-key
"""
        with pytest.raises(ValueError, match="(?i)poll_interval"):
            parse_config(ini)

    def test_max_clients_negative_raises(self):
        ini = """\
[global]
max_clients = -1

[controller:main]
url = https://192.168.1.1
api_key = some-key
"""
        with pytest.raises(ValueError, match="(?i)max_clients"):
            parse_config(ini)

    def test_grace_period_negative_raises(self):
        ini = """\
[global]
grace_period = -10

[controller:main]
url = https://192.168.1.1
api_key = some-key
"""
        with pytest.raises(ValueError, match="(?i)grace_period"):
            parse_config(ini)


# ---------------------------------------------------------------------------
# Sites parsing
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSitesParsing:
    """The sites value is parsed into a list of site slugs."""

    def test_all_returns_all_list(self):
        ini = """\
[controller:main]
url = https://192.168.1.1
api_key = some-key
sites = all
"""
        cfg = parse_config(ini)
        assert cfg.controllers["main"].sites == ["all"]

    def test_comma_separated_returns_list(self):
        ini = """\
[controller:main]
url = https://192.168.1.1
api_key = some-key
sites = default,warehouse
"""
        cfg = parse_config(ini)
        assert cfg.controllers["main"].sites == ["default", "warehouse"]


# ---------------------------------------------------------------------------
# Environment variable overrides (FR-006)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEnvVarOverrides:
    """UNIFI_* env vars create a [controller:default] section."""

    def test_env_vars_override_controller_default(self, monkeypatch):
        monkeypatch.setenv("UNIFI_URL", "https://env.example.com")
        monkeypatch.setenv("UNIFI_API_KEY", "env-api-key")
        monkeypatch.setenv("UNIFI_SITES", "site-a,site-b")

        # Empty INI -- env vars should fill in a controller:default section
        cfg = parse_config("")

        ctrl = cfg.controllers["default"]
        assert ctrl.url == "https://env.example.com"
        assert ctrl.api_key == "env-api-key"
        assert ctrl.sites == ["site-a", "site-b"]


# ---------------------------------------------------------------------------
# Controller NAME validation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControllerNameValidation:
    """NAME in [controller:NAME] must be alphanumeric + hyphens + underscores."""

    def test_hyphenated_name_is_valid(self):
        ini = """\
[controller:my-ctrl]
url = https://192.168.1.1
api_key = some-key
"""
        cfg = parse_config(ini)
        assert "my-ctrl" in cfg.controllers

    def test_underscored_name_is_valid(self):
        ini = """\
[controller:my_ctrl]
url = https://192.168.1.1
api_key = some-key
"""
        cfg = parse_config(ini)
        assert "my_ctrl" in cfg.controllers

    def test_name_with_space_raises(self):
        ini = """\
[controller:my ctrl]
url = https://192.168.1.1
api_key = some-key
"""
        with pytest.raises(ValueError, match="(?i)name"):
            parse_config(ini)


# ---------------------------------------------------------------------------
# US8 / T056: Multi-controller config — independent fields per controller
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMultiControllerConfig:
    """Each [controller:NAME] section produces an independent ControllerConfig
    with its own url, api_key, sites, is_udm, verify_ssl, ca_cert, and
    poll_interval.  No bleeding between sections.
    """

    MULTI_INI = """\
[global]
poll_interval = 30

[controller:hq]
url = https://10.0.0.1
api_key = ak-hq-secret
sites = all
is_udm = true
verify_ssl = true

[controller:branch]
url = https://10.1.0.1
api_key = ak-branch-secret
sites = warehouse,office
is_udm = false
verify_ssl = false
ca_cert = /etc/ssl/branch.pem
poll_interval = 60
"""

    def test_two_controllers_are_parsed(self):
        cfg = parse_config(self.MULTI_INI)
        assert len(cfg.controllers) == 2

    def test_controllers_have_independent_urls(self):
        cfg = parse_config(self.MULTI_INI)
        assert cfg.controllers["hq"].url == "https://10.0.0.1"
        assert cfg.controllers["branch"].url == "https://10.1.0.1"

    def test_controllers_have_independent_api_keys(self):
        cfg = parse_config(self.MULTI_INI)
        assert cfg.controllers["hq"].api_key == "ak-hq-secret"
        assert cfg.controllers["branch"].api_key == "ak-branch-secret"

    def test_controllers_have_independent_sites(self):
        cfg = parse_config(self.MULTI_INI)
        assert cfg.controllers["hq"].sites == ["all"]
        assert cfg.controllers["branch"].sites == ["warehouse", "office"]

    def test_controllers_have_independent_is_udm(self):
        cfg = parse_config(self.MULTI_INI)
        assert cfg.controllers["hq"].is_udm is True
        assert cfg.controllers["branch"].is_udm is False

    def test_controllers_have_independent_verify_ssl(self):
        cfg = parse_config(self.MULTI_INI)
        assert cfg.controllers["hq"].verify_ssl is True
        assert cfg.controllers["branch"].verify_ssl is False

    def test_controllers_have_independent_ca_cert(self):
        cfg = parse_config(self.MULTI_INI)
        assert cfg.controllers["hq"].ca_cert is None
        assert cfg.controllers["branch"].ca_cert == "/etc/ssl/branch.pem"

    def test_per_controller_poll_interval_override(self):
        """Branch overrides to 60s; hq inherits None (uses global at runtime)."""
        cfg = parse_config(self.MULTI_INI)
        assert cfg.controllers["hq"].poll_interval is None
        assert cfg.controllers["branch"].poll_interval == 60

    def test_global_poll_interval_untouched_by_controller_override(self):
        cfg = parse_config(self.MULTI_INI)
        assert cfg.global_settings.poll_interval == 30
