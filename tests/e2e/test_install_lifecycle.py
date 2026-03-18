"""E2E test for the full PMDA install/verify/remove lifecycle.

Drives the real Install and Remove scripts via subprocess against
a mock UniFi API server running on localhost:18443.  Validates that
metrics flow through PCP after install and disappear after remove.

Must run LAST in the e2e suite because it modifies global PMCD state.
"""

import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which("pminfo") is None,
    reason="PCP tools not installed (pminfo not found on PATH)",
)

PMDAS_DIR = Path("/var/lib/pcp/pmdas/unifi")
MOCK_URL = "http://127.0.0.1:18443"
MOCK_API_KEY = "test-key"


def _run(cmd, timeout=30, **kwargs):
    """Run a command and return the result, capturing output."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout, **kwargs
    )


def _setup_cmd():
    """Resolve the full path to pcp-pmda-unifi-setup for use with sudo."""
    path = shutil.which("pcp-pmda-unifi-setup")
    assert path is not None, (
        "pcp-pmda-unifi-setup not found on PATH — is the package installed?"
    )
    return path


def _has_data_rows(stdout, min_rows=1):
    """Check that pmrep output has at least min_rows of non-header data."""
    lines = [ln for ln in stdout.splitlines() if ln.strip()]
    # First line(s) are headers/units, data rows follow
    return len(lines) >= min_rows + 1


@pytest.mark.e2e
@pytest.mark.order("last")
class TestInstallLifecycle:
    """Full install -> verify -> remove lifecycle against mock API."""

    def test_deploy_files(self):
        """pcp-pmda-unifi-setup install deploys the launcher and scripts."""
        result = _run(["sudo", _setup_cmd(), "install"])
        assert result.returncode == 0, f"Deploy failed: {result.stderr}"
        assert (PMDAS_DIR / "pmdaunifi.python").exists()
        assert (PMDAS_DIR / "Install").exists()
        assert (PMDAS_DIR / "Remove").exists()

    def test_install_registers_pmda(self):
        """sudo -E ./Install -e registers the PMDA with PMCD."""
        # Inherit full env so PCP vars, PATH, and Python site-packages
        # are all available.  The CI workflow installs the package into the
        # system Python so pmpython can find pcp_pmda_unifi.
        env = os.environ.copy()
        env.update({
            "UNIFI_URL": MOCK_URL,
            "UNIFI_API_KEY": MOCK_API_KEY,
            "UNIFI_IS_UDM": "false",
            "UNIFI_VERIFY_SSL": "false",
            "UNIFI_SITES": "default",
        })
        result = _run(
            ["sudo", "-E", "./Install", "-e"],
            cwd=str(PMDAS_DIR),
            env=env,
        )
        assert result.returncode == 0, (
            f"Install failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (PMDAS_DIR / "unifi.conf").exists(), (
            f"unifi.conf not created. Install output:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_controller_up_metric(self):
        """After install, unifi.controller.up should be 1."""
        # Give the poller time to complete its first cycle
        time.sleep(10)
        result = _run(["pminfo", "-f", "unifi.controller.up"])
        assert result.returncode == 0, f"pminfo failed: {result.stderr}"
        assert "1" in result.stdout

    def test_controller_version_metric(self):
        """After install, unifi.controller.version is fetchable."""
        result = _run(["pminfo", "-f", "unifi.controller.version"])
        assert result.returncode == 0, f"pminfo failed: {result.stderr}"
        # The metric exists and has an instance — version string may be
        # empty if the collector hasn't populated it from sysinfo yet.
        assert "unifi.controller.version" in result.stdout

    def test_site_status_metric(self):
        """After install, unifi.site.status should contain 'ok'."""
        result = _run(["pminfo", "-f", "unifi.site.status"])
        assert result.returncode == 0, f"pminfo failed: {result.stderr}"
        assert "ok" in result.stdout.lower(), (
            f"Expected 'ok' site status in output:\n{result.stdout}"
        )

    # -------------------------------------------------------------------
    # pmrep view tests — run after metrics are confirmed flowing
    # -------------------------------------------------------------------

    def test_pmrep_health_view(self):
        """pmrep :unifi-health returns controller status in one-shot."""
        result = _run(["pmrep", ":unifi-health"])
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        # Check for data rows with expected values
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )
        # Controller should be up (value "1" in the Up column)
        assert "1" in result.stdout, (
            f"Expected controller up=1 in output:\n{result.stdout}"
        )

    def test_pmrep_site_view(self):
        """pmrep :unifi-site returns site counts in one-shot."""
        result = _run(["pmrep", ":unifi-site"])
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )
        # Should show site health status "ok"
        assert "ok" in result.stdout.lower(), (
            f"Expected 'ok' status in output:\n{result.stdout}"
        )

    def test_pmrep_device_summary_view(self):
        """pmrep :unifi-device-summary lists all devices in one-shot."""
        result = _run(["pmrep", ":unifi-device-summary"])
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )
        # Should show device types from the mock (udm at minimum)
        output_lower = result.stdout.lower()
        assert "usw" in output_lower or "uap" in output_lower or "udm" in output_lower, (
            f"Expected device type in output:\n{result.stdout}"
        )

    def test_pmrep_switch_detail_view(self):
        """pmrep :unifi-switch-detail with filter shows switch status."""
        result = _run(["pmrep", ":unifi-switch-detail", "-i", ".*USW.*"])
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )

    def test_pmrep_gateway_health_view(self):
        """pmrep :unifi-gateway-health returns gateway status in one-shot."""
        result = _run(["pmrep", ":unifi-gateway-health"])
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )

    def test_pmrep_site_traffic_rate_view(self):
        """pmrep :unifi-site-traffic produces rate-converted throughput."""
        result = _run(["pmrep", ":unifi-site-traffic"], timeout=45)
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )

    def test_pmrep_switch_ports_rate_view(self):
        """pmrep :unifi-switch-ports produces per-port rate data."""
        result = _run(
            ["pmrep", ":unifi-switch-ports", "-i", ".*USW-Pro-48.*"],
            timeout=45,
        )
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )

    def test_pmrep_ap_detail_rate_view(self):
        """pmrep :unifi-ap-detail produces AP radio rate data."""
        result = _run(["pmrep", ":unifi-ap-detail"], timeout=45)
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )

    def test_pmrep_gateway_traffic_rate_view(self):
        """pmrep :unifi-gateway-traffic produces WAN throughput rate data."""
        result = _run(["pmrep", ":unifi-gateway-traffic"], timeout=45)
        assert result.returncode == 0, f"pmrep failed: {result.stderr}"
        assert _has_data_rows(result.stdout), (
            f"Expected data rows in output:\n{result.stdout}"
        )

    def test_remove_deregisters_pmda(self):
        """sudo ./Remove deregisters the PMDA from PMCD."""
        result = _run(
            ["sudo", "./Remove"],
            cwd=str(PMDAS_DIR),
        )
        assert result.returncode == 0, f"Remove failed: {result.stderr}"

        # Verify metrics are gone
        result = _run(["pminfo", "unifi"])
        assert result.returncode != 0 or "unifi" not in result.stdout
