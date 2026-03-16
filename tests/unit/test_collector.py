"""T009: Tests for the UniFi API collector/client.

Tests the HTTP client at src/pcp_pmda_unifi/collector.py.
All HTTP interactions are mocked -- no real network calls.
Validates URL construction, auth headers, response envelope handling,
error mapping, defensive parsing, and MAC normalisation.
"""

from unittest.mock import MagicMock

import pytest
import requests as requests_lib

from pcp_pmda_unifi.collector import (
    UnifiApiError,
    UnifiAuthenticationError,
    UnifiClient,
    UnifiConnectionError,
    UnifiServerError,
    normalise_mac,
)

# ---------------------------------------------------------------------------
# URL construction
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestUrlConstruction:
    """Base URL is adjusted depending on is_udm flag."""

    def test_udm_prepends_proxy_network(self):
        """is_udm=True prepends /proxy/network to API paths."""
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="test-key",
            is_udm=True,
            verify_ssl=False,
        )
        built = client._build_url("/api/s/default/stat/device")
        assert "/proxy/network/api/s/default/stat/device" in built

    def test_standalone_no_proxy_prefix(self):
        """is_udm=False uses the URL directly without /proxy/network."""
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="test-key",
            is_udm=False,
            verify_ssl=False,
        )
        built = client._build_url("/api/s/default/stat/device")
        assert "/proxy/network" not in built
        assert built.endswith("/api/s/default/stat/device")


# ---------------------------------------------------------------------------
# Authentication header
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestApiKeyHeader:
    """X-API-Key header is set on the HTTP session."""

    def test_api_key_set_on_session(self):
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="my-secret-key",
            is_udm=True,
            verify_ssl=False,
        )
        assert client.session.headers.get("X-API-Key") == "my-secret-key"


# ---------------------------------------------------------------------------
# Response envelope
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestResponseEnvelope:
    """The client unwraps the UniFi response envelope correctly."""

    def test_ok_response_returns_data_array(self):
        """meta.rc='ok' returns the data array from the envelope."""
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="key",
            is_udm=True,
            verify_ssl=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "ok"},
            "data": [{"mac": "aa:bb:cc:dd:ee:ff"}],
        }
        client.session.get = MagicMock(return_value=mock_response)

        result = client.fetch_devices("default")
        assert isinstance(result, list)
        assert result[0]["mac"] == "aa:bb:cc:dd:ee:ff"

    def test_error_response_raises(self):
        """meta.rc='error' raises UnifiApiError."""
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="key",
            is_udm=True,
            verify_ssl=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "error", "msg": "api.err.NoSiteContext"},
            "data": [],
        }
        client.session.get = MagicMock(return_value=mock_response)

        with pytest.raises(UnifiApiError, match="error"):
            client.fetch_devices("default")


# ---------------------------------------------------------------------------
# HTTP error handling
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHttpErrorHandling:
    """HTTP status codes map to typed exceptions."""

    def test_401_raises_authentication_error(self):
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="bad-key",
            is_udm=True,
            verify_ssl=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        client.session.get = MagicMock(return_value=mock_response)

        with pytest.raises(UnifiAuthenticationError):
            client.fetch_devices("default")

    def test_5xx_raises_server_error(self):
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="key",
            is_udm=True,
            verify_ssl=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 502
        mock_response.text = "Bad Gateway"
        client.session.get = MagicMock(return_value=mock_response)

        with pytest.raises(UnifiServerError):
            client.fetch_devices("default")

    def test_connection_error_raises(self):
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="key",
            is_udm=True,
            verify_ssl=False,
        )
        client.session.get = MagicMock(
            side_effect=requests_lib.ConnectionError("Connection refused")
        )

        with pytest.raises(UnifiConnectionError):
            client.fetch_devices("default")


# ---------------------------------------------------------------------------
# Defensive parsing (raw data pass-through — snapshot builder handles defaults)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestDefensiveParsing:
    """The collector returns raw data; snapshot builder handles defaults."""

    def test_missing_counter_defaults_to_zero(self):
        """A device dict with missing rx_bytes has no rx_bytes key — that's OK."""
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="key",
            is_udm=True,
            verify_ssl=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "ok"},
            "data": [{"mac": "aa:bb:cc:dd:ee:ff", "name": "switch"}],
        }
        client.session.get = MagicMock(return_value=mock_response)

        devices = client.fetch_devices("default")
        device = devices[0]
        assert device.get("rx_bytes", 0) == 0

    def test_missing_string_defaults_to_empty(self):
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="key",
            is_udm=True,
            verify_ssl=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "ok"},
            "data": [{"mac": "aa:bb:cc:dd:ee:ff"}],
        }
        client.session.get = MagicMock(return_value=mock_response)

        devices = client.fetch_devices("default")
        device = devices[0]
        assert device.get("name", "") == ""

    def test_missing_array_defaults_to_empty_list(self):
        client = UnifiClient(
            url="https://192.168.1.1",
            api_key="key",
            is_udm=True,
            verify_ssl=False,
        )
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "meta": {"rc": "ok"},
            "data": [{"mac": "aa:bb:cc:dd:ee:ff"}],
        }
        client.session.get = MagicMock(return_value=mock_response)

        devices = client.fetch_devices("default")
        device = devices[0]
        assert device.get("port_table", []) == []


# ---------------------------------------------------------------------------
# MAC normalisation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMacNormalisation:
    """MACs are lowercased for consistent instance naming."""

    def test_mac_lowercased(self):
        assert normalise_mac("FC:EC:DA:01:02:03") == "fc:ec:da:01:02:03"

    def test_mac_bare_hex(self):
        assert normalise_mac("fcecda010203") == "fc:ec:da:01:02:03"

    def test_mac_dash_separated(self):
        assert normalise_mac("FC-EC-DA-01-02-03") == "fc:ec:da:01:02:03"
