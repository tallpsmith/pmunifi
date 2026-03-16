"""UniFi Controller API client.

Wraps the legacy /api/s/{site}/stat/* REST endpoints with API key
authentication, response envelope parsing, and typed error handling.

Usage:
    from pcp_pmda_unifi.collector import UnifiClient
    client = UnifiClient("https://192.168.1.1", "my-api-key")
    devices = client.fetch_devices("default")
"""

import re
from typing import Any, Dict, List, Optional, Union

import requests

# ---------------------------------------------------------------------------
# Custom exceptions — one per HTTP error category
# ---------------------------------------------------------------------------


class UnifiApiError(Exception):
    """Base exception for all UniFi API errors."""

    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class UnifiAuthenticationError(UnifiApiError):
    """Raised on HTTP 401 — invalid or revoked API key."""


class UnifiForbiddenError(UnifiApiError):
    """Raised on HTTP 403 — insufficient permissions."""


class UnifiNotFoundError(UnifiApiError):
    """Raised on HTTP 404 — wrong path or is_udm misconfigured."""


class UnifiRateLimitError(UnifiApiError):
    """Raised on HTTP 429 — back off and retry next cycle."""


class UnifiServerError(UnifiApiError):
    """Raised on HTTP 5xx — controller-side failure."""


class UnifiConnectionError(UnifiApiError):
    """Raised when the controller is unreachable."""


# ---------------------------------------------------------------------------
# MAC normalisation helper
# ---------------------------------------------------------------------------

_MAC_HEX_PATTERN = re.compile(r"^[0-9a-fA-F]{12}$")


def normalise_mac(mac: str) -> str:
    """Lowercase a MAC address and ensure colon-separated hex format.

    Handles bare hex (aabbccddeeff), dash-separated (aa-bb-cc-dd-ee-ff),
    and already colon-separated formats.  Returns lowercase colon-separated.
    """
    stripped = mac.strip().lower()
    bare = stripped.replace(":", "").replace("-", "").replace(".", "")

    if not _MAC_HEX_PATTERN.match(bare):
        return stripped  # pass through if it doesn't look like a MAC

    return ":".join(bare[i:i + 2] for i in range(0, 12, 2))


# ---------------------------------------------------------------------------
# Response envelope parsing
# ---------------------------------------------------------------------------

_ERROR_HANDLERS = {
    401: UnifiAuthenticationError,
    403: UnifiForbiddenError,
    404: UnifiNotFoundError,
    429: UnifiRateLimitError,
}


def _raise_for_status(response: requests.Response) -> None:
    """Raise a typed exception for non-200 HTTP responses."""
    code = response.status_code

    if code == 200:
        return

    error_class = _ERROR_HANDLERS.get(code)
    if error_class:
        raise error_class(
            f"HTTP {code}: {response.text[:200]}",
            status_code=code,
        )

    if 500 <= code < 600:
        raise UnifiServerError(
            f"HTTP {code}: {response.text[:200]}",
            status_code=code,
        )

    raise UnifiApiError(
        f"Unexpected HTTP {code}: {response.text[:200]}",
        status_code=code,
    )


def _parse_response_envelope(response: requests.Response) -> List[Dict[str, Any]]:
    """Validate the UniFi response envelope and return the data array.

    Expects {"meta": {"rc": "ok"}, "data": [...]}.
    """
    _raise_for_status(response)

    body = response.json()
    meta = body.get("meta", {})
    result_code = meta.get("rc", "")

    if result_code != "ok":
        error_message = meta.get("msg", "unknown error")
        raise UnifiApiError(
            f"API error: {error_message} (rc={result_code})",
            status_code=response.status_code,
        )

    result: List[Dict[str, Any]] = body.get("data", [])
    return result


# ---------------------------------------------------------------------------
# UniFi API client
# ---------------------------------------------------------------------------


class UnifiClient:
    """HTTP client for the UniFi Controller REST API.

    Authenticates via X-API-Key header and builds endpoint paths
    with an optional /proxy/network prefix for UniFi OS devices.
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        is_udm: bool = True,
        verify_ssl: bool = True,
        ca_cert: Optional[str] = None,
    ):
        self.base_url = url.rstrip("/")
        self.is_udm = is_udm
        self.verify_ssl = verify_ssl
        self.ca_cert = ca_cert

        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": api_key,
            "Accept": "application/json",
        })

    # -- URL construction -----------------------------------------------------

    def _build_url(self, path: str) -> str:
        """Prepend /proxy/network for UDM devices, then append the path."""
        prefix = "/proxy/network" if self.is_udm else ""
        return f"{self.base_url}{prefix}{path}"

    # -- SSL parameter helper -------------------------------------------------

    def _ssl_kwargs(self) -> Dict[str, Union[bool, str]]:
        """Build the verify= kwarg for requests calls."""
        if self.ca_cert:
            return {"verify": self.ca_cert}
        return {"verify": self.verify_ssl}

    # -- Low-level request wrapper --------------------------------------------

    def _get(self, path: str) -> List[Dict[str, Any]]:
        """Perform a GET request and return the parsed data array."""
        url = self._build_url(path)
        try:
            response = self.session.get(url, **self._ssl_kwargs())
        except requests.ConnectionError as exc:
            raise UnifiConnectionError(
                f"Connection failed to {url}: {exc}",
                status_code=0,
            ) from exc
        return _parse_response_envelope(response)

    def _post(self, path: str, json_body: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Perform a POST request and return the parsed data array."""
        url = self._build_url(path)
        try:
            response = self.session.post(url, json=json_body, **self._ssl_kwargs())
        except requests.ConnectionError as exc:
            raise UnifiConnectionError(
                f"Connection failed to {url}: {exc}",
                status_code=0,
            ) from exc
        return _parse_response_envelope(response)

    # -- Public endpoint methods ----------------------------------------------

    def discover_sites(self) -> List[Dict[str, Any]]:
        """List all sites visible to the API key.

        GET /api/self/sites
        """
        return self._get("/api/self/sites")

    def fetch_devices(self, site: str) -> List[Dict[str, Any]]:
        """Fetch full device stats including port_table and radio_table.

        GET /api/s/{site}/stat/device
        """
        return self._get(f"/api/s/{site}/stat/device")

    def fetch_clients(self, site: str) -> List[Dict[str, Any]]:
        """Fetch connected client (station) list.

        GET /api/s/{site}/stat/sta
        """
        return self._get(f"/api/s/{site}/stat/sta")

    def fetch_health(self, site: str) -> List[Dict[str, Any]]:
        """Fetch site health subsystems (wan, lan, wlan, vpn).

        GET /api/s/{site}/stat/health
        """
        return self._get(f"/api/s/{site}/stat/health")

    def fetch_sysinfo(self, site: str) -> List[Dict[str, Any]]:
        """Fetch controller system info (version, build, hostname).

        GET /api/s/{site}/stat/sysinfo
        """
        return self._get(f"/api/s/{site}/stat/sysinfo")

    def fetch_dpi(self, site: str) -> List[Dict[str, Any]]:
        """Fetch DPI category statistics (opt-in, enable_dpi=true).

        POST /api/s/{site}/stat/sitedpi with body {"type": "by_cat"}
        """
        return self._post(
            f"/api/s/{site}/stat/sitedpi",
            {"type": "by_cat"},
        )
