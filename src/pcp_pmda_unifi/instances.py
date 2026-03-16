"""PCP instance naming functions for the UniFi PMDA.

Each instance domain has a deterministic naming scheme that encodes
controller, site, and entity identity into a single string.  These
names appear in pminfo, pmval, and archive labels — so they need to
be human-readable, stable, and whitespace-free.

Naming convention (multi-controller):
    controller/site/entity[::qualifier]

Naming convention (single-controller):
    site/entity[::qualifier]

When only one controller is configured, the controller prefix is
redundant noise — it's omitted to keep instance names clean.
"""

import re
import time
from typing import Dict, Set

_WHITESPACE_PATTERN = re.compile(r"\s+")


def _prefix_with_controller(controller: str, rest: str, single_controller: bool) -> str:
    """Prepend controller name only when multiple controllers are configured."""
    if single_controller:
        return rest
    return f"{controller}/{rest}"


def sanitise_instance_name(name: str) -> str:
    """Replace runs of whitespace with hyphens for PCP-safe instance names.

    PCP instance names must not contain whitespace.  This function is
    applied to device names, hostnames, and other user-provided strings
    before they become part of an instance name.
    """
    return _WHITESPACE_PATTERN.sub("-", name.strip())


# ---------------------------------------------------------------------------
# Indom 0: site
# ---------------------------------------------------------------------------


def site_instance_name(controller: str, site: str, *, single_controller: bool = False) -> str:
    """Build instance name for a site: 'controller/site' or just 'site'."""
    return _prefix_with_controller(controller, site, single_controller)


# ---------------------------------------------------------------------------
# Indom 1: device
# ---------------------------------------------------------------------------


def device_instance_name(
    controller: str, site: str, device_name: str, *, single_controller: bool = False,
) -> str:
    """Build instance name for a device: 'controller/site/device_name'."""
    safe_name = sanitise_instance_name(device_name)
    return _prefix_with_controller(controller, f"{site}/{safe_name}", single_controller)


# ---------------------------------------------------------------------------
# Indom 2: switch_port
# ---------------------------------------------------------------------------


def switch_port_instance_name(
    controller: str,
    site: str,
    device_name: str,
    port_idx: int,
    *,
    single_controller: bool = False,
) -> str:
    """Build instance name for a switch port: 'controller/site/device::PortN'."""
    safe_name = sanitise_instance_name(device_name)
    return _prefix_with_controller(
        controller, f"{site}/{safe_name}::Port{port_idx}", single_controller,
    )


# ---------------------------------------------------------------------------
# Indom 3: client
# ---------------------------------------------------------------------------


def client_instance_name(
    controller: str,
    site: str,
    hostname: str,
    mac: str = "",
    *,
    single_controller: bool = False,
) -> str:
    """Build instance name for a client: 'controller/site/hostname'.

    Falls back to MAC address if hostname is empty or whitespace-only.
    """
    identity = hostname.strip() if hostname.strip() else mac
    safe_identity = sanitise_instance_name(identity)
    return _prefix_with_controller(
        controller, f"{site}/{safe_identity}", single_controller,
    )


# ---------------------------------------------------------------------------
# Indom 4: ap_radio
# ---------------------------------------------------------------------------


def ap_radio_instance_name(
    controller: str,
    site: str,
    device_name: str,
    radio_type: str,
    *,
    single_controller: bool = False,
) -> str:
    """Build instance name for an AP radio: 'controller/site/device::radio_type'."""
    safe_name = sanitise_instance_name(device_name)
    return _prefix_with_controller(
        controller, f"{site}/{safe_name}::{radio_type}", single_controller,
    )


# ---------------------------------------------------------------------------
# Indom 5: gateway
# ---------------------------------------------------------------------------


def gateway_instance_name(
    controller: str, site: str, device_name: str, *, single_controller: bool = False,
) -> str:
    """Build instance name for a gateway: 'controller/site/device_name'."""
    safe_name = sanitise_instance_name(device_name)
    return _prefix_with_controller(
        controller, f"{site}/{safe_name}", single_controller,
    )


# ---------------------------------------------------------------------------
# Indom 6: controller
# ---------------------------------------------------------------------------


def controller_instance_name(controller: str) -> str:
    """Build instance name for a controller: just 'controller'."""
    return controller


# ---------------------------------------------------------------------------
# Indom 7: dpi_category
# ---------------------------------------------------------------------------


def dpi_category_instance_name(
    controller: str,
    site: str,
    category_name: str,
    *,
    single_controller: bool = False,
) -> str:
    """Build instance name for a DPI category: 'controller/site/category_name'."""
    safe_category = sanitise_instance_name(category_name)
    return _prefix_with_controller(
        controller, f"{site}/{safe_category}", single_controller,
    )


# ---------------------------------------------------------------------------
# Grace period tracking (FR-017)
# ---------------------------------------------------------------------------


class GracePeriodTracker:
    """Tracks instance last-seen times and identifies stale instances.

    Disconnected devices/clients remain in instance domains until the
    grace period expires, then are pruned.  This avoids instance churn
    when a device briefly goes offline.
    """

    def __init__(self) -> None:
        self._last_seen: Dict[str, float] = {}

    def update_seen(self, instance_names: Set[str]) -> None:
        """Mark all given instance names as seen right now."""
        now = time.monotonic()
        for name in instance_names:
            self._last_seen[name] = now

    def get_stale(self, grace_period_seconds: int) -> Set[str]:
        """Return instance names not seen for longer than the grace period."""
        cutoff = time.monotonic() - grace_period_seconds
        return {
            name for name, last in self._last_seen.items()
            if last < cutoff
        }

    def prune(self, stale_names: Set[str]) -> None:
        """Remove stale entries from internal tracking state."""
        for name in stale_names:
            self._last_seen.pop(name, None)
