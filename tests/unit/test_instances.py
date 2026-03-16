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
