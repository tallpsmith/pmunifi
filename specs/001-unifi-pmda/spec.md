# Feature Specification: UniFi PCP PMDA

**Feature Branch**: `001-unifi-pmda`
**Created**: 2026-03-15
**Status**: Draft
**Input**: Build a Performance Metrics Domain Agent (PMDA) for PCP that collects network performance metrics from Ubiquiti UniFi infrastructure via the UniFi Controller REST API.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Monitor Switch Port Traffic in Real Time (Priority: P1)

A network administrator wants to see per-port traffic counters (bytes, packets, errors, drops) for every switch port across their UniFi network, updating every 30 seconds, using standard PCP tools like `pmrep` and `pmval`.

**Why this priority**: Per-port switch traffic monitoring is the core use case. Without this, the PMDA has no reason to exist. It mirrors what `pmdacisco` does for Cisco routers, but with far richer data from the UniFi API.

**Independent Test**: Can be fully tested by installing the PMDA, pointing it at a UniFi controller (or mock), and running `pmrep unifi.switch.port.rx_bytes unifi.switch.port.tx_bytes` to see per-port byte rate counters updating.

**Acceptance Scenarios**:

1. **Given** a UniFi controller with adopted switches, **When** the PMDA is installed and configured with a valid API key, **Then** all switch ports appear as instances under `unifi.switch.port.*` metrics with correct byte/packet/error counters.
2. **Given** traffic flowing through a switch port, **When** a user runs `pmrep -t 5 unifi.switch.port.rx_bytes`, **Then** they see monotonically increasing counter values that PCP converts to per-second rates.
3. **Given** a switch port with no link, **When** the PMDA polls the controller, **Then** the port instance still exists but `unifi.switch.port.up` reports 0 and counters remain static.
4. **Given** a newly adopted switch appears on the controller, **When** the next poll cycle completes, **Then** the new switch's ports automatically appear in the instance domain without PMDA restart.

---

### User Story 2 - Install and Configure the PMDA Interactively (Priority: P1)

A PCP administrator wants a guided installation experience where they provide their UniFi controller URL and API key, the PMDA validates connectivity, discovers available sites, and writes a working configuration — all within two minutes.

**Why this priority**: If people can't install it easily, no one will use it. The Install script is the front door to the entire product. This is co-P1 with port monitoring because one is useless without the other.

**Independent Test**: Can be tested by running `./Install` with a mock controller, verifying it prompts for URL/API key, tests connectivity, discovers sites, writes config, and registers with PMCD.

**Acceptance Scenarios**:

1. **Given** a PCP host with network access to a UniFi controller, **When** the administrator runs `./Install`, **Then** they are prompted for controller URL, API key, and site selection, and the PMDA registers successfully with PMCD.
2. **Given** an invalid API key, **When** the Install script tests connectivity, **Then** it reports an authentication failure and does not write an incomplete configuration.
3. **Given** a multi-site controller, **When** the Install script discovers sites, **Then** it lists all available sites with device counts and lets the administrator choose which to monitor.
4. **Given** automation requirements, **When** environment variables (`UNIFI_URL`, `UNIFI_API_KEY`, `UNIFI_SITES`) are set and `./Install -e` is run, **Then** installation completes non-interactively without prompts.

---

### User Story 3 - View Site-Level Health and Device Inventory (Priority: P2)

A network operations team wants site-level aggregate metrics (total clients, device counts, WAN throughput) and per-device metadata (model, firmware, uptime, state) to get a high-level health overview of their UniFi infrastructure.

**Why this priority**: Site and device metrics provide the "big picture" context around the per-port detail. They are essential for dashboards and alerting but are less granular than the P1 port data.

**Independent Test**: Can be tested by querying `pminfo -f unifi.site.num_sta` and `pminfo -f unifi.device.uptime` after installation and verifying values match what the controller reports.

**Acceptance Scenarios**:

1. **Given** an active UniFi site, **When** the PMDA polls, **Then** `unifi.site.num_sta` reflects the total connected client count and `unifi.site.wan.rx_bytes` / `tx_bytes` reflect WAN throughput counters.
2. **Given** multiple device types (switches, APs, gateways), **When** querying `unifi.device.*`, **Then** each device appears with correct name, MAC, model, firmware version, and uptime.
3. **Given** a device goes offline, **When** the next poll cycle completes, **Then** the device's `unifi.device.state` changes to reflect its disconnected status.

---

### User Story 4 - Track Connected Clients and Their Switch Ports (Priority: P3)

A network administrator wants to see which clients are connected to which switch ports, including client hostname, IP, MAC, and per-client traffic counters, to troubleshoot connectivity and identify heavy users.

**Why this priority**: Client tracking adds significant value but has cardinality challenges in large deployments. It builds on the P1 port data by adding the "who is on this port" dimension.

**Independent Test**: Can be tested by querying `pminfo -f unifi.client.hostname` and verifying client instances include correct `sw_mac` and `sw_port` values mapping them to switch ports.

**Acceptance Scenarios**:

1. **Given** wired clients connected to switches, **When** the PMDA polls, **Then** each client appears in the `client` instance domain with hostname, IP, MAC, switch MAC, switch port, and traffic counters.
2. **Given** more clients than the `max_clients` limit, **When** the PMDA polls, **Then** only the top N clients by traffic volume are tracked, preventing cardinality explosion.
3. **Given** a client disconnects, **When** the grace period expires (default 5 minutes), **Then** the client's instances are pruned from the instance domain.

---

### User Story 5 - Discover and Export Network Topology (Priority: P3)

A network engineer wants a companion tool that discovers how UniFi devices are interconnected (switch-to-switch uplinks, AP-to-switch connections) and outputs a structured graph with references to the corresponding PMDA port metrics, so topology can be visualised with live traffic overlays.

**Why this priority**: Topology visualisation is a differentiating feature, but it depends on device and port data being solid first. It is implemented as a companion tool rather than as PMDA metrics because graph adjacency is structural data, not time-series data — PCP metrics are not designed to carry unbounded relational structures.

**Independent Test**: Can be tested by running the `unifi2dot` companion tool against a controller and verifying the output graph matches the physical network connections, with correct metric name references on each edge.

**Acceptance Scenarios**:

1. **Given** switches connected via uplink ports, **When** the `unifi2dot` companion tool queries the UniFi controller, **Then** it outputs a valid Graphviz DOT file where nodes are devices and edges represent physical links annotated with the corresponding `unifi.switch.port.*` metric instance names.
2. **Given** a DOT file produced by `unifi2dot`, **When** combined with live PCP metric data, **Then** a visualisation tool can overlay per-port traffic rates onto the topology edges.
3. **Given** a JSON output mode is requested, **When** `unifi2dot --format json` runs, **Then** it outputs a structured JSON graph suitable for D3.js or similar visualisation libraries.

---

### User Story 6 - Monitor PoE Power Delivery Per Port (Priority: P3)

A facilities engineer wants to monitor Power over Ethernet metrics (power draw, voltage, current) for each switch port to track power budgets and detect failing PoE devices.

**Why this priority**: PoE monitoring is valuable for infrastructure management but is a narrower use case than general traffic monitoring. It rides on the same port instance domain as P1.

**Independent Test**: Can be tested by querying `pminfo -f unifi.switch.port.poe.power` on a switch with PoE-powered devices and verifying wattage values.

**Acceptance Scenarios**:

1. **Given** a PoE-enabled switch port powering a device, **When** the PMDA polls, **Then** `unifi.switch.port.poe.power`, `poe.voltage`, and `poe.current` report the correct values.
2. **Given** a port with PoE disabled, **When** queried, **Then** `unifi.switch.port.poe.enabled` reports 0 and power metrics report zero.

---

### User Story 7 - Monitor Access Point Radio Performance (Priority: P4)

A wireless network engineer wants per-radio metrics (channel, client count, tx/rx bytes, retries, satisfaction score) for each access point to identify coverage gaps and congestion.

**Why this priority**: AP metrics are important for wireless-heavy deployments but are a separate concern from the wired switching core. They use a different instance domain and API data path.

**Independent Test**: Can be tested by querying `pminfo -f unifi.ap.num_sta` and verifying per-radio client counts match the controller.

**Acceptance Scenarios**:

1. **Given** access points with connected wireless clients, **When** the PMDA polls, **Then** each radio appears in the `ap_radio` instance domain with channel, radio type, client count, and traffic counters.

---

### User Story 8 - Multi-Controller, Multi-Site Unified Monitoring (Priority: P4)

An enterprise network administrator managing multiple UniFi controllers across branch offices wants all controllers' metrics unified under a single PCP namespace, with site-qualified instance names enabling cross-site comparison.

**Why this priority**: Multi-controller support is an enterprise feature. The architecture must support it from the start (site-prefixed instance names, per-controller threads), but full multi-controller testing is a later concern.

**Independent Test**: Can be tested by configuring two `[controller:NAME]` sections and verifying instances from both controllers appear with correct site prefixes.

**Acceptance Scenarios**:

1. **Given** two controllers configured as `[controller:hq]` and `[controller:branch]`, **When** the PMDA starts, **Then** each spawns its own poller thread and instances are prefixed with their respective site names.
2. **Given** both controllers have a site named "default", **When** the controller NAME override is used, **Then** instance names use the controller name prefix (e.g. `hq/...`, `branch/...`) avoiding collisions.

---

### Edge Cases

- What happens when the UniFi controller is unreachable during a poll cycle? The PMDA retains the last successful data snapshot, logs the error, and increments `unifi.controller.poll_errors`.
- What happens when a switch reboots mid-poll, resetting its counters? PCP's counter semantics handle resets automatically — tools detect the counter decrease and compute rates correctly.
- What happens when the API key is revoked while the PMDA is running? All subsequent polls fail, `unifi.controller.up` drops to 0, errors are logged, and the last successful snapshot is served until the key is restored.
- What happens when the controller returns an unexpected JSON schema (e.g. after a firmware update)? The PMDA uses defensive parsing (`.get()` with defaults), logs warnings for missing expected fields, and continues with available data.
- What happens when a switch has 48+ ports and 200+ MACs per port? The instance domain scales linearly; the `mac_count` metric per port helps operators identify high-density ports without tracking individual MACs.
- What happens with SSL certificate validation on self-signed UniFi controllers? `verify_ssl` defaults to `true`. The Install script detects self-signed certificates and prompts the operator to explicitly disable verification with a security warning. A `ca_cert` path option is available for custom CA bundles.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST authenticate to UniFi controllers exclusively via API key (`X-API-Key` header), requiring UniFi Network Application 9.0+.
- **FR-002**: System MUST discover and poll one or more UniFi sites per controller, with configurable site selection (`all`, explicit list, or single site).
- **FR-003**: System MUST collect per-switch-port traffic counters (rx/tx bytes, packets, errors, drops, broadcast, multicast) and expose them as PCP counter metrics with correct `PM_SEM_COUNTER` semantics.
- **FR-004**: System MUST dynamically discover devices and update instance domains on each poll cycle without requiring restart or reconfiguration.
- **FR-005**: System MUST provide an interactive Install script that validates connectivity, discovers sites, writes configuration, and registers the PMDA with PMCD.
- **FR-006**: System MUST support non-interactive installation via environment variables for automation tooling.
- **FR-007**: System MUST collect site-level aggregate metrics (client counts, device counts, WAN/LAN/WLAN throughput counters).
- **FR-008**: System MUST collect per-device metadata (name, MAC, IP, model, type, firmware version, uptime, state).
- **FR-009**: System MUST collect per-client metrics (hostname, IP, MAC, switch location, traffic counters) with a configurable soft cardinality cap (`max_clients`, default 1000, 0 = unlimited). When the cap is reached, the PMDA MUST log a warning indicating the limit is active and capping, and track only the top N clients by traffic volume.
- **FR-010**: System MUST provide a companion `unifi2dot` tool that queries the UniFi controller API to discover intra-site network topology from uplink tables and LLDP data, and outputs graph formats (DOT, JSON) with references to the corresponding PMDA port metric instance names.
- **FR-011**: System MUST collect per-switch-port PoE metrics (enabled, power, voltage, current, class) where available.
- **FR-012**: System MUST collect per-AP radio metrics (channel, radio type, traffic counters, client count, satisfaction score).
- **FR-013**: System MUST use per-controller background poller threads with a copy-on-write snapshot cache, ensuring the PMCD dispatch thread never blocks on network I/O. Poll interval is configurable per-controller (default 30 seconds, minimum 10 seconds).
- **FR-014**: System MUST handle controller unavailability gracefully — retaining the last successful snapshot, logging errors, and exposing controller health via `unifi.controller.*` metrics.
- **FR-015**: System MUST attach PCP metric labels (`site_name`, `device_mac`, `device_type`, `device_model`, `port_idx`, `controller_url`) to all instances.
- **FR-016**: System MUST support multiple controllers in a single PMDA process via `[controller:NAME]` configuration sections, with site-qualified instance names preventing collisions.
- **FR-017**: System MUST prune disappeared devices/clients from instance domains after a configurable grace period (default 5 minutes).
- **FR-018**: System MUST handle the UniFi OS API path prefix (`/proxy/network`) automatically when `is_udm = true`.
- **FR-019**: System MUST provide a `Remove` script that deregisters the PMDA from PMCD without deleting the configuration file.
- **FR-020**: System MUST export raw counter values only — pre-computed rate fields from the UniFi API are deliberately excluded to maintain PCP counter semantics consistency.
- **FR-021**: The `unifi2dot` companion tool MUST support both Graphviz DOT and JSON output formats for network visualisation.
- **FR-022**: System MUST be distributable via PyPI (`pip install pcp-pmda-unifi`) with `requests` as the only pip-installable dependency.
- **FR-023**: System MUST support optional DPI (Deep Packet Inspection) metrics as an opt-in feature, exposing per-site, per-DPI-category traffic totals (rx/tx bytes) in a `dpi_category` instance domain (~20 categories: Streaming, Social, Gaming, etc.). Per-device DPI breakdown is deferred to a future release.
- **FR-024**: System MUST run as the unprivileged `pcp` user with the configuration file restricted to `root:pcp` ownership (mode 0640).

### Key Entities

- **Controller**: A UniFi Network Application instance (on a UDM, UCG, or self-hosted server) that manages one or more sites. Identified by URL and authenticated by API key.
- **Site**: A logical grouping of devices within a controller (e.g. "default", "warehouse", "branch-melbourne"). The primary scoping dimension for all metrics.
- **Device**: A UniFi network device (switch, access point, gateway, console) adopted by a controller. Identified by MAC address. Has model, firmware, uptime, and state.
- **Switch Port**: A physical port on a switch device. Identified by device + port index. Carries traffic counters, link state, speed, and PoE telemetry. The central entity for the PMDA's core use case.
- **Client**: A connected network station (wired or wireless). Identified by MAC address. Mapped to a switch port via `sw_mac`/`sw_port`. Has traffic counters and connection metadata.
- **Topology Link**: A discovered connection between two UniFi devices, derived from uplink tables and LLDP data by the companion `unifi2dot` tool. Has source/destination device and port, link speed, and references to the corresponding PMDA port metric instances.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An administrator can go from zero to seeing live switch port metrics in under 2 minutes using the interactive Install script.
- **SC-002**: All switch port traffic counters update within 30 seconds of the data changing on the UniFi controller (within one poll cycle at default interval).
- **SC-003**: The PMDA correctly tracks at least 2,400 switch port instances (50 switches x 48 ports) with fetch response time under 4 seconds (below PCP's 5-second PMDA timeout). If a fetch exceeds 4 seconds, the PMDA MUST log a warning indicating it is approaching the PCP timeout threshold.
- **SC-004**: Dynamic instance domain changes (devices added/removed) are reflected within one poll cycle without PMDA restart.
- **SC-005**: Multi-controller deployments produce collision-free instance names that support cross-site filtering via instance name patterns (e.g. filtering by `hq/.*`).
- **SC-006**: Controller connectivity failures are detected within one poll cycle and reflected in controller health metrics, enabling alerting on PMDA health.
- **SC-007**: 90% or greater line coverage on all non-framework code, with unit, integration, and end-to-end test tiers all passing in CI.
- **SC-008**: The PMDA runs continuously for 7+ days without memory leaks, crashes, or stale data when the controller is stable.
- **SC-009**: The `unifi2dot` companion tool correctly discovers topology links for all directly connected UniFi device pairs within a single site and outputs valid graph files with correct PMDA metric instance references.

## Clarifications

### Session 2026-03-15

- Q: What is the poll interval model? → A: Configurable per-controller, default 30s, minimum 10s.
- Q: What should the default max_clients cap be? → A: Soft cap of 1000 (configurable, 0 = unlimited). Log warning when cap is reached and capping is active.
- Q: What is the maximum acceptable fetch response time at 2,400 instances? → A: 4 seconds (under PCP's 5s timeout). Log warning if fetch exceeds 4s threshold.
- Q: What DPI metrics should be exposed? → A: Per-site, per-DPI-category traffic totals only (rx/tx bytes, ~20 categories). Per-device DPI deferred to future release.
- Q: What should the default SSL verification posture be? → A: Default verify_ssl=true. Install script detects self-signed certs and offers to disable with explicit security warning.

## Assumptions

- UniFi Network Application 9.0+ is deployed on all target controllers (required for API key support).
- The host running the PMDA has HTTPS network access to all configured UniFi controllers.
- The UniFi API endpoints (`stat/device`, `stat/sta`, `stat/health`) remain stable in their core field structure across 9.x releases.
- A single API key provides read-only access to all sites on a controller (no per-site scoping).
- The `pcp` system user exists and PCP is installed on the collector host.
- Counter values from the UniFi API are 64-bit integers that reset only on device reboot.
- Cross-site topology discovery is out of scope for the initial release (each controller only knows its own devices).
- Gateway/router WAN metrics follow the same API patterns as switch metrics and do not require separate authentication.
- The project is licensed GPL-2.0-or-later, consistent with PCP upstream.

## Scope Boundaries

**In Scope:**
- Switch port traffic monitoring (site, device, port, PoE, controller health metrics)
- Client tracking with cardinality controls
- Intra-site topology discovery and export via companion `unifi2dot` tool (not as PMDA metrics)
- AP radio metrics
- Gateway WAN metrics
- DPI category metrics (opt-in)
- Interactive and non-interactive installation
- PyPI distribution
- Grafana dashboard JSON files
- Man page and documentation site
- Unit, integration, and end-to-end test suites

**Out of Scope:**
- Cross-site topology discovery (deferred to future work)
- Classic session-based authentication (username/password) — API key only
- Pre-computed rate fields from the UniFi API
- Controller configuration or write operations
- Per-client DPI breakdown (cardinality explosion risk)
- Historical/aggregated report data from the controller (PCP archives serve this purpose)
- Guest portal, hotspot, rogue AP, alarm, and event data
- WebSocket event-driven refresh (future work)
