"""Standalone mock UniFi API server for e2e install testing.

Wraps the existing Flask mock from tests/integration/mock_controller.py
and serves it on a fixed port.  Run as a background process before e2e tests.

Usage:
    python tests/e2e/mock_server.py          # default port 18443
    python tests/e2e/mock_server.py 9999     # custom port
"""

import sys
from pathlib import Path

# Ensure the tests/ directory is importable so we can reach
# integration.mock_controller without installing it as a package.
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.mock_controller import create_mock_app
from werkzeug.serving import make_server


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18443
    app = create_mock_app(api_key="test-key")
    server = make_server("127.0.0.1", port, app)
    print(f"Mock UniFi API listening on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
