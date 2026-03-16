"""T024, T025: Integration tests for the deploy and install helper workflow.

Tests cover:
- setup.deploy_to_pmdas_dir() copies deploy artifacts and generates launcher
- install_helper connectivity validation, site discovery, config generation
- Non-interactive config building from environment variables
"""

import os
import stat
from unittest.mock import MagicMock, patch

import pytest
import requests

from pcp_pmda_unifi.collector import (
    UnifiAuthenticationError,
    UnifiConnectionError,
)
from pcp_pmda_unifi.config import parse_config
from pcp_pmda_unifi.install_helper import (
    build_config_from_env,
    discover_sites,
    generate_config,
    validate_controller_connectivity,
)
from pcp_pmda_unifi.setup import deploy_to_pmdas_dir

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Setup / deploy_to_pmdas_dir
# ---------------------------------------------------------------------------


class TestDeployToPmdasDir:
    """deploy_to_pmdas_dir copies Install, Remove, sample config, and
    generates a launcher script in the target directory."""

    def test_copies_install_script(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        install_script = tmp_path / "Install"
        assert install_script.exists(), "Install script not copied"

    def test_copies_remove_script(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        remove_script = tmp_path / "Remove"
        assert remove_script.exists(), "Remove script not copied"

    def test_copies_sample_config(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        sample = tmp_path / "unifi.conf.sample"
        assert sample.exists(), "Sample config not copied"

    def test_generates_launcher_script(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        launcher = tmp_path / "pmdaunifi.python"
        assert launcher.exists(), "Launcher script not generated"

    def test_launcher_has_pmpython_shebang(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        launcher = tmp_path / "pmdaunifi.python"
        first_line = launcher.read_text().splitlines()[0]
        assert first_line == "#!/usr/bin/env pmpython"

    def test_launcher_imports_pmda(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        launcher = tmp_path / "pmdaunifi.python"
        content = launcher.read_text()
        assert "from pcp_pmda_unifi.pmda import run" in content
        assert "run()" in content

    def test_install_script_is_executable(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        mode = (tmp_path / "Install").stat().st_mode
        assert mode & stat.S_IXUSR, "Install should be owner-executable"

    def test_remove_script_is_executable(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        mode = (tmp_path / "Remove").stat().st_mode
        assert mode & stat.S_IXUSR, "Remove should be owner-executable"

    def test_launcher_is_executable(self, tmp_path):
        deploy_to_pmdas_dir(tmp_path)
        mode = (tmp_path / "pmdaunifi.python").stat().st_mode
        assert mode & stat.S_IXUSR, "Launcher should be owner-executable"


# ---------------------------------------------------------------------------
# Connectivity validation
# ---------------------------------------------------------------------------


class TestValidateControllerConnectivity:
    """validate_controller_connectivity returns (bool, message) tuples."""

    @patch("pcp_pmda_unifi.install_helper.UnifiClient")
    def test_returns_true_on_successful_connection(self, mock_client_cls):
        """Happy path: controller responds with sysinfo."""
        mock_client = MagicMock()
        mock_client.fetch_sysinfo.return_value = [{"version": "8.6.9"}]
        mock_client_cls.return_value = mock_client

        ok, msg = validate_controller_connectivity(
            "https://192.168.1.1", "test-key"
        )
        assert ok is True
        assert "8.6.9" in msg

    @patch("pcp_pmda_unifi.install_helper.UnifiClient")
    def test_returns_false_on_auth_failure(self, mock_client_cls):
        """401 should produce a clear auth error message."""
        mock_client = MagicMock()
        mock_client.fetch_sysinfo.side_effect = UnifiAuthenticationError(
            "HTTP 401: Unauthorized", status_code=401
        )
        mock_client_cls.return_value = mock_client

        ok, msg = validate_controller_connectivity(
            "https://192.168.1.1", "bad-key"
        )
        assert ok is False
        assert "authentication" in msg.lower() or "Authentication" in msg

    @patch("pcp_pmda_unifi.install_helper.UnifiClient")
    def test_returns_false_on_connection_failure(self, mock_client_cls):
        """Network unreachable should produce a connection error."""
        mock_client = MagicMock()
        mock_client.fetch_sysinfo.side_effect = UnifiConnectionError(
            "Connection failed", status_code=0
        )
        mock_client_cls.return_value = mock_client

        ok, msg = validate_controller_connectivity(
            "https://192.168.1.1", "test-key"
        )
        assert ok is False
        assert "connection" in msg.lower() or "Connection" in msg

    @patch("pcp_pmda_unifi.install_helper.UnifiClient")
    def test_returns_ssl_error_with_helpful_suggestion(self, mock_client_cls):
        """SSL verification failure should suggest verify_ssl=false."""
        mock_client = MagicMock()
        # requests wraps SSL errors in a ConnectionError with an SSLError cause
        ssl_error = requests.exceptions.SSLError("certificate verify failed")
        mock_client.fetch_sysinfo.side_effect = ssl_error
        mock_client_cls.return_value = mock_client

        ok, msg = validate_controller_connectivity(
            "https://192.168.1.1", "test-key", verify_ssl=True
        )
        assert ok is False
        assert "ssl" in msg.lower() or "SSL" in msg
        assert "verify_ssl" in msg.lower() or "verify_ssl=false" in msg


# ---------------------------------------------------------------------------
# Site discovery
# ---------------------------------------------------------------------------


class TestDiscoverSites:
    """discover_sites wraps UnifiClient.discover_sites()."""

    @patch("pcp_pmda_unifi.install_helper.UnifiClient")
    def test_returns_list_of_site_dicts(self, mock_client_cls):
        mock_client = MagicMock()
        mock_client.discover_sites.return_value = [
            {"name": "default", "desc": "Default", "num_new_alarms": 0},
            {"name": "branch", "desc": "Branch Office", "num_new_alarms": 2},
        ]
        mock_client_cls.return_value = mock_client

        sites = discover_sites("https://192.168.1.1", "test-key")
        assert len(sites) == 2
        assert sites[0]["name"] == "default"
        assert sites[1]["desc"] == "Branch Office"


# ---------------------------------------------------------------------------
# Config generation
# ---------------------------------------------------------------------------


class TestGenerateConfig:
    """generate_config produces valid INI consumable by parse_config."""

    def test_generates_parseable_ini(self):
        """Generated config should round-trip through parse_config."""
        sites = [{"name": "default"}, {"name": "branch"}]
        ini_text = generate_config(
            controller_name="main",
            url="https://192.168.1.1",
            api_key="abc123",
            sites=sites,
            is_udm=True,
            verify_ssl=False,
            poll_interval=30,
        )
        # Should parse without raising
        cfg = parse_config(ini_text)
        assert "main" in cfg.controllers
        ctrl = cfg.controllers["main"]
        assert ctrl.url == "https://192.168.1.1"
        assert ctrl.api_key == "abc123"
        assert ctrl.is_udm is True
        assert ctrl.verify_ssl is False
        assert ctrl.sites == ["default", "branch"]

    def test_generates_global_poll_interval(self):
        sites = [{"name": "default"}]
        ini_text = generate_config(
            controller_name="main",
            url="https://10.0.0.1",
            api_key="key123",
            sites=sites,
            poll_interval=60,
        )
        cfg = parse_config(ini_text)
        assert cfg.global_settings.poll_interval == 60

    def test_all_sites_keyword(self):
        """When sites list is empty or None, default to 'all'."""
        ini_text = generate_config(
            controller_name="main",
            url="https://10.0.0.1",
            api_key="key123",
            sites=None,
        )
        cfg = parse_config(ini_text)
        assert cfg.controllers["main"].sites == ["all"]


# ---------------------------------------------------------------------------
# Non-interactive config from environment
# ---------------------------------------------------------------------------


class TestBuildConfigFromEnv:
    """build_config_from_env reads UNIFI_* env vars and returns config."""

    def test_returns_none_when_no_env_vars(self):
        """Without UNIFI_URL and UNIFI_API_KEY, returns None."""
        with patch.dict(os.environ, {}, clear=True):
            result = build_config_from_env()
        assert result is None

    def test_returns_none_when_only_url_set(self):
        """Both URL and API_KEY are required."""
        env = {"UNIFI_URL": "https://192.168.1.1"}
        with patch.dict(os.environ, env, clear=True):
            result = build_config_from_env()
        assert result is None

    def test_returns_valid_config_with_required_vars(self):
        """Minimal env: UNIFI_URL + UNIFI_API_KEY produces valid config."""
        env = {
            "UNIFI_URL": "https://192.168.1.1",
            "UNIFI_API_KEY": "test-api-key",
        }
        with patch.dict(os.environ, env, clear=True):
            result = build_config_from_env()

        assert result is not None
        cfg = parse_config(result)
        ctrl = cfg.controllers["default"]
        assert ctrl.url == "https://192.168.1.1"
        assert ctrl.api_key == "test-api-key"

    def test_respects_all_optional_env_vars(self):
        """All UNIFI_* vars map to the correct config keys."""
        env = {
            "UNIFI_URL": "https://10.0.0.1",
            "UNIFI_API_KEY": "my-key",
            "UNIFI_SITES": "warehouse,office",
            "UNIFI_IS_UDM": "false",
            "UNIFI_VERIFY_SSL": "false",
            "UNIFI_POLL_INTERVAL": "45",
        }
        with patch.dict(os.environ, env, clear=True):
            result = build_config_from_env()

        assert result is not None
        cfg = parse_config(result)
        assert cfg.global_settings.poll_interval == 45
        ctrl = cfg.controllers["default"]
        assert ctrl.sites == ["warehouse", "office"]
        assert ctrl.is_udm is False
        assert ctrl.verify_ssl is False
