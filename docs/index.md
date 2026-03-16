# pcp-pmda-unifi

A Performance Metrics Domain Agent (PMDA) that exports Ubiquiti UniFi network
infrastructure metrics through [Performance Co-Pilot](https://pcp.io).

Monitor switch port traffic, device health, gateway WAN/LAN statistics, AP
radio performance, client connections, and more — all through standard PCP
tools like `pmrep`, `pmval`, `pmlogger`, and Grafana via `pmproxy`.

## What You Get

- **Per-port switch counters**: bytes, packets, errors, drops, broadcast,
  multicast, PoE power draw — for every port on every switch.
- **Device inventory**: model, firmware, uptime, temperature, adoption state.
- **Gateway metrics**: WAN traffic, latency, link state, CPU, memory.
- **AP radio stats**: channel, client count, retries, satisfaction.
- **Client tracking**: hostname, IP, MAC, signal, connected switch port.
- **Site aggregates**: station counts, WAN/LAN/WLAN traffic totals.
- **Controller health**: poll duration, error counts, software version.
- **DPI categories**: optional per-category traffic breakdowns.
- **Topology graphs**: `unifi2dot` companion tool exports DOT/JSON network maps.

## Quick Links

- [Getting Started](getting-started.md) — install and verify in 5 minutes
- [Configuration](configuration.md) — full config file reference
- [Metrics Reference](metrics.md) — every metric with type and description
- [Grafana Dashboards](grafana.md) — pre-built dashboards for pmproxy
- [Troubleshooting](troubleshooting.md) — common problems and fixes
