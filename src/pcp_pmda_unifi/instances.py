"""PCP instance naming functions for the UniFi PMDA.

Each instance domain has a deterministic naming scheme that encodes
controller, site, and entity identity into a single string.  These
names appear in pminfo, pmval, and archive labels — so they need to
be human-readable, stable, and whitespace-free.

Naming convention:
    controller/site/entity[::qualifier]
"""

import re

_WHITESPACE_PATTERN = re.compile(r"\s+")


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


def site_instance_name(controller: str, site: str) -> str:
    """Build instance name for a site: 'controller/site'."""
    return f"{controller}/{site}"


# ---------------------------------------------------------------------------
# Indom 1: device
# ---------------------------------------------------------------------------


def device_instance_name(controller: str, site: str, device_name: str) -> str:
    """Build instance name for a device: 'controller/site/device_name'."""
    safe_name = sanitise_instance_name(device_name)
    return f"{controller}/{site}/{safe_name}"


# ---------------------------------------------------------------------------
# Indom 2: switch_port
# ---------------------------------------------------------------------------


def switch_port_instance_name(
    controller: str,
    site: str,
    device_name: str,
    port_idx: int,
) -> str:
    """Build instance name for a switch port: 'controller/site/device::PortN'."""
    safe_name = sanitise_instance_name(device_name)
    return f"{controller}/{site}/{safe_name}::Port{port_idx}"


# ---------------------------------------------------------------------------
# Indom 3: client
# ---------------------------------------------------------------------------


def client_instance_name(
    controller: str,
    site: str,
    hostname: str,
    mac: str = "",
) -> str:
    """Build instance name for a client: 'controller/site/hostname'.

    Falls back to MAC address if hostname is empty or whitespace-only.
    """
    identity = hostname.strip() if hostname.strip() else mac
    safe_identity = sanitise_instance_name(identity)
    return f"{controller}/{site}/{safe_identity}"


# ---------------------------------------------------------------------------
# Indom 4: ap_radio
# ---------------------------------------------------------------------------


def ap_radio_instance_name(
    controller: str,
    site: str,
    device_name: str,
    radio_type: str,
) -> str:
    """Build instance name for an AP radio: 'controller/site/device::radio_type'."""
    safe_name = sanitise_instance_name(device_name)
    return f"{controller}/{site}/{safe_name}::{radio_type}"


# ---------------------------------------------------------------------------
# Indom 5: gateway
# ---------------------------------------------------------------------------


def gateway_instance_name(controller: str, site: str, device_name: str) -> str:
    """Build instance name for a gateway: 'controller/site/device_name'."""
    safe_name = sanitise_instance_name(device_name)
    return f"{controller}/{site}/{safe_name}"


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
) -> str:
    """Build instance name for a DPI category: 'controller/site/category_name'."""
    safe_category = sanitise_instance_name(category_name)
    return f"{controller}/{site}/{safe_category}"
