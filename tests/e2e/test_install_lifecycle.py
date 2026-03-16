"""E2E test for the full PMDA install/verify/remove lifecycle.

Drives the real Install and Remove scripts via subprocess against
a mock UniFi API server running on localhost:18443.  Validates that
metrics flow through PCP after install and disappear after remove.

Must run LAST in the e2e suite because it modifies global PMCD state.
"""

import subprocess
import time
from pathlib import Path

import pytest

pcp = pytest.importorskip("pcp", reason="PCP Python bindings not installed")

PMDAS_DIR = Path("/var/lib/pcp/pmdas/unifi")
MOCK_URL = "http://127.0.0.1:18443"
MOCK_API_KEY = "test-key"


def _run(cmd, **kwargs):
    """Run a command and return the result, capturing output."""
    return subprocess.run(
        cmd, capture_output=True, text=True, timeout=30, **kwargs
    )


@pytest.mark.e2e
@pytest.mark.order("last")
class TestInstallLifecycle:
    """Full install -> verify -> remove lifecycle against mock API."""

    def test_deploy_files(self):
        """pcp-pmda-unifi-setup install deploys the launcher and scripts."""
        result = _run(["sudo", "pcp-pmda-unifi-setup", "install"])
        assert result.returncode == 0, f"Deploy failed: {result.stderr}"
        assert (PMDAS_DIR / "pmdaunifi.python").exists()
        assert (PMDAS_DIR / "Install").exists()
        assert (PMDAS_DIR / "Remove").exists()

    def test_install_registers_pmda(self):
        """sudo -E ./Install -e registers the PMDA with PMCD."""
        env = {
            "UNIFI_URL": MOCK_URL,
            "UNIFI_API_KEY": MOCK_API_KEY,
            "UNIFI_IS_UDM": "false",
            "UNIFI_VERIFY_SSL": "false",
            "UNIFI_SITES": "default",
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/usr/local/bin",
        }
        result = _run(
            ["sudo", "-E", "./Install", "-e"],
            cwd=str(PMDAS_DIR),
            env=env,
        )
        assert result.returncode == 0, (
            f"Install failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert (PMDAS_DIR / "unifi.conf").exists()

    def test_controller_version_metric(self):
        """After install, unifi.controller.version returns the mock version."""
        # Give the poller time to complete its first cycle
        time.sleep(5)
        result = _run(["pminfo", "-f", "unifi.controller.version"])
        assert result.returncode == 0, f"pminfo failed: {result.stderr}"
        assert "9.0.114" in result.stdout, (
            f"Expected mock version 9.0.114 in output:\n{result.stdout}"
        )

    def test_controller_up_metric(self):
        """After install, unifi.controller.up should be 1."""
        result = _run(["pminfo", "-f", "unifi.controller.up"])
        assert result.returncode == 0, f"pminfo failed: {result.stderr}"
        assert "1" in result.stdout

    def test_site_name_metric(self):
        """After install, unifi.site.name should contain 'default'."""
        result = _run(["pminfo", "-f", "unifi.site.name"])
        assert result.returncode == 0, f"pminfo failed: {result.stderr}"
        assert "default" in result.stdout.lower(), (
            f"Expected 'default' site in output:\n{result.stdout}"
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
