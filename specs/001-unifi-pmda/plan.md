# Implementation Plan: UniFi PCP PMDA

**Branch**: `001-unifi-pmda` | **Date**: 2026-03-15 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/001-unifi-pmda/spec.md`

## Summary

Build a Performance Metrics Domain Agent (PMDA) for PCP that polls Ubiquiti UniFi controllers via their REST API and exposes per-port switch traffic, device inventory, site health, gateway WAN/LAN metrics, client tracking, AP radio, and DPI metrics through the standard PCP toolchain. The PMDA uses background poller threads with copy-on-write snapshots to keep the PMCD dispatch thread non-blocking, dict-based `pmdaCache` for dynamic instance domains, and a two-phase PyPI deployment model (pip install → setup command deploys to `$PCP_PMDAS_DIR`). A companion `unifi2dot` CLI tool discovers intra-site topology from device uplink tables and exports DOT/JSON graphs.

## Technical Context

**Language/Version**: Python 3.8+ (must support RHEL 9 / Ubuntu 20.04 LTS system Python)
**Primary Dependencies**: `requests` (pip), `pcp.pmda` + `cpmda` (system package)
**Storage**: In-memory snapshot cache (copy-on-write), `pmdaCache` persistent instance ID mapping on disk
**Testing**: pytest with three tiers (unit, integration, e2e) + ruff linting + mypy strict on public interfaces
**Target Platform**: Linux (any PCP-supported distro)
**Project Type**: PCP PMDA (daemon plugin) + companion CLI tool
**Performance Goals**: Full metric fetch < 4 seconds at 2,400 switch port instances (SC-003)
**Constraints**: Single pip dependency (`requests`), must run as `pcp` user, config file `root:pcp` 0640, PMCD dispatch thread must never block on network I/O
**Scale/Scope**: 50 switches × 48 ports = 2,400 port instances, 1,000 client cap default, 8 instance domains (10 clusters), ~120 unique metric items

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Pre-Research Check

| Principle | Status | Notes |
|---|---|---|
| I. TDD (NON-NEGOTIABLE) | PASS | Test tiers defined: unit (pytest, mock API), integration (mock PCP), e2e (real PCP + mock HTTP). 90%+ coverage target per SC-007. |
| II. PCP Conventions First | PASS | Metric naming (`unifi.switch.port.rx_bytes`), instance naming (`site/device::PortN`), Install/Remove scripts, `pmdaCache` for dynamic indoms, raw counters only — all follow upstream patterns. |
| III. Single Responsibility | PASS | Architecture separates: API client (fetch), snapshot builder (transform), poller thread (scheduling), PMDA dispatch (serve). Each module does one thing. |
| IV. Human-Readable Code | PASS | Method naming convention: `build_switch_port_instances()`, `poll_controller()`, `parse_device_stats()`. No abbreviations beyond PCP conventions. |
| PCP-Specific Constraints | PASS | Runs as `pcp` user (FR-024), dispatch thread does no I/O (FR-013), fetch < 4s (SC-003), `requests` only pip dep (FR-022). |
| Quality Gates | PASS | Three test tiers, ruff + mypy, constitution compliance in PR review. |

### Post-Design Check

| Principle | Status | Notes |
|---|---|---|
| I. TDD | PASS | Data model and contracts are test-specification-ready — each field and error case maps to a test. |
| II. PCP Conventions | PASS | 8 instance domains (10 clusters) with PCP-standard naming. Metric tree follows `unifi.*` dotted convention. Semantic types (COUNTER/INSTANT/DISCRETE) correctly assigned per field nature. |
| III. Single Responsibility | PASS | Snapshot is an immutable data structure — poller builds it, PMDA reads it. No class crosses the build/serve boundary. |
| IV. Human-Readable | PASS | Instance naming (`main/default/USW-Pro-48-Rack1::Port24`) is immediately human-parseable. |
| Quality Gates | PASS | Contracts define error behaviour, enabling test coverage of every error path. |

No violations. Complexity Tracking table not needed.

## Project Structure

### Documentation (this feature)

```text
specs/001-unifi-pmda/
├── plan.md              # This file
├── research.md          # Phase 0 output — technology decisions & rationale
├── data-model.md        # Phase 1 output — instance domains, metric tree, snapshot structure
├── quickstart.md        # Phase 1 output — installation & usage guide
├── contracts/
│   ├── pcp-metrics.md   # PCP metric interface contract
│   ├── unifi-api-client.md  # UniFi API consumption contract
│   └── configuration.md    # Config file contract
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
src/
└── pcp_pmda_unifi/
    ├── __init__.py              # Package version, PCP import guard
    ├── pmda.py                  # PMDA class — metric registration, fetch callbacks, labels
    ├── collector.py             # UniFi API client — HTTP requests, response parsing
    ├── poller.py                # Background poller thread — scheduling, snapshot building
    ├── snapshot.py              # Immutable snapshot data structures (dataclasses)
    ├── config.py                # INI config parsing and validation
    ├── instances.py             # Instance domain construction and naming
    ├── cli.py                   # unifi2dot entry point (argparse)
    ├── topology.py              # Topology graph discovery and DOT/JSON export
    ├── setup.py                 # pcp-pmda-unifi-setup entry point (deploy to $PCP_PMDAS_DIR)
    └── deploy/
        ├── Install              # PCP Install shell script
        ├── Remove               # PCP Remove shell script
        └── unifi.conf.sample    # Example configuration

tests/
├── conftest.py                  # Shared fixtures: canned API responses, fake config
├── fixtures/                    # Recorded & scrubbed UniFi API JSON responses
│   ├── stat_device.json
│   ├── stat_sta.json
│   ├── stat_health.json
│   ├── stat_sysinfo.json
│   └── stat_sitedpi.json
├── unit/
│   ├── conftest.py
│   ├── test_collector.py        # API response parsing, error handling
│   ├── test_config.py           # Config validation, defaults, env var override
│   ├── test_snapshot.py         # Snapshot building from raw API data
│   ├── test_instances.py        # Instance naming, pruning, cardinality cap
│   ├── test_topology.py         # DOT/JSON graph generation
│   └── test_cli.py              # CLI argument parsing, output formatting
├── integration/
│   ├── conftest.py
│   ├── mock_controller.py       # Lightweight Flask app serving fixture JSON
│   ├── test_pmda_fetch.py       # Fetch callbacks with real PCP bindings, mocked UniFi API
│   ├── test_poller.py           # Poller thread lifecycle with mock HTTP
│   └── test_deploy.py           # Setup command file deployment
└── e2e/
    ├── conftest.py              # Skip if PCP not installed
    ├── test_live_pmda.py        # Full PMDA install → pminfo → verify values
    └── test_unifi2dot.py        # CLI against mock HTTP server

docs/                            # mkdocs-material documentation site
├── mkdocs.yml
├── getting-started.md
├── configuration.md
├── metrics.md                   # Auto-generated metric reference
├── topology.md
├── architecture.md
├── grafana.md
├── troubleshooting.md
└── developer.md

dashboards/                      # Pre-built Grafana dashboard JSON files
├── site-overview.json
├── switch-port-detail.json
├── client-insights.json
└── ap-radio-performance.json

packaging/
├── rpm/
│   └── pcp-pmda-unifi.spec
└── deb/
    ├── control
    ├── rules
    └── postinst

man/
└── pmdaunifi.1.md               # Man page source (ronn or pandoc format)

pyproject.toml
LICENSE                          # GPL-2.0-or-later
CONTRIBUTING.md
.github/
├── workflows/
│   ├── ci.yml                   # Lint + unit + integration + e2e
│   └── release.yml              # Build + publish to PyPI (Trusted Publishing)
```

**Structure Decision**: `src/` layout, single Python package (`pcp_pmda_unifi`). The `src/` layout prevents import shadowing and forces install discipline, which is critical for a package that deploys into `$PCP_PMDAS_DIR` separately from site-packages. Deploy assets (Install, Remove, sample config) are bundled as package data and extracted by the setup command.

## Ancillary Deliverables

These are required deliverables that sit outside the core PMDA implementation. They must be tracked as tasks — if not implemented in the main iteration, they must be filed as independent GitHub issues.

| Deliverable | Description | Priority | Depends On |
|---|---|---|---|
| **Man page** (`pmdaunifi.1`) | Standard PCP man page: synopsis, description, config format, CLI options, files, diagnostics | P2 | Core PMDA complete |
| **mkdocs site** | GitHub Pages docs: getting started, config ref, metric ref (auto-gen), topology guide, architecture, Grafana guide, troubleshooting, developer guide | P2 | Core PMDA + dashboards |
| **Grafana dashboards** | Site Overview, Switch Port Detail, Client Insights, AP Radio Performance — JSON files for import via pmproxy | P2 | Metric implementation |
| **CONTRIBUTING.md** | Dev setup, repo structure, testing requirements, code style, PR process, API resource links | P2 | Project structure finalised |
| **RPM packaging** | Spec file for Fedora/RHEL/CentOS, declares deps on pcp + python3-requests | P3 | PyPI package working |
| **Debian packaging** | control/rules/postinst for Ubuntu/Debian | P3 | PyPI package working |
| **CI pipeline** | GitHub Actions: lint (ruff+mypy), unit, integration (with PCP), e2e (with PMCD), coverage | P1 | Test suite exists |
| **PyPI publishing** | Trusted Publishing via GitHub Actions OIDC, release workflow | P2 | CI pipeline working |
| **Install `-u` upgrade mode** | Preserve existing config, update code/PMNS/help, re-register with PMCD | P2 | Install script working |
| **CLI options** (`-d`, `-l`, `-c`, `-U`, `-r`) | Standard PCP PMDA command-line flags for domain, logfile, config path, user, refresh override | P1 | Core PMDA class |
| **Synthetic archive generator** | Script to generate PCP archives with realistic UniFi data for testing dashboards and downstream tools | P3 | Metric definitions stable |

## Complexity Tracking

No constitution violations to justify. The design follows all four principles and all PCP-specific constraints without exception.
