"""Tests for setup.py deploy logic — specifically venv site-packages propagation.

When pcp-pmda-unifi is pip-installed into a venv, the deployed Install script
and pmdaunifi.python launcher must be able to find the package even when
invoked via the system Python (pmpython).
"""

import sys
import sysconfig
from pathlib import Path
from unittest import mock

import pytest

from pcp_pmda_unifi.setup import deploy_to_pmdas_dir


class TestVenvSitePackagesPropagation:
    """Verify that venv site-packages are recorded during deploy."""

    def test_python_env_sh_created_when_in_venv(self, tmp_path):
        """When running inside a venv, deploy should write python_env.sh."""
        target = tmp_path / "unifi"
        fake_site = "/tmp/myvenv/lib/python3.14/site-packages"

        with mock.patch("pcp_pmda_unifi.setup._detect_venv_site_packages",
                        return_value=fake_site):
            deploy_to_pmdas_dir(target, pmrep_conf_dir=None)

        env_file = target / "python_env.sh"
        assert env_file.exists(), "python_env.sh should be created for venv installs"
        content = env_file.read_text()
        assert fake_site in content
        assert "PMDA_PYTHONPATH" in content

    def test_no_python_env_sh_when_system_python(self, tmp_path):
        """When running on system Python (not a venv), no python_env.sh."""
        target = tmp_path / "unifi"

        with mock.patch("pcp_pmda_unifi.setup._detect_venv_site_packages",
                        return_value=None):
            deploy_to_pmdas_dir(target, pmrep_conf_dir=None)

        env_file = target / "python_env.sh"
        assert not env_file.exists(), "python_env.sh should not exist for system Python"

    def test_launcher_includes_sys_path_for_venv(self, tmp_path):
        """Launcher script should insert venv site-packages into sys.path."""
        target = tmp_path / "unifi"
        fake_site = "/tmp/myvenv/lib/python3.14/site-packages"

        with mock.patch("pcp_pmda_unifi.setup._detect_venv_site_packages",
                        return_value=fake_site):
            deploy_to_pmdas_dir(target, pmrep_conf_dir=None)

        launcher = target / "pmdaunifi.python"
        content = launcher.read_text()
        assert fake_site in content
        assert "sys.path.insert" in content

    def test_launcher_clean_when_system_python(self, tmp_path):
        """Launcher should NOT have sys.path hack when on system Python."""
        target = tmp_path / "unifi"

        with mock.patch("pcp_pmda_unifi.setup._detect_venv_site_packages",
                        return_value=None):
            deploy_to_pmdas_dir(target, pmrep_conf_dir=None)

        launcher = target / "pmdaunifi.python"
        content = launcher.read_text()
        assert "sys.path.insert" not in content
        assert "#!/usr/bin/env pmpython" in content


class TestDetectVenvSitePackages:
    """Test the venv detection helper itself."""

    def test_returns_site_packages_in_venv(self):
        """When sys.prefix != sys.base_prefix, return the site-packages path."""
        from pcp_pmda_unifi.setup import _detect_venv_site_packages

        with mock.patch.object(sys, "prefix", "/tmp/myvenv"), \
             mock.patch.object(sys, "base_prefix", "/usr"), \
             mock.patch("sysconfig.get_path", return_value="/tmp/myvenv/lib/python3.14/site-packages"):
            result = _detect_venv_site_packages()

        assert result == "/tmp/myvenv/lib/python3.14/site-packages"

    def test_returns_none_for_system_python(self):
        """When sys.prefix == sys.base_prefix, return None."""
        from pcp_pmda_unifi.setup import _detect_venv_site_packages

        with mock.patch.object(sys, "prefix", "/usr"), \
             mock.patch.object(sys, "base_prefix", "/usr"):
            result = _detect_venv_site_packages()

        assert result is None
