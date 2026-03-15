<!--
  Sync Impact Report
  Version change: 0.0.0 → 1.0.0 (initial ratification)
  Added principles:
    - I. Test-Driven Development (NON-NEGOTIABLE)
    - II. PCP Conventions First
    - III. Single Responsibility
    - IV. Human-Readable Code
  Added sections:
    - PCP-Specific Constraints
    - Quality Gates
  Templates requiring updates:
    - .specify/templates/plan-template.md — ✅ no changes needed (Constitution Check section already generic)
    - .specify/templates/spec-template.md — ✅ no changes needed (already uses MUST language)
    - .specify/templates/tasks-template.md — ✅ no changes needed (already has test-first guidance)
  Follow-up TODOs: none
-->

# pmdaunifi Constitution

## Core Principles

### I. Test-Driven Development (NON-NEGOTIABLE)

Every behaviour MUST be described by a test before its implementation exists.

- Red-Green-Refactor cycle strictly enforced: write a failing test, write
  the minimum code to pass it, refactor while green.
- Bug fixes MUST start with a test that reproduces the bug.
- Refactoring MUST be covered by existing tests that prove behaviour is
  preserved. If coverage is insufficient, add tests first.
- Tests MUST NOT be deleted or silenced to make a build pass. A failing
  test is a conversation, not an obstacle.
- Integration tests MUST hit the real PCP PMDA framework stubs (not mocks
  of the framework itself). Mock the UniFi API, never mock PCP.
- Target: 90%+ line coverage on all non-framework code (per SC-007).

### II. PCP Conventions First

All naming, structure, and packaging decisions MUST follow established
PCP project conventions before inventing anything new.

- Metric names use dotted lowercase: `unifi.switch.port.rx_bytes`.
- Instance domain names follow PCP's `site/device::PortN` human-readable
  pattern with forward-slash separators.
- Metric semantics (PM_SEM_COUNTER, PM_SEM_INSTANT, PM_SEM_DISCRETE)
  MUST match the nature of the data — counters for monotonically
  increasing values, instant for point-in-time, discrete for rarely
  changing metadata.
- Export raw counter values only. Never pre-compute rates — PCP tools
  handle rate conversion.
- PMDA file layout MUST follow PCP's `$PCP_PMDAS_DIR/unifi/` convention:
  Install, Remove, pmda_unifi.py, domain.h, help text.
- Install/Remove scripts MUST follow the patterns established by upstream
  Python PMDAs (pmdagluster, pmdaopenmetrics, etc.).
- Use `pmdaCache` for dynamic instance domains, not hand-rolled dicts.

### III. Single Responsibility

Every module, class, and function MUST do exactly one thing.

- A function that fetches data MUST NOT also transform or cache it.
- A class that manages instance domains MUST NOT also handle HTTP.
- Poller threads own the network call cycle. Snapshot builders own the
  data transformation. The PMDA dispatch layer owns metric registration
  and fetch callbacks. These are distinct concerns.
- If a function needs a comment explaining what it does, it is too big
  or poorly named. Split it.
- Prefer many small, well-named functions over fewer large ones.

### IV. Human-Readable Code

Code is written for humans first, machines second.

- Method and variable names MUST be descriptive of their purpose. Prefer
  `build_switch_port_instances()` over `build_indoms()`.
- No single-letter variable names outside of trivial loop counters.
- Keep functions short and tight — if it scrolls off screen, split it.
- Comments explain *why*, never *what*. The code explains the what.
- Avoid clever tricks. Straightforward code that a new contributor can
  read in one pass is always preferred over compact code that requires
  head-scratching.

## PCP-Specific Constraints

- The PMDA MUST run as the unprivileged `pcp` user (FR-024).
- Configuration file MUST be `root:pcp` owned, mode 0640.
- The PMCD dispatch thread MUST NOT perform network I/O. All API calls
  happen in background poller threads with copy-on-write snapshot
  handoff.
- PMDA fetch response time MUST stay under 4 seconds at scale
  (2,400 switch port instances) to remain within PCP's 5-second
  PMDA timeout (SC-003).
- `requests` is the only pip-installable dependency. The PCP Python
  bindings (`pcp.pmda`, `cpmda`) come from the system package.
- The project is licensed GPL-2.0-or-later, consistent with PCP upstream.

## Quality Gates

- No code merges without passing tests at all tiers (unit, integration).
- Every user story MUST have at least one end-to-end acceptance test
  that exercises the full PMDA fetch path with a mocked UniFi API.
- Linting (ruff or flake8) and type checking (mypy in strict mode on
  public interfaces) MUST pass before merge.
- Constitution compliance MUST be verified during code review — if a PR
  violates a principle, it MUST be justified in the Complexity Tracking
  table of the implementation plan.

## Governance

- This constitution supersedes all other practices for pmdaunifi
  development.
- Amendments require: (1) documented rationale, (2) review by at least
  one maintainer, (3) a migration plan if the change affects existing
  code or tests.
- All PRs and reviews MUST verify compliance with these principles.
- Complexity that violates a principle MUST be justified in writing.
  If there is no justification, simplify.
- Version follows semantic versioning: MAJOR for principle
  removals/redefinitions, MINOR for additions/expansions, PATCH for
  wording clarifications.

**Version**: 1.0.0 | **Ratified**: 2026-03-15 | **Last Amended**: 2026-03-15
