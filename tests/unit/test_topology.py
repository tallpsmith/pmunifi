"""Tests for topology discovery and export (US5 - T045, T046).

TDD: These tests define the expected behaviour of discover_topology(),
to_dot(), and to_json() before the implementation exists.
"""

import json

import pytest

from pcp_pmda_unifi.topology import TopologyLink, discover_topology, to_dot, to_json


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _make_switch(name, mac, ip="10.0.0.1", model="USW-Pro-48-PoE",
                 uplink=None, port_table=None):
    """Build a minimal device dict resembling stat/device output."""
    device = {
        "name": name,
        "mac": mac,
        "ip": ip,
        "model": model,
        "type": "usw",
        "port_table": port_table or [],
    }
    if uplink is not None:
        device["uplink"] = uplink
    return device


def _two_switch_topology():
    """Core switch + access switch connected via uplink."""
    core = _make_switch(
        "Core-SW", "aa:bb:cc:00:00:01",
        port_table=[{"port_idx": 24, "speed": 10000}],
    )
    access = _make_switch(
        "Access-SW", "aa:bb:cc:00:00:02",
        uplink={
            "mac": "aa:bb:cc:00:00:01",
            "port_idx": 24,
            "speed": 10000,
            "type": "wire",
        },
        port_table=[{"port_idx": 48, "is_uplink": True, "speed": 10000}],
    )
    return [core, access]


# ===========================================================================
# T045 — TestTopologyDiscovery
# ===========================================================================


class TestTopologyDiscovery:
    """Given device data with uplink fields, discover inter-device links."""

    def test_discovers_link_from_uplink_mac(self):
        """Uplink.mac matching a known device produces a link."""
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")

        assert len(links) == 1
        link = links[0]
        assert link.src_device == "Access-SW"
        assert link.dst_device == "Core-SW"

    def test_link_has_instance_name(self):
        """Each link carries the PMDA switch port instance name."""
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")

        link = links[0]
        # Instance name for the uplink port on Core-SW port 24
        assert "Core-SW" in link.instance_name
        assert "Port24" in link.instance_name

    def test_orphan_device_produces_no_links(self):
        """A device without an uplink field generates no links."""
        devices = [_make_switch("Lonely-SW", "aa:bb:cc:00:00:99")]
        links = discover_topology(devices, controller="main", site="default")

        assert links == []

    def test_uplink_to_unknown_mac_produces_no_link(self):
        """An uplink pointing at a MAC not in the device list is skipped."""
        devices = [
            _make_switch(
                "Orphan-SW", "aa:bb:cc:00:00:03",
                uplink={"mac": "ff:ff:ff:ff:ff:ff", "port_idx": 1, "speed": 1000},
            ),
        ]
        links = discover_topology(devices, controller="main", site="default")
        assert links == []

    def test_missing_uplink_fields_handled_gracefully(self):
        """Partial or empty uplink dicts don't crash discovery."""
        devices = [
            _make_switch("Bad-SW", "aa:bb:cc:00:00:04", uplink={}),
            _make_switch("Also-Bad", "aa:bb:cc:00:00:05", uplink={"mac": ""}),
        ]
        links = discover_topology(devices, controller="main", site="default")
        assert links == []

    def test_self_referencing_uplink_ignored(self):
        """A device whose uplink.mac is its own MAC is skipped."""
        devices = [
            _make_switch(
                "Self-SW", "aa:bb:cc:00:00:06",
                uplink={"mac": "aa:bb:cc:00:00:06", "port_idx": 1, "speed": 1000},
            ),
        ]
        links = discover_topology(devices, controller="main", site="default")
        assert links == []

    def test_link_carries_speed(self):
        """The link speed is taken from the uplink field."""
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        assert links[0].speed == 10000

    def test_multiple_devices_with_uplinks(self):
        """Multiple devices pointing at the same core produce multiple links."""
        core = _make_switch(
            "Core-SW", "aa:bb:cc:00:00:01",
            port_table=[
                {"port_idx": 24, "speed": 10000},
                {"port_idx": 25, "speed": 1000},
            ],
        )
        sw_a = _make_switch(
            "SW-A", "aa:bb:cc:00:00:10",
            uplink={"mac": "aa:bb:cc:00:00:01", "port_idx": 24, "speed": 10000},
        )
        sw_b = _make_switch(
            "SW-B", "aa:bb:cc:00:00:11",
            uplink={"mac": "aa:bb:cc:00:00:01", "port_idx": 25, "speed": 1000},
        )
        links = discover_topology([core, sw_a, sw_b], controller="main", site="default")
        assert len(links) == 2
        src_names = {link.src_device for link in links}
        assert src_names == {"SW-A", "SW-B"}


# ===========================================================================
# T046 — TestDotExport
# ===========================================================================


class TestDotExport:
    """DOT output must be valid Graphviz syntax with device labels and port annotations."""

    def test_output_contains_digraph_keyword(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        dot = to_dot(links, devices)

        assert "digraph" in dot

    def test_nodes_have_device_name_labels(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        dot = to_dot(links, devices)

        assert "Core-SW" in dot
        assert "Access-SW" in dot

    def test_nodes_have_model_info(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        dot = to_dot(links, devices)

        assert "USW-Pro-48-PoE" in dot

    def test_edges_have_port_labels(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        dot = to_dot(links, devices)

        assert "Port24" in dot

    def test_edges_reference_instance_names(self):
        """Edges carry the unifi.switch.port.* instance name as annotation."""
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        dot = to_dot(links, devices)

        assert "main/default/Core-SW::Port24" in dot

    def test_basic_dot_structure(self):
        """Output has opening brace and closing brace."""
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        dot = to_dot(links, devices)

        stripped = dot.strip()
        assert stripped.startswith("digraph")
        assert stripped.endswith("}")

    def test_empty_topology_produces_valid_dot(self):
        """No links still produces a valid digraph with nodes only."""
        devices = [_make_switch("Lonely-SW", "aa:bb:cc:00:00:99")]
        links = discover_topology(devices, controller="main", site="default")
        dot = to_dot(links, devices)

        assert "digraph" in dot
        assert "Lonely-SW" in dot


# ===========================================================================
# T046 — TestJsonExport
# ===========================================================================


class TestJsonExport:
    """JSON export must have nodes/edges with required fields."""

    def test_output_has_nodes_and_edges_keys(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        result = json.loads(to_json(links, devices))

        assert "nodes" in result
        assert "edges" in result

    def test_nodes_have_required_fields(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        result = json.loads(to_json(links, devices))

        for node in result["nodes"]:
            assert "name" in node
            assert "mac" in node
            assert "model" in node
            assert "type" in node

    def test_edges_have_required_fields(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        result = json.loads(to_json(links, devices))

        assert len(result["edges"]) == 1
        edge = result["edges"][0]
        assert "src_device" in edge
        assert "src_port" in edge
        assert "dst_device" in edge
        assert "dst_port" in edge
        assert "speed" in edge
        assert "instance_name" in edge

    def test_node_ip_field_present(self):
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        result = json.loads(to_json(links, devices))

        for node in result["nodes"]:
            assert "ip" in node

    def test_valid_json_output(self):
        """to_json returns a parseable JSON string."""
        devices = _two_switch_topology()
        links = discover_topology(devices, controller="main", site="default")
        output = to_json(links, devices)

        # Should not raise
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_empty_topology_json(self):
        devices = [_make_switch("Lonely-SW", "aa:bb:cc:00:00:99")]
        links = discover_topology(devices, controller="main", site="default")
        result = json.loads(to_json(links, devices))

        assert len(result["nodes"]) == 1
        assert len(result["edges"]) == 0
