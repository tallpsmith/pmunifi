# Grafana Dashboards

Pre-built Grafana dashboards are included in the `dashboards/` directory.
They connect to PCP via the `pmproxy` datasource.

## Prerequisites

- **Grafana** 9.0+ with the
  [PCP plugin](https://grafana.com/grafana/plugins/performancecopilot-pcp-app/)
  installed
- **pmproxy** running on the PCP host (provides the REST API that Grafana
  queries)

### Start pmproxy

```bash
sudo systemctl enable --now pmproxy
```

By default, pmproxy listens on port 44322.

## Configure the Datasource

1. In Grafana, go to **Configuration > Data Sources > Add data source**
2. Search for **PCP Redis** (or **PCP Vector** for live metrics)
3. Set the URL to `http://<pcp-host>:44322`
4. Click **Save & Test**

!!! tip
    Use **PCP Redis** if you are logging metrics with `pmlogger` and want
    historical data. Use **PCP Vector** for live, real-time metrics only.

## Import Dashboards

1. In Grafana, go to **Dashboards > Import**
2. Click **Upload JSON file**
3. Select one of the dashboard files from `dashboards/`
4. Choose your PCP datasource
5. Click **Import**

## Available Dashboards

### Site Overview (`site-overview.json`)

Top-level view of all monitored sites. Panels include:

- Controller health and poll status
- Site station counts (users, guests, APs, switches)
- WAN/LAN/WLAN aggregate traffic rates
- Device inventory table

### Switch Port Detail (`switch-port-detail.json`)

Deep dive into switch port metrics. Panels include:

- Per-port traffic rates (bytes/sec, packets/sec)
- Error and drop rates
- PoE power draw per port
- Link state and speed overview
- Top talker ports by throughput

### Client Insights (`client-insights.json`)

Connected client analysis. Panels include:

- Client count over time (wired vs wireless)
- Top clients by traffic
- Signal strength distribution (wireless clients)
- Client connection uptime

### AP Radio Performance (`ap-radio-performance.json`)

Wireless infrastructure health. Panels include:

- Per-radio client count
- Channel utilisation
- Transmit retries and drops
- Satisfaction scores by AP

## Docker Deployment

To run Grafana with the PCP plugin pre-installed:

```bash
docker run -d \
  --name grafana \
  -p 3000:3000 \
  -e GF_INSTALL_PLUGINS=performancecopilot-pcp-app \
  grafana/grafana:latest
```

Then configure the PCP datasource pointing at your pmproxy host.

## Tips

- **Rate conversion**: PCP COUNTER metrics are automatically converted to
  rates by the Grafana PCP plugin. You do not need to apply `rate()` or
  `irate()` — just query `unifi.switch.port.rx_bytes` directly.
- **Instance filtering**: Use PCP labels in Grafana queries to filter by
  site, device, or controller. For example, filter by
  `site_name="default"` to show only the default site.
- **Dashboard variables**: The pre-built dashboards include template
  variables for site, device, and controller selection.
