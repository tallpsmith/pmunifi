"""T010: Tests for snapshot building from raw API data.

Tests the snapshot builder at src/pcp_pmda_unifi/snapshot.py.
Validates that raw JSON dicts from the UniFi API are transformed
into typed, default-safe data structures with correct values.
"""

import pytest

from pcp_pmda_unifi.snapshot import (
    ClientData,
    DeviceData,
    GatewayData,
    PortData,
    RadioData,
    Snapshot,
    build_snapshot_from_api,
)


def _build(devices, clients=None, health=None):
    """Helper to build a snapshot with sensible defaults."""
    return build_snapshot_from_api(
        controller_name="main",
        site_name="default",
        devices_data=devices,
        clients_data=clients or [],
        health_data=health or [],
    )


# ---------------------------------------------------------------------------
# Full snapshot construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBuildSnapshot:
    """build_snapshot_from_api assembles a Snapshot from raw API dicts."""

    def test_builds_snapshot_from_fixture_data(
        self, sample_devices_data, sample_clients_data, sample_health_data
    ):
        """Snapshot is created from the three main API response arrays."""
        snap = build_snapshot_from_api(
            "main", "default",
            sample_devices_data, sample_clients_data, sample_health_data,
        )
        assert isinstance(snap, Snapshot)
        assert snap.controller_name == "main"
        assert "default" in snap.sites

    def test_snapshot_contains_devices(
        self, sample_devices_data, sample_clients_data, sample_health_data
    ):
        snap = build_snapshot_from_api(
            "main", "default",
            sample_devices_data, sample_clients_data, sample_health_data,
        )
        site = snap.sites["default"]
        # Fixture has 3 devices: switch, UDM, AP
        assert len(site.devices) == 3

    def test_snapshot_contains_clients(
        self, sample_devices_data, sample_clients_data, sample_health_data
    ):
        snap = build_snapshot_from_api(
            "main", "default",
            sample_devices_data, sample_clients_data, sample_health_data,
        )
        site = snap.sites["default"]
        assert len(site.clients) == 3

    def test_snapshot_contains_health(
        self, sample_devices_data, sample_clients_data, sample_health_data
    ):
        snap = build_snapshot_from_api(
            "main", "default",
            sample_devices_data, sample_clients_data, sample_health_data,
        )
        site = snap.sites["default"]
        # Health fixture has wan, lan, wlan, vpn subsystems
        assert len(site.health) == 4

    def test_devices_discovered_count(
        self, sample_devices_data, sample_clients_data, sample_health_data
    ):
        snap = build_snapshot_from_api(
            "main", "default",
            sample_devices_data, sample_clients_data, sample_health_data,
        )
        assert snap.devices_discovered == 3

    def test_clients_discovered_count(
        self, sample_devices_data, sample_clients_data, sample_health_data
    ):
        snap = build_snapshot_from_api(
            "main", "default",
            sample_devices_data, sample_clients_data, sample_health_data,
        )
        assert snap.clients_discovered == 3


# ---------------------------------------------------------------------------
# Port data extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPortData:
    """Port metrics are extracted from device port_table entries."""

    def test_port_rx_bytes(self, sample_devices_data):
        snap = _build(sample_devices_data)
        site = snap.sites["default"]
        # First device (switch) keyed by its MAC
        switch_mac = "fc:ec:da:01:02:03"
        switch = site.devices[switch_mac]
        port1 = switch.ports[1]  # port_idx=1
        assert isinstance(port1, PortData)
        assert port1.rx_bytes == 1000000

    def test_port_tx_bytes(self, sample_devices_data):
        snap = _build(sample_devices_data)
        port1 = snap.sites["default"].devices["fc:ec:da:01:02:03"].ports[1]
        assert port1.tx_bytes == 2000000

    def test_port_speed(self, sample_devices_data):
        snap = _build(sample_devices_data)
        port1 = snap.sites["default"].devices["fc:ec:da:01:02:03"].ports[1]
        assert port1.speed == 1000

    def test_port_idx_preserved(self, sample_devices_data):
        snap = _build(sample_devices_data)
        switch = snap.sites["default"].devices["fc:ec:da:01:02:03"]
        assert 1 in switch.ports
        assert 48 in switch.ports
        assert switch.ports[1].port_idx == 1
        assert switch.ports[48].port_idx == 48

    def test_port_mac_count(self, sample_devices_data):
        snap = _build(sample_devices_data)
        port1 = snap.sites["default"].devices["fc:ec:da:01:02:03"].ports[1]
        # port 1 has 2 entries in mac_table
        assert port1.mac_count == 2


# ---------------------------------------------------------------------------
# Radio data extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRadioData:
    """Radio metrics are extracted from device radio_table entries."""

    def test_radio_channel(self, sample_devices_data):
        snap = _build(sample_devices_data)
        # Third device (AP) keyed by MAC
        ap = snap.sites["default"].devices["aa:bb:cc:00:11:22"]
        assert len(ap.radios) == 2
        assert isinstance(ap.radios[0], RadioData)
        assert ap.radios[0].channel == 6

    def test_radio_num_sta(self, sample_devices_data):
        snap = _build(sample_devices_data)
        ap = snap.sites["default"].devices["aa:bb:cc:00:11:22"]
        assert ap.radios[0].num_sta == 8
        assert ap.radios[1].num_sta == 4

    def test_radio_type(self, sample_devices_data):
        snap = _build(sample_devices_data)
        ap = snap.sites["default"].devices["aa:bb:cc:00:11:22"]
        assert ap.radios[0].radio_type == "ng"
        assert ap.radios[1].radio_type == "na"


# ---------------------------------------------------------------------------
# Gateway data extraction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGatewayData:
    """Gateway-specific fields are extracted from UDM-type devices."""

    def test_gateway_wan_ip(self, sample_devices_data):
        snap = _build(sample_devices_data)
        # Second device is UDM-Pro (type=udm)
        udm = snap.sites["default"].devices["de:ad:be:ef:00:01"]
        assert isinstance(udm.gateway, GatewayData)
        assert udm.gateway.wan_ip == "203.0.113.42"

    def test_gateway_wan_rx_bytes(self, sample_devices_data):
        snap = _build(sample_devices_data)
        udm = snap.sites["default"].devices["de:ad:be:ef:00:01"]
        assert udm.gateway.wan_rx_bytes == 300000000000

    def test_gateway_cpu(self, sample_devices_data):
        snap = _build(sample_devices_data)
        udm = snap.sites["default"].devices["de:ad:be:ef:00:01"]
        # system-stats.cpu is "8.5" in fixture → gateway cpu
        assert udm.gateway.cpu == pytest.approx(8.5)

    def test_gateway_mem(self, sample_devices_data):
        snap = _build(sample_devices_data)
        udm = snap.sites["default"].devices["de:ad:be:ef:00:01"]
        assert udm.gateway.mem == pytest.approx(62.1)


# ---------------------------------------------------------------------------
# Default values for missing fields
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDefaults:
    """Missing fields get safe defaults instead of crashing."""

    def test_counter_defaults_to_zero(self):
        """A device dict with no rx_bytes should produce rx_bytes=0."""
        snap = _build([{"mac": "aa:bb:cc:00:00:01", "type": "usw"}])
        device = list(snap.sites["default"].devices.values())[0]
        assert device.meta.rx_bytes == 0

    def test_string_defaults_to_empty(self):
        snap = _build([{"mac": "aa:bb:cc:00:00:01", "type": "usw"}])
        device = list(snap.sites["default"].devices.values())[0]
        assert device.meta.name == ""

    def test_missing_port_table_defaults_to_empty_dict(self):
        snap = _build([{"mac": "aa:bb:cc:00:00:01", "type": "usw"}])
        device = list(snap.sites["default"].devices.values())[0]
        assert device.ports == {}

    def test_missing_radio_table_defaults_to_empty_list(self):
        snap = _build([{"mac": "aa:bb:cc:00:00:01", "type": "uap"}])
        device = list(snap.sites["default"].devices.values())[0]
        assert device.radios == []

    def test_non_gateway_has_no_gateway_data(self):
        """A non-UDM device should have gateway=None."""
        snap = _build([{"mac": "aa:bb:cc:00:00:01", "type": "usw"}])
        device = list(snap.sites["default"].devices.values())[0]
        assert device.gateway is None
