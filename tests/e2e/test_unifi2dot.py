"""E2E tests for the unifi2dot CLI companion tool.

Starts the mock HTTP controller from integration/, runs unifi2dot via
subprocess, and validates the DOT and JSON output formats.  These tests
run on macOS without PCP installed.

Marked @pytest.mark.e2e for selective test runs.
"""

import json
import subprocess
import sys
import threading

import pytest

from tests.integration.mock_controller import create_mock_app


@pytest.fixture()
def live_mock_controller():
    """Start the mock controller on a random port, yield connection info."""
    from werkzeug.serving import make_server

    api_key = "e2e-test-key"
    app = create_mock_app(api_key=api_key)
    server = make_server("127.0.0.1", 0, app)
    port = server.socket.getsockname()[1]

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    yield {"url": f"http://127.0.0.1:{port}", "api_key": api_key, "port": port}

    server.shutdown()


def _run_unifi2dot(args, timeout=15):
    """Run unifi2dot as a subprocess and return the CompletedProcess."""
    # cli.py has no __main__ guard, so we invoke main() directly
    # with the args list serialised into the subprocess.
    args_repr = repr(args)
    cmd = [
        sys.executable, "-c",
        f"from pcp_pmda_unifi.cli import main; main({args_repr})",
    ]
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.e2e
class TestUnifi2dotDotOutput:
    """Verify DOT format output from unifi2dot against the mock controller."""

    def test_dot_output_is_digraph(self, live_mock_controller):
        """DOT output must begin with 'digraph' and contain closing brace."""
        info = live_mock_controller
        result = _run_unifi2dot([
            "--url", info["url"],
            "--api-key", info["api_key"],
            "--site", "default",
            "--no-udm",
            "--no-verify-ssl",
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert result.stdout.strip().startswith("digraph")
        assert "}" in result.stdout

    def test_dot_output_contains_device_names(self, live_mock_controller):
        """DOT output should reference device names from our fixtures."""
        info = live_mock_controller
        result = _run_unifi2dot([
            "--url", info["url"],
            "--api-key", info["api_key"],
            "--site", "default",
            "--no-udm",
            "--no-verify-ssl",
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        output = result.stdout
        # Fixture devices: USW-Pro-48-Rack1, UDM-Pro, UAP-AC-Pro-Lobby
        assert "USW-Pro-48-Rack1" in output
        assert "UDM-Pro" in output

    def test_dot_output_to_file(self, live_mock_controller, tmp_path):
        """The -o flag should write output to a file instead of stdout."""
        info = live_mock_controller
        outfile = tmp_path / "network.dot"
        result = _run_unifi2dot([
            "--url", info["url"],
            "--api-key", info["api_key"],
            "--site", "default",
            "--no-udm",
            "--no-verify-ssl",
            "-o", str(outfile),
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        content = outfile.read_text()
        assert content.strip().startswith("digraph")


@pytest.mark.e2e
class TestUnifi2dotJsonOutput:
    """Verify JSON format output from unifi2dot against the mock controller."""

    def test_json_output_is_parseable(self, live_mock_controller):
        """JSON output must be valid JSON with 'nodes' and 'edges' keys."""
        info = live_mock_controller
        result = _run_unifi2dot([
            "--url", info["url"],
            "--api-key", info["api_key"],
            "--site", "default",
            "--format", "json",
            "--no-udm",
            "--no-verify-ssl",
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert "nodes" in data
        assert "edges" in data

    def test_json_nodes_contain_device_info(self, live_mock_controller):
        """JSON nodes should have id and label fields from fixture devices."""
        info = live_mock_controller
        result = _run_unifi2dot([
            "--url", info["url"],
            "--api-key", info["api_key"],
            "--site", "default",
            "--format", "json",
            "--no-udm",
            "--no-verify-ssl",
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        node_labels = [n.get("label", n.get("name", "")) for n in data["nodes"]]
        # At least one fixture device should appear as a node
        fixture_devices = {"USW-Pro-48-Rack1", "UDM-Pro", "UAP-AC-Pro-Lobby"}
        found = fixture_devices.intersection(set(node_labels))
        assert len(found) > 0, f"No fixture devices found in nodes: {node_labels}"

    def test_json_edges_are_lists(self, live_mock_controller):
        """JSON edges must be a list (possibly empty if no uplinks in fixture)."""
        info = live_mock_controller
        result = _run_unifi2dot([
            "--url", info["url"],
            "--api-key", info["api_key"],
            "--site", "default",
            "--format", "json",
            "--no-udm",
            "--no-verify-ssl",
        ])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert isinstance(data["edges"], list)


@pytest.mark.e2e
class TestUnifi2dotErrorHandling:
    """Verify unifi2dot fails gracefully on bad input."""

    def test_bad_url_exits_nonzero(self):
        """Connecting to a bogus URL should exit with non-zero status."""
        result = _run_unifi2dot([
            "--url", "http://127.0.0.1:1",
            "--api-key", "nope",
            "--site", "default",
            "--no-verify-ssl",
        ], timeout=10)
        assert result.returncode != 0

    def test_missing_required_args_exits_nonzero(self):
        """Running without --url should fail."""
        result = _run_unifi2dot([], timeout=5)
        assert result.returncode != 0

    def test_bad_api_key_exits_nonzero(self, live_mock_controller):
        """A wrong API key should produce a non-zero exit."""
        info = live_mock_controller
        result = _run_unifi2dot([
            "--url", info["url"],
            "--api-key", "wrong-key",
            "--site", "default",
            "--no-udm",
            "--no-verify-ssl",
        ])
        assert result.returncode != 0
