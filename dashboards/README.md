# Grafana Dashboards

Pre-built Grafana dashboards for pcp-pmda-unifi, designed to work with
[pmproxy](https://man7.org/linux/man-pages/man1/pmproxy.1.html) as a
Grafana datasource.

## Dashboards

| File | Description |
|------|-------------|
| `site-overview.json` | Top-level site health: device counts, WAN/LAN/WLAN traffic, station totals |
| `switch-port-detail.json` | Per-port traffic, errors, drops, PoE power draw for a selected switch |
| `client-insights.json` | Connected clients: signal strength, traffic, wired/wireless breakdown |
| `ap-radio-performance.json` | AP radio channels, retries, satisfaction scores, client counts |

## Import

1. Configure pmproxy as a Grafana datasource (see [Grafana guide](../docs/grafana.md))
2. In Grafana, go to **Dashboards > Import**
3. Upload or paste the JSON file

Each dashboard uses template variables for controller and site selection,
so they work out of the box with any pcp-pmda-unifi deployment.
