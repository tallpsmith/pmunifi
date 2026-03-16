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
    _sort_clients_by_traffic,
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


# ---------------------------------------------------------------------------
# T040: Client sorting by traffic
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClientSorting:
    """Clients are sorted by total traffic (rx + tx bytes) descending."""

    def test_sorts_by_total_traffic_descending(self):
        """Highest total-traffic client comes first."""
        clients = [
            ClientData(mac="aa:bb:cc:00:00:01", rx_bytes=100, tx_bytes=50),
            ClientData(mac="aa:bb:cc:00:00:02", rx_bytes=5000, tx_bytes=3000),
            ClientData(mac="aa:bb:cc:00:00:03", rx_bytes=200, tx_bytes=100),
        ]
        sorted_clients = _sort_clients_by_traffic(clients)
        assert sorted_clients[0].mac == "aa:bb:cc:00:00:02"
        assert sorted_clients[1].mac == "aa:bb:cc:00:00:03"
        assert sorted_clients[2].mac == "aa:bb:cc:00:00:01"

    def test_empty_list_returns_empty(self):
        assert _sort_clients_by_traffic([]) == []

    def test_single_client_unchanged(self):
        clients = [ClientData(mac="aa:bb:cc:00:00:01", rx_bytes=100, tx_bytes=50)]
        result = _sort_clients_by_traffic(clients)
        assert len(result) == 1
        assert result[0].mac == "aa:bb:cc:00:00:01"

    def test_equal_traffic_preserves_order(self):
        """Clients with identical traffic maintain stable sort order."""
        clients = [
            ClientData(mac="aa:bb:cc:00:00:01", rx_bytes=100, tx_bytes=100),
            ClientData(mac="aa:bb:cc:00:00:02", rx_bytes=100, tx_bytes=100),
        ]
        result = _sort_clients_by_traffic(clients)
        assert result[0].mac == "aa:bb:cc:00:00:01"
        assert result[1].mac == "aa:bb:cc:00:00:02"


# ---------------------------------------------------------------------------
# T041: Client cardinality capping
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestClientCapping:
    """build_snapshot_from_api caps clients at max_clients."""

    def test_max_clients_caps_to_top_n_by_traffic(self):
        """With max_clients=2, only the top 2 by traffic are kept."""
        clients_data = [
            {"mac": "aa:bb:cc:00:00:01", "rx_bytes": 100, "tx_bytes": 50},
            {"mac": "aa:bb:cc:00:00:02", "rx_bytes": 5000, "tx_bytes": 3000},
            {"mac": "aa:bb:cc:00:00:03", "rx_bytes": 200, "tx_bytes": 100},
            {"mac": "aa:bb:cc:00:00:04", "rx_bytes": 9000, "tx_bytes": 1000},
        ]
        snap = build_snapshot_from_api(
            "main", "default", [], clients_data, [], max_clients=2,
        )
        site = snap.sites["default"]
        assert len(site.clients) == 2
        # Highest traffic clients kept (sorted descending)
        macs = [c.mac for c in site.clients]
        assert "aa:bb:cc:00:00:04" in macs  # 10000 total
        assert "aa:bb:cc:00:00:02" in macs  # 8000 total

    def test_max_clients_zero_keeps_all(self):
        """max_clients=0 means no cap — all clients are kept."""
        clients_data = [
            {"mac": f"aa:bb:cc:00:00:{i:02x}", "rx_bytes": i * 100, "tx_bytes": 0}
            for i in range(10)
        ]
        snap = build_snapshot_from_api(
            "main", "default", [], clients_data, [], max_clients=0,
        )
        site = snap.sites["default"]
        assert len(site.clients) == 10

    def test_max_clients_larger_than_actual_keeps_all(self):
        """When max_clients exceeds actual count, all clients kept."""
        clients_data = [
            {"mac": "aa:bb:cc:00:00:01", "rx_bytes": 100, "tx_bytes": 50},
        ]
        snap = build_snapshot_from_api(
            "main", "default", [], clients_data, [], max_clients=100,
        )
        site = snap.sites["default"]
        assert len(site.clients) == 1


# ---------------------------------------------------------------------------
# T033: Grace period pruning
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestGracePeriodPruning:
    """GracePeriodTracker removes stale instances after the grace window."""

    def test_tracker_importable(self):
        """GracePeriodTracker must be importable from instances module."""
        from pcp_pmda_unifi.instances import GracePeriodTracker
        tracker = GracePeriodTracker()
        assert tracker is not None

    def test_new_instances_are_not_stale(self):
        """Freshly seen instances should not appear in the stale set."""
        from pcp_pmda_unifi.instances import GracePeriodTracker
        tracker = GracePeriodTracker()
        tracker.update_seen({"a", "b", "c"})
        stale = tracker.get_stale(grace_period_seconds=300)
        assert stale == set()

    def test_unseen_instances_become_stale_after_grace_period(self):
        """Instances not updated beyond the grace period are pruned."""
        import time
        from pcp_pmda_unifi.instances import GracePeriodTracker
        tracker = GracePeriodTracker()
        # Manually backdate the last_seen timestamp
        tracker.update_seen({"a", "b"})
        tracker._last_seen["a"] = time.monotonic() - 600  # 10 min ago
        stale = tracker.get_stale(grace_period_seconds=300)
        assert stale == {"a"}

    def test_reappearing_instance_resets_timer(self):
        """An instance that reappears should no longer be stale."""
        import time
        from pcp_pmda_unifi.instances import GracePeriodTracker
        tracker = GracePeriodTracker()
        tracker.update_seen({"a"})
        tracker._last_seen["a"] = time.monotonic() - 600
        # Confirm it's stale
        assert "a" in tracker.get_stale(grace_period_seconds=300)
        # Now it reappears
        tracker.update_seen({"a"})
        assert "a" not in tracker.get_stale(grace_period_seconds=300)

    def test_prune_removes_stale_from_tracking(self):
        """After pruning, stale entries should be removed from internal state."""
        import time
        from pcp_pmda_unifi.instances import GracePeriodTracker
        tracker = GracePeriodTracker()
        tracker.update_seen({"a", "b"})
        tracker._last_seen["a"] = time.monotonic() - 600
        stale = tracker.get_stale(grace_period_seconds=300)
        tracker.prune(stale)
        # "a" should no longer be tracked at all
        assert "a" not in tracker._last_seen
        assert "b" in tracker._last_seen
