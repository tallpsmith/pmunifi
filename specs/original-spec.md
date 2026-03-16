# pmdaunifi — PCP PMDA Specification

**Performance Metrics Domain Agent for Ubiquiti UniFi Network Infrastructure**

Version 1.2 — March 2026 | DRAFT SPECIFICATION

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Background and Motivation](#2-background-and-motivation)
3. [Architecture](#3-architecture)
4. [UniFi API Endpoints Used](#4-unifi-api-endpoints-used)
5. [Performance Metrics Name Space (PMNS)](#5-performance-metrics-name-space-pmns)
6. [Topology Discovery and Graph Construction](#6-topology-discovery-and-graph-construction)
7. [Configuration](#7-configuration)
8. [Packaging, Installation, and Updates](#8-packaging-installation-and-updates)
9. [File and Directory Layout](#9-file-and-directory-layout)
10. [Example Usage Scenarios](#10-example-usage-scenarios)
11. [Excluded UniFi Metrics and Design Rationale](#11-excluded-unifi-metrics-and-design-rationale)
12. [Comparison with pmdacisco](#12-comparison-with-pmdacisco)
13. [Documentation](#13-documentation)
14. [Development Roadmap](#14-development-roadmap)
15. [Assumptions, Open Questions, and Future Work](#15-assumptions-open-questions-and-future-work)
16. [Appendices](#16-appendices)
    - [16.7 Testing Strategy](#167-testing-strategy)
    - [16.8 Dependencies](#168-dependencies)
    - [16.9 PyPI Account and Publishing Setup](#169-pypi-account-and-publishing-setup)

---

## 1. Executive Summary

This document specifies **pmdaunifi**, a Performance Metrics Domain Agent (PMDA) for Performance Co-Pilot (PCP) that collects comprehensive network performance metrics from Ubiquiti UniFi infrastructure. The PMDA communicates with one or more UniFi Network Controllers via their REST API to discover network topology, extract per-device and per-port traffic statistics, map connected clients to switch ports, and export all of this as structured PCP metrics suitable for real-time monitoring, historical archiving, capacity planning, and topology visualisation.

The design is modelled after the existing **pmdacisco** PMDA, which extracts interface-level counters from Cisco routers via telnet. pmdaunifi significantly extends this pattern by leveraging the UniFi Controller's JSON API to provide far richer data: full switch port tables with byte/packet/error/drop counters, PoE telemetry, client-to-port MAC address mapping, access point radio statistics, gateway WAN metrics, site-level health aggregates, and a topology adjacency model that captures how devices interconnect.

The PMDA is implemented as a Python daemon process (consistent with modern PCP PMDAs such as pmdabcc, pmdaopenmetrics, and pmdaproc) and runs as the unprivileged "pcp" user. It authenticates exclusively via UniFi API keys (requiring Network Application 9.0+) and uses per-controller poller threads with a copy-on-write snapshot cache to ensure low-latency responses to PMCD fetch requests while still providing fresh data from the controller(s).

---

## 2. Background and Motivation

### 2.1 The Existing pmdacisco PMDA

PCP ships with pmdacisco, which connects to Cisco routers over telnet, issues "show interface" commands, and parses the text output to extract five core metrics per interface: bytes in, bytes out, bandwidth (the configured interface speed), and two utilisation ratios. The instance domain is the set of monitored interfaces, expressed as hostname:interface-name tuples. This approach works well for Cisco CLI-based devices but is limited by the text-parsing dependency and the narrow set of metrics available through the show interface command.

### 2.2 The UniFi Opportunity

UniFi Network Controllers expose a comprehensive REST/JSON API that provides:

- Complete device inventory (switches, access points, gateways, consoles) with model, firmware, uptime, and state.
- Per-port statistics on every switch including rx_bytes, tx_bytes, rx_packets, tx_packets, rx_errors, tx_errors, rx_dropped, tx_dropped, rx_broadcast, tx_broadcast, rx_multicast, tx_multicast, speed, full_duplex, and PoE metrics.
- A `mac_table` on each port that lists every MAC address learned on that port, enabling client-to-port-to-switch mapping.
- Connected client (station) data including hostname, IP, MAC, the switch MAC and port index they are connected to (`sw_mac`, `sw_port`), and per-client rx/tx byte counters.
- Site-level health and aggregate throughput statistics (wan-tx_bytes, wan-rx_bytes, num_sta, LAN/WLAN splits).
- Access point radio statistics, VAP tables, and per-radio tx/rx counters.
- Deep Packet Inspection (DPI) category-level traffic breakdowns.
- LLDP neighbour discovery information for topology construction.

This rich data set allows pmdaunifi to provide something no existing PCP PMDA offers: a complete, topology-aware view of a managed network's performance, where every switch port's byte counters, every connected client's traffic, and every uplink/downlink relationship is available as first-class PCP metrics. These can then be logged by pmlogger, graphed in Grafana (via pmproxy), alerted on by pmie, and used to reconstruct full network topology graphs.

---

## 3. Architecture

### 3.1 Deployment Model

pmdaunifi is a daemon PMDA that communicates with PMCD via pipes (the default) or a Unix domain socket. It runs on a PCP collector host that has HTTPS network access to one or more UniFi Controller instances. The PMDA does not need to run on the controller itself — it acts as a remote collector, similar in concept to pmdacisco.

The high-level data flow is:

1. pmdaunifi authenticates to the UniFi Controller(s) using API key headers (`X-API-Key`).
2. On a configurable refresh cycle (default: 30 seconds), per-controller poller threads poll for device, client, and site statistics.
3. Responses are parsed and cached in-memory data structures. Instance domains are updated dynamically as devices and clients appear or disappear.
4. When PMCD forwards a fetch or instance request from a monitoring client, pmdaunifi returns values from its cache with minimal latency.
5. PCP tools (pmlogger, pmrep, pmchart, Grafana via pmproxy) consume the metrics for monitoring, archiving, and visualisation.

### 3.2 Implementation Language and Dependencies

The PMDA is written in Python 3 using the PCP Python bindings (`pcp.pmda` module). Python is chosen because:

- The UniFi API returns JSON, which Python handles natively.
- The PCP Python PMDA framework (as used by pmdabcc, pmdaopenmetrics, pmdagluster, and many others) is mature and well-documented.
- Dynamic instance domain management (devices and clients coming and going) is straightforward with `pmdaCache`.
- The `requests` library provides robust HTTPS client functionality with SSL configuration.

Runtime dependencies: `python3`, `python3-pcp` (PCP Python bindings), `python3-requests`.

### 3.3 Refresh and Caching Strategy

Because the UniFi API involves network round-trips to the controller, pmdaunifi uses an asynchronous caching model. In multi-controller deployments, each controller is polled by a dedicated background thread (see Section 7.2.2 for the full threading design). The key principles are:

- Each controller's poller thread runs independently on its own timer (configurable, default 30 seconds), owns its own authenticated HTTP session, and builds a complete immutable data snapshot on each cycle.
- Each refresh fetches: `stat/device` (all devices with port tables), `stat/sta` (all active clients), and `stat/health` (site-level health). These three API calls are sufficient for the core metric set.
- Completed snapshots are atomically swapped into a shared data store using a copy-on-write model. The main PMCD dispatch thread reads only from completed snapshots, so it never blocks on network I/O and never sees partially-updated data.
- Fetched data is stored in Python dictionaries keyed by device MAC and port index. Counter metrics (byte/packet counts) are exported directly as PCP counters with monotonically increasing semantics — PCP tools handle rate conversion automatically.
- If a refresh fails (network error, HTTP error), the PMDA retains the last successful cache and logs the error. Since API key authentication is stateless (no session to expire), transient failures are typically network-related and resolve on the next cycle.

---

## 4. UniFi API Endpoints Used

The following table lists every UniFi Controller API endpoint that pmdaunifi consumes, the purpose of each, and the refresh frequency. Note that on UniFi OS devices (UDM, UDR, UCG), all paths must be prefixed with `/proxy/network`.

| Endpoint | Method | Purpose | Refresh |
|----------|--------|---------|---------|
| `api/s/{site}/stat/device` | GET | Full device list with port_table, uplink, LLDP, counters | 30s |
| `api/s/{site}/stat/sta` | GET | Active client list with sw_mac, sw_port, rx/tx bytes | 30s |
| `api/s/{site}/stat/health` | GET | Site-level subsystem health (LAN, WLAN, WAN, VPN) | 30s |
| `api/s/{site}/stat/sysinfo` | GET | Controller version and system info | 300s |
| `api/s/{site}/rest/portconf` | GET | Switch port profile definitions | 300s |
| `api/s/{site}/stat/sitedpi` | POST | DPI category traffic breakdown (opt-in) | 300s |
| `api/self/sites` | GET | List of sites managed by the controller | On start |

The **`stat/device`** endpoint is the richest single data source. For each switch, it returns a `port_table` array where each entry contains fields including: `port_idx`, `name`, `up`, `speed`, `full_duplex`, `rx_bytes`, `tx_bytes`, `rx_packets`, `tx_packets`, `rx_errors`, `tx_errors`, `rx_dropped`, `tx_dropped`, `rx_broadcast`, `tx_broadcast`, `rx_multicast`, `tx_multicast`, `poe_enable`, `poe_power`, `poe_voltage`, `poe_current`, `poe_class`, `is_uplink`, and a `mac_table` sub-array with every learned MAC on that port.

The **`stat/sta`** endpoint returns per-client data including: `mac`, `hostname`, `ip`, `oui` (vendor prefix), `is_wired`, `sw_mac` (switch the client is connected to), `sw_port` (port index on that switch), `rx_bytes`, `tx_bytes`, `rx_packets`, `tx_packets`, `signal` (for wireless), and `uptime`.

---

## 5. Performance Metrics Name Space (PMNS)

All metrics are rooted under the **`unifi`** subtree. The namespace is organised into clusters reflecting the hierarchy of UniFi concepts: site, device, switch port, client, access point, gateway, and topology.

### 5.1 Cluster Allocation

| Cluster | PMNS Prefix | Description |
|---------|-------------|-------------|
| 0 | `unifi.site.*` | Site-level aggregate metrics and health |
| 1 | `unifi.device.*` | Per-device metrics (all device types) |
| 2 | `unifi.switch.port.*` | Per-switch-port traffic counters and state |
| 3 | `unifi.switch.port.poe.*` | Per-switch-port PoE telemetry |
| 4 | `unifi.client.*` | Per-connected-client metrics |
| 5 | `unifi.ap.*` | Per-access-point radio and VAP metrics |
| 6 | `unifi.gateway.*` | Gateway/router WAN and routing metrics |
| 7 | `unifi.topology.*` | Topology adjacency and uplink mapping |
| 8 | `unifi.dpi.*` | Deep Packet Inspection category metrics |
| 9 | `unifi.controller.*` | Controller health and PMDA operational metrics |

### 5.2 Instance Domains

Instance domains define the set of instances over which metrics in a given cluster are enumerated. pmdaunifi uses dynamic instance domains managed via `pmdaCache`, so instances appear and disappear as devices and clients join or leave the network.

All instance external names are prefixed with the site name to guarantee global uniqueness across multi-controller deployments (see Section 7.2). For single-site installations, this prefix is still present but is simply "default/". The separator between the site prefix and the rest of the instance name is a forward slash.

| Indom ID | Name | Instance Format | Example |
|----------|------|-----------------|---------|
| 0 | site | `site_name` | `default` |
| 1 | device | `site/device_name (MAC)` | `default/USW-Pro-48 (fc:ec:da:01:02:03)` |
| 2 | switch_port | `site/device_name::PortN` | `default/USW-Pro-48::Port1` |
| 3 | client | `site/hostname (MAC)` | `default/workstation1 (aa:bb:cc:dd:ee:ff)` |
| 4 | ap_radio | `site/ap_name::radioN` | `default/U6-LR-Lounge::radio0` |
| 5 | topology_link | `site/src::portN->dst` | `default/USW-Pro-48::Port24->USW-Lite-8` |

The **switch_port** instance domain is the central instance domain for the PMDA's core use case. Each instance represents one physical port on one switch. The instance name encodes the site, device identity, and port number, allowing PCP tools to filter, aggregate, and graph at the port level. The instance external name format (`site/device_name::PortN`) is designed to be human-readable while remaining unique across multi-site, multi-switch deployments. PCP metric labels (see Section 7.2.5) provide a structured alternative to parsing instance name strings.

### 5.3 Core Metric Definitions

#### 5.3.1 Site Metrics (Cluster 0)

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.site.status` | STRING | instant | | Site health status (ok, warn, error) |
| `unifi.site.num_sta` | U32 | instant | count | Total connected stations |
| `unifi.site.num_user` | U32 | instant | count | User (non-guest) stations |
| `unifi.site.num_guest` | U32 | instant | count | Guest stations |
| `unifi.site.num_ap` | U32 | instant | count | Adopted access points |
| `unifi.site.num_sw` | U32 | instant | count | Adopted switches |
| `unifi.site.num_gw` | U32 | instant | count | Adopted gateways |
| `unifi.site.wan.tx_bytes` | U64 | counter | byte | WAN transmit bytes |
| `unifi.site.wan.rx_bytes` | U64 | counter | byte | WAN receive bytes |
| `unifi.site.lan.tx_bytes` | U64 | counter | byte | LAN transmit bytes |
| `unifi.site.lan.rx_bytes` | U64 | counter | byte | LAN receive bytes |
| `unifi.site.wlan.tx_bytes` | U64 | counter | byte | WLAN transmit bytes |
| `unifi.site.wlan.rx_bytes` | U64 | counter | byte | WLAN receive bytes |

#### 5.3.2 Device Metrics (Cluster 1)

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.device.name` | STRING | discrete | | Device display name |
| `unifi.device.mac` | STRING | discrete | | Device MAC address |
| `unifi.device.ip` | STRING | instant | | Device management IP |
| `unifi.device.model` | STRING | discrete | | Hardware model identifier |
| `unifi.device.type` | STRING | discrete | | Device type (usw, uap, ugw) |
| `unifi.device.version` | STRING | instant | | Firmware version string |
| `unifi.device.uptime` | U64 | instant | sec | Device uptime in seconds |
| `unifi.device.state` | U32 | instant | | State code (1=connected, etc.) |
| `unifi.device.adopted` | U32 | discrete | | Boolean: 1 if adopted |
| `unifi.device.rx_bytes` | U64 | counter | byte | Total device receive bytes |
| `unifi.device.tx_bytes` | U64 | counter | byte | Total device transmit bytes |
| `unifi.device.temperature` | FLOAT | instant | °C | General temperature (if avail) |
| `unifi.device.user_num_sta` | U32 | instant | count | Connected user stations |
| `unifi.device.guest_num_sta` | U32 | instant | count | Connected guest stations |
| `unifi.device.num_ports` | U32 | discrete | count | Total port count (switches) |

#### 5.3.3 Switch Port Metrics (Cluster 2) — Primary Metric Set

These are the core metrics that drive the per-port traffic monitoring and topology use case. All byte and packet counters are monotonically increasing counters; PCP tools automatically compute rates.

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.switch.port.up` | U32 | instant | | Boolean: 1 if port link is up |
| `unifi.switch.port.speed` | U32 | instant | Mbit/s | Negotiated link speed |
| `unifi.switch.port.full_duplex` | U32 | instant | | Boolean: 1 if full duplex |
| `unifi.switch.port.is_uplink` | U32 | instant | | Boolean: 1 if port is uplink |
| `unifi.switch.port.rx_bytes` | U64 | counter | byte | Received bytes counter |
| `unifi.switch.port.tx_bytes` | U64 | counter | byte | Transmitted bytes counter |
| `unifi.switch.port.rx_packets` | U64 | counter | count | Received packets counter |
| `unifi.switch.port.tx_packets` | U64 | counter | count | Transmitted packets counter |
| `unifi.switch.port.rx_errors` | U64 | counter | count | Receive error counter |
| `unifi.switch.port.tx_errors` | U64 | counter | count | Transmit error counter |
| `unifi.switch.port.rx_dropped` | U64 | counter | count | Receive drop counter |
| `unifi.switch.port.tx_dropped` | U64 | counter | count | Transmit drop counter |
| `unifi.switch.port.rx_broadcast` | U64 | counter | count | Receive broadcast counter |
| `unifi.switch.port.tx_broadcast` | U64 | counter | count | Transmit broadcast counter |
| `unifi.switch.port.rx_multicast` | U64 | counter | count | Receive multicast counter |
| `unifi.switch.port.tx_multicast` | U64 | counter | count | Transmit multicast counter |
| `unifi.switch.port.mac_count` | U32 | instant | count | Number of MACs on this port |

#### 5.3.4 Switch Port PoE Metrics (Cluster 3)

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.switch.port.poe.enabled` | U32 | instant | | Boolean: 1 if PoE enabled |
| `unifi.switch.port.poe.good` | U32 | instant | | Boolean: 1 if PoE delivering power |
| `unifi.switch.port.poe.power` | FLOAT | instant | W | PoE power draw in watts |
| `unifi.switch.port.poe.voltage` | FLOAT | instant | V | PoE voltage |
| `unifi.switch.port.poe.current` | FLOAT | instant | mA | PoE current draw |
| `unifi.switch.port.poe.class` | STRING | instant | | PoE class (Class 0–4) |

#### 5.3.5 Client Metrics (Cluster 4)

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.client.hostname` | STRING | instant | | Client hostname |
| `unifi.client.ip` | STRING | instant | | Client IP address |
| `unifi.client.mac` | STRING | discrete | | Client MAC address |
| `unifi.client.oui` | STRING | discrete | | OUI vendor string |
| `unifi.client.is_wired` | U32 | instant | | Boolean: 1 if wired client |
| `unifi.client.sw_mac` | STRING | instant | | Switch MAC this client is on |
| `unifi.client.sw_port` | U32 | instant | | Switch port index |
| `unifi.client.rx_bytes` | U64 | counter | byte | Client receive bytes |
| `unifi.client.tx_bytes` | U64 | counter | byte | Client transmit bytes |
| `unifi.client.rx_packets` | U64 | counter | count | Client receive packets |
| `unifi.client.tx_packets` | U64 | counter | count | Client transmit packets |
| `unifi.client.uptime` | U64 | instant | sec | Client connection uptime |
| `unifi.client.signal` | S32 | instant | dBm | Wireless signal strength |
| `unifi.client.network` | STRING | instant | | Network/VLAN name |

#### 5.3.6 Access Point Metrics (Cluster 5)

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.ap.channel` | U32 | instant | | Radio channel number |
| `unifi.ap.radio_type` | STRING | discrete | | Radio type (ng, na, ax, be) |
| `unifi.ap.tx_bytes` | U64 | counter | byte | Radio transmit bytes |
| `unifi.ap.rx_bytes` | U64 | counter | byte | Radio receive bytes |
| `unifi.ap.tx_packets` | U64 | counter | count | Radio transmit packets |
| `unifi.ap.rx_packets` | U64 | counter | count | Radio receive packets |
| `unifi.ap.tx_dropped` | U64 | counter | count | Radio transmit drops |
| `unifi.ap.tx_retries` | U64 | counter | count | Radio transmit retries |
| `unifi.ap.num_sta` | U32 | instant | count | Stations on this radio |
| `unifi.ap.satisfaction` | U32 | instant | % | Client satisfaction score |

#### 5.3.7 Topology Metrics (Cluster 7)

Topology metrics encode the physical and logical adjacency relationships between UniFi devices. These are derived from `uplink_table` and LLDP data in the `stat/device` response.

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.topology.src_device` | STRING | discrete | | Source device name |
| `unifi.topology.src_port` | U32 | discrete | | Source port index |
| `unifi.topology.dst_device` | STRING | discrete | | Destination device name |
| `unifi.topology.dst_port` | U32 | discrete | | Destination port index |
| `unifi.topology.link_speed` | U32 | instant | Mbit/s | Negotiated speed of the link |
| `unifi.topology.rx_bytes` | U64 | counter | byte | Bytes on this link (src rx) |
| `unifi.topology.tx_bytes` | U64 | counter | byte | Bytes on this link (src tx) |
| `unifi.topology.link_type` | STRING | discrete | | uplink, downlink, inter-switch, or cross-site |

#### 5.3.8 Controller and PMDA Health Metrics (Cluster 9)

These metrics monitor the health of the PMDA itself and its connectivity to the UniFi controller(s). They are essential for operational alerting — if the PMDA cannot reach a controller, you want to know before you notice missing data in Grafana.

| Metric Name | Type | Sem | Units | Description |
|-------------|------|-----|-------|-------------|
| `unifi.controller.up` | U32 | instant | | Boolean: 1 if last poll succeeded |
| `unifi.controller.last_poll_duration` | DOUBLE | instant | ms | Duration of last poll cycle |
| `unifi.controller.last_poll_timestamp` | U64 | instant | sec | Unix timestamp of last successful poll |
| `unifi.controller.poll_errors` | U64 | counter | count | Cumulative poll failure counter |
| `unifi.controller.version` | STRING | discrete | | Controller software version |
| `unifi.controller.devices_discovered` | U32 | instant | count | Number of devices found last poll |
| `unifi.controller.clients_discovered` | U32 | instant | count | Number of clients found last poll |
| `unifi.controller.sites_polled` | U32 | instant | count | Number of sites being polled |

### 5.4 Dynamic Instance Domain Behaviour

pmdaunifi discovers devices and clients dynamically on every poll cycle. When the UniFi controller reports a new device (e.g. a newly adopted switch), the PMDA adds instances to the relevant instance domains automatically — no restart or reconfiguration is required. Conversely, when a device disappears from the controller's response (e.g. it is decommissioned or loses connectivity), its instances are pruned from the instance domains after a configurable grace period (default: 5 minutes, to avoid flapping during brief disconnections).

This means PCP tools see instance domains that grow and shrink in real time. `pmlogger` archives capture these changes transparently — replaying an archive shows the devices that were present at each point in time. `pmie` rules fire only for instances that exist at the time of evaluation.

For clients specifically, the high churn rate (clients connecting and disconnecting frequently) means the client instance domain can change significantly between poll cycles. The `max_clients` configuration option provides a cardinality cap: if a poll returns more clients than the limit, only the top N by traffic volume are retained as instances. This protects the PMDA, PMCD, and downstream consumers from cardinality explosion in large venues (shopping centres, hotels, conference facilities).

---

## 6. Topology Discovery and Graph Construction

One of the defining features of pmdaunifi is its ability to expose network topology as structured PCP metrics, enabling external tools to reconstruct and visualise the physical network graph.

### 6.1 Data Sources for Topology

Topology is inferred from three complementary data sources within the `stat/device` API response:

1. **Uplink Table:** Each device reports its uplink connection, including the uplink MAC, port index, speed, and type. This establishes the primary tree structure of the network.
2. **LLDP Information:** UniFi devices exchange LLDP (Link Layer Discovery Protocol) frames. The `lldp_table` on each device reports the remote chassis ID and port ID of its neighbours, providing bidirectional link verification.
3. **Port mac_table:** When a port's `mac_table` contains the MAC address of another UniFi device, this confirms a device-to-device link on that specific port. Combined with the client `sw_mac`/`sw_port` fields, this completes the picture.

### 6.2 Graph Construction Algorithm

On each refresh cycle, the PMDA constructs an adjacency list:

1. Build a MAC-to-device lookup table from all devices in `stat/device`.
2. For each device, examine its uplink: if the uplink MAC matches a known device, record a link (`this_device:uplink_port -> parent_device:parent_port`).
3. Cross-reference LLDP tables for bidirectional confirmation and to discover links not captured by the uplink model (e.g. inter-switch LAGs, ring topologies).
4. For each switch port, classify what's connected: another UniFi device (device link), one or more non-UniFi clients (leaf port), or nothing (empty port).
5. Export each discovered device-to-device link as an instance in the `topology_link` instance domain with associated counters.

### 6.3 Using Topology Data

External tools can consume the topology metrics to build visualisations:

- Use `pmrep` or `pminfo` to enumerate all `unifi.topology.*` instances to get the link list.
- Combine with `unifi.device.*` for node attributes (model, IP, type) and `unifi.topology.*` for edge attributes (speed, traffic).
- Attach `unifi.client.sw_mac` and `unifi.client.sw_port` to place leaf clients on the correct switch port in the graph.
- Overlay `unifi.switch.port.rx_bytes` and `tx_bytes` rates onto edges for real-time traffic heatmaps.
- A companion script (`unifi2dot` or `unifi2json`) can query PCP and output Graphviz DOT or JSON suitable for D3.js/Cytoscape.js visualisation.

---

## 7. Configuration

### 7.1 Authentication: API Key Only

pmdaunifi exclusively uses the **official UniFi API key** authentication mechanism. This is a deliberate simplification — the classic session-based API (username/password with cookie jar management) is not supported.

**Rationale for dropping classic API support:**

- **Simplicity:** API key auth is a single `X-API-Key` HTTP header on every request. No login endpoint, no cookie jar, no session expiry detection, no re-authentication retry logic, no MFA complications. This eliminates an entire class of failure modes and roughly halves the authentication code.
- **Statelessness:** API key requests are stateless. There is no session to expire mid-polling-cycle, no risk of PMCD fetch requests being delayed by a re-login round-trip.
- **Security:** API keys are inherently read-only (as of current firmware), which is exactly what a monitoring PMDA needs. Username/password auth could inadvertently grant write access if the account role is misconfigured. API keys also avoid the risk of credential lockout from too many failed login attempts.
- **MFA immunity:** Since July 2024, Ubiquiti mandates MFA on cloud (UI.com) accounts. This breaks automated session logins entirely. Local admin accounts can work around this, but API keys sidestep the issue completely.

**Minimum version requirement:** UniFi Network Application **9.0+** (released late 2024). API key generation is available at `Settings > Control Plane > Integrations`. All current UniFi OS devices (UDM, UDM Pro, UDM SE, UDR, UCG-Ultra, UCG-Max, CK Gen2+) support this. Self-hosted Network Application 9.x on Linux also supports it.

**Users on older firmware (7.x, 8.x)** should upgrade before deploying pmdaunifi. These versions are approaching end-of-life from Ubiquiti and lack many of the API improvements that pmdaunifi depends on.

A single API key provides access to **all sites** on a controller — there are no per-site API keys. The PMDA uses a `sites` directive in the configuration to control which sites are polled (see Section 7.2).

### 7.2 Configuration File

The PMDA reads its configuration from `$PCP_PMDAS_DIR/unifi/unifi.conf` (or a path specified by the `-c` command line option). The file uses INI-style syntax:

```ini
[controller]
url = https://192.168.1.1
api_key = your-api-key-here

# UniFi OS device (UDM, UDR, UCG)? Adds /proxy/network prefix.
is_udm = true

# SSL verification (recommended true in production)
verify_ssl = false
# ca_cert = /etc/pki/tls/certs/unifi-ca.pem

# Which sites to poll. Options:
#   sites = all              (discover and poll every site — the default)
#   sites = default          (just the default site)
#   sites = default, branch  (explicit comma-separated list)
sites = all

[refresh]
interval = 30
topology_interval = 60

[options]
# Enable per-client metrics (can be high cardinality)
clients = true
# Enable DPI metrics
dpi = false
# Enable AP radio metrics
access_points = true
# Maximum number of clients to track (safety valve)
max_clients = 500
```

The `sites` directive is the mechanism for controlling scope. Setting `sites = all` causes the PMDA to call `api/self/sites` on startup, discover every site on the controller, and poll them all. Setting an explicit list lets the administrator choose exactly which sites to monitor — useful for large MSP controllers where you only care about specific customer sites, or for reducing API load.

### 7.3 Multi-Controller and Multi-Site Architecture

A single pmdaunifi process handles all controllers and sites. There is no need (and it would be counterproductive) to run separate PMDA instances per site. A single PMDA means a single PMNS, a single domain number, and — critically — unified instance domains that allow PCP tools to query, compare, and aggregate metrics across all sites in a single expression.

#### 7.3.1 Design Decision: One PMDA, Multiple Sites

The alternative of running one PMDA per controller was rejected for several reasons:

- Each PMDA requires a unique domain number and a separate PMNS subtree. Running N PMDAs would fragment the metric namespace (`unifi_sitea.switch.port.rx_bytes` vs `unifi_siteb.switch.port.rx_bytes`) and make cross-site queries impossible with standard PCP tools.
- Each PMDA is a separate process managed by PMCD. Administrative overhead scales linearly with sites.
- Cross-site topology (Section 7.3.4) would be impossible if each site's devices lived in an isolated PMDA with no visibility of the others.
- The pmie alerting engine and pmlogger can address all sites in a single rule or config stanza when they share a namespace, e.g. `some_inst (rate(unifi.switch.port.rx_errors) > 100)` fires across all sites.

#### 7.3.2 Polling Architecture: Per-Controller Threads

Each `[controller]` (or `[controller:NAME]`) section in the configuration file spawns a dedicated poller thread. Within a controller, each selected site is polled sequentially by that controller's thread (since they share one authenticated session). The threading model is:

1. **Main thread:** Communicates with PMCD via the `pcp.pmda` dispatch loop. Handles all fetch, instance, text, and label callbacks. Reads from a shared, thread-safe data store (copy-on-write snapshot model). This thread never blocks on network I/O.

2. **Poller threads (one per controller):** Each thread makes stateless HTTP requests with the `X-API-Key` header. On each cycle, it iterates over its configured sites, calls `stat/device`, `stat/sta`, and `stat/health` for each site, parses the JSON responses, builds a local data snapshot, and then atomically swaps it into the shared data store. If a request fails, the thread logs the error; the main thread continues serving the last successful snapshot.

3. **Refresh independence:** Each poller thread runs on its own timer. A large campus controller with 200 devices may take 2–3 seconds to respond to `stat/device`, while a small branch controller with 5 devices responds in 100ms. Threaded polling eliminates this dependency and ensures each controller's data is as fresh as possible.

4. **Thread safety:** Each poller thread builds a complete immutable dict for its controller's sites, then atomically replaces the reference in the shared store. The main thread always reads a consistent snapshot — it never sees a partially-updated site. This avoids fine-grained locking and eliminates the risk of deadlocks between the PMCD dispatch loop and the pollers.

#### 7.3.3 Instance Naming and Site Qualification

Every instance external name is prefixed with the site identifier. For single-controller setups, this is the UniFi site name (typically "default"). For multi-controller setups with explicit `[controller:NAME]` sections, the NAME overrides the site name prefix to avoid collisions when two controllers both have a site called "default".

Examples across a multi-site deployment:

```
hq/USW-Pro-48::Port1          # HQ campus core switch, port 1
hq/USW-Pro-48::Port24         # HQ campus core switch, uplink port
branch-mel/USW-Lite-8::Port1  # Melbourne branch switch, port 1
branch-syd/USW-Lite-16::Port5 # Sydney branch switch, port 5
```

PCP instance filtering works naturally:

```bash
# Show all ports across all sites:
$ pmrep -i '.*' unifi.switch.port.rx_bytes

# Show only HQ ports:
$ pmrep -i 'hq/.*' unifi.switch.port.rx_bytes

# Show a specific port on a specific site:
$ pmval -i 'branch-mel/USW-Lite-8::Port1' unifi.switch.port.rx_bytes
```

#### 7.3.4 Cross-Site Topology

Within a single site, topology discovery is fully automatic (Section 6). Across sites, each controller only knows about its own adopted devices — there is no protocol for automatic cross-site link discovery.

**Current scope:** Cross-site topology is **deferred to future work** (see Section 15). The intra-site topology within each controller/site is fully supported from Phase 2. Cross-site link declaration may be added in a future version if there is demand, but the design complexity (polling phase alignment, bidirectional counter correlation, configuration fragility when re-cabling occurs) suggests it warrants its own design spike and will be tracked as a separate GitHub issue.

#### 7.3.5 Metric Labels for Multi-Site Queries

pmdaunifi attaches the following labels to every instance using the PCP label (`pmdaLabel`) interface:

| Label Key | Scope | Example Value | Purpose |
|-----------|-------|---------------|---------|
| `site_name` | All instances | `hq` | Filter/group by site in Grafana, pmrep |
| `device_mac` | Device, port, AP | `fc:ec:da:01:02:03` | Stable device identifier |
| `device_type` | Device, port, AP | `usw` | Filter by device class |
| `device_model` | Device, port, AP | `USW-Pro-48` | Filter by hardware model |
| `port_idx` | Switch port | `1` | Numeric port index |
| `controller_url` | All instances | `https://10.0.0.1` | Trace metric to source controller |

Labels allow Grafana to build dashboards with site-selector variables without parsing instance name strings. A Grafana variable defined as `label_values(unifi.switch.port.rx_bytes, site_name)` produces a dropdown of all monitored sites.

Labels are emitted from Phase 1 (MVP) for all deployments. Single-site installations get `site_name = "default"` so that dashboards written for multi-site work identically without modification.

#### 7.3.6 Configuration Example: Multi-Controller Deployment

```ini
[controller:hq]
url = https://10.0.0.1
api_key = ak_hq_xxxxxxxxxxxx
is_udm = true
sites = all

[controller:branches]
url = https://10.1.0.1
api_key = ak_branches_xxxxxxxxxxxx
is_udm = true
sites = melbourne, sydney

[refresh]
interval = 30
```

This configuration spawns two poller threads. Each authenticates with its own API key. The HQ controller polls all its sites; the branches controller polls only Melbourne and Sydney (ignoring any others).

### 7.4 Command-Line Options

| Flag | Description | Default |
|------|-------------|---------|
| `-d domain` | PMDA domain number | From `domain.h` |
| `-l logfile` | Log file path | `$PCP_LOG_DIR/pmcd/unifi.log` |
| `-c configfile` | Configuration file path | `$PCP_PMDAS_DIR/unifi/unifi.conf` |
| `-U username` | Run as this user | `pcp` |
| `-r refresh` | Override refresh interval (seconds) | `30` |

### 7.5 Security Considerations

The configuration file contains the API key and should be owned by `root:pcp` with mode `0640`. The PMDA process runs as the unprivileged "pcp" user. UniFi API keys are inherently read-only, so even if the key were compromised, it could not be used to modify the network configuration.

SSL certificate verification should be enabled in production (`verify_ssl = true`) with the controller's CA certificate installed in the system trust store, or specified via a `ca_cert` configuration option. Self-signed certificates are common in UniFi deployments, so the option to disable verification is provided but discouraged.

---

## 8. Packaging, Installation, and Updates

### 8.1 Distribution Strategy

pmdaunifi should be distributed through **two complementary channels**:

1. **PyPI (`pip install pcp-pmda-unifi`):** This is the primary distribution mechanism. It provides the simplest installation path, automatic dependency resolution, version management, and a familiar workflow for Python-literate administrators. The package includes the PMDA Python code, help text source, PMNS template, domain.h template, and the Install/Remove scripts. It does *not* include PCP itself — that is a system dependency.

2. **OS package repositories (RPM/DEB):** For environments that prefer system packages, the project should provide RPM spec files and Debian packaging. These would be submitted to COPR (Fedora), PPA (Ubuntu), or eventually to PCP upstream for inclusion in the main `pcp-pmda-unifi` package. The OS package simply wraps the same Python code with proper file placement and declares dependencies on `pcp` and `python3-requests`.

The PyPI package is the development-velocity channel (release early, release often). The OS packages are the stability channel (lag behind, tested with specific OS/PCP version combinations).

### 8.2 Python Package Structure

```
pcp-pmda-unifi/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── pmdaunifi/
│       ├── __init__.py          # Version, metadata
│       ├── pmda.py              # Main PMDA implementation
│       ├── collector.py         # Per-controller poller thread logic
│       ├── unifi_client.py      # UniFi API client (API key auth, fetch, parse)
│       ├── topology.py          # Topology graph construction
│       ├── config.py            # Configuration file parser
│       └── metrics.py           # Metric definitions, PMNS, help text
├── scripts/
│   ├── Install                  # PCP Install script
│   ├── Remove                   # PCP Remove script
│   └── unifi2dot                # Topology export companion
├── templates/
│   ├── domain.h.in
│   ├── pmns.in
│   └── unifi.conf.example
└── tests/
    ├── test_collector.py
    ├── test_topology.py
    ├── fixtures/                 # Recorded API responses for testing
    │   ├── stat_device.json
    │   ├── stat_sta.json
    │   └── stat_health.json
    └── conftest.py
```

### 8.3 The Install Script: Interactive Setup

The `./Install` script (invoked after `pip install` or from the OS package) should provide an interactive, guided setup experience. The goal is that an administrator who has already created an API key on their UniFi Console can go from zero to working metrics in under two minutes.

#### 8.3.1 Install Flow

```
# cd $PCP_PMDAS_DIR/unifi
# ./Install

=== pmdaunifi Installation ===

Controller URL [https://192.168.1.1]: https://10.0.0.1
Is this a UniFi OS device (UDM/UDR/UCG)? [Y/n]: Y

API Key (generate at Settings > Control Plane > Integrations):
  ak_xxxxxxxxxxxxxxxxxxxxxxxx

Testing connectivity to https://10.0.0.1 ...
✓ Connected. Controller version: 9.0.114
✓ Authentication successful.

Discovering sites...
  Found 3 sites:
    [1] default     — "Main Office" (24 devices)
    [2] warehouse   — "Warehouse"   (6 devices)
    [3] guest       — "Guest Network" (2 devices)

Which sites to monitor?
  a. All sites
  b. Select specific sites
Choice [a]: b
Enter site numbers (comma-separated): 1, 2

Configuration summary:
  Controller: https://10.0.0.1 (UniFi OS)
  Auth: API Key
  Sites: default, warehouse
  Refresh: 30s

Write configuration and install? [Y/n]: Y

Writing /var/lib/pcp/pmdas/unifi/unifi.conf (mode 0640) ...
Updating the Performance Metrics Name Space (PMNS) ...
Updating the PMCD control file, and notifying PMCD ...
Check unifi metrics have appeared ... 47 metrics and 312 values

Installation complete. Verify with:
  $ pminfo -f unifi.site.num_sta
  $ pmrep -t 5 unifi.switch.port.rx_bytes unifi.switch.port.tx_bytes
```

#### 8.3.2 Non-Interactive Install

For automation (Ansible, Puppet, etc.), the Install script accepts arguments or environment variables:

```bash
# Non-interactive install with all parameters:
UNIFI_URL=https://10.0.0.1 \
UNIFI_API_KEY=ak_xxxxx \
UNIFI_IS_UDM=true \
UNIFI_SITES=all \
./Install -e
```

#### 8.3.3 What Install Does Under the Hood

1. Validates input (URL reachable, credentials work, sites exist).
2. Writes `unifi.conf` with correct ownership and permissions (`root:pcp`, `0640`).
3. Generates `domain.h` with the assigned domain number.
4. Generates the PMNS file from the metric definitions.
5. Compiles help text with `newhelp`.
6. Registers the PMDA with PMCD (updates `$PCP_PMCDCONF_PATH`).
7. Sends SIGHUP to PMCD to pick up the new PMDA.
8. Runs a smoke test (`pminfo -f unifi.site.num_sta`) to verify end-to-end.

### 8.4 Updates

#### 8.4.1 PyPI Updates

```bash
pip install --upgrade pcp-pmda-unifi
cd $PCP_PMDAS_DIR/unifi
./Install -u   # Upgrade mode: preserves existing unifi.conf, updates code/PMNS/help
```

The `-u` (upgrade) flag skips the interactive setup and simply re-registers the PMDA with updated metric definitions. The existing configuration file is preserved. If the new version adds metrics, the PMNS is expanded; existing pmlogger archives remain readable (new metrics simply have no historical data).

#### 8.4.2 OS Package Updates

```bash
# RPM
dnf upgrade pcp-pmda-unifi

# DEB
apt upgrade pcp-pmda-unifi
```

OS package post-install scripts call `./Install -u` automatically.

#### 8.4.3 Version Compatibility

The PMDA should maintain backward compatibility with its configuration file format. New configuration options are always optional with sensible defaults. If a future version deprecates an option, it is ignored with a logged warning rather than causing a failure.

### 8.5 Uninstallation

```bash
cd $PCP_PMDAS_DIR/unifi
./Remove
# Optionally:
pip uninstall pcp-pmda-unifi
```

The Remove script deregisters the PMDA from PMCD and removes the PMNS entries. It does **not** delete `unifi.conf` (which contains credentials the administrator entered) — this must be removed manually. This is consistent with how other PCP PMDAs handle removal.

---

## 9. File and Directory Layout

| Path | Description |
|------|-------------|
| `$PCP_PMDAS_DIR/unifi/` | PMDA installation directory |
| `$PCP_PMDAS_DIR/unifi/pmdaunifi.python` | Main PMDA entry point (or symlink to installed package) |
| `$PCP_PMDAS_DIR/unifi/unifi.conf` | Configuration file (mode 0640, `root:pcp`) |
| `$PCP_PMDAS_DIR/unifi/domain.h` | Domain number definition (`#define UNIFI N`) |
| `$PCP_PMDAS_DIR/unifi/pmns` | PMNS namespace definition file |
| `$PCP_PMDAS_DIR/unifi/root` | Root PMNS for the PMDA |
| `$PCP_PMDAS_DIR/unifi/help` | Help text source file for `newhelp` |
| `$PCP_PMDAS_DIR/unifi/Install` | Installation script |
| `$PCP_PMDAS_DIR/unifi/Remove` | Removal script |
| `$PCP_LOG_DIR/pmcd/unifi.log` | Runtime log file |

---

## 10. Example Usage Scenarios

### 10.1 Real-Time Port Monitoring

Display per-port byte rates across all switches, updating every 5 seconds:

```bash
$ pmrep -p -t 5 unifi.switch.port.rx_bytes unifi.switch.port.tx_bytes
```

### 10.2 Historical Archiving

Configure pmlogger to archive UniFi metrics for capacity planning:

```
# /etc/pcp/pmlogger/config.d/unifi.config
log mandatory on 30sec {
    unifi.switch.port.rx_bytes
    unifi.switch.port.tx_bytes
    unifi.switch.port.rx_errors
    unifi.switch.port.tx_errors
    unifi.device.uptime
    unifi.site.num_sta
    unifi.client.rx_bytes
    unifi.client.tx_bytes
}
```

### 10.3 Error Rate Alerting with pmie

Alert when any switch port error rate exceeds 100 errors/second:

```
some_inst (
    rate(unifi.switch.port.rx_errors) > 100 ||
    rate(unifi.switch.port.tx_errors) > 100
) -> syslog "High error rate on " "%i";
```

### 10.4 Grafana Dashboard via pmproxy

With pmproxy running, Grafana can query live and archived UniFi metrics using the PCP plugin. Dashboard panels might include: a topology map with per-link bandwidth colouring, per-switch stacked port utilisation charts, top-N clients by traffic, PoE power budget utilisation, and wireless client counts over time.

### 10.5 Topology Export

A companion script exports the current topology as a Graphviz DOT file:

```bash
$ unifi2dot | dot -Tsvg -o topology.svg
```

This script uses PMAPI to query all `unifi.topology.*` and `unifi.device.*` instances and generates a directed graph where nodes are devices and edges are links annotated with speed and current throughput.

---

## 11. Excluded UniFi Metrics and Design Rationale

The UniFi Controller API exposes a number of fields and computed values that pmdaunifi deliberately does not export as PCP metrics. This section documents each category of excluded data and the reasoning behind the exclusion.

### 11.1 Controller Pre-Computed Rate Fields

The UniFi API returns pre-computed rate-of-change values alongside raw counters. For example, every device object includes `tx_bytes-r` and `rx_bytes-r` (bytes per second), and every switch port includes a `bytes-r` field.

**Why excluded:** PCP's fundamental design principle is that raw counters are exported with `PM_SEM_COUNTER` semantics, and PCP monitoring tools (`pmrep`, `pmval`, `pmie`, `pmchart`, Grafana) compute rates themselves using the precise time delta between consecutive fetches. This approach is superior for several reasons:

- **Precision:** PCP knows the exact timestamps of its own fetch operations. The controller's rate is computed over an internal window whose length and alignment are opaque.
- **Consistency:** Every other PCP PMDA that exports network byte counters (pmdalinux, pmdacisco, pmdainfiniband) exports raw counters. Mixing in pre-computed rates creates inconsistency.
- **Redundancy:** The pre-computed rates carry no additional information beyond what is derivable from the raw counters.
- **Precision at scale:** The raw U64 counters are exact integers regardless of magnitude. Even a 400 GbE link at line rate is only ~50 GB/s, well within double precision — but the counters remain lossless whereas any floating point representation introduces rounding.

**Excluded fields:** `tx_bytes-r`, `rx_bytes-r`, `bytes-r` (on devices, ports, and site health subsystems).

### 11.2 Controller-Internal Identifiers

Every UniFi object carries an internal `_id` field — a 24-character hex string used by the controller's MongoDB backend. Devices also carry `device_id`, `hash_id`, `anon_id`, and similar identifiers.

**Why excluded:** These are opaque implementation details with no performance monitoring value. The PMDA uses the MAC address as the canonical device identifier.

### 11.3 Configuration and Provisioning State

The `stat/device` response includes extensive configuration data: `port_overrides`, `config_network`, `led_override`, `mgmt_network_id`, and dozens of other settings.

**Why excluded:** PCP is a performance monitoring framework. Configuration state is largely static and is better accessed through the controller UI or a configuration management tool. The exception is configuration that directly affects performance interpretation — port speed and PoE state are exported because they are operationally relevant.

### 11.4 Historical and Aggregated Report Data

The controller maintains historical statistics via `stat/report` endpoints (5-minute, hourly, and daily roll-ups).

**Why excluded:** PCP has its own archiving infrastructure (pmlogger). Importing the controller's historical aggregates would create a parallel, redundant time-series store with different granularity and semantics.

### 11.5 Guest Portal and Hotspot Data

Guest portal authorisations, hotspot vouchers, and payment transactions.

**Why excluded:** This relates to authentication and billing rather than network performance.

### 11.6 Rogue AP and RF Scan Data

The `stat/rogueap` and `stat/spectrumscan` endpoints.

**Why excluded:** Survey data with unpredictable cardinality, better consumed through RF planning tools.

### 11.7 Alarm and Event Data

Controller alarm and event logs (`rest/alarm`, `stat/event`).

**Why excluded:** pmie can generate alerts from threshold violations on the exported counters. The controller's events are better consumed via its WebSocket interface or syslog.

### 11.8 Per-Client DPI Breakdown

The `stat/stadpi` endpoint provides per-client DPI statistics by application category.

**Why excluded from default:** Creates a two-dimensional instance domain (client × DPI category) that can produce extremely high cardinality. 500 clients × 25 categories = 12,500 metric instances per refresh cycle. Site-level DPI (cluster 8) is retained as opt-in.

### 11.9 Summary Table

| Excluded Data | API Source | Reason |
|---------------|-----------|--------|
| Pre-computed rates (`tx/rx_bytes-r`) | `stat/device`, `stat/sta` | Redundant; PCP computes rates from raw U64 counters with better precision |
| Internal IDs (`_id`, `device_id`, etc.) | All endpoints | Opaque; no performance monitoring value |
| Configuration state | `stat/device`, `rest/setting` | Static config, not performance data |
| Historical roll-ups | `stat/report/*` | Redundant with pmlogger archives |
| Guest portal / hotspot | `guest/*`, `stat/voucher` | Billing/auth, not network performance |
| Rogue AP / RF scan | `stat/rogueap`, `spectrumscan` | Survey data; unpredictable cardinality |
| Alarms and events | `rest/alarm`, `stat/event` | Event-driven; better via syslog/WebSocket |
| Per-client DPI | `stat/stadpi` | Cardinality explosion (clients × categories) |

---

## 12. Comparison with pmdacisco

| Capability | pmdacisco | pmdaunifi |
|-----------|-----------|-----------|
| Data source | Telnet CLI (`show interface`) | REST/JSON API (`stat/device`, `stat/sta`) |
| Authentication | Password (telnet) | API key (`X-API-Key` header) |
| Protocol | Telnet (port 23) | HTTPS (port 443 or 8443) |
| Metrics per interface | 5 (bytes in/out, bandwidth, util) | 17+ counters per port + PoE + state |
| Client tracking | Not supported | Full: hostname, IP, MAC, location, traffic |
| Topology | Not supported | Full adjacency graph from uplink/LLDP |
| Device types | Routers only | Switches, APs, gateways, consoles |
| DPI | Not supported | Application category traffic (opt-in) |
| Dynamic instances | Static (configured) | Dynamic (auto-discovered) |
| Implementation | C (compiled) | Python 3 (daemon) |
| PoE monitoring | Not supported | Per-port power, voltage, current |
| Multi-site | N/A | Unified namespace with per-controller threads |

---

## 13. Documentation

pmdaunifi ships with documentation at three levels, matching the conventions of the PCP ecosystem while also providing modern web-accessible docs.

### 16.1 Man Pages

A `pmdaunifi(1)` man page is produced as part of the build, following PCP PMDA conventions. It covers: synopsis, description, configuration file format, command-line options, installation/removal, files, environment variables, and diagnostics. The man page is installed to the standard `$PCP_MAN_DIR` location and is accessible via `man pmdaunifi` on any system where the PMDA is installed.

### 16.2 GitHub Pages (mkdocs-material)

The project publishes comprehensive documentation to GitHub Pages using **mkdocs** with the **Material** theme. The docs site is auto-deployed on every push to `main` via GitHub Actions and covers:

- **Getting Started:** Quick-start guide from zero to working metrics in under 5 minutes.
- **Configuration Reference:** Complete reference for `unifi.conf` with all options, defaults, and examples.
- **Metric Reference:** Every metric, its type, semantics, units, and help text — auto-generated from the PMDA's metric definitions to stay in sync with the code.
- **Topology Guide:** How topology discovery works, what the topology metrics represent, and how to export them (DOT, JSON).
- **Architecture:** Threading model, caching strategy, authentication flows.
- **Grafana Dashboards:** How to import the pre-built dashboards, what each panel shows, and how to customise them.
- **Troubleshooting:** Common issues (authentication failures, missing devices, stale metrics, SSL errors) with diagnostic steps.
- **Developer Guide:** Local development setup, running tests, architecture overview, how to navigate the codebase.
- **UniFi API Reference Links:** Links to the official UniFi Developer Portal, community API documentation, and the unpoller/unifi data model reference — everything a developer needs to orient themselves.

The mkdocs configuration and content live in `docs/` within the repository. The build is declared in `mkdocs.yml` at the project root.

### 16.3 Grafana Dashboards

The project ships pre-built Grafana dashboard JSON files under `dashboards/` in the repository, designed to work with PCP's pmproxy as the data source. These are modelled on the established patterns from the UnPoller/Grafana ecosystem but adapted for the PCP data model and label structure.

Planned dashboards:

| Dashboard | Description |
|-----------|-------------|
| **Site Overview** | Site health, total clients, device counts, WAN throughput, subsystem status. Site selector variable. |
| **Switch Port Detail** | Per-port rx/tx byte rates, error rates, PoE power, link state. Switch and port selector variables. |
| **Client Insights** | Top clients by traffic, client count over time, wired vs wireless breakdown. |
| **AP Radio Performance** | Per-radio channel utilisation, client counts, tx retries, satisfaction scores. |
| **Topology Map** | (Phase 2+) Network topology visualisation using the Grafana Node Graph panel, driven by topology metrics. |

Each dashboard JSON uses PCP metric labels (`site_name`, `device_type`, `device_model`) for template variables, so they work across single-site and multi-site deployments without modification.

### 16.4 CONTRIBUTING.md

The repository includes a `CONTRIBUTING.md` that covers:

- **Local development setup:** How to clone, install dependencies, start the mock controller, and run the test suite.
- **Repository structure:** What lives where, which modules do what.
- **Making changes:** How to modify the UniFi client, add support for new controller firmware versions, update parsing logic.
- **Testing requirements:** All PRs must pass lint, unit, and integration tests. Coverage must not decrease.
- **Code style:** Enforced by ruff; type hints expected on all public interfaces.
- **UniFi API resources:** Links to the official UniFi Developer Portal (https://developer.ui.com/network), community API documentation (https://ubntwiki.com/products/software/unifi-controller/api), the Art-of-WiFi PHP client, and the unpoller Go library — these are the canonical references for understanding the API surface.
- **Submitting PRs:** Conventional commits, changelog updates, version bumping.

---

## 14. Development Roadmap

### 14.1 Phase 1 — Core (MVP)

Implement controller authentication (both session-based and API key), device/port discovery, the `switch_port` instance domain, and all cluster 0–2 and cluster 9 metrics (site, device, switch port counters, controller health). Implement the per-controller poller thread model and copy-on-write snapshot cache. Emit PCP metric labels (`site_name`, `device_mac`, `device_type`, `device_model`, `port_idx`) on all instances from day one. Implement the interactive Install script with site discovery. Publish to PyPI as `pcp-pmda-unifi`.

Phase 1 deliverables: functional PMDA, Install/Remove scripts, help text, multi-controller support, `pmdaunifi(1)` man page, `CONTRIBUTING.md`, mkdocs site skeleton with Getting Started and Configuration Reference, Site Overview Grafana dashboard, and unit + integration test suites passing in GitHub Actions.

### 14.2 Phase 2 — Clients and Topology

Add the client instance domain (cluster 4) and topology metrics (cluster 7). Implement the intra-site topology graph construction algorithm. Deliver the `unifi2dot` companion script (DOT output with PCP metric names as attributes for pmview-nextgen integration). Add Client Insights and Switch Port Detail Grafana dashboards. Expand mkdocs with Topology Guide.

### 14.3 Phase 3 — Access Points, DPI, and Packaging

Add AP radio metrics (cluster 5), gateway metrics (cluster 6), and DPI metrics (cluster 8, opt-in). Add AP Radio Performance Grafana dashboard. Provide RPM spec and Debian packaging. Submit to COPR/PPA. Expand mkdocs with Metric Reference (auto-generated) and Troubleshooting guide.

### 14.4 Phase 4 — Polish, WebSocket, and Upstream

Implement WebSocket event-driven refresh (`wss/s/{site}/events`) as an optional low-latency alternative to polling. Add extended labels (`port_name`, `client_hostname`, `network_name`). Add Topology Map Grafana dashboard (using Node Graph panel). Write comprehensive QA tests and pmlogconf integration. Prepare the PMDA for submission to the PCP upstream project.

---

## 15. Assumptions, Open Questions, and Future Work

This section captures design decisions that are explicitly deferred, areas where assumptions have been made that may need revisiting, and items that should be tracked as separate GitHub issues.

### 15.1 Cross-Site Topology

**Status:** Deferred / future work.

Automatic cross-site topology discovery is not possible because each UniFi controller only knows about its own adopted devices. A manual link declaration mechanism was considered (see earlier spec drafts) but adds configuration fragility and design complexity (polling phase alignment, bidirectional counter correlation) that is not justified without demonstrated demand. This should be tracked as a GitHub issue and revisited if enterprise users request it.

### 15.2 pmview-nextgen Integration

The `unifi2dot` topology export script (Phase 2 deliverable) outputs Graphviz DOT notation, which can serve as an input for the [pmview-nextgen](https://github.com/tallpsmith/pmview-nextgen) project. The envisioned integration path is: pmdaunifi exposes topology metrics → `unifi2dot` queries PCP and outputs DOT → pmview-nextgen's Host Projector (or a future Network Projector) ingests the DOT graph and generates a Godot `.tscn` scene with `PcpBindable` nodes bound to `unifi.switch.port.*` metrics. This would render the UniFi network as a living 3D visualisation where port traffic drives bar heights, error rates drive colour temperature, and PoE power drives glow intensity.

The DOT output format should include PCP metric names as node/edge attributes so that pmview-nextgen can generate bindings automatically. The exact attribute schema will be co-designed with the pmview-nextgen project. A JSON graph output (`unifi2json`) may also be provided if the Godot scene generator prefers structured data over DOT.

### 15.3 UniFi API Versioning

The UniFi local controller API is undocumented and community-reverse-engineered. While the core endpoints (`stat/device`, `stat/sta`, `stat/health`) have been stable across many controller versions (5.x through 9.x), there is no formal versioning or deprecation policy. The PMDA should handle unexpected fields gracefully (ignore unknown fields, use `.get()` with defaults, log warnings for missing expected fields) and the test fixture suite should include responses from multiple controller versions to catch regressions.

### 15.4 pmlogsynth Integration

The [pmlogsynth](https://github.com/tallpsmith/pmlogsynth) project can be used to generate synthetic PCP archives containing UniFi metric data for testing downstream consumers (Grafana dashboards, pmie rules, pmview-nextgen). The synthetic archive generator (Section 16.7) should output archives that pmlogsynth can also produce from a declarative topology specification. Coordination between the two projects on metric naming and instance domain conventions is assumed.

### 15.5 Client Metric Cardinality at Enterprise Scale

Enterprise deployments (shopping centres, hotels, conference venues) may have 2,000–10,000+ simultaneous clients. At the default `max_clients = 500`, only the top 500 by traffic volume are tracked as PCP instances. This is a deliberate trade-off: full client tracking at 10,000 instances with 14 metrics each would produce 140,000 metric values per fetch cycle, which may stress PMCD and pmlogger. The `max_clients` value should be tunable and the documentation should clearly state the cardinality implications.

If full client tracking is essential for a specific deployment, a dedicated "client-only" pmlogger configuration with a longer sampling interval (e.g. 5 minutes) may be more appropriate than increasing `max_clients` on the main polling loop.

### 15.6 Licence

The project is licensed under **GPL-2.0-or-later**, matching PCP itself. This maximises compatibility for eventual upstream submission to the PCP project and aligns with the existing PCP PMDA ecosystem.

---

## 16. Appendices

### 16.1 Domain Number

The PMDA requires a unique domain number. Domain numbers for PMDAs shipped with PCP are registered in `$PCP_VAR_DIR/pmns/stdpmid`. For a new PMDA under development, use a number in the reserved range (e.g. 450). If/when accepted upstream, an official number will be assigned.

### 16.2 UniFi OS API Path Prefix

On UniFi OS-based devices (UDM, UDM Pro, UDR, UCG-Ultra, CK Gen2+), all API paths must be prefixed with `/proxy/network`. The PMDA handles this automatically when `is_udm = true` is set in the configuration.

### 16.3 Counter Wrap Handling

UniFi port counters are 64-bit integers that reset on device reboot. PCP's counter semantics (`PM_SEM_COUNTER`) handle wrap-around and resets automatically in monitoring tools. The PMDA exports raw counter values and leaves rate conversion entirely to PCP.

### 16.4 Cardinality Considerations

A large UniFi deployment might have 50 switches with 48 ports each (2,400 switch port instances), 200 access points, and 2,000 active clients. The PMDA's memory footprint scales linearly. The `max_clients` configuration option provides a safety valve for extremely large deployments. Instance domains are pruned on each refresh to remove devices and clients that are no longer present.

### 16.5 UniFi API Key Scoping

As of UniFi Network Application 9.x, API keys are generated per-controller at `Settings > Control Plane > Integrations`. A single key provides read-only access to **all sites** on that controller — there is no mechanism for per-site API keys. This is why pmdaunifi's configuration model uses one credential block per controller with a `sites` filter to control which sites are polled, rather than separate credentials per site.

The cloud-based Site Manager API at `unifi.ui.com` uses a separate, account-level API key. pmdaunifi does not use this API — it communicates directly with each local controller for lower latency and access to the full `stat/device` data set that the cloud API does not expose.

### 16.6 References

- PCP Programmer's Guide: https://pcp.readthedocs.io/en/latest/PG/WritingPMDA.html
- `pmdacisco(1)` man page
- UniFi Controller API (community docs): https://ubntwiki.com/products/software/unifi-controller/api
- UniFi Official API: https://help.ui.com/hc/en-us/articles/30076656117655
- UniFi Developer Portal: https://developer.ui.com/network
- unpoller/unifi Go library (data model reference): https://github.com/unpoller/unifi
- Art-of-WiFi/UniFi-API-client (PHP reference): https://github.com/Art-of-WiFi/UniFi-API-client

### 16.7 Testing Strategy

pmdaunifi follows a TDD (Test-Driven Development) approach across three tiers. All tests must run locally without any UniFi hardware and within GitHub Actions runners (Ubuntu `ubuntu-latest`) without privileged access.

#### Tier 1: Unit Tests

**Scope:** Individual functions and classes in isolation. No network, no PCP, no filesystem side effects.

**Framework:** `pytest` with `pytest-cov` for coverage reporting.

**What is tested:**
- `unifi_client.py`: JSON response parsing, authentication header construction, URL path assembly (with/without `/proxy/network` prefix), error handling for malformed responses. Input is raw JSON loaded from fixture files in `tests/fixtures/`.
- `topology.py`: Graph construction algorithm — given a set of device dicts with `uplink`, `lldp_table`, and `mac_table` fields, assert that the correct adjacency list is produced. Edge cases: orphan devices, LLDP-only links, ring topologies, missing uplink fields.
- `config.py`: Configuration parsing — valid configs, missing required fields, multi-controller sections, site list parsing (`all`, single, comma-separated), `[topology]` section parsing.
- `metrics.py`: Metric definition completeness — every metric has a valid type, semantics, units, and help text. PMID cluster/item uniqueness.
- `collector.py`: Snapshot assembly — given parsed device, client, and health dicts, verify that the correct instance names are generated (site-qualified, correctly formatted), counter values are extracted into the right metric slots, and instance domains are correctly populated.

**Fixture data:** The `tests/fixtures/` directory contains recorded (and scrubbed) JSON responses from a real UniFi controller. These are checked into the repository and versioned. A `conftest.py` provides pytest fixtures that load these files:

```python
@pytest.fixture
def sample_devices():
    return json.loads((FIXTURES / "stat_device.json").read_text())

@pytest.fixture
def sample_clients():
    return json.loads((FIXTURES / "stat_sta.json").read_text())
```

**Coverage target:** ≥90% line coverage on all non-PCP-framework code.

#### Tier 2: Integration Tests

**Scope:** The PMDA's interaction with a mock UniFi controller and with PCP's `dbpmda` debugger. Tests the full data path from HTTP response through to PCP metric values.

**Mock UniFi Controller:** A lightweight Flask/FastAPI application (`tests/mock_controller.py`) that serves the fixture JSON files over HTTPS (using a self-signed certificate generated at test time). It implements just enough of the UniFi API to satisfy the PMDA:

- `POST /api/login` — accepts any credentials, returns a session cookie
- `GET /api/self/sites` — returns a site list
- `GET /api/s/{site}/stat/device` — returns the device fixture
- `GET /api/s/{site}/stat/sta` — returns the client fixture
- `GET /api/s/{site}/stat/health` — returns the health fixture
- `GET /api/s/{site}/stat/sysinfo` — returns a minimal sysinfo response

The mock controller runs in-process (or as a subprocess) during the test and listens on `localhost:<random_port>`. This works identically on a developer laptop and in a GitHub Actions runner.

**dbpmda testing:** PCP provides `dbpmda`, an interactive PMDA debugger that can launch a PMDA and exercise its fetch/instance/text/label callbacks without needing a full PMCD installation. Integration tests use `dbpmda` in scripted (non-interactive) mode:

```bash
# tests/integration/test_dbpmda.sh
dbpmda -n pmns -ie <<'EOF'
open pipe pmdaunifi.python -c tests/integration/test.conf
fetch unifi.site.num_sta
fetch unifi.switch.port.rx_bytes
instance 2
EOF
```

These tests verify that: metrics have the correct types and semantics, instance domains are populated with the expected instances, counter values match the fixture data, and labels are correctly attached.

**GitHub Actions requirement:** The CI workflow installs PCP from the OS package manager (`apt install pcp pcp-devel python3-pcp`) to get `dbpmda` and the Python bindings. The mock controller is started as a background process before the integration tests run.

#### Tier 3: End-to-End (E2E) Tests

**Scope:** Full PMDA lifecycle — install, register with PMCD, fetch metrics via `pminfo`/`pmrep`, archive with `pmlogger`, replay from archive.

**Environment:** These tests require a running PMCD instance. In GitHub Actions, this is achieved by starting `pmcd` in the workflow:

```yaml
- name: Start PCP services
  run: |
    sudo systemctl start pmcd
    pmcd_wait -t 10
```

**Test flow:**

1. Start mock controller.
2. Run `./Install` with a test configuration pointing at the mock.
3. Verify `pminfo -f unifi.site.num_sta` returns the expected value.
4. Verify `pminfo -f unifi.switch.port.rx_bytes` returns values for all expected instances.
5. Verify `pminfo -l unifi.switch.port.rx_bytes` returns correct labels (`site_name`, `device_mac`, etc.).
6. Run `pmlogger` for a brief capture (5 seconds), then replay with `pmval -a` and verify values.
7. Run `./Remove` and verify metrics are gone.

**Synthetic archive generation (pmlogsynth integration):** As a supplementary test path, a script generates synthetic PCP archives containing realistic UniFi metric data. This is valuable for testing downstream tools (Grafana dashboards, pmie rules, the `unifi2dot` topology exporter) without needing a live PMDA. The script:

1. Defines the full pmdaunifi PMNS with all metric descriptors.
2. Generates synthetic instance domains representing a configurable topology (e.g. "3 switches, 48 ports each, 120 clients, 2 APs").
3. Writes time-series data with realistic patterns: monotonically increasing byte counters with configurable rates, occasional counter resets (simulating reboots), oscillating client counts, and PoE power values.
4. Outputs a standard PCP archive that can be replayed with any PCP tool.

This script lives at `tests/generate_synthetic_archive.py` and uses the `pcp.LogImport` (libpcp_import) Python bindings to write archives programmatically. It can also be used standalone for demo/evaluation purposes.

#### CI Pipeline (GitHub Actions)

```yaml
name: CI
on: [push, pull_request]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: mypy src/pmdaunifi/

  unit:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[test]"
      - run: pytest tests/unit/ --cov=pmdaunifi --cov-report=xml
      - uses: codecov/codecov-action@v4

  integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y pcp pcp-devel python3-pcp
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[test]"
      - run: pytest tests/integration/

  e2e:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sudo apt-get install -y pcp pcp-devel python3-pcp
      - run: sudo systemctl start pmcd && pmcd_wait -t 10
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -e ".[test]"
      - run: pytest tests/e2e/
```

### 16.8 Dependencies

#### Development Dependencies

| Dependency | Purpose | Install |
|-----------|---------|---------|
| Python ≥3.9 | Runtime and development | System package or pyenv |
| `pcp`, `pcp-devel`, `python3-pcp` | PCP framework, headers, Python bindings | `apt install pcp pcp-devel python3-pcp` (Debian/Ubuntu) or `dnf install pcp pcp-devel python3-pcp` (Fedora/RHEL) |
| `requests` | HTTP client for UniFi API | `pip install requests` |
| `pytest`, `pytest-cov` | Unit/integration test framework | `pip install pytest pytest-cov` |
| `ruff` | Linter and formatter | `pip install ruff` |
| `mypy` | Static type checking | `pip install mypy` |
| `flask` or `fastapi`+`uvicorn` | Mock UniFi controller for integration tests | `pip install flask` |
| `build` | Python package builder (sdist + wheel) | `pip install build` |
| `twine` | PyPI upload tool | `pip install twine` |

All test/dev dependencies are declared in `pyproject.toml` under `[project.optional-dependencies]`:

```toml
[project.optional-dependencies]
test = ["pytest>=7.0", "pytest-cov", "flask", "cryptography"]
dev = ["ruff", "mypy", "build", "twine"]
```

Developers install everything with: `pip install -e ".[test,dev]"`

#### End-User Runtime Dependencies

| Dependency | Purpose | Install |
|-----------|---------|---------|
| `pcp` ≥5.3 | PMCD, pmlogger, pmrep, and core PCP tools | System package manager |
| `python3-pcp` | PCP Python bindings (`pcp.pmda`, `pcp.pmapi`) | System package manager (comes with `pcp` on most distros) |
| `python3` ≥3.9 | Python runtime | System package |
| `python3-requests` | HTTP client | `pip install requests` or system package |

The end user does **not** need build tools, pytest, ruff, or any development tooling. The `pip install pcp-pmda-unifi` path pulls only `requests` as a dependency; `pcp` and `python3-pcp` are system-level dependencies that cannot be installed via pip and must be pre-installed.

#### RPM Build Dependencies

For building RPMs (Fedora, RHEL, CentOS Stream, AlmaLinux):

```
BuildRequires: python3-devel
BuildRequires: python3-setuptools
BuildRequires: pcp-devel
Requires: pcp
Requires: python3-pcp
Requires: python3-requests
```

A `pcp-pmda-unifi.spec` file will be maintained in the repository under `packaging/rpm/`. The spec file follows the conventions of the existing `pcp-pmda-*` packages in Fedora/RHEL — the PMDA files are installed to `%{_libexecdir}/pcp/pmdas/unifi/` with the Install/Remove scripts in `%{_localstatedir}/lib/pcp/pmdas/unifi/`.

For Debian/Ubuntu packaging, a `debian/` directory with `control`, `rules`, and `postinst` files will be provided under `packaging/deb/`.

### 16.9 PyPI Account and Publishing Setup

To publish `pcp-pmda-unifi` to PyPI, the following one-time setup steps are required. These are actions **you** (the project owner) need to perform personally.

#### One-Time Account Setup

1. **Create a PyPI account** at https://pypi.org/account/register/ if you don't already have one.
2. **Enable two-factor authentication** (mandatory for publishing) — PyPI supports TOTP apps and hardware security keys.
3. **Create a TestPyPI account** at https://test.pypi.org/account/register/ (separate account, separate credentials). Use this for dry-run uploads before publishing to the real index.
4. **Reserve the package name** by doing an initial upload to PyPI. The name `pcp-pmda-unifi` is globally unique — first uploader owns it.

#### Recommended: Trusted Publishing (GitHub Actions OIDC)

Rather than managing API tokens manually, PyPI supports **Trusted Publishing** via GitHub Actions OIDC. This is the recommended approach because it eliminates long-lived secrets entirely:

1. On PyPI, go to your project's settings → "Publishing" → "Add a new publisher".
2. Select "GitHub Actions" and enter:
   - **Owner:** your GitHub username or org
   - **Repository:** the repo name (e.g. `pcp-pmda-unifi`)
   - **Workflow:** `release.yml` (or whatever you name the CI release workflow)
   - **Environment:** `pypi` (optional but recommended)
3. In your GitHub repo, create a release workflow:

```yaml
# .github/workflows/release.yml
name: Publish to PyPI
on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write  # Required for Trusted Publishing
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install build
      - run: python -m build
      - uses: pypa/gh-action-pypi-publish@release/v1
```

With this setup, creating a GitHub Release automatically builds and publishes to PyPI — no API tokens or secrets to manage.

#### Alternative: API Token (Manual or for TestPyPI)

If you prefer manual control or need to publish to TestPyPI:

1. On PyPI (or TestPyPI), go to Account Settings → API Tokens → "Add API Token".
2. Scope the token to the `pcp-pmda-unifi` project (after the initial upload).
3. Store the token as a GitHub Actions secret (`PYPI_API_TOKEN`).
4. Use in CI:

```yaml
- uses: pypa/gh-action-pypi-publish@release/v1
  with:
    password: ${{ secrets.PYPI_API_TOKEN }}
```

Or upload manually:

```bash
python -m build
twine upload dist/*  # Will prompt for token
```

#### Release Workflow Summary

1. Bump version in `src/pmdaunifi/__init__.py` and `pyproject.toml`.
2. Update CHANGELOG.md.
3. Commit and tag: `git tag v0.1.0 && git push --tags`.
4. Create a GitHub Release from the tag.
5. The `release.yml` workflow triggers automatically, builds sdist + wheel, and publishes to PyPI via Trusted Publishing.
6. Users install/upgrade with `pip install --upgrade pcp-pmda-unifi`.

