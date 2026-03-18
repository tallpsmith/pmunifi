"""E2E tests for the full PMDA lifecycle.

Validates that the PMDA class can be instantiated, all metric lists are
populated, and cluster coverage matches the data-model spec.  Most of
these tests are skip-friendly because actually installing a PMDA needs
root and a live PMCD.

Marked @pytest.mark.e2e so the normal `pytest -m "not e2e"` run skips them.
"""

import textwrap

import pytest

# Gate everything on PCP availability — the metric constants are []
# when PCP is not installed, which is the exact thing we want to verify.
pcp = pytest.importorskip("pcp", reason="PCP Python bindings not installed")


@pytest.mark.e2e
class TestPmdaMetricCoverage:
    """Verify all expected clusters have metric definitions."""

    # Expected clusters from data-model.md:
    # 0=site, 1=device, 2=switch_port, 3=poe, 4=client,
    # 5=ap_radio, 6=gateway, 8=dpi, 9=controller
    EXPECTED_CLUSTERS = {0, 1, 2, 3, 4, 5, 6, 8, 9}

    def test_all_metric_lists_populated(self):
        """Every cluster's metric list must contain at least one entry."""
        from pcp_pmda_unifi.pmda import (
            AP_RADIO_METRICS,
            CLIENT_METRICS,
            CONTROLLER_METRICS,
            DEVICE_METRICS,
            DPI_METRICS,
            GATEWAY_METRICS,
            POE_METRICS,
            SITE_METRICS,
            SWITCH_PORT_METRICS,
        )

        cluster_map = {
            0: ("SITE_METRICS", SITE_METRICS),
            1: ("DEVICE_METRICS", DEVICE_METRICS),
            2: ("SWITCH_PORT_METRICS", SWITCH_PORT_METRICS),
            3: ("POE_METRICS", POE_METRICS),
            4: ("CLIENT_METRICS", CLIENT_METRICS),
            5: ("AP_RADIO_METRICS", AP_RADIO_METRICS),
            6: ("GATEWAY_METRICS", GATEWAY_METRICS),
            8: ("DPI_METRICS", DPI_METRICS),
            9: ("CONTROLLER_METRICS", CONTROLLER_METRICS),
        }

        for cluster_id in self.EXPECTED_CLUSTERS:
            name, metrics = cluster_map[cluster_id]
            assert len(metrics) > 0, f"Cluster {cluster_id} ({name}) has no metrics"

    def test_cluster_coverage_matches_spec(self):
        """The set of defined cluster constants must match the spec."""
        from pcp_pmda_unifi.pmda import (
            CLUSTER_AP_RADIO,
            CLUSTER_CLIENT,
            CLUSTER_CONTROLLER,
            CLUSTER_DEVICE,
            CLUSTER_DPI,
            CLUSTER_GATEWAY,
            CLUSTER_POE,
            CLUSTER_SITE,
            CLUSTER_SWITCH_PORT,
        )

        actual = {
            CLUSTER_SITE,
            CLUSTER_DEVICE,
            CLUSTER_SWITCH_PORT,
            CLUSTER_POE,
            CLUSTER_CLIENT,
            CLUSTER_AP_RADIO,
            CLUSTER_GATEWAY,
            CLUSTER_DPI,
            CLUSTER_CONTROLLER,
        }
        assert actual == self.EXPECTED_CLUSTERS

    def test_site_metric_count(self):
        """Cluster 0 should have 15 site metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import SITE_METRICS

        assert len(SITE_METRICS) == 15

    def test_device_metric_count(self):
        """Cluster 1 should have 17 device metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import DEVICE_METRICS

        assert len(DEVICE_METRICS) == 17

    def test_switch_port_metric_count(self):
        """Cluster 2 should have 19 switch port metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import SWITCH_PORT_METRICS

        assert len(SWITCH_PORT_METRICS) == 19

    def test_poe_metric_count(self):
        """Cluster 3 should have 6 PoE metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import POE_METRICS

        assert len(POE_METRICS) == 6

    def test_client_metric_count(self):
        """Cluster 4 should have 17 client metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import CLIENT_METRICS

        assert len(CLIENT_METRICS) == 17

    def test_ap_radio_metric_count(self):
        """Cluster 5 should have 10 AP radio metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import AP_RADIO_METRICS

        assert len(AP_RADIO_METRICS) == 10

    def test_gateway_metric_count(self):
        """Cluster 6 should have 19 gateway metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import GATEWAY_METRICS

        assert len(GATEWAY_METRICS) == 19

    def test_dpi_metric_count(self):
        """Cluster 8 should have 2 DPI metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import DPI_METRICS

        assert len(DPI_METRICS) == 2

    def test_controller_metric_count(self):
        """Cluster 9 should have 9 controller metrics per data-model.md."""
        from pcp_pmda_unifi.pmda import CONTROLLER_METRICS

        assert len(CONTROLLER_METRICS) == 9

    def test_metric_tuples_have_five_fields(self):
        """Every metric tuple should be (pmns_name, item, type, sem, attr)."""
        from pcp_pmda_unifi.pmda import (
            AP_RADIO_METRICS,
            CLIENT_METRICS,
            CONTROLLER_METRICS,
            DEVICE_METRICS,
            DPI_METRICS,
            GATEWAY_METRICS,
            POE_METRICS,
            SITE_METRICS,
            SWITCH_PORT_METRICS,
        )

        all_metrics = (
            SITE_METRICS
            + DEVICE_METRICS
            + SWITCH_PORT_METRICS
            + POE_METRICS
            + CLIENT_METRICS
            + AP_RADIO_METRICS
            + GATEWAY_METRICS
            + DPI_METRICS
            + CONTROLLER_METRICS
        )
        for metric in all_metrics:
            assert len(metric) == 5, f"Metric {metric[0]} has {len(metric)} fields, expected 5"

    def test_all_pmns_names_start_with_unifi(self):
        """Every metric PMNS name must live under the 'unifi.' namespace."""
        from pcp_pmda_unifi.pmda import (
            AP_RADIO_METRICS,
            CLIENT_METRICS,
            CONTROLLER_METRICS,
            DEVICE_METRICS,
            DPI_METRICS,
            GATEWAY_METRICS,
            POE_METRICS,
            SITE_METRICS,
            SWITCH_PORT_METRICS,
        )

        all_metrics = (
            SITE_METRICS
            + DEVICE_METRICS
            + SWITCH_PORT_METRICS
            + POE_METRICS
            + CLIENT_METRICS
            + AP_RADIO_METRICS
            + GATEWAY_METRICS
            + DPI_METRICS
            + CONTROLLER_METRICS
        )
        for metric in all_metrics:
            assert metric[0].startswith("unifi."), f"{metric[0]} not under unifi namespace"


@pytest.mark.e2e
class TestPmdaInstantiation:
    """Verify the PMDA class can be created (without actually running PMCD)."""

    @pytest.fixture()
    def test_config_path(self, tmp_path):
        """Write a minimal unifi.conf and return its path."""
        config_text = textwrap.dedent("""\
            [global]
            poll_interval = 30
            max_clients = 500
            grace_period = 300
            enable_dpi = false

            [controller:main]
            url = https://192.168.1.1
            api_key = test-key-12345
            sites = all
            is_udm = true
            verify_ssl = false
        """)
        conf_file = tmp_path / "unifi.conf"
        conf_file.write_text(config_text)
        return conf_file

    def test_config_parses_cleanly(self, test_config_path):
        """The test config should parse without error."""
        from pcp_pmda_unifi.config import parse_config

        config = parse_config(test_config_path.read_text())
        assert config.global_settings.poll_interval == 30
        assert len(config.controllers) == 1
        assert "main" in config.controllers

    def test_indom_constants_are_sequential(self):
        """Indom serial numbers should be contiguous 0-7."""
        from pcp_pmda_unifi.pmda import (
            INDOM_AP_RADIO,
            INDOM_CLIENT,
            INDOM_CONTROLLER,
            INDOM_DEVICE,
            INDOM_DPI_CATEGORY,
            INDOM_GATEWAY,
            INDOM_SITE,
            INDOM_SWITCH_PORT,
        )

        indoms = sorted([
            INDOM_SITE,
            INDOM_DEVICE,
            INDOM_SWITCH_PORT,
            INDOM_CLIENT,
            INDOM_AP_RADIO,
            INDOM_GATEWAY,
            INDOM_CONTROLLER,
            INDOM_DPI_CATEGORY,
        ])
        assert indoms == list(range(8))
