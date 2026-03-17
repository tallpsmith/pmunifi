"""Quickstart validation tests.

Verifies that CLI entry points work correctly.

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
