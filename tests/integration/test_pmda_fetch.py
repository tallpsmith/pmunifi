"""T017, T018, T030-T033: Integration tests for the UniFi PMDA fetch callbacks.

These tests validate metric registration and fetch callback behaviour.
Since PCP Python bindings (pcp.pmda) are unlikely to be installed on
macOS development machines, all tests skip gracefully when unavailable.
"""

import pytest

try:
    from pcp_pmda_unifi.pmda import (
        HAS_PCP,
        CONTROLLER_METRICS,
        SWITCH_PORT_METRICS,
    )
except ImportError:
    HAS_PCP = False

# New metric lists — imported separately so old tests survive if these
# don't exist yet (the tests below will fail with a clear ImportError).
_SITE_METRICS = None
_DEVICE_METRICS = None
_GATEWAY_METRICS = None
try:
    from pcp_pmda_unifi.pmda import SITE_METRICS as _SM
    _SITE_METRICS = _SM
except ImportError:
    pass
try:
    from pcp_pmda_unifi.pmda import DEVICE_METRICS as _DM
    _DEVICE_METRICS = _DM
except ImportError:
    pass
try:
    from pcp_pmda_unifi.pmda import GATEWAY_METRICS as _GM
    _GATEWAY_METRICS = _GM
except ImportError:
    pass

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not HAS_PCP, reason="PCP bindings not installed"),
]


# ---------------------------------------------------------------------------
# Metric registration — existing clusters
# ---------------------------------------------------------------------------


class TestSwitchPortMetricRegistration:
    """Cluster 2: all 19 switch port metrics should be defined."""

    def test_switch_port_metrics_count(self):
        """Exactly 19 switch port metrics per the data model."""
        assert len(SWITCH_PORT_METRICS) == 19

    def test_switch_port_metrics_have_required_fields(self):
        """Each metric tuple has (name, item, type, sem, attr_name)."""
        for metric in SWITCH_PORT_METRICS:
            assert len(metric) == 5, f"Metric {metric[0]} has wrong tuple length"

    def test_switch_port_metric_names_are_namespaced(self):
        """All switch port metrics live under unifi.switch.port.*"""
        for metric in SWITCH_PORT_METRICS:
            name = metric[0]
            assert name.startswith("unifi.switch.port."), (
                f"Metric {name} not under unifi.switch.port"
            )


class TestControllerMetricRegistration:
    """Cluster 9: controller health metrics — 8 after US3 expansion."""

    def test_controller_metrics_count(self):
        """Exactly 8 controller metrics after US3 (original 4 + 4 new)."""
        assert len(CONTROLLER_METRICS) == 8

    def test_controller_metric_names(self):
        expected_names = {
            "unifi.controller.up",
            "unifi.controller.poll_duration_ms",
            "unifi.controller.poll_errors",
            "unifi.controller.last_poll",
            "unifi.controller.version",
            "unifi.controller.devices_discovered",
            "unifi.controller.clients_discovered",
            "unifi.controller.sites_polled",
        }
        actual_names = {m[0] for m in CONTROLLER_METRICS}
        assert actual_names == expected_names


# ---------------------------------------------------------------------------
# T030: Site metric registration (cluster 0)
# ---------------------------------------------------------------------------


class TestSiteMetricRegistration:
    """Cluster 0: all 15 site-level metrics from data-model.md."""

    def test_site_metrics_list_exists(self):
        """SITE_METRICS must be importable from pmda module."""
        assert _SITE_METRICS is not None, "SITE_METRICS not exported from pmda"

    def test_site_metrics_count(self):
        """Exactly 15 site metrics per the data model."""
        assert _SITE_METRICS is not None
        assert len(_SITE_METRICS) == 15

    def test_site_metrics_have_required_fields(self):
        """Each metric tuple has (name, item, type, sem, attr_name)."""
        assert _SITE_METRICS is not None
        for metric in _SITE_METRICS:
            assert len(metric) == 5, f"Metric {metric[0]} has wrong tuple length"

    def test_site_metric_names_are_namespaced(self):
        """All site metrics live under unifi.site.*"""
        assert _SITE_METRICS is not None
        for metric in _SITE_METRICS:
            name = metric[0]
            assert name.startswith("unifi.site."), (
                f"Metric {name} not under unifi.site"
            )

    def test_site_metric_names_match_data_model(self):
        """All 15 metric names from the data model are present."""
        assert _SITE_METRICS is not None
        expected_names = {
            "unifi.site.status",
            "unifi.site.num_sta",
            "unifi.site.num_user",
            "unifi.site.num_guest",
            "unifi.site.num_ap",
            "unifi.site.num_sw",
            "unifi.site.num_gw",
            "unifi.site.wan.rx_bytes",
            "unifi.site.wan.tx_bytes",
            "unifi.site.lan.rx_bytes",
            "unifi.site.lan.tx_bytes",
            "unifi.site.lan.num_user",
            "unifi.site.lan.num_guest",
            "unifi.site.wlan.rx_bytes",
            "unifi.site.wlan.tx_bytes",
        }
        actual_names = {m[0] for m in _SITE_METRICS}
        assert actual_names == expected_names

    def test_site_item_ids_are_unique(self):
        """Item IDs within the cluster must not collide."""
        assert _SITE_METRICS is not None
        item_ids = [m[1] for m in _SITE_METRICS]
        assert len(item_ids) == len(set(item_ids)), "Duplicate item IDs in SITE_METRICS"


# ---------------------------------------------------------------------------
# T031: Device metric registration (cluster 1)
# ---------------------------------------------------------------------------


class TestDeviceMetricRegistration:
    """Cluster 1: all 15 device-level metrics from data-model.md."""

    def test_device_metrics_list_exists(self):
        """DEVICE_METRICS must be importable from pmda module."""
        assert _DEVICE_METRICS is not None, "DEVICE_METRICS not exported from pmda"

    def test_device_metrics_count(self):
        """Exactly 15 device metrics per the data model."""
        assert _DEVICE_METRICS is not None
        assert len(_DEVICE_METRICS) == 15

    def test_device_metrics_have_required_fields(self):
        """Each metric tuple has (name, item, type, sem, attr_name)."""
        assert _DEVICE_METRICS is not None
        for metric in _DEVICE_METRICS:
            assert len(metric) == 5, f"Metric {metric[0]} has wrong tuple length"

    def test_device_metric_names_are_namespaced(self):
        """All device metrics live under unifi.device.*"""
        assert _DEVICE_METRICS is not None
        for metric in _DEVICE_METRICS:
            name = metric[0]
            assert name.startswith("unifi.device."), (
                f"Metric {name} not under unifi.device"
            )

    def test_device_metric_names_match_data_model(self):
        """All 15 metric names from the data model are present."""
        assert _DEVICE_METRICS is not None
        expected_names = {
            "unifi.device.name",
            "unifi.device.mac",
            "unifi.device.ip",
            "unifi.device.model",
            "unifi.device.type",
            "unifi.device.version",
            "unifi.device.state",
            "unifi.device.uptime",
            "unifi.device.adopted",
            "unifi.device.rx_bytes",
            "unifi.device.tx_bytes",
            "unifi.device.temperature",
            "unifi.device.user_num_sta",
            "unifi.device.guest_num_sta",
            "unifi.device.num_ports",
        }
        actual_names = {m[0] for m in _DEVICE_METRICS}
        assert actual_names == expected_names

    def test_device_item_ids_are_unique(self):
        """Item IDs within the cluster must not collide."""
        assert _DEVICE_METRICS is not None
        item_ids = [m[1] for m in _DEVICE_METRICS]
        assert len(item_ids) == len(set(item_ids)), "Duplicate item IDs in DEVICE_METRICS"


# ---------------------------------------------------------------------------
# T032: Gateway metric registration (cluster 6)
# ---------------------------------------------------------------------------


class TestGatewayMetricRegistration:
    """Cluster 6: all 18 gateway metrics from data-model.md."""

    def test_gateway_metrics_list_exists(self):
        """GATEWAY_METRICS must be importable from pmda module."""
        assert _GATEWAY_METRICS is not None, "GATEWAY_METRICS not exported from pmda"

    def test_gateway_metrics_count(self):
        """Exactly 18 gateway metrics per the data model."""
        assert _GATEWAY_METRICS is not None
        assert len(_GATEWAY_METRICS) == 18

    def test_gateway_metrics_have_required_fields(self):
        """Each metric tuple has (name, item, type, sem, attr_name)."""
        assert _GATEWAY_METRICS is not None
        for metric in _GATEWAY_METRICS:
            assert len(metric) == 5, f"Metric {metric[0]} has wrong tuple length"

    def test_gateway_metric_names_are_namespaced(self):
        """All gateway metrics live under unifi.gateway.*"""
        assert _GATEWAY_METRICS is not None
        for metric in _GATEWAY_METRICS:
            name = metric[0]
            assert name.startswith("unifi.gateway."), (
                f"Metric {name} not under unifi.gateway"
            )

    def test_gateway_metric_names_match_data_model(self):
        """All 18 metric names from the data model are present."""
        assert _GATEWAY_METRICS is not None
        expected_names = {
            "unifi.gateway.wan_ip",
            "unifi.gateway.wan_rx_bytes",
            "unifi.gateway.wan_tx_bytes",
            "unifi.gateway.wan_rx_packets",
            "unifi.gateway.wan_tx_packets",
            "unifi.gateway.wan_rx_dropped",
            "unifi.gateway.wan_tx_dropped",
            "unifi.gateway.wan_rx_errors",
            "unifi.gateway.wan_tx_errors",
            "unifi.gateway.wan_up",
            "unifi.gateway.wan_speed",
            "unifi.gateway.wan_latency",
            "unifi.gateway.lan_rx_bytes",
            "unifi.gateway.lan_tx_bytes",
            "unifi.gateway.uptime",
            "unifi.gateway.cpu",
            "unifi.gateway.mem",
            "unifi.gateway.temperature",
        }
        actual_names = {m[0] for m in _GATEWAY_METRICS}
        assert actual_names == expected_names

    def test_gateway_item_ids_are_unique(self):
        """Item IDs within the cluster must not collide."""
        assert _GATEWAY_METRICS is not None
        item_ids = [m[1] for m in _GATEWAY_METRICS]
        assert len(item_ids) == len(set(item_ids)), "Duplicate item IDs in GATEWAY_METRICS"


# ---------------------------------------------------------------------------
# T033: Extended controller metrics (cluster 9)
# ---------------------------------------------------------------------------


class TestControllerExtendedMetrics:
    """Cluster 9: 8 controller metrics (original 4 + version, counts)."""

    def test_version_metric_exists(self):
        """unifi.controller.version should be in the list."""
        names = {m[0] for m in CONTROLLER_METRICS}
        assert "unifi.controller.version" in names

    def test_devices_discovered_metric_exists(self):
        names = {m[0] for m in CONTROLLER_METRICS}
        assert "unifi.controller.devices_discovered" in names

    def test_clients_discovered_metric_exists(self):
        names = {m[0] for m in CONTROLLER_METRICS}
        assert "unifi.controller.clients_discovered" in names

    def test_sites_polled_metric_exists(self):
        names = {m[0] for m in CONTROLLER_METRICS}
        assert "unifi.controller.sites_polled" in names


# ---------------------------------------------------------------------------
# Fetch callback tests (require PCP to actually instantiate the PMDA)
# ---------------------------------------------------------------------------
# These would test the actual PMDA instance with injected snapshots.
# Since PMDA instantiation requires a running PMCD, these are left as
# stubs that document what would be tested in a full PCP environment.


class TestFetchCallbackWithSnapshot:
    """Fetch callback returns correct values from a pre-built snapshot."""

    @pytest.mark.skip(reason="Requires running PMCD for full PMDA instantiation")
    def test_fetch_returns_port_rx_bytes(self):
        """Cluster 2 item 0 should return PortData.rx_bytes."""
        pass

    @pytest.mark.skip(reason="Requires running PMCD for full PMDA instantiation")
    def test_fetch_returns_pm_err_inst_for_unknown_instance(self):
        """Unknown instance ID should get PM_ERR_INST."""
        pass

    @pytest.mark.skip(reason="Requires running PMCD for full PMDA instantiation")
    def test_fetch_returns_pm_err_again_when_no_snapshot(self):
        """Before first poll completes, fetch should return PM_ERR_AGAIN."""
        pass


class TestLabels:
    """PMDA label callbacks attach correct metadata."""

    @pytest.mark.skip(reason="Requires running PMCD for full PMDA instantiation")
    def test_domain_label_has_agent_unifi(self):
        """Domain-level label should include agent=unifi."""
        pass
