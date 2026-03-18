"""Human-readable formatting helpers for metric display values.

Patterns:
  format_duration(seconds)      → "65d 16h 11m"   (for uptime values)
  format_time_ago(epoch)        → "30s ago"        (for last_poll / last_seen)
  format_device_state(state)    → "connected"      (for device state codes)
"""

import time


def format_duration(seconds: int) -> str:
    """Format a duration in seconds as a compact human-readable string.

    Drops sub-components that are noise at larger scales:
      < 1h   → "2m 5s"
      >= 1h  → "1h 1m"    (seconds dropped)
      >= 1d  → "65d 16h 11m"  (seconds dropped)
    """
    if seconds <= 0:
        return "0s"

    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)

    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    if minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_time_ago(epoch: float) -> str:
    """Format an epoch timestamp as a relative 'X ago' string.

    Returns "never" for epoch == 0 (meaning 'not yet polled').
    Returns "0s ago" for future timestamps (clock skew).
    """
    if epoch == 0:
        return "never"

    elapsed = int(time.time() - epoch)
    if elapsed < 0:
        elapsed = 0

    return f"{format_duration(elapsed)} ago"


# UniFi device state codes — reverse-engineered from community docs and
# the unpoller project.  The controller API doesn't formally document these.
_DEVICE_STATE_NAMES = {
    0: "disconnected",
    1: "connected",
    2: "pending",
    4: "upgrading",
    5: "provisioning",
    6: "heartbeat-miss",
    7: "adopting",
    9: "discovery",
    11: "isolated",
}


def format_device_state(state: int) -> str:
    """Map a UniFi device state integer to a human-readable label."""
    return _DEVICE_STATE_NAMES.get(state, f"unknown({state})")
