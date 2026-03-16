"""Quickstart validation tests.

Each test corresponds to a command from specs/001-unifi-pmda/quickstart.md.
Most require a live controller or PCP installation, so they skip with a
reason explaining what they would validate.

The tests that CAN run on a bare dev machine (help flags) are executed
for real.

Marked @pytest.mark.e2e for selective test runs.
"""

import subprocess
import sys

import pytest


@pytest.mark.e2e
class TestCliHelpFlags:
    """Verify that CLI entry points respond to --help without error."""

    def test_unifi2dot_help(self):
        """unifi2dot --help should exit 0 and show usage info."""
        result = subprocess.run(
            [sys.executable, "-c",
             "from pcp_pmda_unifi.cli import main; main(['--help'])"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        # argparse --help exits with code 0
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "unifi2dot" in combined or "usage" in combined.lower()

    def test_setup_help(self):
        """pcp-pmda-unifi-setup --help should exit 0 and show usage info."""
        result = subprocess.run(
            [sys.executable, "-c",
             "import sys; sys.argv = ['pcp-pmda-unifi-setup', '--help']; "
             "from pcp_pmda_unifi.setup import main; main()"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        assert "install" in combined.lower()


@pytest.mark.e2e
class TestQuickstartPcpCommands:
    """Quickstart commands that require PCP and a live controller.

    Each test is documented with the command it validates, but skipped
    because we cannot safely run them outside a real PCP+controller
    environment.
    """

    @pytest.mark.skip(reason=(
        "Validates: pminfo unifi — requires PMDA installed and PMCD running. "
        "Run manually after ./Install."
    ))
    def test_pminfo_lists_namespace(self):
        """pminfo unifi should list all metrics under the unifi namespace."""

    @pytest.mark.skip(reason=(
        "Validates: pminfo -f unifi.switch.port.rx_bytes — requires live PMDA "
        "with an active controller connection to have instance values."
    ))
    def test_pminfo_fetch_switch_port_rx_bytes(self):
        """pminfo -f should show per-port byte counters with instance names."""

    @pytest.mark.skip(reason=(
        "Validates: pmrep -t 5 unifi.switch.port.rx_bytes unifi.switch.port.tx_bytes — "
        "requires live PMDA. Verifies rate conversion works on COUNTER semantics."
    ))
    def test_pmrep_rate_conversion(self):
        """pmrep should display per-second rates for counter metrics."""

    @pytest.mark.skip(reason=(
        "Validates: pmval unifi.controller.up — requires live PMDA. "
        "Should show 1 when the controller is reachable."
    ))
    def test_pmval_controller_up(self):
        """pmval should show the controller.up instant value."""

    @pytest.mark.skip(reason=(
        "Validates: pminfo -f unifi.device.name — requires live PMDA. "
        "Should list all adopted devices with their instance names."
    ))
    def test_pminfo_device_inventory(self):
        """pminfo -f on device.name should show the full device inventory."""


@pytest.mark.e2e
class TestQuickstartInstallWorkflow:
    """Install/upgrade workflow commands from the quickstart guide."""

    @pytest.mark.skip(reason=(
        "Validates: pip install pcp-pmda-unifi — package installation. "
        "Tested implicitly by the dev environment setup."
    ))
    def test_pip_install(self):
        """pip install should succeed and make entry points available."""

    @pytest.mark.skip(reason=(
        "Validates: sudo pcp-pmda-unifi-setup install — deploys files to "
        "$PCP_PMDAS_DIR/unifi/. Requires root and PCP installed."
    ))
    def test_setup_install(self):
        """pcp-pmda-unifi-setup install should deploy PMDA artifacts."""

    @pytest.mark.skip(reason=(
        "Validates: sudo ./Install — interactive PMDA registration. "
        "Requires root, PMCD, and a live controller for connectivity check."
    ))
    def test_interactive_install(self):
        """./Install should prompt for URL, key, sites, then register."""

    @pytest.mark.skip(reason=(
        "Validates: sudo -E ./Install -e — non-interactive from env vars. "
        "Requires root, PMCD, and UNIFI_* env vars set."
    ))
    def test_env_install(self):
        """./Install -e should read UNIFI_* env vars and register silently."""

    @pytest.mark.skip(reason=(
        "Validates: sudo ./Install -u — upgrade mode preserves unifi.conf "
        "and re-registers the PMDA. Requires root and PMCD."
    ))
    def test_upgrade_install(self):
        """./Install -u should skip prompts, keep config, re-register."""
