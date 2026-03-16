# Data Model: UniFi PCP PMDA

**Feature Branch**: `001-unifi-pmda` | **Date**: 2026-03-15

## Instance Domains

PCP instance domains group related metric instances. Each domain gets a serial number (0–N) scoped to the PMDA's domain number.

### Indom 0: `site`

Instances represent monitored UniFi sites.

**Instance naming**: `{controller_name}/{site_name}` (e.g., `main/default`, `branch/warehouse`)

| Field | Source | Notes |
|---|---|---|
| name | `site.name` | Site slug (e.g., "default") |
| desc | `site.desc` | Human-readable description |

### Indom 1: `device`

Instances represent adopted UniFi network devices (switches, APs, gateways, consoles).

**Instance naming**: `{controller}/{site}/{device_name}` (e.g., `main/default/USW-Pro-48-Rack1`)

| Field | Type | Source | Notes |
|---|---|---|---|
| mac | string | `device.mac` | Primary identifier |
| name | string | `device.name` | Human-assigned name |
| ip | string | `device.ip` | Management IP |
| model | string | `device.model` | Model code (e.g., "USW-Pro-48-PoE") |
| type | string | `device.type` | "usw", "uap", "ugw", "udm" |
| version | string | `device.version` | Firmware version |
| state | int | `device.state` | 1=connected, 2=provisioning, etc. |
| uptime | int | `device.uptime` | Seconds since boot |
| adopted | bool | `device.adopted` | Adoption state |
| rx_bytes | u64 | `device.rx_bytes` | Total device receive bytes |
| tx_bytes | u64 | `device.tx_bytes` | Total device transmit bytes |
| temperature | float | `device.general_temperature` | General temperature (°C, if available) |
| user_num_sta | int | `device.user-num_sta` | Connected user stations |
| guest_num_sta | int | `device.guest-num_sta` | Connected guest stations |
| num_ports | int | `device.port_table.length` | Total port count (switches only) |

### Indom 2: `switch_port`

Instances represent physical ports on switch devices. Central entity for P1.

**Instance naming**: `{controller}/{site}/{device_name}::Port{port_idx}` (e.g., `main/default/USW-Pro-48-Rack1::Port1`)

| Field | Type | Semantic | Source | Notes |
|---|---|---|---|---|
| rx_bytes | u64 | COUNTER | `port.rx_bytes` | Total bytes received |
| tx_bytes | u64 | COUNTER | `port.tx_bytes` | Total bytes transmitted |
| rx_packets | u64 | COUNTER | `port.rx_packets` | Total packets received |
| tx_packets | u64 | COUNTER | `port.tx_packets` | Total packets transmitted |
| rx_errors | u64 | COUNTER | `port.rx_errors` | Receive errors |
| tx_errors | u64 | COUNTER | `port.tx_errors` | Transmit errors |
| rx_dropped | u64 | COUNTER | `port.rx_dropped` | Receive drops |
| tx_dropped | u64 | COUNTER | `port.tx_dropped` | Transmit drops |
| rx_broadcast | u64 | COUNTER | `port.rx_broadcast` | Broadcast frames rx |
| tx_broadcast | u64 | COUNTER | `port.tx_broadcast` | Broadcast frames tx |
| rx_multicast | u64 | COUNTER | `port.rx_multicast` | Multicast frames rx |
| tx_multicast | u64 | COUNTER | `port.tx_multicast` | Multicast frames tx |
| up | u32 | INSTANT | `port.up` | Link state (0/1) |
| enable | u32 | INSTANT | `port.enable` | Admin enabled (0/1) |
| speed | u32 | INSTANT | `port.speed` | Link speed (Mbps) |
| full_duplex | u32 | INSTANT | `port.full_duplex` | Duplex mode (0/1) |
| is_uplink | u32 | INSTANT | `port.is_uplink` | Uplink port flag (0/1) |
| satisfaction | u32 | INSTANT | `port.satisfaction` | Client satisfaction % |
| mac_count | u32 | INSTANT | `len(port.mac_table)` | Number of MACs learned on this port |
| poe_enable | u32 | INSTANT | `port.poe_enable` | PoE enabled (0/1) |
| poe_good | u32 | INSTANT | `port.poe_good` | PoE delivering power (0/1) |
| poe_power | float | INSTANT | `port.poe_power` | PoE power draw (W) |
| poe_voltage | float | INSTANT | `port.poe_voltage` | PoE voltage (V) |
| poe_current | float | INSTANT | `port.poe_current` | PoE current (mA) |
| poe_class | string | INSTANT | `port.poe_class` | PoE class (Class 0–4) |

### Indom 3: `client`

Instances represent connected network clients (wired and wireless).

**Instance naming**: `{controller}/{site}/{hostname_or_mac}` (e.g., `main/default/laptop-alice`)

| Field | Type | Semantic | Source | Notes |
|---|---|---|---|---|
| hostname | string | INSTANT | `sta.hostname` | Client hostname |
| ip | string | INSTANT | `sta.ip` | Client IP address |
| mac | string | DISCRETE | `sta.mac` | Client MAC address |
| oui | string | DISCRETE | `sta.oui` | OUI vendor string |
| is_wired | u32 | INSTANT | `sta.is_wired` | Wired vs wireless (0/1) |
| sw_mac | string | INSTANT | `sta.sw_mac` | Connected switch MAC |
| sw_port | u32 | INSTANT | `sta.sw_port` | Connected switch port index |
| rx_bytes | u64 | COUNTER | `sta.rx_bytes` | Total bytes received |
| tx_bytes | u64 | COUNTER | `sta.tx_bytes` | Total bytes transmitted |
| rx_packets | u64 | COUNTER | `sta.rx_packets` | Total packets received |
| tx_packets | u64 | COUNTER | `sta.tx_packets` | Total packets transmitted |
| uptime | u64 | INSTANT | `sta.uptime` | Client connection uptime (sec) |
| signal | s32 | INSTANT | `sta.signal` | Wireless signal strength (dBm) |
| network | string | INSTANT | `sta.network` | Network/VLAN name |
| last_seen | u64 | INSTANT | `sta.last_seen` | Unix timestamp |

### Indom 4: `ap_radio`

Instances represent radio interfaces on access points.

**Instance naming**: `{controller}/{site}/{device_name}::{radio_type}` (e.g., `main/default/UAP-AC-Pro-Lobby::na`)

| Field | Type | Semantic | Source | Notes |
|---|---|---|---|---|
| channel | u32 | INSTANT | `radio.channel` | Operating channel |
| radio_type | string | DISCRETE | `radio.radio` | Radio type (ng, na, ax, be) |
| rx_bytes | u64 | COUNTER | `radio.rx_bytes` | Bytes received |
| tx_bytes | u64 | COUNTER | `radio.tx_bytes` | Bytes transmitted |
| rx_packets | u64 | COUNTER | `radio.rx_packets` | Packets received |
| tx_packets | u64 | COUNTER | `radio.tx_packets` | Packets transmitted |
| tx_dropped | u64 | COUNTER | `radio.tx_dropped` | Transmit drops |
| tx_retries | u64 | COUNTER | `radio.tx_retries` | Transmit retries |
| num_sta | u32 | INSTANT | `radio.num_sta` | Connected client count |
| satisfaction | u32 | INSTANT | `radio.satisfaction` | Satisfaction score (%) |

### Indom 5: `gateway`

Instances represent gateway/router devices (UGW, UDM acting as gateway). One instance per gateway per site.

**Instance naming**: `{controller}/{site}/{device_name}` (e.g., `main/default/UDM-Pro`)

| Field | Type | Semantic | Source | Notes |
|---|---|---|---|---|
| wan_ip | string | INSTANT | `gw.wan1.ip` | WAN interface IP address |
| wan_rx_bytes | u64 | COUNTER | `gw.wan1.rx_bytes` | WAN receive bytes |
| wan_tx_bytes | u64 | COUNTER | `gw.wan1.tx_bytes` | WAN transmit bytes |
| wan_rx_packets | u64 | COUNTER | `gw.wan1.rx_packets` | WAN receive packets |
| wan_tx_packets | u64 | COUNTER | `gw.wan1.tx_packets` | WAN transmit packets |
| wan_rx_dropped | u64 | COUNTER | `gw.wan1.rx_dropped` | WAN receive drops |
| wan_tx_dropped | u64 | COUNTER | `gw.wan1.tx_dropped` | WAN transmit drops |
| wan_rx_errors | u64 | COUNTER | `gw.wan1.rx_errors` | WAN receive errors |
| wan_tx_errors | u64 | COUNTER | `gw.wan1.tx_errors` | WAN transmit errors |
| wan_up | u32 | INSTANT | `gw.wan1.up` | WAN link state (0/1) |
| wan_speed | u32 | INSTANT | `gw.wan1.speed` | WAN link speed (Mbps) |
| wan_latency | u32 | INSTANT | `health.wan.latency` | WAN latency (ms, from speedtest/ping) |
| lan_rx_bytes | u64 | COUNTER | `gw.lan.rx_bytes` | LAN aggregate receive bytes |
| lan_tx_bytes | u64 | COUNTER | `gw.lan.tx_bytes` | LAN aggregate transmit bytes |
| uptime | u64 | INSTANT | `gw.uptime` | Gateway uptime (sec) |
| cpu | float | INSTANT | `gw.system-stats.cpu` | CPU utilisation (%) |
| mem | float | INSTANT | `gw.system-stats.mem` | Memory utilisation (%) |
| temperature | float | INSTANT | `gw.general_temperature` | Device temperature (°C) |

### Indom 6: `controller`

Instances represent configured UniFi controllers. Singleton per controller.

**Instance naming**: `{controller_name}` (e.g., `main`)

| Field | Type | Semantic | Notes |
|---|---|---|---|
| up | u32 | INSTANT | Controller reachable (0/1) |
| poll_duration_ms | float | INSTANT | Last poll round-trip (ms) |
| poll_errors | u64 | COUNTER | Cumulative poll failure count |
| last_poll | u64 | INSTANT | Unix timestamp of last successful poll |
| version | string | DISCRETE | Controller software version (from stat/sysinfo) |
| devices_discovered | u32 | INSTANT | Number of devices found last poll |
| clients_discovered | u32 | INSTANT | Number of clients found last poll |
| sites_polled | u32 | INSTANT | Number of sites being polled |

### Indom 7: `dpi_category`

Instances represent DPI traffic categories per site. Opt-in (FR-023).

**Instance naming**: `{controller}/{site}/{category_name}` (e.g., `main/default/Streaming`)

| Field | Type | Semantic | Source | Notes |
|---|---|---|---|---|
| rx_bytes | u64 | COUNTER | `dpi.rx_bytes` | Category rx bytes |
| tx_bytes | u64 | COUNTER | `dpi.tx_bytes` | Category tx bytes |

---

## Cluster Allocation

Clusters group related metrics for efficient PMID assignment.

| Cluster | PMNS Prefix | Instance Domain |
|---------|-------------|-----------------|
| 0 | `unifi.site.*` | site |
| 1 | `unifi.device.*` | device |
| 2 | `unifi.switch.port.*` | switch_port |
| 3 | `unifi.switch.port.poe.*` | switch_port |
| 4 | `unifi.client.*` | client |
| 5 | `unifi.ap.*` | ap_radio |
| 6 | `unifi.gateway.*` | gateway |
| 7 | *(reserved — topology companion tool, not PMDA metrics)* | — |
| 8 | `unifi.dpi.*` | dpi_category |
| 9 | `unifi.controller.*` | controller |

---

## Metric Namespace Tree

```
unifi
├── site
│   ├── status                [INSTANT,STRING]  indom:site
│   ├── num_sta               [INSTANT]   indom:site
│   ├── num_user              [INSTANT]   indom:site
│   ├── num_guest             [INSTANT]   indom:site
│   ├── num_ap                [INSTANT]   indom:site
│   ├── num_sw                [INSTANT]   indom:site
│   ├── num_gw                [INSTANT]   indom:site
│   ├── wan
│   │   ├── rx_bytes          [COUNTER]   indom:site
│   │   └── tx_bytes          [COUNTER]   indom:site
│   ├── lan
│   │   ├── rx_bytes          [COUNTER]   indom:site
│   │   ├── tx_bytes          [COUNTER]   indom:site
│   │   ├── num_user          [INSTANT]   indom:site
│   │   └── num_guest         [INSTANT]   indom:site
│   └── wlan
│       ├── rx_bytes          [COUNTER]   indom:site
│       └── tx_bytes          [COUNTER]   indom:site
├── device
│   ├── name                  [DISCRETE]  indom:device
│   ├── mac                   [DISCRETE]  indom:device
│   ├── ip                    [INSTANT]   indom:device
│   ├── model                 [DISCRETE]  indom:device
│   ├── type                  [DISCRETE]  indom:device
│   ├── version               [INSTANT]   indom:device
│   ├── state                 [INSTANT]   indom:device
│   ├── uptime                [INSTANT]   indom:device
│   ├── adopted               [DISCRETE]  indom:device
│   ├── rx_bytes              [COUNTER]   indom:device
│   ├── tx_bytes              [COUNTER]   indom:device
│   ├── temperature           [INSTANT]   indom:device
│   ├── user_num_sta          [INSTANT]   indom:device
│   ├── guest_num_sta         [INSTANT]   indom:device
│   └── num_ports             [DISCRETE]  indom:device
├── switch
│   └── port
│       ├── rx_bytes          [COUNTER]   indom:switch_port
│       ├── tx_bytes          [COUNTER]   indom:switch_port
│       ├── rx_packets        [COUNTER]   indom:switch_port
│       ├── tx_packets        [COUNTER]   indom:switch_port
│       ├── rx_errors         [COUNTER]   indom:switch_port
│       ├── tx_errors         [COUNTER]   indom:switch_port
│       ├── rx_dropped        [COUNTER]   indom:switch_port
│       ├── tx_dropped        [COUNTER]   indom:switch_port
│       ├── rx_broadcast      [COUNTER]   indom:switch_port
│       ├── tx_broadcast      [COUNTER]   indom:switch_port
│       ├── rx_multicast      [COUNTER]   indom:switch_port
│       ├── tx_multicast      [COUNTER]   indom:switch_port
│       ├── up                [INSTANT]   indom:switch_port
│       ├── enable            [INSTANT]   indom:switch_port
│       ├── speed             [INSTANT]   indom:switch_port
│       ├── full_duplex       [INSTANT]   indom:switch_port
│       ├── is_uplink         [INSTANT]   indom:switch_port
│       ├── satisfaction      [INSTANT]   indom:switch_port
│       ├── mac_count         [INSTANT]   indom:switch_port
│       └── poe
│           ├── enable        [INSTANT]   indom:switch_port
│           ├── good          [INSTANT]   indom:switch_port
│           ├── power         [INSTANT]   indom:switch_port
│           ├── voltage       [INSTANT]   indom:switch_port
│           ├── current       [INSTANT]   indom:switch_port
│           └── class         [INSTANT,STRING]  indom:switch_port
├── client
│   ├── hostname              [INSTANT]   indom:client
│   ├── ip                    [INSTANT]   indom:client
│   ├── mac                   [DISCRETE]  indom:client
│   ├── oui                   [DISCRETE]  indom:client
│   ├── is_wired              [INSTANT]   indom:client
│   ├── sw_mac                [INSTANT]   indom:client
│   ├── sw_port               [INSTANT]   indom:client
│   ├── rx_bytes              [COUNTER]   indom:client
│   ├── tx_bytes              [COUNTER]   indom:client
│   ├── rx_packets            [COUNTER]   indom:client
│   ├── tx_packets            [COUNTER]   indom:client
│   ├── uptime                [INSTANT]   indom:client
│   ├── signal                [INSTANT]   indom:client
│   ├── network               [INSTANT]   indom:client
│   └── last_seen             [INSTANT]   indom:client
├── ap
│   ├── channel               [INSTANT]   indom:ap_radio
│   ├── radio_type            [DISCRETE]  indom:ap_radio
│   ├── rx_bytes              [COUNTER]   indom:ap_radio
│   ├── tx_bytes              [COUNTER]   indom:ap_radio
│   ├── rx_packets            [COUNTER]   indom:ap_radio
│   ├── tx_packets            [COUNTER]   indom:ap_radio
│   ├── tx_dropped            [COUNTER]   indom:ap_radio
│   ├── tx_retries            [COUNTER]   indom:ap_radio
│   ├── num_sta               [INSTANT]   indom:ap_radio
│   └── satisfaction          [INSTANT]   indom:ap_radio
├── gateway
│   ├── wan_ip                [INSTANT,STRING]  indom:gateway
│   ├── wan_rx_bytes          [COUNTER]   indom:gateway
│   ├── wan_tx_bytes          [COUNTER]   indom:gateway
│   ├── wan_rx_packets        [COUNTER]   indom:gateway
│   ├── wan_tx_packets        [COUNTER]   indom:gateway
│   ├── wan_rx_dropped        [COUNTER]   indom:gateway
│   ├── wan_tx_dropped        [COUNTER]   indom:gateway
│   ├── wan_rx_errors         [COUNTER]   indom:gateway
│   ├── wan_tx_errors         [COUNTER]   indom:gateway
│   ├── wan_up                [INSTANT]   indom:gateway
│   ├── wan_speed             [INSTANT]   indom:gateway
│   ├── wan_latency           [INSTANT]   indom:gateway
│   ├── lan_rx_bytes          [COUNTER]   indom:gateway
│   ├── lan_tx_bytes          [COUNTER]   indom:gateway
│   ├── uptime                [INSTANT]   indom:gateway
│   ├── cpu                   [INSTANT]   indom:gateway
│   ├── mem                   [INSTANT]   indom:gateway
│   └── temperature           [INSTANT]   indom:gateway
├── controller
│   ├── up                    [INSTANT]   indom:controller
│   ├── poll_duration_ms      [INSTANT]   indom:controller
│   ├── poll_errors           [COUNTER]   indom:controller
│   ├── last_poll             [INSTANT]   indom:controller
│   ├── version               [DISCRETE]  indom:controller
│   ├── devices_discovered    [INSTANT]   indom:controller
│   ├── clients_discovered    [INSTANT]   indom:controller
│   └── sites_polled          [INSTANT]   indom:controller
└── dpi
    ├── rx_bytes              [COUNTER]   indom:dpi_category
    └── tx_bytes              [COUNTER]   indom:dpi_category
```

---

## PCP Labels

Labels are attached at the instance level (per FR-015):

| Label Key | Applies To | Example Value |
|---|---|---|
| `agent` | Domain | `"unifi"` |
| `controller_name` | All instances | `"main"` |
| `controller_url` | All instances | `"https://192.168.1.1"` |
| `site_name` | site, device, port, client, ap, gateway, dpi | `"default"` |
| `device_mac` | device, port, gateway | `"aa:bb:cc:dd:ee:ff"` |
| `device_type` | device, port, gateway | `"usw"` |
| `device_model` | device, port, gateway | `"USW-Pro-48-PoE"` |
| `port_idx` | port | `1` |

---

## Snapshot Cache Structure

The poller thread builds a complete `Snapshot` and atomically swaps it into the PMDA. The PMDA dispatch thread only ever reads from the current snapshot — never writes.

```
Snapshot (immutable once published)
├── timestamp: float              # When this snapshot was taken
├── controller_name: str
├── controller_version: str       # From stat/sysinfo
├── sites: dict[str, SiteData]
│   └── SiteData
│       ├── health: HealthData    # From stat/health (wan, lan, wlan, vpn subsystems)
│       ├── devices: dict[str, DeviceData]  # Keyed by MAC
│       │   └── DeviceData
│       │       ├── meta: DeviceMeta        # name, model, type, version, state, uptime,
│       │       │                           # adopted, temperature, user/guest_num_sta,
│       │       │                           # rx_bytes, tx_bytes, num_ports
│       │       ├── ports: dict[int, PortData]  # Keyed by port_idx (switches only)
│       │       │   └── PortData            # All counter + status + PoE fields
│       │       ├── radios: list[RadioData]     # AP radio interfaces
│       │       └── gateway: GatewayData | None # Gateway WAN/LAN metrics (ugw/udm only)
│       ├── clients: list[ClientData]       # Sorted by traffic, capped by max_clients
│       └── dpi_categories: list[DpiData]   # Optional, if enable_dpi=true
├── devices_discovered: int       # Count for controller metrics
├── clients_discovered: int       # Count for controller metrics
└── sites_polled: int             # Count for controller metrics
```

This structure is built by the poller, frozen, and swapped via reference assignment. The old snapshot is garbage collected when no fetch callback references it.

---

## Validation Rules

- `port_idx` MUST be a positive integer (1-based on most switches)
- `mac` fields MUST be lowercase colon-separated hex (normalise on ingestion)
- Counter fields MUST be non-negative integers (use `.get(field, 0)` with default)
- `speed` values: 0 (no link), 10, 100, 1000, 2500, 5000, 10000
- `state` values: 0=disconnected, 1=connected, 2=pending, 4=upgrading, 5=provisioning
- Instance names MUST NOT contain whitespace (replace with hyphens)
- Hostname fallback: if `sta.hostname` is empty, use MAC address
- `temperature` may be absent on devices without thermal sensors — return `PM_ERR_VALUE`
- `signal` is only meaningful for wireless clients — return `PM_ERR_VALUE` for wired
- Gateway fields from `wan1` — if `wan1` absent, try `wan` as fallback

---

## State Transitions

### Device State

```
Offline(0) → Adopting → Provisioning(5) → Connected(1)
Connected(1) → Upgrading(4) → Connected(1)
Connected(1) → Disconnected(0)
```

Grace period (default 5 min): disconnected devices/clients remain in instance domains until the grace period expires, then are pruned (FR-017).

### Controller State

```
Up(1) → poll failure → Up(1) [retain last snapshot, increment poll_errors]
Up(1) → repeated failures → Down(0) [still serve last snapshot]
Down(0) → successful poll → Up(1) [swap in fresh snapshot]
```
