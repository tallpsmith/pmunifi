# Developer Guide

This page covers development setup and workflow. For the full contribution
guide, see [CONTRIBUTING.md](https://github.com/you/pcp-pmda-unifi/blob/main/CONTRIBUTING.md)
in the repository root.

## Quick Start

```bash
brew install just
git clone https://github.com/you/pcp-pmda-unifi.git
cd pcp-pmda-unifi
just setup
just test
```

## Development Workflow

| Command | What it does |
|---------|-------------|
| `just setup` | Create venv with system-site-packages, install deps |
| `just test` | Run unit + integration tests |
| `just test-cov` | Unit tests with coverage report |
| `just check` | Lint (ruff) + typecheck (mypy) |
| `just clean` | Remove build artifacts |

## Project Structure

```
src/pcp_pmda_unifi/     Core PMDA package
  pmda.py               Metric registration, fetch/label callbacks
  collector.py          UniFi API HTTP client
  poller.py             Background poll thread, snapshot assembly
  snapshot.py           Immutable snapshot dataclasses
  config.py             INI config parsing and validation
  instances.py          Instance domain naming and pruning
  topology.py           Network topology graph discovery
  cli.py                unifi2dot CLI entry point
  setup.py              pcp-pmda-unifi-setup deploy tool
  deploy/               Install/Remove scripts, sample config

tests/
  unit/                 Fast, mocked, no PCP required
  integration/          Real PCP bindings, mock HTTP
  e2e/                  Full PMDA lifecycle (needs PMCD)
  fixtures/             Recorded UniFi API JSON responses
```

## TDD Workflow

TDD is mandatory. Before writing any implementation:

1. Write failing tests that describe the expected behaviour
2. Run `just test` — confirm they fail for the right reason
3. Implement code to make the tests pass
4. Refactor while keeping tests green

## Testing Tiers

**Unit tests** (`tests/unit/`): Pure logic with mocked I/O. Must run
without PCP installed. This is where most tests live.

**Integration tests** (`tests/integration/`): Use real PCP Python
bindings with a mock HTTP controller. Require PCP system packages.

**E2E tests** (`tests/e2e/`): Full PMDA install/remove against a running
PMCD. Marked with `@pytest.mark.e2e` and skipped by default.

Coverage target: 90%+ on the `pcp_pmda_unifi` package.

## Why `--system-site-packages`?

The PCP Python bindings (`pcp`, `cpmda`, `cpmapi`) are C extensions
installed by OS packages. They cannot be pip-installed. The venv inherits
them via `--system-site-packages` while still isolating project
dependencies.

On macOS (where PCP doesn't exist), unit tests still work — the PMDA
module gracefully stubs out missing PCP imports.

## Code Style

- **ruff** for linting (zero warnings enforced)
- **mypy --strict** on public interfaces
- Descriptive method names: `build_switch_port_instances()` not
  `bld_sw_pt_inst()`
- Single Responsibility Principle: one function, one job
- PCP naming: `unifi.<category>.<metric>`, instance names use `/` for
  hierarchy and `::` for sub-device components

## API Resources

- [UniFi Network API (official)](https://developer.ui.com/network/)
- [Community API wiki](https://ubntwiki.com/products/software/unifi-controller/api)
- [unpoller reference implementation](https://github.com/unpoller/unifi)
