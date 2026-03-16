# Tasks: UniFi PCP PMDA

**Input**: Design documents from `/specs/001-unifi-pmda/`
**Prerequisites**: plan.md, spec.md, data-model.md, contracts/, research.md, quickstart.md

**Tests**: MANDATORY per constitution principle I (TDD). All tests written and failing before implementation.

**Organization**: Tasks grouped by user story. 8 user stories from spec.md (US1–US8), plus setup, foundational, and polish phases.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Project Scaffolding)

**Purpose**: Create the project structure, build system, and test infrastructure

- [x] T001 Create `src/` layout directory structure per plan.md: `src/pcp_pmda_unifi/`, `tests/unit/`, `tests/integration/`, `tests/e2e/`, `tests/fixtures/`
- [x] T002 Create `pyproject.toml` with project metadata, `requests` dependency, entry points (`unifi2dot`, `pcp-pmda-unifi-setup`), pytest config, ruff config, and `[tool.setuptools.packages.find]` for `src/` layout
- [x] T003 [P] Create `src/pcp_pmda_unifi/__init__.py` with `__version__`, PCP import guard (try/except ImportError with helpful message)
- [x] T004 [P] Create `LICENSE` file with GPL-2.0-or-later text
- [x] T005 [P] Create test fixture files from scrubbed UniFi API responses: `tests/fixtures/stat_device.json` (include switches with port_table, APs with radio_table, gateway with wan1/system-stats), `tests/fixtures/stat_sta.json`, `tests/fixtures/stat_health.json`, `tests/fixtures/stat_sysinfo.json`, `tests/fixtures/stat_sitedpi.json`
- [x] T006 [P] Create `tests/conftest.py` with shared pytest fixtures: `sample_devices()`, `sample_clients()`, `sample_health()`, `sample_sysinfo()`, `sample_dpi()` loading from fixture JSON files; `sample_config()` returning a valid INI string
- [x] T007 [P] Create `.github/workflows/ci.yml` with lint (ruff + mypy), unit test, integration test, and e2e test jobs per plan.md CI pipeline spec

**Checkpoint**: Project builds (`pip install -e .`), pytest discovers empty test dirs, CI pipeline runs (lint only passes at this stage)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure modules that ALL user stories depend on. MUST complete before any US work begins.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

### Tests for Foundational

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T008 [P] Write failing tests for config parsing in `tests/unit/test_config.py`: valid single-controller config, multi-controller config, missing required fields (url, api_key), poll_interval validation (min 10), max_clients validation (>= 0), grace_period validation, sites parsing (`all`, single, comma-separated), env var override (UNIFI_URL, UNIFI_API_KEY, etc.), controller NAME validation (alphanumeric + hyphens)
- [x] T009 [P] Write failing tests for API collector in `tests/unit/test_collector.py`: URL construction with/without `/proxy/network` prefix (is_udm), API key header injection, response envelope parsing (`meta.rc == "ok"`), error response handling (401, 403, 404, 429, 5xx, connection error), defensive field access (`.get()` with defaults for missing fields), MAC normalisation to lowercase colon-separated
- [x] T010 [P] Write failing tests for snapshot building in `tests/unit/test_snapshot.py`: build snapshot from raw device/client/health dicts, extract port_table into PortData, extract radio_table into RadioData, extract gateway fields into GatewayData, extract system-stats (cpu, mem), counter fields as non-negative integers, missing optional fields default correctly, snapshot immutability
- [x] T011 [P] Write failing tests for instance naming in `tests/unit/test_instances.py`: site instance naming (`controller/site`), device instance naming (`controller/site/device_name`), switch port naming (`controller/site/device::PortN`), client naming (hostname fallback to MAC when empty), AP radio naming (`controller/site/device::radio_type`), gateway naming, controller naming, whitespace replacement with hyphens, DPI category naming

### Implementation for Foundational

- [x] T012 [P] Implement config parser in `src/pcp_pmda_unifi/config.py`: parse INI with `configparser` (case-sensitive), `[global]` section with defaults (poll_interval=30, max_clients=1000, grace_period=300, enable_dpi=false, log_level=warning), `[controller:NAME]` sections (url, api_key required; sites, is_udm, verify_ssl, ca_cert, poll_interval optional), env var override for non-interactive install, validation rules per contracts/configuration.md
- [x] T013 [P] Implement UniFi API collector in `src/pcp_pmda_unifi/collector.py`: `UnifiClient` class with `requests.Session`, API key header, base URL construction (is_udm prefix), methods: `discover_sites()`, `fetch_devices(site)`, `fetch_clients(site)`, `fetch_health(site)`, `fetch_sysinfo(site)`, `fetch_dpi(site)`, response envelope parsing, error handling per contracts/unifi-api-client.md, SSL/TLS config (verify_ssl, ca_cert)
- [x] T014 [P] Implement snapshot data structures in `src/pcp_pmda_unifi/snapshot.py`: frozen dataclasses for `Snapshot`, `SiteData`, `DeviceData`, `DeviceMeta`, `PortData`, `RadioData`, `GatewayData`, `ClientData`, `HealthData`, `DpiData` per data-model.md snapshot cache structure; builder functions `build_snapshot_from_api()` that transforms raw API dicts into typed snapshot
- [x] T015 [P] Implement instance naming in `src/pcp_pmda_unifi/instances.py`: functions `site_instance_name()`, `device_instance_name()`, `switch_port_instance_name()`, `client_instance_name()`, `ap_radio_instance_name()`, `gateway_instance_name()`, `controller_instance_name()`, `dpi_category_instance_name()` per data-model.md naming patterns; whitespace sanitisation; hostname fallback logic

- [x] T015a [P] Create mock UniFi controller in `tests/integration/mock_controller.py`: lightweight Flask app serving fixture JSON over HTTPS with self-signed cert, API key validation via `X-API-Key` header, endpoints: `/api/self/sites`, `/api/s/{site}/stat/device`, `/api/s/{site}/stat/sta`, `/api/s/{site}/stat/health`, `/api/s/{site}/stat/sysinfo`; runs in-process or as subprocess on `localhost:<random_port>`

**Checkpoint**: Foundation ready — all unit tests green for config, collector, snapshot, instances. Mock controller serves fixture data. User story implementation can now begin.

---

## Phase 3: User Story 1 — Monitor Switch Port Traffic in Real Time (Priority: P1) 🎯 MVP

**Goal**: Per-port traffic counters (bytes, packets, errors, drops) for every switch port, updating every 30 seconds, queryable via standard PCP tools.

**Independent Test**: Install PMDA, point at mock controller, run `pmrep unifi.switch.port.rx_bytes unifi.switch.port.tx_bytes` and see per-port byte rate counters updating.

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T016 [P] [US1] Write failing tests for poller thread in `tests/unit/test_poller.py`: poller starts/stops cleanly, polls on configured interval, builds snapshot from collector responses, handles collector errors (retains last snapshot, increments poll_errors), atomic snapshot swap via reference assignment, poll duration measurement
- [x] T017 [P] [US1] Write failing tests for PMDA switch port fetch callbacks in `tests/integration/test_pmda_fetch.py`: register switch_port metrics (cluster 2: rx_bytes, tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors, rx_dropped, tx_dropped, rx_broadcast, tx_broadcast, rx_multicast, tx_multicast, up, enable, speed, full_duplex, is_uplink, satisfaction, mac_count), fetch returns correct values from snapshot, fetch returns PM_ERR_INST for unknown instance, fetch returns PM_ERR_AGAIN when no snapshot yet, controller metrics (cluster 9: up, poll_duration_ms, poll_errors, last_poll)
- [x] T018 [US1] Write failing tests for PMDA labels in `tests/integration/test_pmda_fetch.py`: domain label (`agent=unifi`), instance labels (controller_name, controller_url, site_name, device_mac, device_type, device_model, port_idx) per data-model.md labels section

### Implementation for User Story 1

- [x] T019 [US1] Implement poller thread in `src/pcp_pmda_unifi/poller.py`: `ControllerPoller(threading.Thread)` with configurable interval, owns a `UnifiClient`, iterates configured sites calling fetch_devices/fetch_clients/fetch_health, builds `Snapshot` via `build_snapshot_from_api()`, atomically swaps `self._current_snapshot` reference, measures poll duration, handles errors (log + retain last snapshot + increment error count), daemon thread, clean start/stop
- [x] T020 [US1] Implement core PMDA class in `src/pcp_pmda_unifi/pmda.py`: `UnifiPMDA(PMDA)` extending `pcp.pmda.PMDA`, `__init__` reads config, registers switch_port indom (dict-based for pmdaCache), registers controller indom, registers all cluster 2 metrics (switch port counters/state per data-model.md) and cluster 9 metrics (controller health), sets fetch callback, sets label callbacks, calls `set_user('pcp')`, starts poller thread(s), `run()` entry point
- [x] T021 [US1] Implement fetch callback in `src/pcp_pmda_unifi/pmda.py`: `fetch_callback(cluster, item, inst)` reads from current snapshot, looks up instance via `inst_lookup()`, returns `[value, 1]` for known metrics or `[PM_ERR_PMID, 0]` / `[PM_ERR_INST, 0]` / `[PM_ERR_AGAIN, 0]` for errors; pre-fetch hook calls `replace_indom()` to sync instance domains from snapshot
- [x] T022 [US1] Implement label callbacks in `src/pcp_pmda_unifi/pmda.py`: domain label `{"agent":"unifi"}`, per-instance labels for switch_port (controller_name, controller_url, site_name, device_mac, device_type, device_model, port_idx) and controller (controller_name, controller_url)
- [x] T023 [US1] Implement CLI option parsing in `src/pcp_pmda_unifi/pmda.py`: support `-d domain`, `-l logfile`, `-c configfile`, `-U username`, `-r refresh` flags per contracts/configuration.md; wire to config overrides
- [x] T023a [US1] Implement fetch duration timing and warning in `src/pcp_pmda_unifi/pmda.py`: measure wall-clock time of each full fetch cycle, log warning if fetch exceeds 4 seconds (SC-003: "approaching PCP timeout threshold"), expose timing via `unifi.controller.poll_duration_ms`
- [x] T023b [US1] Write performance validation test in `tests/integration/test_pmda_fetch.py`: generate synthetic snapshot with 2,400 switch port instances (50 switches × 48 ports), invoke full fetch cycle, assert completes in < 4 seconds (SC-003)

**Checkpoint**: `pminfo -f unifi.switch.port.rx_bytes` returns per-port counters from a mock controller. `unifi.controller.up` reports 1. Labels attached. Fetch performance validated at scale. This is the MVP — the PMDA has a reason to exist.

---

## Phase 4: User Story 2 — Install and Configure the PMDA (Priority: P1)

**Goal**: Guided interactive installation: prompt for URL/API key, validate connectivity, discover sites, write config, register with PMCD — under 2 minutes.

**Independent Test**: Run `./Install` with a mock controller, verify prompts, config file written correctly, PMDA registered.

### Tests for User Story 2

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T024 [P] [US2] Write failing tests for Install script logic in `tests/integration/test_deploy.py`: connectivity validation (success + auth failure), site discovery listing, config file generation with correct ownership/permissions, non-interactive mode via env vars (`./Install -e`), upgrade mode (`./Install -u`) preserves existing config
- [x] T025 [P] [US2] Write failing tests for setup command in `tests/integration/test_deploy.py`: `pcp-pmda-unifi-setup install` copies deploy assets to target dir, generates PMDA launcher script, sets correct file permissions

### Implementation for User Story 2

- [x] T026 [P] [US2] Create Install shell script in `src/pcp_pmda_unifi/deploy/Install`: source `pmdaproc.sh`, set `iam=unifi`, `python_opt=true`, `daemon_opt=false`; before `pmdaSetup`: interactive prompts for URL, is_udm, API key; call Python helper to validate connectivity and discover sites; site selection prompt; detect self-signed certificate during connectivity test and prompt with security warning offering to set `verify_ssl = false`; write `unifi.conf` with `root:pcp` 0640; support `-e` (env var) and `-u` (upgrade) flags
- [x] T027 [P] [US2] Create Remove shell script in `src/pcp_pmda_unifi/deploy/Remove`: source `pmdaproc.sh`, `pmdaRemove`; preserve `unifi.conf`
- [x] T028 [P] [US2] Create sample config in `src/pcp_pmda_unifi/deploy/unifi.conf.sample` per contracts/configuration.md example
- [x] T029 [US2] Implement setup command in `src/pcp_pmda_unifi/setup.py`: `main()` entry point for `pcp-pmda-unifi-setup`, copies deploy assets from package data (via `importlib.resources`) to `$PCP_PMDAS_DIR/unifi/`, generates PMDA launcher script (`pmda_unifi.python`) that imports from site-packages, sets permissions

**Checkpoint**: `pip install -e . && sudo pcp-pmda-unifi-setup install && cd /var/lib/pcp/pmdas/unifi && sudo ./Install` works end-to-end with a mock controller. Config written, PMDA registered, metrics flowing.

---

## Phase 5: User Story 3 — Site-Level Health and Device Inventory (Priority: P2)

**Goal**: Site-level aggregate metrics (client counts, device counts, WAN/LAN/WLAN throughput) and per-device metadata (model, firmware, uptime, state) plus gateway WAN/LAN metrics.

**Independent Test**: Query `pminfo -f unifi.site.num_sta`, `pminfo -f unifi.device.uptime`, `pminfo -f unifi.gateway.wan_rx_bytes` and verify values match mock controller data.

### Tests for User Story 3

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T030 [P] [US3] Write failing tests for site metric fetch in `tests/integration/test_pmda_fetch.py`: cluster 0 metrics (status, num_sta, num_user, num_guest, num_ap, num_sw, num_gw, wan.rx_bytes, wan.tx_bytes, lan.rx_bytes, lan.tx_bytes, lan.num_user, lan.num_guest, wlan.rx_bytes, wlan.tx_bytes), site indom populated from health data
- [x] T031 [P] [US3] Write failing tests for device metric fetch in `tests/integration/test_pmda_fetch.py`: cluster 1 metrics (name, mac, ip, model, type, version, state, uptime, adopted, rx_bytes, tx_bytes, temperature, user_num_sta, guest_num_sta, num_ports), device indom populated, PM_ERR_VALUE for temperature on unsupported devices, device state transitions
- [x] T032 [P] [US3] Write failing tests for gateway metric fetch in `tests/integration/test_pmda_fetch.py`: cluster 6 metrics (wan_ip, wan_rx_bytes, wan_tx_bytes, wan_rx_packets, wan_tx_packets, wan_rx_dropped, wan_tx_dropped, wan_rx_errors, wan_tx_errors, wan_up, wan_speed, wan_latency, lan_rx_bytes, lan_tx_bytes, uptime, cpu, mem, temperature), gateway indom, labels (device_mac, device_type, device_model)
- [x] T033 [P] [US3] Write failing tests for controller extended metrics in `tests/integration/test_pmda_fetch.py`: cluster 9 additions (version, devices_discovered, clients_discovered, sites_polled) sourced from stat/sysinfo and snapshot counts

### Implementation for User Story 3

- [x] T034 [US3] Register site metrics (cluster 0) in `src/pcp_pmda_unifi/pmda.py`: add site indom (dict-based), register all 15 site metrics per data-model.md with correct types/semantics/units, extend fetch_callback for cluster 0, extend label_callback for site instances
- [x] T035 [US3] Register device metrics (cluster 1) in `src/pcp_pmda_unifi/pmda.py`: add device indom (dict-based), register all 15 device metrics per data-model.md, extend fetch_callback for cluster 1 (return PM_ERR_VALUE for temperature when unavailable), extend label_callback for device instances
- [x] T036 [US3] Register gateway metrics (cluster 6) in `src/pcp_pmda_unifi/pmda.py`: add gateway indom (dict-based), register all 18 gateway metrics per data-model.md, extend fetch_callback for cluster 6, extract wan1 fields with wan fallback, extract system-stats for cpu/mem, extend label_callback for gateway instances
- [x] T037 [US3] Extend controller metrics (cluster 9) in `src/pcp_pmda_unifi/pmda.py`: add version (from stat/sysinfo), devices_discovered, clients_discovered, sites_polled from snapshot counts; extend collector to call `fetch_sysinfo()` on 300s interval
- [x] T038 [US3] Implement grace period pruning in `src/pcp_pmda_unifi/instances.py`: track last-seen timestamp per instance, prune instances not seen for `grace_period` seconds (FR-017), apply to device and site indoms

**Checkpoint**: `pminfo -f unifi.site.num_sta`, `pminfo -f unifi.device.uptime`, `pminfo -f unifi.gateway.wan_rx_bytes` all return correct values. Device state changes reflected within one poll cycle.

---

## Phase 6: User Story 4 — Track Connected Clients (Priority: P3)

**Goal**: Per-client metrics (hostname, IP, MAC, switch port mapping, traffic counters) with configurable cardinality cap.

**Independent Test**: Query `pminfo -f unifi.client.hostname` and verify client instances include correct `sw_mac`/`sw_port` values.

### Tests for User Story 4

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T039 [P] [US4] Write failing tests for client metric fetch in `tests/integration/test_pmda_fetch.py`: cluster 4 metrics (hostname, ip, mac, oui, is_wired, sw_mac, sw_port, rx_bytes, tx_bytes, rx_packets, tx_packets, uptime, signal, network, last_seen), client indom populated, PM_ERR_VALUE for signal on wired clients
- [x] T040 [P] [US4] Write failing tests for cardinality cap in `tests/unit/test_instances.py`: max_clients=0 tracks all, max_clients=5 keeps top 5 by traffic, log warning when cap active, clients sorted by (rx_bytes + tx_bytes) descending
- [x] T041 [P] [US4] Write failing tests for client pruning in `tests/unit/test_instances.py`: client disappears from API response, grace period countdown, pruned after expiry, re-appears during grace period resets timer

### Implementation for User Story 4

- [x] T042 [US4] Register client metrics (cluster 4) in `src/pcp_pmda_unifi/pmda.py`: add client indom (dict-based), register all 15 client metrics per data-model.md with correct types/semantics, extend fetch_callback for cluster 4 (PM_ERR_VALUE for signal on wired clients), extend label_callback for client instances
- [x] T043 [US4] Implement cardinality cap in `src/pcp_pmda_unifi/snapshot.py`: sort clients by (rx_bytes + tx_bytes) descending, cap at `max_clients` if > 0, log warning when capping active (FR-009)
- [x] T044 [US4] Extend grace period pruning in `src/pcp_pmda_unifi/instances.py`: apply client-specific pruning with same grace_period logic as devices

**Checkpoint**: `pminfo -f unifi.client.hostname` shows clients. Cardinality cap works. Disconnected clients pruned after grace period.

---

## Phase 7: User Story 5 — Discover and Export Network Topology (Priority: P3)

**Goal**: Companion `unifi2dot` tool that queries the UniFi controller, discovers device interconnections from uplink tables, and outputs DOT/JSON graphs with PMDA metric instance name references.

**Independent Test**: Run `unifi2dot --url https://mock --api-key test --site default` and verify output graph matches expected topology.

### Tests for User Story 5

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T045 [P] [US5] Write failing tests for topology discovery in `tests/unit/test_topology.py`: build MAC-to-device lookup, discover links from uplink fields (uplink.mac → parent device, uplink.port_idx → parent port), classify ports (device link vs leaf vs empty), handle orphan devices (no uplink), handle missing uplink fields gracefully
- [x] T046 [P] [US5] Write failing tests for graph export in `tests/unit/test_topology.py`: DOT output is valid Graphviz syntax, nodes have device name/model/type attributes, edges have port labels and `unifi.switch.port.*` instance name references, JSON output has nodes/edges arrays with same data
- [x] T047 [P] [US5] Write failing tests for CLI in `tests/unit/test_cli.py`: `--url`, `--api-key`, `--site` required args, `--format dot` (default) and `--format json`, `-o` output file (default stdout), `--is-udm` flag, `--verify-ssl` flag

### Implementation for User Story 5

- [x] T048 [US5] Implement topology discovery in `src/pcp_pmda_unifi/topology.py`: `discover_topology(devices)` builds MAC-to-device lookup, walks uplink fields to build adjacency list, returns list of `TopologyLink(src_device, src_port, dst_device, dst_port, speed)` dataclasses
- [x] T049 [US5] Implement graph export in `src/pcp_pmda_unifi/topology.py`: `to_dot(links, devices)` outputs valid Graphviz DOT with device nodes and link edges annotated with PMDA instance names; `to_json(links, devices)` outputs `{"nodes": [...], "edges": [...]}` structure
- [x] T050 [US5] Implement CLI entry point in `src/pcp_pmda_unifi/cli.py`: argparse with `--url`, `--api-key`, `--site`, `--format {dot,json}`, `-o`, `--is-udm`, `--verify-ssl`/`--no-verify-ssl`; creates `UnifiClient`, fetches devices, runs `discover_topology()`, outputs via `to_dot()` or `to_json()`

**Checkpoint**: `unifi2dot --url https://mock --api-key test --site default | dot -Tpng -o topo.png` produces a valid topology graph. JSON output parseable by D3.js.

---

## Phase 8: User Story 6 — Monitor PoE Power Delivery Per Port (Priority: P3)

**Goal**: Per-port PoE metrics (enabled, good, power, voltage, current, class) on the same switch_port instance domain as US1.

**Independent Test**: Query `pminfo -f unifi.switch.port.poe.power` on a switch with PoE devices and verify wattage values.

### Tests for User Story 6

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T051 [P] [US6] Write failing tests for PoE metric fetch in `tests/integration/test_pmda_fetch.py`: cluster 3 metrics (poe.enable, poe.good, poe.power, poe.voltage, poe.current, poe.class), PoE-disabled port reports enable=0 and power/voltage/current=0, PoE fields extracted correctly from port_table

### Implementation for User Story 6

- [x] T052 [US6] Register PoE metrics (cluster 3) in `src/pcp_pmda_unifi/pmda.py`: register 6 PoE metrics per data-model.md on switch_port indom, extend fetch_callback for cluster 3, PoE-disabled ports return zero values

**Checkpoint**: `pminfo -f unifi.switch.port.poe.power` shows per-port power draw. `poe.class` returns PoE class string.

---

## Phase 9: User Story 7 — Monitor Access Point Radio Performance (Priority: P4)

**Goal**: Per-radio metrics (channel, client count, tx/rx bytes/packets, retries, drops, satisfaction) for each AP.

**Independent Test**: Query `pminfo -f unifi.ap.num_sta` and verify per-radio client counts match mock controller data.

### Tests for User Story 7

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T053 [P] [US7] Write failing tests for AP radio metric fetch in `tests/integration/test_pmda_fetch.py`: cluster 5 metrics (channel, radio_type, rx_bytes, tx_bytes, rx_packets, tx_packets, tx_dropped, tx_retries, num_sta, satisfaction), ap_radio indom populated from radio_table, labels (device_mac, device_type, device_model)

### Implementation for User Story 7

- [x] T054 [US7] Register AP radio metrics (cluster 5) in `src/pcp_pmda_unifi/pmda.py`: add ap_radio indom (dict-based), register all 10 AP metrics per data-model.md, extend fetch_callback for cluster 5, extend label_callback for ap_radio instances
- [x] T055 [US7] Extend snapshot building in `src/pcp_pmda_unifi/snapshot.py`: extract `radio_table` from AP devices into `RadioData` list within `DeviceData`, populate ap_radio instances via `ap_radio_instance_name()`

**Checkpoint**: `pminfo -f unifi.ap.num_sta` shows per-radio client counts. All 10 AP metrics populated.

---

## Phase 10: User Story 8 — Multi-Controller, Multi-Site Unified Monitoring (Priority: P4)

**Goal**: Multiple controllers in single PMDA, site-qualified instance names, per-controller poller threads, collision-free naming.

**Independent Test**: Configure two `[controller:NAME]` sections, verify instances from both appear with correct prefixes.

### Tests for User Story 8

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T056 [P] [US8] Write failing tests for multi-controller config in `tests/unit/test_config.py`: parse multiple `[controller:NAME]` sections, each with independent url/api_key/sites/is_udm/poll_interval
- [x] T057 [P] [US8] Write failing tests for multi-controller instance naming in `tests/unit/test_instances.py`: two controllers with same site name "default" produce distinct instance names (`hq/default/...` vs `branch/default/...`), instance name filtering with regex works (`hq/.*`)
- [x] T058 [P] [US8] Write failing tests for multi-controller poller in `tests/integration/test_poller.py`: PMDA starts one poller thread per `[controller:NAME]` section, each poller builds independent snapshots, snapshot merge produces unified instance domains, pollers run on independent intervals

### Implementation for User Story 8

- [x] T059 [US8] Extend PMDA startup in `src/pcp_pmda_unifi/pmda.py`: iterate config controller sections, start one `ControllerPoller` thread per section, merge snapshots from all pollers into unified instance domains during pre-fetch
- [x] T060 [US8] Extend poller for multi-controller in `src/pcp_pmda_unifi/poller.py`: each poller owns its controller name, passes it to instance naming functions, independent poll intervals from per-controller config

**Checkpoint**: Two mock controllers configured, `pminfo -f unifi.switch.port.rx_bytes` shows instances from both with distinct prefixes. No instance name collisions.

---

## Phase 11: DPI Metrics (Opt-in, FR-023)

**Purpose**: Per-site, per-DPI-category traffic totals (rx/tx bytes). Opt-in via `enable_dpi = true`.

- [x] T061 [P] Write failing tests for DPI metric fetch in `tests/integration/test_pmda_fetch.py`: cluster 8 metrics (rx_bytes, tx_bytes), dpi_category indom populated from sitedpi response (~20 categories), DPI disabled by default (no indom entries), DPI enabled via config flag
- [x] T062 Implement DPI metrics (cluster 8) in `src/pcp_pmda_unifi/pmda.py`: add dpi_category indom (dict-based), register 2 DPI metrics, extend fetch_callback for cluster 8; extend poller to call `fetch_dpi()` on 300s interval only when `enable_dpi = true`; extend snapshot with `dpi_categories` list

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Documentation, dashboards, packaging, and ancillary deliverables

### Documentation

- [ ] T063 [P] Create `CONTRIBUTING.md` at repository root: dev setup (`pip install -e ".[dev]"`), repo structure guide, testing requirements (TDD mandatory, 90%+ coverage), code style (ruff enforced, mypy on public interfaces), PR process, UniFi API resource links (developer.ui.com, ubntwiki, unpoller)
- [ ] T064 [P] Create man page source in `man/pmdaunifi.1.md`: synopsis, description, configuration file format, command-line options, installation/removal, files, environment variables, diagnostics — following PCP man page conventions
- [ ] T065 [P] Create mkdocs site in `docs/`: `mkdocs.yml` config (material theme), `getting-started.md` (from quickstart.md), `configuration.md` (from contracts/configuration.md), `metrics.md` (auto-generated metric reference from data-model.md), `topology.md` (unifi2dot usage), `architecture.md` (threading, snapshot, caching), `grafana.md` (dashboard import guide), `troubleshooting.md` (common issues), `developer.md` (from CONTRIBUTING.md)

### Grafana Dashboards

- [ ] T066 [P] Create Site Overview dashboard in `dashboards/site-overview.json`: site health status, total clients, device counts, WAN throughput, subsystem status; site_name template variable from labels
- [ ] T067 [P] Create Switch Port Detail dashboard in `dashboards/switch-port-detail.json`: per-port rx/tx byte rates, error rates, PoE power, link state; switch and port selector variables
- [ ] T068 [P] Create Client Insights dashboard in `dashboards/client-insights.json`: top clients by traffic, client count over time, wired vs wireless breakdown
- [ ] T069 [P] Create AP Radio Performance dashboard in `dashboards/ap-radio-performance.json`: per-radio channel, client counts, tx retries, satisfaction scores

### Packaging

- [ ] T070 [P] Create RPM spec file in `packaging/rpm/pcp-pmda-unifi.spec`: BuildRequires python3-devel/setuptools/pcp-devel, Requires pcp/python3-pcp/python3-requests, installs to `%{_localstatedir}/lib/pcp/pmdas/unifi/`
- [ ] T071 [P] Create Debian packaging in `packaging/deb/`: `control` (Depends: pcp, python3-pcp, python3-requests), `rules` (dh_python3), `postinst` (calls Install -u)

### CI & Publishing

- [ ] T072 Create release workflow in `.github/workflows/release.yml`: triggers on GitHub Release publish, builds sdist+wheel, publishes to PyPI via Trusted Publishing (OIDC, `pypa/gh-action-pypi-publish`)

### Ancillary Features

- [ ] T073 Implement Install `-u` upgrade mode in `src/pcp_pmda_unifi/deploy/Install`: skip interactive prompts, preserve existing `unifi.conf`, re-generate PMNS/domain.h, re-register with PMCD
- [ ] T074 [P] Create synthetic archive generator in `tests/generate_synthetic_archive.py`: define full PMNS, generate configurable topology (N switches × M ports, K clients, J APs), write realistic time-series data (monotonic counters, oscillating client counts, PoE values), output standard PCP archive via `pcp.LogImport`

### Final Validation

- [ ] T075 Write e2e test for full PMDA lifecycle in `tests/e2e/test_live_pmda.py`: start mock controller, run `./Install`, verify at least one metric per cluster — `unifi.site.num_sta` (cluster 0), `unifi.device.uptime` (cluster 1), `unifi.switch.port.rx_bytes` (cluster 2), `unifi.switch.port.poe.power` (cluster 3), `unifi.client.hostname` (cluster 4), `unifi.ap.num_sta` (cluster 5), `unifi.gateway.wan_rx_bytes` (cluster 6), `unifi.dpi.rx_bytes` (cluster 8), `unifi.controller.up` (cluster 9); verify `pminfo -l unifi.switch.port.rx_bytes` returns correct labels; run `./Remove` and verify metrics gone
- [ ] T076 Write e2e test for unifi2dot in `tests/e2e/test_unifi2dot.py`: start mock HTTP server, run `unifi2dot` CLI, verify DOT output is valid Graphviz, verify JSON output is parseable
- [ ] T077 Run quickstart.md validation: execute all commands from quickstart.md against mock controller and verify each produces expected output

**Checkpoint**: Full test suite green (unit + integration + e2e). Documentation site builds. Dashboards importable. Package builds cleanly.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories
- **US1 (Phase 3)**: Depends on Foundational — this is the MVP
- **US2 (Phase 4)**: Depends on US1 (Install needs a working PMDA to register)
- **US3 (Phase 5)**: Depends on Foundational — can run parallel with US1 if needed
- **US4 (Phase 6)**: Depends on Foundational — independent of other stories
- **US5 (Phase 7)**: Depends on Foundational (collector) — independent of PMDA stories
- **US6 (Phase 8)**: Depends on US1 (extends switch_port indom)
- **US7 (Phase 9)**: Depends on Foundational — independent of other stories
- **US8 (Phase 10)**: Depends on US1 (extends single-controller to multi)
- **DPI (Phase 11)**: Depends on Foundational — independent
- **Polish (Phase 12)**: Depends on all desired user stories being complete

### User Story Dependencies

```
Setup → Foundational → US1 (MVP) → US2 (Install)
                     ↘ US3 (site/device/gateway)
                     ↘ US4 (clients)
                     ↘ US5 (topology — standalone tool)
                     → US1 → US6 (PoE — extends US1 indom)
                     ↘ US7 (AP radios)
                     → US1 → US8 (multi-controller — extends US1 architecture)
                     ↘ DPI (opt-in)
                     All → Polish
```

### Within Each User Story

- Tests MUST be written and FAIL before implementation (constitution principle I)
- Snapshot/data model before PMDA registration
- PMDA registration before fetch callbacks
- Fetch callbacks before labels
- Story complete before moving to next priority

### Parallel Opportunities

- All Setup tasks marked [P] can run in parallel (T003–T007)
- All Foundational tests marked [P] can run in parallel (T008–T011)
- All Foundational implementations marked [P] can run in parallel (T012–T015)
- US3, US4, US5, US7, DPI can all start in parallel once Foundational completes (if team capacity allows)
- US5 (topology tool) is fully independent — can be developed in parallel with everything
- All Polish phase tasks marked [P] can run in parallel (T063–T071, T074)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 tests in parallel (different files):
Task: "Write failing tests for poller thread in tests/unit/test_poller.py"
Task: "Write failing tests for PMDA switch port fetch callbacks in tests/integration/test_pmda_fetch.py"
Task: "Write failing tests for PMDA labels in tests/integration/test_pmda_fetch.py"

# Then implement sequentially (shared pmda.py):
Task: "Implement poller thread in src/pcp_pmda_unifi/poller.py"
Task: "Implement core PMDA class in src/pcp_pmda_unifi/pmda.py"
Task: "Implement fetch callback in src/pcp_pmda_unifi/pmda.py"
Task: "Implement label callbacks in src/pcp_pmda_unifi/pmda.py"
```

## Parallel Example: Independent Stories After Foundational

```bash
# These can all run in parallel (different indoms, different clusters):
Task: US3 "Register site metrics (cluster 0)"
Task: US4 "Register client metrics (cluster 4)"
Task: US5 "Implement topology discovery"
Task: US7 "Register AP radio metrics (cluster 5)"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1 (switch port traffic)
4. **STOP and VALIDATE**: `pmrep -t 5 unifi.switch.port.rx_bytes` works against a mock controller
5. Complete Phase 4: User Story 2 (Install script)
6. **Deploy/demo**: functional PMDA with per-port monitoring

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 → Test independently → **MVP!** Per-port traffic monitoring works
3. US2 → Test independently → Users can install it
4. US3 → Test independently → Site health + device inventory + gateway metrics
5. US4 → Test independently → Client tracking with cardinality cap
6. US5 → Test independently → Topology export tool
7. US6 → Test independently → PoE monitoring (small addition)
8. US7 → Test independently → AP radio metrics
9. US8 → Test independently → Multi-controller support
10. DPI + Polish → Feature complete

### Single Developer Strategy (Recommended)

Work in priority order: Setup → Foundational → US1 → US2 → US3 → US4 → US5 → US6 → US7 → US8 → DPI → Polish. Each story is a complete, shippable increment.

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable
- Tests MUST fail before implementation begins (constitution principle I)
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Total: 77 tasks across 12 phases
