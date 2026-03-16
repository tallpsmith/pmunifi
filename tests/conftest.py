"""Shared pytest fixtures for pcp-pmda-unifi tests."""

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_devices():
    """Full stat/device API response with switch, gateway, and AP."""
    return json.loads((FIXTURES_DIR / "stat_device.json").read_text())


@pytest.fixture
def sample_devices_data(sample_devices):
    """Just the data array from stat/device response."""
    return sample_devices["data"]


@pytest.fixture
def sample_clients():
    """Full stat/sta API response with wired and wireless clients."""
    return json.loads((FIXTURES_DIR / "stat_sta.json").read_text())


@pytest.fixture
def sample_clients_data(sample_clients):
    """Just the data array from stat/sta response."""
    return sample_clients["data"]


@pytest.fixture
def sample_health():
    """Full stat/health API response with wan, lan, wlan, vpn subsystems."""
    return json.loads((FIXTURES_DIR / "stat_health.json").read_text())


@pytest.fixture
def sample_health_data(sample_health):
    """Just the data array from stat/health response."""
    return sample_health["data"]


@pytest.fixture
def sample_sysinfo():
    """Full stat/sysinfo API response."""
    return json.loads((FIXTURES_DIR / "stat_sysinfo.json").read_text())


@pytest.fixture
def sample_sysinfo_data(sample_sysinfo):
    """Just the data array from stat/sysinfo response."""
    return sample_sysinfo["data"]


@pytest.fixture
def sample_dpi():
    """Full stat/sitedpi API response with DPI categories."""
    return json.loads((FIXTURES_DIR / "stat_sitedpi.json").read_text())


@pytest.fixture
def sample_dpi_data(sample_dpi):
    """Just the data array from stat/sitedpi response."""
    return sample_dpi["data"]


@pytest.fixture
def sample_config():
    """A valid single-controller INI config string."""
    return """\
[global]
poll_interval = 30
max_clients = 1000
grace_period = 300
enable_dpi = false

[controller:main]
url = https://192.168.1.1
api_key = test-api-key-12345
sites = all
is_udm = true
verify_ssl = false
"""


@pytest.fixture
def sample_multi_controller_config():
    """A valid multi-controller INI config string."""
    return """\
[global]
poll_interval = 30
max_clients = 500

[controller:hq]
url = https://10.0.0.1
api_key = ak-hq-key
sites = all
is_udm = true

[controller:branch]
url = https://10.1.0.1
api_key = ak-branch-key
sites = warehouse,office
is_udm = false
poll_interval = 60
"""
