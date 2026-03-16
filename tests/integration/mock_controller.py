"""Lightweight Flask mock of the UniFi Controller REST API.

Serves fixture JSON files with proper authentication and response
envelope handling.  Supports both standalone and UDM (/proxy/network)
path prefixes.

Usage in tests:
    from tests.integration.mock_controller import create_mock_app

    app = create_mock_app(api_key="test-key")
    with app.test_client() as client:
        resp = client.get("/api/self/sites", headers={"X-API-Key": "test-key"})

For pytest integration, use the `mock_controller` fixture which
starts the app on a random port and yields the base URL.
"""

import json
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import pytest
from flask import Flask, Response, jsonify, request

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

# Default fixture file mapping: endpoint suffix → fixture filename
ENDPOINT_FIXTURE_MAP = {
    "self/sites": None,  # generated dynamically
    "stat/device": "stat_device.json",
    "stat/sta": "stat_sta.json",
    "stat/health": "stat_health.json",
    "stat/sysinfo": "stat_sysinfo.json",
    "stat/sitedpi": "stat_sitedpi.json",
}


def _load_fixture(filename: str) -> Dict[str, Any]:
    """Read and parse a fixture JSON file."""
    fixture_path = FIXTURES_DIR / filename
    return json.loads(fixture_path.read_text())


def _unifi_envelope(data: Any) -> Dict[str, Any]:
    """Wrap data in the standard UniFi response envelope."""
    return {"meta": {"rc": "ok"}, "data": data}


def _error_response(status_code: int, message: str) -> Response:
    """Build a UniFi-style error response."""
    body = {"meta": {"rc": "error", "msg": message}, "data": []}
    return Response(
        json.dumps(body),
        status=status_code,
        content_type="application/json",
    )


def _check_api_key(expected_key: str) -> Optional[Response]:
    """Validate the X-API-Key header.  Returns an error Response or None."""
    provided_key = request.headers.get("X-API-Key", "")
    if provided_key != expected_key:
        return _error_response(401, "api.err.Invalid")
    return None


# ---------------------------------------------------------------------------
# Flask app factory
# ---------------------------------------------------------------------------


def create_mock_app(api_key: str = "test-key") -> Flask:
    """Build a Flask app that mimics the UniFi Controller REST API.

    The app validates the X-API-Key header on every request and serves
    fixture data from tests/fixtures/.  Both direct paths and
    /proxy/network-prefixed paths (UDM mode) are supported.
    """
    app = Flask(__name__)
    app.config["TESTING"] = True

    # -- Site discovery -------------------------------------------------------

    def handle_sites() -> Response:
        auth_error = _check_api_key(api_key)
        if auth_error:
            return auth_error
        sites_data = [
            {
                "name": "default",
                "desc": "Default",
                "_id": "000000000000000000000001",
                "attr_hidden_id": "default",
                "attr_no_delete": True,
            }
        ]
        return jsonify(_unifi_envelope(sites_data))

    # -- Stat endpoints -------------------------------------------------------

    def handle_stat_device(site: str) -> Response:
        auth_error = _check_api_key(api_key)
        if auth_error:
            return auth_error
        fixture = _load_fixture("stat_device.json")
        return jsonify(fixture)

    def handle_stat_sta(site: str) -> Response:
        auth_error = _check_api_key(api_key)
        if auth_error:
            return auth_error
        fixture = _load_fixture("stat_sta.json")
        return jsonify(fixture)

    def handle_stat_health(site: str) -> Response:
        auth_error = _check_api_key(api_key)
        if auth_error:
            return auth_error
        fixture = _load_fixture("stat_health.json")
        return jsonify(fixture)

    def handle_stat_sysinfo(site: str) -> Response:
        auth_error = _check_api_key(api_key)
        if auth_error:
            return auth_error
        fixture = _load_fixture("stat_sysinfo.json")
        return jsonify(fixture)

    def handle_stat_sitedpi(site: str) -> Response:
        auth_error = _check_api_key(api_key)
        if auth_error:
            return auth_error
        fixture = _load_fixture("stat_sitedpi.json")
        return jsonify(fixture)

    # -- Register routes for both direct and UDM-prefixed paths ---------------

    for prefix in ("", "/proxy/network"):
        # Site discovery
        app.add_url_rule(
            f"{prefix}/api/self/sites",
            endpoint=f"sites{prefix}",
            view_func=handle_sites,
            methods=["GET"],
        )

        # Per-site stat endpoints
        app.add_url_rule(
            f"{prefix}/api/s/<site>/stat/device",
            endpoint=f"stat_device{prefix}",
            view_func=handle_stat_device,
            methods=["GET"],
        )
        app.add_url_rule(
            f"{prefix}/api/s/<site>/stat/sta",
            endpoint=f"stat_sta{prefix}",
            view_func=handle_stat_sta,
            methods=["GET"],
        )
        app.add_url_rule(
            f"{prefix}/api/s/<site>/stat/health",
            endpoint=f"stat_health{prefix}",
            view_func=handle_stat_health,
            methods=["GET"],
        )
        app.add_url_rule(
            f"{prefix}/api/s/<site>/stat/sysinfo",
            endpoint=f"stat_sysinfo{prefix}",
            view_func=handle_stat_sysinfo,
            methods=["GET"],
        )
        app.add_url_rule(
            f"{prefix}/api/s/<site>/stat/sitedpi",
            endpoint=f"stat_sitedpi{prefix}",
            view_func=handle_stat_sitedpi,
            methods=["POST", "GET"],
        )

    return app


# ---------------------------------------------------------------------------
# Pytest fixture — starts the mock on a random port in a background thread
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_controller():
    """Start a mock UniFi controller on a random port and yield the base URL.

    The server runs in a daemon thread and is automatically torn down
    when the test finishes.
    """
    test_api_key = "test-key"
    app = create_mock_app(api_key=test_api_key)

    # Use port 0 to let the OS pick an available port
    from werkzeug.serving import make_server

    server = make_server("127.0.0.1", 0, app)
    port = server.socket.getsockname()[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://127.0.0.1:{port}"

    yield {"url": base_url, "api_key": test_api_key}

    server.shutdown()
