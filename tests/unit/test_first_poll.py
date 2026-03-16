"""Tests for synchronous first poll — eliminates the startup race window.

Issue #2: PMDA returns errors during first poll cycle after install because
poller threads haven't produced a snapshot yet when PMCD starts fetching.

The fix runs the first poll synchronously before starting the background
thread, so snapshots are always available when PMCD connects.
"""

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


# ---------------------------------------------------------------------------
# Synchronous first poll on the poller
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSynchronousFirstPoll:
    """ControllerPoller.run_initial_poll() executes one poll cycle on the
    calling thread so a snapshot exists before the background loop starts.
    """

    def test_run_initial_poll_populates_snapshot(self):
        """After run_initial_poll, snapshot must not be None."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        assert poller.snapshot is None

        poller.run_initial_poll()

        assert poller.snapshot is not None
        assert isinstance(poller.snapshot, Snapshot)

    def test_run_initial_poll_returns_true_on_success(self):
        """Callers need to know whether the initial poll succeeded."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        result = poller.run_initial_poll()
        assert result is True

    def test_run_initial_poll_returns_false_on_failure(self):
        """If the API is unreachable, initial poll returns False but doesn't crash."""
        client = _make_mock_client()
        client.fetch_devices.side_effect = ConnectionError("unreachable")
        poller = ControllerPoller("main", client, sites=["default"])
        result = poller.run_initial_poll()
        assert result is False

    def test_run_initial_poll_leaves_snapshot_none_on_failure(self):
        """A failed initial poll should not produce a bogus snapshot."""
        client = _make_mock_client()
        client.fetch_devices.side_effect = ConnectionError("unreachable")
        poller = ControllerPoller("main", client, sites=["default"])
        poller.run_initial_poll()
        assert poller.snapshot is None

    def test_snapshot_available_before_thread_start(self):
        """The whole point: snapshot exists before the daemon thread runs."""
        client = _make_mock_client()
        poller = ControllerPoller("main", client, sites=["default"])
        poller.run_initial_poll()
        # Haven't called poller.start() yet — snapshot is already there
        assert poller.snapshot is not None
        assert not poller.is_alive()

    def test_thread_continues_polling_after_initial_poll(self):
        """After run_initial_poll + start, the background loop still works."""
        client = _make_mock_client()
        poller = ControllerPoller(
            "main", client, sites=["default"], poll_interval=1,
        )
        poller.run_initial_poll()
        first_snap = poller.snapshot

        poller.start()
        time.sleep(0.3)
        poller.stop()
        poller.join(timeout=2)

        # Thread should have polled at least once more
        assert poller.snapshot is not first_snap or client.fetch_devices.call_count > 1
