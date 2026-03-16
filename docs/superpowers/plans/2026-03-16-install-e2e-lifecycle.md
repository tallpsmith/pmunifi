# Install E2E Lifecycle Test Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an e2e test that validates the full PMDA install/verify-metrics/remove lifecycle against a mock UniFi API on a real PCP instance.

**Architecture:** Reuse the existing Flask mock server from `tests/integration/mock_controller.py` as a standalone background process. Add a new `tests/e2e/test_install_lifecycle.py` with `@pytest.mark.order("last")` that drives the real Install/Remove scripts via subprocess and checks a handful of smoke metrics via `pminfo`. Runs in the existing e2e CI job.

**Tech Stack:** pytest, pytest-ordering, Flask mock server, subprocess, PCP CLI tools (`pminfo`)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `tests/e2e/mock_server.py` | Create | Standalone entry point to run the Flask mock on a fixed port |
| `tests/e2e/test_install_lifecycle.py` | Create | Full install/verify/remove e2e test |
| `.github/workflows/ci.yml` | Modify | Add `pytest-ordering` dep and start mock server before e2e tests |
| `pyproject.toml` | Modify | Add `pytest-ordering` to test dependencies, register `order` marker |

---

## Chunk 1: Mock Server Entry Point + CI Wiring

### Task 1: Create standalone mock server script

**Files:**
- Create: `tests/e2e/mock_server.py`

- [ ] **Step 1: Create the mock server entry point**

```python
"""Standalone mock UniFi API server for e2e install testing.

Wraps the existing Flask mock from tests/integration/mock_controller.py
and serves it on a fixed port. Run as a background process before e2e tests.

Usage:
    python -m tests.e2e.mock_server          # default port 18443
    python -m tests.e2e.mock_server 9999     # custom port
"""

import sys
from pathlib import Path

# Ensure the tests/ directory is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from integration.mock_controller import create_mock_app
from werkzeug.serving import make_server


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18443
    app = create_mock_app(api_key="test-key")
    server = make_server("127.0.0.1", port, app)
    print(f"Mock UniFi API listening on http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify mock server starts and responds**

```bash
# In one terminal:
cd tests/e2e && python mock_server.py &
SERVER_PID=$!

# In another:
curl -s -H "X-API-Key: test-key" http://127.0.0.1:18443/api/self/sites | python -m json.tool
# Expect: {"meta": {"rc": "ok"}, "data": [{"name": "default", ...}]}

kill $SERVER_PID
```

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/mock_server.py
git commit -m "Add standalone mock server entry point for install e2e tests"
```

---

### Task 2: Add pytest-ordering dependency and register marker

**Files:**
- Modify: `pyproject.toml:38` (test dependencies)
- Modify: `pyproject.toml:50-53` (markers)

- [ ] **Step 1: Add pytest-ordering to test deps**

In `pyproject.toml`, change:
```toml
test = ["pytest>=7.0", "pytest-cov", "flask", "cryptography"]
```
To:
```toml
test = ["pytest>=7.0", "pytest-cov", "flask", "cryptography", "pytest-ordering"]
```

- [ ] **Step 2: Register the `order` marker**

In `pyproject.toml` under `[tool.pytest.ini_options]` markers, add:
```toml
    "order: control test execution order",
```

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "Add pytest-ordering for e2e test execution order"
```

---

### Task 3: Wire mock server into CI e2e job

**Files:**
- Modify: `.github/workflows/ci.yml:44-57`

- [ ] **Step 1: Update the e2e job**

Add `pytest-ordering` to the install step (it's in `[test]` extras, so already
covered by `".[test]"` — but verify). Add a step to start the mock server
as a background process before running pytest.

Change the e2e job to:
```yaml
  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get update && sudo apt-get install -y pcp python3-pcp
      - run: |
          sudo systemctl start pmcd
          . /etc/pcp.env && "$PCP_BINADM_DIR/pmcd_wait" -t 10
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - uses: astral-sh/setup-uv@v4
      - run: uv pip install --system -e ".[test]"
      - name: Start mock UniFi API
        run: python tests/e2e/mock_server.py &
      - run: pytest tests/e2e/ -m e2e -v
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "Start mock UniFi API server in e2e CI job"
```

---

## Chunk 2: Install Lifecycle Test

### Task 4: Write the install lifecycle e2e test

**Files:**
- Create: `tests/e2e/test_install_lifecycle.py`

- [ ] **Step 1: Write the full test file**

```python
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


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
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
        # Give the poller a moment to complete its first cycle
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
        assert '1' in result.stdout

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
        # pminfo should fail or return nothing when PMDA is removed
        assert result.returncode != 0 or "unifi" not in result.stdout
```

- [ ] **Step 2: Run locally (skip if no PCP)**

If running on a machine with PCP installed and PMCD running:
```bash
python tests/e2e/mock_server.py &
sudo -E pytest tests/e2e/test_install_lifecycle.py -m e2e -v
kill %1
```

Otherwise, verify the test file parses cleanly:
```bash
python -c "import ast; ast.parse(open('tests/e2e/test_install_lifecycle.py').read()); print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_install_lifecycle.py
git commit -m "Add e2e install lifecycle test against mock UniFi API

Validates deploy, install -e, metric smoke checks, and clean removal."
```

---

### Task 5: Final verification — push and monitor CI

- [ ] **Step 1: Push and verify CI**

```bash
git push
```

Monitor the CI run — all four jobs should pass, with the e2e job now running
the install lifecycle test last.

- [ ] **Step 2: If e2e fails, check**

Common issues:
- Mock server not starting: check the background process step
- `sudo` not available in CI: GitHub Actions runners have passwordless sudo
- `pminfo` timing: the `time.sleep(5)` may need adjusting
- PATH issues: the `env` dict in `test_install_registers_pmda` may need
  the runner's full PATH
