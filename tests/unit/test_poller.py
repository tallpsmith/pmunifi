"""T016: Tests for the background controller poller thread.

Validates that ControllerPoller correctly polls the UniFi API,
builds snapshots, handles errors gracefully, and provides atomic
snapshot access to the PMDA dispatch thread.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from pcp_pmda_unifi.poller import ControllerPoller
from pcp_pmda_unifi.snapshot import Snapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_client():
    """Build a mock UnifiClient that returns minimal valid API responses."""
    client = MagicMock()
    client.fetch_devices.return_value = [
        {
            "mac": "aa:bb:cc:dd:ee:ff",
            "name": "USW-Test",
            "type": "usw",
            "port_table": [
                {"port_idx": 1, "rx_bytes": 100, "tx_bytes": 200, "up": True, "enable": True},
            ],
        },
    ]
    client.fetch_clients.return_value = [
        {"mac": "11:22:33:44:55:66", "hostname": "laptop-test", "is_wired": True},
    ]
    client.fetch_health.return_value = [
        {"subsystem": "wan", "status": "ok"},
    ]
    return client


# ---------------------------------------------------------------------------
# Construction and daemon thread behaviour
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPollerConstruction:
    """ControllerPoller is a daemon thread with sane defaults."""

    def test_is_a_daemon_thread(self):
        """Poller must be a daemon so it dies with the main process."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        assert poller.daemon is True

    def test_is_a_thread(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        assert isinstance(poller, threading.Thread)

    def test_snapshot_is_none_before_first_poll(self):
        """No snapshot until the first poll cycle completes."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        assert poller.snapshot is None

    def test_default_poll_interval(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        assert poller.poll_interval == 30

    def test_custom_poll_interval(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"], poll_interval=60)
        assert poller.poll_interval == 60


# ---------------------------------------------------------------------------
# Single poll cycle (poll_once)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPollOnce:
    """poll_once() performs a single poll cycle and updates the snapshot."""

    def test_poll_once_calls_fetch_devices(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        client.fetch_devices.assert_called_with("default")

    def test_poll_once_calls_fetch_clients(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        client.fetch_clients.assert_called_with("default")

    def test_poll_once_calls_fetch_health(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        client.fetch_health.assert_called_with("default")

    def test_poll_once_builds_snapshot(self):
        """After one poll, a Snapshot should be available."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        assert isinstance(poller.snapshot, Snapshot)
        assert poller.snapshot.controller_name == "main"

    def test_poll_once_snapshot_contains_site_data(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        assert "default" in poller.snapshot.sites
        site = poller.snapshot.sites["default"]
        assert len(site.devices) == 1

    def test_poll_once_polls_multiple_sites(self):
        """When configured with multiple sites, poll each one."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default", "branch"])
        poller.poll_once()
        snap = poller.snapshot
        assert "default" in snap.sites
        assert "branch" in snap.sites

    def test_poll_once_records_duration(self):
        """Poll duration should be tracked in milliseconds."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        assert poller._poll_duration_ms >= 0

    def test_poll_once_records_last_poll_timestamp(self):
        client = _make_mock_client()
        before = time.time()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        after = time.time()
        assert before <= poller._last_poll_timestamp <= after

    def test_poll_once_sets_controller_up(self):
        """A successful poll means the controller is reachable."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        health = poller.controller_health
        assert health["up"] == 1


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPollerErrorHandling:
    """On collector failure, poller retains the last snapshot and counts errors."""

    def test_retains_last_snapshot_on_error(self):
        """If a poll fails, the previous snapshot should remain available."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        first_snapshot = poller.snapshot

        # Now make the client explode
        client.fetch_devices.side_effect = ConnectionError("boom")
        poller.poll_once()

        assert poller.snapshot is first_snapshot

    def test_increments_poll_errors_on_failure(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        assert poller._poll_errors == 0

        client.fetch_devices.side_effect = ConnectionError("boom")
        poller.poll_once()
        assert poller._poll_errors == 1

        poller.poll_once()
        assert poller._poll_errors == 2

    def test_controller_down_after_error(self):
        """Controller health should report down after a failed poll."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        client.fetch_devices.side_effect = RuntimeError("nope")
        poller.poll_once()
        assert poller.controller_health["up"] == 0

    def test_controller_recovers_after_error(self):
        """Controller should go back to up after a successful poll following failure."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])

        client.fetch_devices.side_effect = RuntimeError("nope")
        poller.poll_once()
        assert poller.controller_health["up"] == 0

        # Recover
        client.fetch_devices.side_effect = None
        client.fetch_devices.return_value = [{"mac": "aa:bb:cc:dd:ee:ff", "type": "usw"}]
        poller.poll_once()
        assert poller.controller_health["up"] == 1


# ---------------------------------------------------------------------------
# Atomic snapshot swap
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAtomicSnapshotSwap:
    """Snapshot property returns the latest completed snapshot."""

    def test_second_poll_replaces_snapshot(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        first = poller.snapshot

        poller.poll_once()
        second = poller.snapshot

        assert first is not second
        assert isinstance(second, Snapshot)

    def test_snapshot_property_is_read_only(self):
        """The snapshot property should not be directly settable."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        with pytest.raises(AttributeError):
            poller.snapshot = "nope"


# ---------------------------------------------------------------------------
# Controller health reporting
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestControllerHealth:
    """controller_health property returns a status dict for the PMDA."""

    def test_controller_health_has_required_keys(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.poll_once()
        health = poller.controller_health
        assert "up" in health
        assert "poll_duration_ms" in health
        assert "poll_errors" in health
        assert "last_poll" in health

    def test_controller_health_poll_errors_is_cumulative(self):
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        client.fetch_devices.side_effect = RuntimeError("fail")
        poller.poll_once()
        poller.poll_once()
        assert poller.controller_health["poll_errors"] == 2


# ---------------------------------------------------------------------------
# Thread start/stop lifecycle
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPollerLifecycle:
    """Poller starts and stops cleanly via the stop event."""

    def test_starts_and_stops_cleanly(self):
        """Poller thread should start, run briefly, and stop on request."""
        client = _make_mock_client()
        poller = ControllerPoller(
            "main", client, sites=["default"], poll_interval=1
        )
        poller.start()
        # Give it a moment to spin up
        time.sleep(0.1)
        assert poller.is_alive()

        poller.stop()
        poller.join(timeout=2)
        assert not poller.is_alive()

    def test_polls_on_startup_before_sleeping(self):
        """The poller should do an immediate poll, not wait for poll_interval first."""
        client = _make_mock_client()
        poller = ControllerPoller(
            "main", client, sites=["default"], poll_interval=60
        )
        poller.start()
        # Even with a 60s interval, snapshot should appear quickly
        time.sleep(0.5)
        poller.stop()
        poller.join(timeout=2)
        assert poller.snapshot is not None


# ---------------------------------------------------------------------------
# US8 / T058: Multi-controller poller — independent pollers, distinct snapshots
# ---------------------------------------------------------------------------


def _make_mock_client_for(device_name="USW-Test", device_mac="aa:bb:cc:dd:ee:ff"):
    """Build a mock UnifiClient with a configurable device identity."""
    client = MagicMock()
    client.fetch_devices.return_value = [
        {
            "mac": device_mac,
            "name": device_name,
            "type": "usw",
            "port_table": [
                {"port_idx": 1, "rx_bytes": 100, "tx_bytes": 200, "up": True},
            ],
        },
    ]
    client.fetch_clients.return_value = [
        {"mac": "11:22:33:44:55:66", "hostname": "laptop-test", "is_wired": True},
    ]
    client.fetch_health.return_value = [
        {"subsystem": "wan", "status": "ok"},
    ]
    return client


@pytest.mark.unit
class TestMultiControllerPoller:
    """Two ControllerPoller instances with different names produce independent
    snapshots tagged with their respective controller_name values.
    """

    def test_pollers_have_distinct_controller_names(self):
        hq_client = _make_mock_client_for("HQ-Switch", "aa:bb:cc:00:00:01")
        branch_client = _make_mock_client_for("Branch-Switch", "aa:bb:cc:00:00:02")
        hq = ControllerPoller("hq", hq_client, sites=["default"])
        branch = ControllerPoller("branch", branch_client, sites=["default"])
        assert hq.controller_name == "hq"
        assert branch.controller_name == "branch"

    def test_snapshots_have_distinct_controller_names(self):
        hq_client = _make_mock_client_for("HQ-Switch", "aa:bb:cc:00:00:01")
        branch_client = _make_mock_client_for("Branch-Switch", "aa:bb:cc:00:00:02")
        hq = ControllerPoller("hq", hq_client, sites=["default"])
        branch = ControllerPoller("branch", branch_client, sites=["default"])
        hq.poll_once()
        branch.poll_once()
        assert hq.snapshot.controller_name == "hq"
        assert branch.snapshot.controller_name == "branch"

    def test_snapshots_contain_independent_device_data(self):
        """Each poller's snapshot should contain its own devices, not the other's."""
        hq_client = _make_mock_client_for("HQ-Switch", "aa:bb:cc:00:00:01")
        branch_client = _make_mock_client_for("Branch-Switch", "aa:bb:cc:00:00:02")
        hq = ControllerPoller("hq", hq_client, sites=["default"])
        branch = ControllerPoller("branch", branch_client, sites=["default"])
        hq.poll_once()
        branch.poll_once()

        hq_devices = list(hq.snapshot.sites["default"].devices.values())
        branch_devices = list(branch.snapshot.sites["default"].devices.values())
        assert hq_devices[0].meta.name == "HQ-Switch"
        assert branch_devices[0].meta.name == "Branch-Switch"

    def test_independent_poll_intervals(self):
        """Each poller can have its own poll interval."""
        hq = ControllerPoller("hq", _make_mock_client(), sites=["default"], poll_interval=30)
        branch = ControllerPoller("branch", _make_mock_client(), sites=["default"], poll_interval=60)
        assert hq.poll_interval == 30
        assert branch.poll_interval == 60

    def test_error_in_one_poller_does_not_affect_the_other(self):
        """A failure in one poller should not corrupt the other's snapshot."""
        hq_client = _make_mock_client_for("HQ-Switch", "aa:bb:cc:00:00:01")
        branch_client = _make_mock_client_for("Branch-Switch", "aa:bb:cc:00:00:02")

        hq = ControllerPoller("hq", hq_client, sites=["default"])
        branch = ControllerPoller("branch", branch_client, sites=["default"])

        # Both poll successfully first
        hq.poll_once()
        branch.poll_once()

        # HQ blows up; branch stays fine
        hq_client.fetch_devices.side_effect = ConnectionError("hq is on fire")
        hq.poll_once()
        branch.poll_once()

        assert hq.controller_health["up"] == 0
        assert branch.controller_health["up"] == 1
        assert branch.snapshot.controller_name == "branch"

    def test_controller_health_reports_are_independent(self):
        hq_client = _make_mock_client_for("HQ-Switch", "aa:bb:cc:00:00:01")
        branch_client = _make_mock_client_for("Branch-Switch", "aa:bb:cc:00:00:02")

        hq = ControllerPoller("hq", hq_client, sites=["default"])
        branch = ControllerPoller("branch", branch_client, sites=["default"])

        hq.poll_once()
        branch.poll_once()

        # Both healthy, distinct reports
        assert hq.controller_health["up"] == 1
        assert branch.controller_health["up"] == 1
        assert hq.controller_health is not branch.controller_health


# ---------------------------------------------------------------------------
# T061/T062: DPI opt-in polling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPollerDpiOptIn:
    """When enable_dpi=True, poller calls fetch_dpi and includes DPI data."""

    def test_dpi_disabled_by_default(self):
        """By default, enable_dpi should be False."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        assert poller._enable_dpi is False

    def test_enable_dpi_constructor_parameter(self):
        """Constructor accepts enable_dpi kwarg."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"], enable_dpi=True)
        assert poller._enable_dpi is True

    def test_dpi_disabled_does_not_call_fetch_dpi(self):
        """When DPI is off, fetch_dpi must never be called."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"], enable_dpi=False)
        poller.poll_once()
        client.fetch_dpi.assert_not_called()

    def test_dpi_enabled_calls_fetch_dpi(self):
        """When DPI is on, fetch_dpi must be called for each site."""
        client = _make_mock_client()
        client.fetch_dpi.return_value = [
            {"by_cat": [{"cat": 3, "rx_bytes": 1000, "tx_bytes": 2000}]},
        ]
        poller = ControllerPoller("main", client, sites=["default"], enable_dpi=True)
        poller.poll_once()
        client.fetch_dpi.assert_called_with("default")

    def test_dpi_enabled_snapshot_has_dpi_categories(self):
        """When DPI is on, snapshot should contain DPI category data."""
        client = _make_mock_client()
        client.fetch_dpi.return_value = [
            {"by_cat": [{"cat": 3, "rx_bytes": 1000, "tx_bytes": 2000}]},
        ]
        poller = ControllerPoller("main", client, sites=["default"], enable_dpi=True)
        poller.poll_once()
        site = poller.snapshot.sites["default"]
        assert len(site.dpi_categories) == 1
        assert site.dpi_categories[0].category_name == "Streaming-Media"
        assert site.dpi_categories[0].rx_bytes == 1000

    def test_dpi_disabled_snapshot_has_empty_dpi_categories(self):
        """When DPI is off, dpi_categories should be empty."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"], enable_dpi=False)
        poller.poll_once()
        site = poller.snapshot.sites["default"]
        assert site.dpi_categories == []
