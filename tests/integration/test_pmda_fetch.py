"""T017, T018: Integration tests for the UniFi PMDA fetch callbacks.

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

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not HAS_PCP, reason="PCP bindings not installed"),
]


# ---------------------------------------------------------------------------
# Metric registration
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
    """Cluster 9: all 4 controller health metrics should be defined."""

    def test_controller_metrics_count(self):
        """Exactly 4 controller metrics for MVP."""
        assert len(CONTROLLER_METRICS) == 4

    def test_controller_metric_names(self):
        expected_names = {
            "unifi.controller.up",
            "unifi.controller.poll_duration_ms",
            "unifi.controller.poll_errors",
            "unifi.controller.last_poll",
        }
        actual_names = {m[0] for m in CONTROLLER_METRICS}
        assert actual_names == expected_names


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
