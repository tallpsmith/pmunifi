# Metrics Reference

All metrics live under the `unifi.*` namespace. They are grouped into
clusters, each backed by a PCP instance domain.

## Namespace Tree

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
│   ├── num_ports             [DISCRETE]  indom:device
│   ├── uptime_display        [INSTANT,STRING]  indom:device
│   └── state_display         [INSTANT,STRING]  indom:device
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
│   ├── last_seen             [INSTANT]   indom:client
│   ├── uptime_display        [INSTANT,STRING]  indom:client
│   └── last_seen_display     [INSTANT,STRING]  indom:client
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
│   ├── temperature           [INSTANT]   indom:gateway
│   └── uptime_display        [INSTANT,STRING]  indom:gateway
├── controller
│   ├── up                    [INSTANT]   indom:controller
│   ├── poll_duration_ms      [INSTANT]   indom:controller
│   ├── poll_errors           [COUNTER]   indom:controller
│   ├── last_poll             [INSTANT]   indom:controller
│   ├── version               [DISCRETE]  indom:controller
│   ├── devices_discovered    [INSTANT]   indom:controller
│   ├── clients_discovered    [INSTANT]   indom:controller
│   ├── sites_polled          [INSTANT]   indom:controller
│   └── last_poll_display     [INSTANT,STRING]  indom:controller
└── dpi
    ├── rx_bytes              [COUNTER]   indom:dpi_category
    └── tx_bytes              [COUNTER]   indom:dpi_category
```

## Instance Domains

| ID | Name | Instance Naming | Example |
|----|------|-----------------|---------|
| 0 | site | `controller/site` | `main/default` |
| 1 | device | `controller/site/device_name` | `main/default/USW-Pro-48-Rack1` |
| 2 | switch_port | `controller/site/device_name::PortN` | `main/default/USW-Pro-48-Rack1::Port1` |
| 3 | client | `controller/site/hostname_or_mac` | `main/default/laptop-alice` |
| 4 | ap_radio | `controller/site/device_name::radio_type` | `main/default/UAP-AC-Pro-Lobby::na` |
| 5 | gateway | `controller/site/device_name` | `main/default/UDM-Pro` |
| 6 | controller | `controller_name` | `main` |
| 7 | dpi_category | `controller/site/category_name` | `main/default/Streaming` |

## Cluster Allocation

| Cluster | PMNS Prefix | Instance Domain |
|---------|-------------|-----------------|
| 0 | `unifi.site.*` | site |
| 1 | `unifi.device.*` | device |
| 2 | `unifi.switch.port.*` | switch_port |
| 3 | `unifi.switch.port.poe.*` | switch_port |
| 4 | `unifi.client.*` | client |
| 5 | `unifi.ap.*` | ap_radio |
| 6 | `unifi.gateway.*` | gateway |
| 7 | *(reserved)* | -- |
| 8 | `unifi.dpi.*` | dpi_category |
| 9 | `unifi.controller.*` | controller |

## Metric Semantics

- **COUNTER**: Monotonically increasing value. PCP tools automatically
  compute rates. All byte and packet counters use this semantic.
- **INSTANT**: Point-in-time value that can go up or down (e.g., CPU
  utilisation, link speed, station count).
- **DISCRETE**: Value that rarely changes (e.g., MAC address, model name,
  device type). PCP caches these aggressively.

## PCP Labels

Labels are attached at the instance level for filtering and grouping:

| Label Key | Applies To | Example |
|-----------|------------|---------|
| `agent` | Domain | `"unifi"` |
| `controller_name` | All instances | `"main"` |
| `controller_url` | All instances | `"https://192.168.1.1"` |
| `site_name` | site, device, port, client, ap, gateway, dpi | `"default"` |
| `device_mac` | device, port, gateway | `"aa:bb:cc:dd:ee:ff"` |
| `device_type` | device, port, gateway | `"usw"` |
| `device_model` | device, port, gateway | `"USW-Pro-48-PoE"` |
| `port_idx` | port | `1` |
