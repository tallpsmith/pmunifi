# Contributing to pcp-pmda-unifi

## Quick Start

```bash
brew install just uv       # or: apt install just && curl -LsSf https://astral.sh/uv/install.sh | sh
git clone https://github.com/tallpsmith/pmunifi.git
cd pmunifi
just setup
just test
```

`just setup` uses [uv](https://docs.astral.sh/uv/) to create a virtualenv
with `--system-site-packages` so the PCP Python bindings (`pcp.pmda`,
`cpmda`, `cpmapi`) installed by your OS package manager are visible inside
the venv.  If you don't have PCP installed locally, unit tests still pass —
the PMDA module gracefully stubs out PCP imports.

## Repo Structure

```
src/pcp_pmda_unifi/     Core package — PMDA, collector, poller, snapshot, config
  deploy/               PCP Install/Remove scripts and sample config
tests/
  unit/                 Fast, no external deps, mocked everything
  integration/          Real PCP bindings + mock HTTP controller
  e2e/                  Full PMDA lifecycle against a running PMCD
specs/                  Feature specifications and design contracts
docs/                   mkdocs-material documentation site
dashboards/             Pre-built Grafana dashboard JSON files
man/                    Man page source (ronn/pandoc markdown)
packaging/              RPM and Debian packaging files
```

## Just Commands

| Command              | What it does                                    |
|----------------------|-------------------------------------------------|
| `just setup`         | Create venv, install deps (inc. dev/test extras)|
| `just test`          | Run unit + integration tests                    |
| `just test-cov`      | Run unit tests with coverage report             |
| `just check`         | Lint (ruff) + typecheck (mypy)                  |
| `just build`         | Build sdist and wheel                           |
| `just trial-install` | Build, install into fresh venv, deploy + register PMDA |
| `just clean-dist`    | Remove old wheels/sdists                        |
| `just clean`         | Remove build artifacts and caches               |

## Testing Requirements

**TDD is mandatory.** This is non-negotiable per project constitution.

1. Write failing tests first that describe expected behaviour
2. Run the tests — confirm they fail for the right reason
3. Implement the code to make the tests pass
4. Refactor while keeping tests green

### Three Test Tiers

- **Unit** (`tests/unit/`): Pure logic, mocked I/O, fast. This is where most
  tests live. Must run without PCP installed.
- **Integration** (`tests/integration/`): Real PCP bindings with a mock HTTP
  controller. Requires PCP system packages.
- **E2E** (`tests/e2e/`): Full PMDA install/remove cycle against a running
  PMCD. Marked `@pytest.mark.e2e` and skipped by default.

### Coverage Target

90%+ line coverage on the `pcp_pmda_unifi` package. Check with:

```bash
just test-cov
```

### Never Delete Tests

Existing tests are not disposable. If a test breaks, investigate why — don't
delete it. If a test is genuinely wrong, discuss it in the PR before removing.

## Code Style

- **Linting**: `ruff` enforced — zero warnings in CI.
- **Type checking**: `mypy --strict` on public interfaces (`src/`).
- **Method names**: Descriptive and readable. `build_switch_port_instances()`
  not `bld_sw_pt_inst()`.
- **Single Responsibility**: Each function/class does one thing. If a method
  needs an "and" in its description, split it.
- **PCP naming conventions**: Metric names follow `unifi.<category>.<metric>`
  dotted notation. Instance names use `/` for hierarchy, `::` for sub-device
  components (e.g., `main/default/USW-Pro-48::Port24`).

## PR Process

1. Branch from `main` — name it descriptively (e.g., `add-gateway-wan-metrics`).
2. Write tests first, then implementation.
3. Run `just check && just test` before pushing.
4. All CI checks must pass (lint, unit, integration).
5. PR description should explain *why*, not just *what*.
6. Constitution compliance is checked during review — TDD, SRP, PCP
   conventions, human-readable code.

## UniFi API Resources

These are useful when adding new metrics or debugging API responses:

- **UniFi Network API (official)**: <https://developer.ui.com/network/>
- **Community API wiki**: <https://ubntwiki.com/products/software/unifi-controller/api>
- **unpoller (reference implementation)**: <https://github.com/unpoller/unifi>

## Notes

### System Site Packages

The venv uses `--system-site-packages` because the PCP Python bindings
(`pcp`, `cpmda`, `cpmapi`) are C extensions installed by OS packages
(`pcp-libs-python` on RHEL, `python3-pcp` on Debian/Ubuntu). They cannot
be pip-installed. The venv inherits these while still isolating everything
else.

### Running on macOS

PCP is available on macOS via Homebrew (`brew install pcp`). For development,
unit tests run without PCP installed — the PMDA module detects missing PCP
imports and stubs them out. Integration and e2e tests require PCP and will be
skipped automatically if not present.

To test the full install flow locally, use `just trial-install` with a `.env`
file containing your controller details (see the Developer Guide).
