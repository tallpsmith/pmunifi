"""Tests for human-readable metric display formatting helpers.

Three formatters:
  format_duration      — seconds → "65d 16h 11m"
  format_time_ago      — epoch   → "3s ago" / "2m 15s ago"
  format_device_state  — int     → "connected" / "disconnected"
"""

import time

from pcp_pmda_unifi.formatting import (
    format_device_state,
    format_duration,
    format_time_ago,
)


class TestFormatDuration:
    """Seconds → compact human-readable duration string."""

    def test_zero_seconds(self):
        assert format_duration(0) == "0s"

    def test_seconds_only(self):
        assert format_duration(45) == "45s"

    def test_minutes_and_seconds(self):
        assert format_duration(125) == "2m 5s"

    def test_hours_and_minutes(self):
        assert format_duration(3661) == "1h 1m"

    def test_days_hours_minutes(self):
        assert format_duration(5674519) == "65d 16h 15m"

    def test_exactly_one_day(self):
        assert format_duration(86400) == "1d 0h 0m"

    def test_large_uptime(self):
        # 365 days
        result = format_duration(365 * 86400)
        assert result.startswith("365d")

    def test_drops_seconds_when_hours_present(self):
        """Once we're in hours territory, seconds are noise."""
        result = format_duration(3661)
        assert "s" not in result

    def test_drops_seconds_when_days_present(self):
        result = format_duration(90061)
        assert "s" not in result

    def test_shows_seconds_when_under_an_hour(self):
        result = format_duration(125)
        assert "s" in result


class TestFormatTimeAgo:
    """Epoch timestamp → 'Xs ago' / 'Xm Ys ago' string."""

    def test_just_now(self):
        now = time.time()
        result = format_time_ago(now)
        assert result == "0s ago"

    def test_seconds_ago(self):
        now = time.time()
        result = format_time_ago(now - 30)
        assert result == "30s ago"

    def test_minutes_ago(self):
        now = time.time()
        result = format_time_ago(now - 150)
        assert result == "2m 30s ago"

    def test_hours_ago(self):
        now = time.time()
        result = format_time_ago(now - 7200)
        assert result == "2h 0m ago"

    def test_days_ago(self):
        now = time.time()
        result = format_time_ago(now - 172800)
        assert result == "2d 0h 0m ago"

    def test_zero_epoch_returns_never(self):
        """An epoch of 0 means 'never polled'."""
        assert format_time_ago(0) == "never"

    def test_future_timestamp_returns_zero(self):
        """If timestamp is in the future (clock skew), treat as 0s ago."""
        future = time.time() + 100
        assert format_time_ago(future) == "0s ago"


class TestFormatDeviceState:
    """UniFi device state integer → human-readable label."""

    def test_connected(self):
        assert format_device_state(1) == "connected"

    def test_disconnected(self):
        assert format_device_state(0) == "disconnected"

    def test_upgrading(self):
        assert format_device_state(4) == "upgrading"

    def test_provisioning(self):
        assert format_device_state(5) == "provisioning"

    def test_adopting(self):
        assert format_device_state(7) == "adopting"

    def test_heartbeat_missed(self):
        assert format_device_state(6) == "heartbeat-miss"

    def test_isolated(self):
        assert format_device_state(11) == "isolated"

    def test_unknown_state_includes_code(self):
        """Unmapped state codes should show the raw number."""
        assert format_device_state(99) == "unknown(99)"
