# pcp-pmda-unifi

A [Performance Co-Pilot](https://pcp.io) PMDA that exports Ubiquiti UniFi
network infrastructure metrics — switch ports, devices, gateways, APs,
clients, and more — through the standard PCP toolchain.

## Why

PCP already monitors your hosts. This PMDA extends that to your network
infrastructure so you can correlate switch port saturation with application
latency, track PoE power budgets, and spot flapping clients — all from
`pmrep`, `pmlogger`, or Grafana via `pmproxy`.

## What You Get

- **Per-port switch counters** — bytes, packets, errors, drops, PoE power
- **Device inventory** — model, firmware, uptime, temperature, adoption state
- **Gateway metrics** — WAN traffic, latency, CPU, memory
- **AP radio stats** — channel, client count, retries, satisfaction
- **Client tracking** — hostname, IP, signal, connected port (cardinality-capped)
- **Site aggregates** — station counts, WAN/LAN/WLAN traffic totals
- **Controller health** — poll duration, error counts, software version
- **DPI categories** — optional per-category traffic breakdowns
- **Topology graphs** — `unifi2dot` companion tool exports DOT/JSON network maps

## Quick Start

```bash
# Install PCP (if not already present)
sudo dnf install pcp python3-pcp          # RHEL/Fedora
sudo apt install pcp python3-pcp          # Debian/Ubuntu

# Install the PMDA
pip install pcp-pmda-unifi
sudo pcp-pmda-unifi-setup install

# Run the interactive installer
cd /var/lib/pcp/pmdas/unifi
sudo ./Install

# Verify
pminfo -f unifi.switch.port.rx_bytes
pmrep -t 5 unifi.switch.port.rx_bytes unifi.switch.port.tx_bytes
```

## Documentation

Full documentation is available at the [project docs site](docs/):

- [Getting Started](docs/getting-started.md) — install and verify in 5 minutes
- [Configuration](docs/configuration.md) — config file reference
- [Metrics Reference](docs/metrics.md) — every metric with type and semantics
- [Grafana Dashboards](docs/grafana.md) — pre-built dashboards for pmproxy
- [Architecture](docs/architecture.md) — design decisions and internals
- [Troubleshooting](docs/troubleshooting.md) — common problems and fixes

## Grafana Dashboards

Four pre-built dashboards ship in [`dashboards/`](dashboards/) for use with
`pmproxy` as a Grafana datasource. See the [Grafana guide](docs/grafana.md).

## License

GPL-2.0-or-later — same as PCP itself.
