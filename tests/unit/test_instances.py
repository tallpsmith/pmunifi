"""T011: Tests for PCP instance naming functions.

Tests the instance name builders at src/pcp_pmda_unifi/instances.py.
Instance names follow the hierarchical pattern defined in the data model:
  {controller}/{site}/{entity}[::qualifier]
"""

import pytest

from pcp_pmda_unifi.instances import (
    ap_radio_instance_name,
    client_instance_name,
    controller_instance_name,
    device_instance_name,
    dpi_category_instance_name,
    gateway_instance_name,
    site_instance_name,
    switch_port_instance_name,
)

# ---------------------------------------------------------------------------
# Site instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSiteInstanceName:
    def test_basic(self):
        assert site_instance_name("main", "default") == "main/default"


# ---------------------------------------------------------------------------
# Device instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDeviceInstanceName:
    def test_basic(self):
        assert (
            device_instance_name("main", "default", "USW-Pro-48-Rack1")
            == "main/default/USW-Pro-48-Rack1"
        )

    def test_whitespace_replaced_with_hyphens(self):
        """Whitespace in device names is replaced with hyphens."""
        assert (
            device_instance_name("main", "default", "My Switch")
            == "main/default/My-Switch"
        )


# ---------------------------------------------------------------------------
# Switch port instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSwitchPortInstanceName:
    def test_basic(self):
        assert (
            switch_port_instance_name("main", "default", "USW-Pro-48-Rack1", 1)
            == "main/default/USW-Pro-48-Rack1::Port1"
        )


# ---------------------------------------------------------------------------
# Client instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClientInstanceName:
    def test_with_hostname(self):
        assert (
            client_instance_name("main", "default", "laptop-alice")
            == "main/default/laptop-alice"
        )

    def test_empty_hostname_falls_back_to_mac(self):
        """When hostname is empty, the MAC address is used instead."""
        assert (
            client_instance_name("main", "default", "", "aa:bb:cc:dd:ee:03")
            == "main/default/aa:bb:cc:dd:ee:03"
        )


# ---------------------------------------------------------------------------
# AP radio instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApRadioInstanceName:
    def test_basic(self):
        assert (
            ap_radio_instance_name("main", "default", "UAP-AC-Pro-Lobby", "na")
            == "main/default/UAP-AC-Pro-Lobby::na"
        )


# ---------------------------------------------------------------------------
# Gateway instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGatewayInstanceName:
    def test_basic(self):
        assert (
            gateway_instance_name("main", "default", "UDM-Pro")
            == "main/default/UDM-Pro"
        )


# ---------------------------------------------------------------------------
# Controller instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControllerInstanceName:
    def test_basic(self):
        assert controller_instance_name("main") == "main"


# ---------------------------------------------------------------------------
# DPI category instances
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDpiCategoryInstanceName:
    def test_basic(self):
        assert (
            dpi_category_instance_name("main", "default", "Streaming")
            == "main/default/Streaming"
        )


# ---------------------------------------------------------------------------
# US8 / T057: Multi-controller naming — distinct prefixes avoid collisions
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMultiControllerNaming:
    """Two controllers ('hq' and 'branch') with the same site produce
    distinct instance names across every indom type.
    """

    def test_site_names_are_distinct(self):
        hq = site_instance_name("hq", "default")
        branch = site_instance_name("branch", "default")
        assert hq != branch
        assert hq == "hq/default"
        assert branch == "branch/default"

    def test_device_names_are_distinct(self):
        hq = device_instance_name("hq", "default", "SwitchA")
        branch = device_instance_name("branch", "default", "SwitchB")
        assert hq != branch
        assert hq == "hq/default/SwitchA"
        assert branch == "branch/default/SwitchB"

    def test_same_device_name_different_controller_is_distinct(self):
        """Even identical device names are disambiguated by controller prefix."""
        hq = device_instance_name("hq", "default", "USW-Pro-48")
        branch = device_instance_name("branch", "default", "USW-Pro-48")
        assert hq != branch

    def test_switch_port_names_are_distinct(self):
        hq = switch_port_instance_name("hq", "default", "SwitchA", 1)
        branch = switch_port_instance_name("branch", "default", "SwitchB", 1)
        assert hq != branch
        assert hq == "hq/default/SwitchA::Port1"
        assert branch == "branch/default/SwitchB::Port1"

    def test_client_names_are_distinct(self):
        hq = client_instance_name("hq", "default", "laptop-alice")
        branch = client_instance_name("branch", "default", "laptop-alice")
        assert hq != branch

    def test_gateway_names_are_distinct(self):
        hq = gateway_instance_name("hq", "default", "UDM-Pro")
        branch = gateway_instance_name("branch", "default", "UDM-Pro")
        assert hq != branch

    def test_controller_names_are_distinct(self):
        assert controller_instance_name("hq") != controller_instance_name("branch")


# ---------------------------------------------------------------------------
# Issue #3: Single-controller simplification — omit controller prefix
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSingleControllerOmitsPrefix:
    """When single_controller=True, the controller prefix is dropped from
    instance names because it's redundant noise for the 90% case.
    """

    def test_site_omits_controller_prefix(self):
        assert site_instance_name("main", "default", single_controller=True) == "default"

    def test_device_omits_controller_prefix(self):
        assert (
            device_instance_name("main", "default", "USW-Ultra-60W", single_controller=True)
            == "default/USW-Ultra-60W"
        )

    def test_switch_port_omits_controller_prefix(self):
        assert (
            switch_port_instance_name("main", "default", "USW-Pro-48", 1, single_controller=True)
            == "default/USW-Pro-48::Port1"
        )

    def test_client_omits_controller_prefix(self):
        assert (
            client_instance_name("main", "default", "laptop-alice", single_controller=True)
            == "default/laptop-alice"
        )

    def test_ap_radio_omits_controller_prefix(self):
        assert (
            ap_radio_instance_name("main", "default", "UAP-AC-Pro", "na", single_controller=True)
            == "default/UAP-AC-Pro::na"
        )

    def test_gateway_omits_controller_prefix(self):
        assert (
            gateway_instance_name("main", "default", "UDM-Pro", single_controller=True)
            == "default/UDM-Pro"
        )

    def test_dpi_category_omits_controller_prefix(self):
        assert (
            dpi_category_instance_name("main", "default", "Streaming", single_controller=True)
            == "default/Streaming"
        )


@pytest.mark.unit
class TestMultiControllerKeepsPrefix:
    """When single_controller=False (the default), the controller prefix
    remains for disambiguation — backwards-compatible behavior.
    """

    def test_site_keeps_controller_prefix(self):
        assert site_instance_name("hq", "default", single_controller=False) == "hq/default"

    def test_device_keeps_controller_prefix(self):
        assert (
            device_instance_name("hq", "default", "SwitchA", single_controller=False)
            == "hq/default/SwitchA"
        )

    def test_default_is_multi_controller(self):
        """Calling without single_controller kwarg preserves the old behavior."""
        assert site_instance_name("hq", "default") == "hq/default"


@pytest.mark.unit
class TestPmdaConfigSingleControllerFlag:
    """PmdaConfig.is_single_controller is derived from controller count."""

    def test_single_controller_config(self):
        from pcp_pmda_unifi.config import parse_config

        ini = """\
[controller:main]
url = https://192.168.1.1
api_key = some-key
"""
        cfg = parse_config(ini)
        assert cfg.is_single_controller is True

    def test_multi_controller_config(self):
        from pcp_pmda_unifi.config import parse_config

        ini = """\
[controller:hq]
url = https://10.0.0.1
api_key = ak-hq

[controller:branch]
url = https://10.1.0.1
api_key = ak-branch
"""
        cfg = parse_config(ini)
        assert cfg.is_single_controller is False
