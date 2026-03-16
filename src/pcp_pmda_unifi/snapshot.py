"""Immutable snapshot data structures for the UniFi PCP PMDA.

The poller thread builds a Snapshot from raw API responses and atomically
swaps it into the PMDA.  The dispatch thread only reads — never writes.

Usage:
    from pcp_pmda_unifi.snapshot import build_snapshot_from_api
    snap = build_snapshot_from_api("main", "default", devices, clients, health)
"""

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pcp_pmda_unifi.collector import normalise_mac


# ---------------------------------------------------------------------------
# DPI category name lookup (UniFi numeric cat → human-readable)
# ---------------------------------------------------------------------------

DPI_CATEGORY_NAMES: Dict[int, str] = {
    0: "Instant-Messaging",
    1: "P2P",
    2: "File-Transfer",
    3: "Streaming-Media",
    4: "Mail-and-Collaboration",
    5: "Voice-over-IP",
    6: "Database",
    7: "Gaming",
    8: "Network-Management",
    9: "Remote-Access",
    10: "Software-Update",
    11: "Web",
    12: "Security",
    13: "Social-Network",
    14: "Business",
    15: "Network-Protocol",
    16: "IOT",
    17: "Shopping",
    18: "Video",
    19: "Music",
    20: "Productivity",
    21: "Cloud",
    22: "Advertisement",
    23: "Adult",
    24: "VPN",
    25: "Health",
}


# ---------------------------------------------------------------------------
# Data classes — one per instance domain entity
# ---------------------------------------------------------------------------


@dataclass
class PortData:
    """Switch port counters and status fields."""
    port_idx: int = 0
    name: str = ""
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    rx_errors: int = 0
    tx_errors: int = 0
    rx_dropped: int = 0
    tx_dropped: int = 0
    rx_broadcast: int = 0
    tx_broadcast: int = 0
    rx_multicast: int = 0
    tx_multicast: int = 0
    up: bool = False
    enable: bool = False
    speed: int = 0
    full_duplex: bool = False
    is_uplink: bool = False
    satisfaction: int = 0
    mac_count: int = 0
    poe_enable: bool = False
    poe_good: bool = False
    poe_power: float = 0.0
    poe_voltage: float = 0.0
    poe_current: float = 0.0
    poe_class: str = ""


@dataclass
class RadioData:
    """Access point radio interface metrics."""
    radio_type: str = ""
    channel: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    tx_dropped: int = 0
    tx_retries: int = 0
    num_sta: int = 0
    satisfaction: int = 0


@dataclass
class GatewayData:
    """Gateway WAN/LAN interface metrics."""
    wan_ip: str = ""
    wan_rx_bytes: int = 0
    wan_tx_bytes: int = 0
    wan_rx_packets: int = 0
    wan_tx_packets: int = 0
    wan_rx_dropped: int = 0
    wan_tx_dropped: int = 0
    wan_rx_errors: int = 0
    wan_tx_errors: int = 0
    wan_up: bool = False
    wan_speed: int = 0
    wan_latency: int = 0
    lan_rx_bytes: int = 0
    lan_tx_bytes: int = 0
    cpu: float = 0.0
    mem: float = 0.0
    temperature: Optional[float] = None


@dataclass
class DeviceMeta:
    """Static and slow-changing device metadata."""
    mac: str = ""
    name: str = ""
    ip: str = ""
    model: str = ""
    device_type: str = ""
    version: str = ""
    state: int = 0
    uptime: int = 0
    adopted: bool = False
    rx_bytes: int = 0
    tx_bytes: int = 0
    temperature: Optional[float] = None
    user_num_sta: int = 0
    guest_num_sta: int = 0
    num_ports: int = 0


@dataclass
class DeviceData:
    """Complete device state: metadata plus ports, radios, and gateway data."""
    meta: DeviceMeta = field(default_factory=DeviceMeta)
    ports: Dict[int, PortData] = field(default_factory=dict)
    radios: List[RadioData] = field(default_factory=list)
    gateway: Optional[GatewayData] = None


@dataclass
class ClientData:
    """Connected network client (wired or wireless)."""
    hostname: str = ""
    ip: str = ""
    mac: str = ""
    oui: str = ""
    is_wired: bool = False
    sw_mac: str = ""
    sw_port: int = 0
    rx_bytes: int = 0
    tx_bytes: int = 0
    rx_packets: int = 0
    tx_packets: int = 0
    uptime: int = 0
    signal: int = 0
    network: str = ""
    last_seen: int = 0


@dataclass
class HealthData:
    """Site health subsystem summary (wan, lan, wlan, vpn)."""
    subsystem: str = ""
    status: str = ""
    num_sta: int = 0
    num_user: int = 0
    num_guest: int = 0
    num_ap: int = 0
    num_sw: int = 0
    num_gw: int = 0
    wan_ip: str = ""
    latency: int = 0


@dataclass
class DpiData:
    """DPI traffic category counters."""
    category_id: int = 0
    category_name: str = ""
    rx_bytes: int = 0
    tx_bytes: int = 0


@dataclass
class SiteData:
    """All collected data for a single site."""
    health: List[HealthData] = field(default_factory=list)
    devices: Dict[str, DeviceData] = field(default_factory=dict)
    clients: List[ClientData] = field(default_factory=list)
    dpi_categories: List[DpiData] = field(default_factory=list)


@dataclass
class Snapshot:
    """Immutable snapshot of all data collected in one poll cycle.

    The poller builds this, freezes it, and swaps it into the PMDA
    via a single reference assignment (atomic under the GIL).
    """
    timestamp: float = 0.0
    controller_name: str = ""
    controller_version: str = ""
    sites: Dict[str, SiteData] = field(default_factory=dict)
    devices_discovered: int = 0
    clients_discovered: int = 0
    sites_polled: int = 0


# ---------------------------------------------------------------------------
# Builder helpers — extract typed dataclass instances from raw API dicts
# ---------------------------------------------------------------------------


def _extract_port_data(raw_port: Dict[str, Any]) -> PortData:
    """Build a PortData from a single port_table entry."""
    mac_table = raw_port.get("mac_table", [])
    return PortData(
        port_idx=int(raw_port.get("port_idx", 0)),
        name=str(raw_port.get("name", "")),
        rx_bytes=int(raw_port.get("rx_bytes", 0)),
        tx_bytes=int(raw_port.get("tx_bytes", 0)),
        rx_packets=int(raw_port.get("rx_packets", 0)),
        tx_packets=int(raw_port.get("tx_packets", 0)),
        rx_errors=int(raw_port.get("rx_errors", 0)),
        tx_errors=int(raw_port.get("tx_errors", 0)),
        rx_dropped=int(raw_port.get("rx_dropped", 0)),
        tx_dropped=int(raw_port.get("tx_dropped", 0)),
        rx_broadcast=int(raw_port.get("rx_broadcast", 0)),
        tx_broadcast=int(raw_port.get("tx_broadcast", 0)),
        rx_multicast=int(raw_port.get("rx_multicast", 0)),
        tx_multicast=int(raw_port.get("tx_multicast", 0)),
        up=bool(raw_port.get("up", False)),
        enable=bool(raw_port.get("enable", False)),
        speed=int(raw_port.get("speed", 0)),
        full_duplex=bool(raw_port.get("full_duplex", False)),
        is_uplink=bool(raw_port.get("is_uplink", False)),
        satisfaction=int(raw_port.get("satisfaction", 0)),
        mac_count=len(mac_table),
        poe_enable=bool(raw_port.get("poe_enable", False)),
        poe_good=bool(raw_port.get("poe_good", False)),
        poe_power=float(raw_port.get("poe_power", 0)),
        poe_voltage=float(raw_port.get("poe_voltage", 0)),
        poe_current=float(raw_port.get("poe_current", 0)),
        poe_class=str(raw_port.get("poe_class", "")),
    )


def _extract_radio_data(raw_radio: Dict[str, Any]) -> RadioData:
    """Build a RadioData from a single radio_table entry."""
    return RadioData(
        radio_type=str(raw_radio.get("radio", "")),
        channel=int(raw_radio.get("channel", 0)),
        rx_bytes=int(raw_radio.get("rx_bytes", 0)),
        tx_bytes=int(raw_radio.get("tx_bytes", 0)),
        rx_packets=int(raw_radio.get("rx_packets", 0)),
        tx_packets=int(raw_radio.get("tx_packets", 0)),
        tx_dropped=int(raw_radio.get("tx_dropped", 0)),
        tx_retries=int(raw_radio.get("tx_retries", 0)),
        num_sta=int(raw_radio.get("num_sta", 0)),
        satisfaction=int(raw_radio.get("satisfaction", 0)),
    )


def _extract_gateway_data(raw_device: Dict[str, Any]) -> Optional[GatewayData]:
    """Build GatewayData from a gateway/UDM device's wan1 or wan fields.

    Returns None if the device has no WAN interface data.
    """
    wan = raw_device.get("wan1") or raw_device.get("wan")
    if wan is None:
        return None

    system_stats = raw_device.get("system-stats", {})

    temperature_raw = raw_device.get("general_temperature")
    temperature = float(temperature_raw) if temperature_raw is not None else None

    return GatewayData(
        wan_ip=str(wan.get("ip", "")),
        wan_rx_bytes=int(wan.get("rx_bytes", 0)),
        wan_tx_bytes=int(wan.get("tx_bytes", 0)),
        wan_rx_packets=int(wan.get("rx_packets", 0)),
        wan_tx_packets=int(wan.get("tx_packets", 0)),
        wan_rx_dropped=int(wan.get("rx_dropped", 0)),
        wan_tx_dropped=int(wan.get("tx_dropped", 0)),
        wan_rx_errors=int(wan.get("rx_errors", 0)),
        wan_tx_errors=int(wan.get("tx_errors", 0)),
        wan_up=bool(wan.get("up", False)),
        wan_speed=int(wan.get("speed", 0)),
        cpu=float(system_stats.get("cpu", 0)),
        mem=float(system_stats.get("mem", 0)),
        temperature=temperature,
    )


def _extract_device_data(raw_device: Dict[str, Any]) -> DeviceData:
    """Build a complete DeviceData from a raw stat/device entry."""
    port_table = raw_device.get("port_table", [])
    radio_table = raw_device.get("radio_table", [])

    ports = {}
    for raw_port in port_table:
        port_data = _extract_port_data(raw_port)
        ports[port_data.port_idx] = port_data

    radios = [_extract_radio_data(r) for r in radio_table]

    device_type = str(raw_device.get("type", ""))
    gateway = None
    if device_type in ("ugw", "udm"):
        gateway = _extract_gateway_data(raw_device)

    temperature_raw = raw_device.get("general_temperature")
    temperature = float(temperature_raw) if temperature_raw is not None else None

    meta = DeviceMeta(
        mac=normalise_mac(str(raw_device.get("mac", ""))),
        name=str(raw_device.get("name", "")),
        ip=str(raw_device.get("ip", "")),
        model=str(raw_device.get("model", "")),
        device_type=device_type,
        version=str(raw_device.get("version", "")),
        state=int(raw_device.get("state", 0)),
        uptime=int(raw_device.get("uptime", 0)),
        adopted=bool(raw_device.get("adopted", False)),
        rx_bytes=int(raw_device.get("rx_bytes", 0)),
        tx_bytes=int(raw_device.get("tx_bytes", 0)),
        temperature=temperature,
        user_num_sta=int(raw_device.get("user-num_sta", 0)),
        guest_num_sta=int(raw_device.get("guest-num_sta", 0)),
        num_ports=len(port_table),
    )

    return DeviceData(meta=meta, ports=ports, radios=radios, gateway=gateway)


def _extract_client_data(raw_client: Dict[str, Any]) -> ClientData:
    """Build a ClientData from a raw stat/sta entry."""
    return ClientData(
        hostname=str(raw_client.get("hostname", "")),
        ip=str(raw_client.get("ip", "")),
        mac=normalise_mac(str(raw_client.get("mac", ""))),
        oui=str(raw_client.get("oui", "")),
        is_wired=bool(raw_client.get("is_wired", False)),
        sw_mac=normalise_mac(str(raw_client.get("sw_mac", ""))),
        sw_port=int(raw_client.get("sw_port", 0)),
        rx_bytes=int(raw_client.get("rx_bytes", 0)),
        tx_bytes=int(raw_client.get("tx_bytes", 0)),
        rx_packets=int(raw_client.get("rx_packets", 0)),
        tx_packets=int(raw_client.get("tx_packets", 0)),
        uptime=int(raw_client.get("uptime", 0)),
        signal=int(raw_client.get("signal", 0)),
        network=str(raw_client.get("network", "")),
        last_seen=int(raw_client.get("last_seen", 0)),
    )


def _extract_health_data(raw_health: Dict[str, Any]) -> HealthData:
    """Build a HealthData from a raw stat/health subsystem entry."""
    return HealthData(
        subsystem=str(raw_health.get("subsystem", "")),
        status=str(raw_health.get("status", "")),
        num_sta=int(raw_health.get("num_sta", 0)),
        num_user=int(raw_health.get("num_user", 0)),
        num_guest=int(raw_health.get("num_guest", 0)),
        num_ap=int(raw_health.get("num_ap", 0)),
        num_sw=int(raw_health.get("num_sw", 0)),
        num_gw=int(raw_health.get("num_gw", 0)),
        wan_ip=str(raw_health.get("wan_ip", "")),
        latency=int(raw_health.get("latency", 0)),
    )


def _extract_dpi_data(raw_dpi_list: List[Dict[str, Any]]) -> List[DpiData]:
    """Build DpiData objects from the by_cat array in a stat/sitedpi response.

    The API returns a wrapper object with a 'by_cat' array; each entry
    has a numeric 'cat' id plus rx/tx byte counters.
    """
    results = []
    for wrapper in raw_dpi_list:
        for cat_entry in wrapper.get("by_cat", []):
            cat_id = int(cat_entry.get("cat", 0))
            category_name = DPI_CATEGORY_NAMES.get(cat_id, f"Category-{cat_id}")
            results.append(DpiData(
                category_id=cat_id,
                category_name=category_name,
                rx_bytes=int(cat_entry.get("rx_bytes", 0)),
                tx_bytes=int(cat_entry.get("tx_bytes", 0)),
            ))
    return results


def _sort_clients_by_traffic(clients: List[ClientData]) -> List[ClientData]:
    """Sort clients by total traffic (rx + tx bytes) descending."""
    return sorted(
        clients,
        key=lambda c: c.rx_bytes + c.tx_bytes,
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Public builder
# ---------------------------------------------------------------------------


def build_snapshot_from_api(
    controller_name: str,
    site_name: str,
    devices_data: List[Dict[str, Any]],
    clients_data: List[Dict[str, Any]],
    health_data: List[Dict[str, Any]],
    sysinfo_data: Optional[List[Dict[str, Any]]] = None,
    dpi_data: Optional[List[Dict[str, Any]]] = None,
    max_clients: int = 1000,
) -> Snapshot:
    """Build a Snapshot from raw API response data arrays.

    This is the single entry point for converting API JSON into the
    typed dataclass hierarchy the PMDA dispatch thread reads from.
    """
    # Devices — keyed by normalised MAC
    devices: Dict[str, DeviceData] = {}
    for raw_device in devices_data:
        device = _extract_device_data(raw_device)
        devices[device.meta.mac] = device

    # Clients — sorted by traffic, capped at max_clients
    clients = [_extract_client_data(c) for c in clients_data]
    clients = _sort_clients_by_traffic(clients)
    if max_clients > 0:
        clients = clients[:max_clients]

    # Health subsystems
    health = [_extract_health_data(h) for h in health_data]

    # DPI categories (optional)
    dpi_categories = _extract_dpi_data(dpi_data) if dpi_data else []

    # Controller version from sysinfo
    controller_version = ""
    if sysinfo_data:
        first_info = sysinfo_data[0] if sysinfo_data else {}
        controller_version = str(first_info.get("version", ""))

    site_data = SiteData(
        health=health,
        devices=devices,
        clients=clients,
        dpi_categories=dpi_categories,
    )

    return Snapshot(
        timestamp=time.time(),
        controller_name=controller_name,
        controller_version=controller_version,
        sites={site_name: site_data},
        devices_discovered=len(devices),
        clients_discovered=len(clients),
        sites_polled=1,
    )
