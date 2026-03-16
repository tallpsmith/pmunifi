# pmrep Views for UniFi PMDA

**Date:** 2026-03-16
**Status:** Approved

## Overview

Ship a set of `pmrep` view configurations for CLI-based monitoring of UniFi
network infrastructure. The views serve two primary use cases:

1. **SSH-and-glance** — quick health snapshots from a terminal
2. **Troubleshooting** — drill down from site to device to port to find problems

## Deliverable

A single configuration file `pmrep-unifi.conf` containing eleven named view
sections, installed to `/etc/pcp/pmrep/` during PMDA setup.

## Global Defaults

- **samples:** `1` (one-shot snapshot; override with `-t 5s` for live monitoring)
- **timestamp:** enabled
- **unitinfo:** enabled
- **colxrow:** instance name as row label

Rate/counter views override to `samples = 2`, `interval = 5s` to produce one
line of meaningful rate-converted output. These views show progressive metrics
and are not one-shot.

## Semantic Split Rule

Views are strictly separated by metric semantics:

- **One-shot views** contain only instant/discrete values (gauges, strings,
  counts). They print a single snapshot and exit.
- **Rate views** (`-traffic` suffix) contain only counter-derived metrics.
  They default to `samples = 2`, `interval = 5s` to produce rate-converted
  output.

No view mixes counter and instant metrics. This ensures one-shot views return
instantly and rate views always show meaningful per-second values.

## Views

### 1. `:unifi-health` — PMDA & Controller Health

**Instance domain:** controller | **Default:** one-shot

| Column | Metric | Notes |
|--------|--------|-------|
| Up | `unifi.controller.up` | Controller reachable (0/1) |
| Version | `unifi.controller.version` | Controller software version |
| Poll Time | `unifi.controller.poll_duration_ms` | Last poll round-trip (ms) |
| Poll Errors | `unifi.controller.poll_errors` | Cumulative poll failures |
| Last Poll | `unifi.controller.last_poll` | Unix timestamp of last success |
| Sites | `unifi.controller.sites_polled` | Number of sites polled |
| Devices | `unifi.controller.devices_discovered` | Devices found |
| Clients | `unifi.controller.clients_discovered` | Clients found |

### 2. `:unifi-site` — Site Status & Counts

**Instance domain:** site | **Default:** one-shot

| Column | Metric | Notes |
|--------|--------|-------|
| Status | `unifi.site.status` | Site health string |
| APs | `unifi.site.num_ap` | Access point count |
| Switches | `unifi.site.num_sw` | Switch count |
| Gateways | `unifi.site.num_gw` | Gateway count |
| Clients | `unifi.site.num_sta` | Total connected stations |
| Users | `unifi.site.num_user` | User (non-guest) count |
| Guests | `unifi.site.num_guest` | Guest count |

### 3. `:unifi-site-traffic` — Site Throughput

**Instance domain:** site | **Default:** `samples = 2`, `interval = 5s`

| Column | Metric | Notes |
|--------|--------|-------|
| WAN RX | `unifi.site.wan.rx_bytes` | WAN inbound (bytes/s) |
| WAN TX | `unifi.site.wan.tx_bytes` | WAN outbound (bytes/s) |
| LAN RX | `unifi.site.lan.rx_bytes` | LAN inbound (bytes/s) |
| LAN TX | `unifi.site.lan.tx_bytes` | LAN outbound (bytes/s) |
| WLAN RX | `unifi.site.wlan.rx_bytes` | Wireless inbound (bytes/s) |
| WLAN TX | `unifi.site.wlan.tx_bytes` | Wireless outbound (bytes/s) |

### 4. `:unifi-device-summary` — All Devices Triage

**Instance domain:** device | **Default:** one-shot

| Column | Metric | Notes |
|--------|--------|-------|
| Name | `unifi.device.name` | Device name |
| Type | `unifi.device.type` | usw/uap/ugw/udm |
| Model | `unifi.device.model` | Hardware model |
| IP | `unifi.device.ip` | Management IP |
| State | `unifi.device.state` | Connectivity state |
| Uptime | `unifi.device.uptime` | Seconds since boot |
| Users | `unifi.device.user_num_sta` | Connected user clients |
| Guests | `unifi.device.guest_num_sta` | Connected guest clients |
| Temp | `unifi.device.temperature` | Thermal reading |
| Version | `unifi.device.version` | Firmware version |

### 5. `:unifi-device-traffic` — Per-Device Throughput

**Instance domain:** device | **Default:** `samples = 2`, `interval = 5s`

| Column | Metric | Notes |
|--------|--------|-------|
| Name | `unifi.device.name` | Device name (for row identification) |
| Type | `unifi.device.type` | Device type (for row identification) |
| RX | `unifi.device.rx_bytes` | Inbound (bytes/s) |
| TX | `unifi.device.tx_bytes` | Outbound (bytes/s) |

### 6. `:unifi-switch-detail` — Switch Status

**Instance domain:** device (filtered) | **Default:** one-shot

Usage: `pmrep :unifi-switch-detail -i ".*USW.*"`

| Column | Metric | Notes |
|--------|--------|-------|
| Name | `unifi.device.name` | Switch name |
| Model | `unifi.device.model` | Hardware model |
| State | `unifi.device.state` | Connectivity state |
| Uptime | `unifi.device.uptime` | Seconds since boot |
| Ports | `unifi.device.num_ports` | Total port count |
| Users | `unifi.device.user_num_sta` | Connected clients |
| Temp | `unifi.device.temperature` | Thermal |

### 7. `:unifi-switch-traffic` — Switch Aggregate Throughput

**Instance domain:** device (filtered) | **Default:** `samples = 2`, `interval = 5s`

Usage: `pmrep :unifi-switch-traffic -i ".*USW.*"`

| Column | Metric | Notes |
|--------|--------|-------|
| Name | `unifi.device.name` | Switch name (for row identification) |
| RX | `unifi.device.rx_bytes` | Aggregate inbound (bytes/s) |
| TX | `unifi.device.tx_bytes` | Aggregate outbound (bytes/s) |

### 8. `:unifi-switch-ports` — Per-Port Troubleshooting

**Instance domain:** switch_port | **Default:** `samples = 2`, `interval = 5s`

Usage: `pmrep :unifi-switch-ports -i ".*USW-Pro-48.*"`

| Column | Metric | Notes |
|--------|--------|-------|
| Up | `unifi.switch.port.up` | Link up (0/1) |
| Speed | `unifi.switch.port.speed` | Negotiated speed (Mbps) |
| Duplex | `unifi.switch.port.full_duplex` | Full duplex (0/1) |
| RX | `unifi.switch.port.rx_bytes` | Inbound (bytes/s) |
| TX | `unifi.switch.port.tx_bytes` | Outbound (bytes/s) |
| RX Pkt | `unifi.switch.port.rx_packets` | Inbound (packets/s) |
| TX Pkt | `unifi.switch.port.tx_packets` | Outbound (packets/s) |
| RX Err | `unifi.switch.port.rx_errors` | Inbound errors (/s) |
| TX Err | `unifi.switch.port.tx_errors` | Outbound errors (/s) |
| RX Drop | `unifi.switch.port.rx_dropped` | Inbound drops (/s) |
| TX Drop | `unifi.switch.port.tx_dropped` | Outbound drops (/s) |
| MACs | `unifi.switch.port.mac_count` | Learned MAC addresses |
| Satis | `unifi.switch.port.satisfaction` | Satisfaction % |
| PoE W | `unifi.switch.port.poe.power` | PoE power draw (W) |

### 9. `:unifi-ap-detail` — AP Radio Performance

**Instance domain:** ap_radio | **Default:** `samples = 2`, `interval = 5s`

| Column | Metric | Notes |
|--------|--------|-------|
| Radio | `unifi.ap.radio_type` | ng/na/ax/be |
| Channel | `unifi.ap.channel` | Operating channel |
| Clients | `unifi.ap.num_sta` | Connected stations |
| RX | `unifi.ap.rx_bytes` | Inbound (bytes/s) |
| TX | `unifi.ap.tx_bytes` | Outbound (bytes/s) |
| TX Drop | `unifi.ap.tx_dropped` | Dropped transmits (/s) |
| TX Retry | `unifi.ap.tx_retries` | Retransmissions (/s) |
| Satis | `unifi.ap.satisfaction` | Satisfaction % |

### 10. `:unifi-gateway-health` — Gateway Status & Resources

**Instance domain:** gateway | **Default:** one-shot

| Column | Metric | Notes |
|--------|--------|-------|
| WAN IP | `unifi.gateway.wan_ip` | WAN interface address |
| WAN Up | `unifi.gateway.wan_up` | Link state (0/1) |
| WAN Speed | `unifi.gateway.wan_speed` | Negotiated speed (Mbps) |
| Latency | `unifi.gateway.wan_latency` | WAN latency (ms) |
| CPU | `unifi.gateway.cpu` | CPU utilisation % |
| Mem | `unifi.gateway.mem` | Memory utilisation % |
| Temp | `unifi.gateway.temperature` | Thermal |
| Uptime | `unifi.gateway.uptime` | Seconds since boot |

### 11. `:unifi-gateway-traffic` — Gateway Throughput & Errors

**Instance domain:** gateway | **Default:** `samples = 2`, `interval = 5s`

| Column | Metric | Notes |
|--------|--------|-------|
| WAN RX | `unifi.gateway.wan_rx_bytes` | WAN inbound (bytes/s) |
| WAN TX | `unifi.gateway.wan_tx_bytes` | WAN outbound (bytes/s) |
| WAN RX Err | `unifi.gateway.wan_rx_errors` | WAN inbound errors (/s) |
| WAN TX Err | `unifi.gateway.wan_tx_errors` | WAN outbound errors (/s) |
| WAN RX Drop | `unifi.gateway.wan_rx_dropped` | WAN inbound drops (/s) |
| WAN TX Drop | `unifi.gateway.wan_tx_dropped` | WAN outbound drops (/s) |
| LAN RX | `unifi.gateway.lan_rx_bytes` | LAN-side inbound (bytes/s) |
| LAN TX | `unifi.gateway.lan_tx_bytes` | LAN-side outbound (bytes/s) |

## Drill-Down Flow

```
:unifi-health  →  Is the PMDA working?
:unifi-site  →  Is the site healthy?
:unifi-site-traffic  →  What's the throughput?
:unifi-device-summary  →  Which device is the problem?
:unifi-device-traffic  →  Which device is busiest?
    ├── :unifi-switch-detail -i "..."  →  Is this switch OK?
    │   ├── :unifi-switch-traffic -i "..."  →  Switch throughput?
    │   └── :unifi-switch-ports -i "..."  →  Which port?
    ├── :unifi-ap-detail -i "..."  →  Which radio?
    └── :unifi-gateway-health  →  Gateway status?
        └── :unifi-gateway-traffic  →  WAN throughput?
```

All views support instance filtering via `pmrep -i ".*pattern.*"`.

## Installation

The config file is installed to `/etc/pcp/pmrep/pmrep-unifi.conf` as part of
the existing `pcp-pmda-unifi-setup` deployment process.

## Design Decisions

1. **Single file, multiple sections** — idiomatic pmrep pattern; one file to
   install, views independently invocable.
2. **Strict semantic split** — one-shot views contain only instant/discrete
   values; rate views (`-traffic` suffix) contain only counters. No view mixes
   both semantics, ensuring one-shot views return instantly and rate views
   always show meaningful per-second values.
3. **Rate views default to `samples = 2`** — single-sample counter values are
   meaningless; two samples with a 5s interval produce one line of
   rate-converted output.
4. **PoE collapsed to single power column** — voltage/current/class are
   diagnostic-level detail not needed in a summary view.
5. **Gateway split into health/traffic** — 16 columns is too wide for a
   terminal; semantic split keeps each view under ~8 columns.
6. **No multi-controller complexity** — designed for single-site/single-controller;
   instance naming supports multi-controller without view changes.

## Known Issues

- `unifi.gateway.wan_latency` is registered as a metric but not currently
  populated by the collector. The Latency column in `:unifi-gateway-health`
  will show 0 until this is fixed (pre-existing codebase bug, tracked
  separately).

## Future Considerations

- **Client view** (`:unifi-clients`) — the PMDA exposes 15 client metrics
  with their own instance domain. A client view could complete the "who is
  connected to this port?" troubleshooting story.
- **DPI view** (`:unifi-dpi`) — per-category traffic breakdown, opt-in.
  Worth adding if DPI is commonly enabled.
