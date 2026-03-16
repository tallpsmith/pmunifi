"""Network topology discovery and export (US5 companion tool).

Discovers inter-device links from UniFi stat/device uplink fields
and exports them as Graphviz DOT or structured JSON.  Each edge is
annotated with the corresponding PCP switch-port instance name so
visualisation tools can overlay live metric data.

This module has zero dependency on the PMDA class — it is a
standalone library used by the unifi2dot CLI.
"""

import json
from dataclasses import dataclass
from typing import Dict, List

from pcp_pmda_unifi.collector import normalise_mac
from pcp_pmda_unifi.instances import switch_port_instance_name

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class TopologyLink:
    """A discovered physical link between two UniFi devices."""

    src_device: str
    src_mac: str
    src_port: int
    dst_device: str
    dst_mac: str
    dst_port: int
    speed: int
    instance_name: str


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_topology(
    devices: List[Dict],
    controller: str = "main",
    site: str = "default",
) -> List[TopologyLink]:
    """Walk device uplinks and build a list of inter-device links.

    For each device that has an ``uplink`` field whose MAC matches
    another known device, we create a TopologyLink.  The link's
    instance_name references the destination port on the upstream
    device, matching the PCP metric instance for that port.

    Self-referencing uplinks and unresolvable MACs are silently skipped.
    """
    # Build MAC → device lookup
    mac_to_device: Dict[str, Dict] = {}
    for dev in devices:
        mac = normalise_mac(dev.get("mac", ""))
        if mac:
            mac_to_device[mac] = dev

    links: List[TopologyLink] = []

    for dev in devices:
        uplink = dev.get("uplink")
        if not uplink or not isinstance(uplink, dict):
            continue

        uplink_mac_raw = uplink.get("mac", "")
        if not uplink_mac_raw:
            continue

        uplink_mac = normalise_mac(uplink_mac_raw)
        dev_mac = normalise_mac(dev.get("mac", ""))

        # Skip self-references
        if uplink_mac == dev_mac:
            continue

        # Skip if upstream device is unknown
        upstream = mac_to_device.get(uplink_mac)
        if upstream is None:
            continue

        uplink_port_idx = uplink.get("port_idx", 0)
        uplink_speed = uplink.get("speed", 0)
        upstream_name = upstream.get("name", uplink_mac)

        # Find which port on *this* device is the uplink port
        src_port_idx = _find_uplink_port(dev)

        # Instance name references the upstream device's port
        inst_name = switch_port_instance_name(
            controller, site, upstream_name, uplink_port_idx,
        )

        links.append(TopologyLink(
            src_device=dev.get("name", dev_mac),
            src_mac=dev_mac,
            src_port=src_port_idx,
            dst_device=upstream_name,
            dst_mac=uplink_mac,
            dst_port=uplink_port_idx,
            speed=uplink_speed,
            instance_name=inst_name,
        ))

    return links


def _find_uplink_port(device: Dict) -> int:
    """Find the port_idx of the uplink port on a device, or 0 if unknown."""
    for port in device.get("port_table", []):
        if port.get("is_uplink"):
            result: int = port.get("port_idx", 0)
            return result
    return 0


# ---------------------------------------------------------------------------
# DOT export
# ---------------------------------------------------------------------------


def _dot_safe_id(name: str) -> str:
    """Turn a device name into a DOT-safe node identifier."""
    return name.replace("-", "_").replace(" ", "_").replace(".", "_")


def to_dot(links: List[TopologyLink], devices: List[Dict]) -> str:
    """Render the topology as a Graphviz DOT digraph.

    Nodes get device-name labels with model info.  Edges carry
    port and speed labels, with the PCP instance name as a comment.
    """
    lines = ["digraph unifi_topology {", '  rankdir=LR;', '  node [shape=box];']

    # Emit all device nodes (even those with no links)
    for dev in devices:
        name = dev.get("name", dev.get("mac", "unknown"))
        model = dev.get("model", "")
        node_id = _dot_safe_id(name)
        label = f"{name}\\n{model}" if model else name
        lines.append(f'  {node_id} [label="{label}"];')

    # Emit edges
    for link in links:
        src_id = _dot_safe_id(link.src_device)
        dst_id = _dot_safe_id(link.dst_device)
        label = f"Port{link.dst_port} ({link.speed}Mbps)"
        # Instance name as comment for tooling and as tooltip for SVG
        lines.append(
            f'  {src_id} -> {dst_id} [label="{label}" '
            f'tooltip="{link.instance_name}"];'
            f"  // {link.instance_name}"
        )

    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# JSON export
# ---------------------------------------------------------------------------


def to_json(links: List[TopologyLink], devices: List[Dict]) -> str:
    """Render the topology as a JSON graph for D3.js / web visualisation.

    Returns a JSON string with ``nodes`` and ``edges`` arrays.
    """
    nodes = []
    for dev in devices:
        nodes.append({
            "name": dev.get("name", dev.get("mac", "unknown")),
            "mac": dev.get("mac", ""),
            "model": dev.get("model", ""),
            "type": dev.get("type", ""),
            "ip": dev.get("ip", ""),
        })

    edges = []
    for link in links:
        edges.append({
            "src_device": link.src_device,
            "src_port": link.src_port,
            "dst_device": link.dst_device,
            "dst_port": link.dst_port,
            "speed": link.speed,
            "instance_name": link.instance_name,
        })

    return json.dumps({"nodes": nodes, "edges": edges}, indent=2)
