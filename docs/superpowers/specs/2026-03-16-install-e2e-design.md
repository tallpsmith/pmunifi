# Install E2E Lifecycle Test — Design Spec

## Goal

Validate the full PMDA install/verify/remove lifecycle on a real PCP instance
with a mock UniFi API, catching the class of bugs that only surface when you
actually run `./Install` on a real box (e.g., wrong launcher filename, broken
entry point, SSL warnings corrupting JSON).

## Architecture

Add a new `tests/e2e/test_install_lifecycle.py` to the existing e2e test suite.
It runs the full install -> verify metrics -> remove cycle via subprocess calls,
talking to a Flask mock server that serves the existing test fixtures.

Runs inside the existing `e2e` job in `ci.yml` — no new workflow needed.

## Components

### 1. Mock server entry point (`tests/e2e/mock_server.py`)

A standalone script that wraps the existing `create_mock_app()` from
`tests/integration/mock_controller.py`. Binds to a fixed port (18443) on
localhost, serves HTTP (not HTTPS — no SSL ceremony needed for testing the
install pipeline). Started as a background process in CI before pytest runs.

### 2. Test file (`tests/e2e/test_install_lifecycle.py`)

Single test class with `@pytest.mark.order("last")` so it runs after the
other e2e tests that test the PMDA in isolation. Uses subprocess to drive
the real install scripts, same as a human would.

**Tests in order:**

1. `test_deploy_files` — runs `pcp-pmda-unifi-setup install`, asserts
   `pmdaunifi.python` exists in `/var/lib/pcp/pmdas/unifi/`

2. `test_install_registers_pmda` — runs `sudo -E ./Install -e` with env vars
   pointing at the mock server (`UNIFI_URL=http://127.0.0.1:18443`,
   `UNIFI_API_KEY=test-key`, `UNIFI_VERIFY_SSL=false`). Asserts exit 0,
   asserts `unifi.conf` was written.

3. `test_metrics_are_live` — waits briefly for the poller to complete a cycle,
   then runs `pminfo -f` on a few smoke-check metrics:
   - `unifi.controller.version` — proves PMDA talks to mock
   - `unifi.controller.up` — proves poller is healthy
   - `unifi.site.name` — proves instance domain is populated

4. `test_remove_deregisters_pmda` — runs `sudo ./Remove`, asserts exit 0,
   runs `pminfo unifi` and confirms it errors (PMDA no longer registered).

### 3. CI changes (`ci.yml`)

The existing e2e job needs two additions:
- `pytest-ordering` added to pip install
- Mock server started as a background process before the pytest step

## Constraints

- Mock uses HTTP on port 18443, no HTTPS/SSL
- `./Install -e` requires `sudo -E` to preserve env vars
- Tests modify global PCP state (register/deregister PMDA) so must run last
- Smoke-check only — verify a handful of metrics, not an exhaustive audit

## Dependencies

- Existing `tests/integration/mock_controller.py` (Flask mock, all 6 endpoints)
- Existing `tests/fixtures/*.json` (response data)
- `pytest-ordering` package (for `@pytest.mark.order("last")`)
