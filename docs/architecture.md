# Architecture

## Overview

The PMDA follows a producer-consumer architecture with strict separation
between network I/O (polling) and PCP metric serving (dispatch).

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│ UniFi       │ ──> │ Poller       │ ──> │ Snapshot      │
│ Controller  │HTTP │ Thread       │swap │ (immutable)   │
│ REST API    │     │ (per-ctrl)   │     │               │
└─────────────┘     └──────────────┘     └───────┬───────┘
                                                 │ read
                                         ┌───────┴───────┐
                                         │ PMDA Dispatch  │
                                         │ (main thread)  │
                                         │ fetch/label CB │
                                         └───────┬───────┘
                                                 │
                                         ┌───────┴───────┐
                                         │ PMCD          │
                                         │ pminfo/pmrep  │
                                         └───────────────┘
```

## Threading Model

### Poller Threads

One `ControllerPoller` thread per configured `[controller:NAME]` section.
Each thread:

1. Sleeps for `poll_interval` seconds
2. Makes HTTP requests to the UniFi REST API (stat/device, stat/sta,
   stat/health, stat/sysinfo, optionally stat/sitedpi)
3. Parses responses into typed dataclasses
4. Builds a complete `Snapshot` object
5. Atomically swaps the snapshot reference via Python assignment

The poller never touches PCP APIs. It only writes to a single shared
reference that the dispatch thread reads.

### Dispatch Thread (Main Thread)

The PMDA main thread runs inside PMCD's process management. It handles:

- `fetch` callbacks: read the current snapshot, look up the requested
  metric and instance, return the value
- `instance` callbacks: enumerate instance domain members from the snapshot
- `label` callbacks: return PCP labels for filtering and grouping

The dispatch thread does **zero network I/O**. Every fetch completes from
in-memory data. This is a hard architectural constraint — PMCD will kill
an agent that blocks its dispatch thread.

## Copy-on-Write Snapshots

The `Snapshot` dataclass is immutable once published. The poller builds
a new snapshot each cycle and replaces the reference. The old snapshot
is garbage collected when no fetch callback holds a reference to it.

```python
# Poller thread (writes)
self._snapshot = new_snapshot   # atomic reference swap

# Dispatch thread (reads)
snap = self._snapshot           # grab reference — safe to read
value = snap.sites["default"].devices["aa:bb:cc"].ports[1].rx_bytes
```

This avoids locks entirely. The dispatch thread always sees a consistent
point-in-time view, even if a poll is in progress.

## Snapshot Structure

```
Snapshot (immutable once published)
├── timestamp: float
├── controller_name: str
├── controller_version: str
├── sites: dict[str, SiteData]
│   └── SiteData
│       ├── health: HealthData
│       ├── devices: dict[str, DeviceData]
│       │   └── DeviceData
│       │       ├── meta: DeviceMeta
│       │       ├── ports: dict[int, PortData]
│       │       ├── radios: list[RadioData]
│       │       └── gateway: GatewayData | None
│       ├── clients: list[ClientData]
│       └── dpi_categories: list[DpiData]
├── devices_discovered: int
├── clients_discovered: int
└── sites_polled: int
```

## Instance Domains

PCP instance domains group related metric instances. Each domain gets a
serial number scoped to the PMDA's domain number.

| ID | Name | Represents | Naming Pattern |
|----|------|-----------|----------------|
| 0 | site | Monitored UniFi sites | `controller/site` |
| 1 | device | Adopted network devices | `controller/site/device_name` |
| 2 | switch_port | Physical switch ports | `controller/site/device::PortN` |
| 3 | client | Connected network clients | `controller/site/hostname` |
| 4 | ap_radio | AP radio interfaces | `controller/site/device::radio` |
| 5 | gateway | Gateway/router devices | `controller/site/device` |
| 6 | controller | Configured controllers | `controller_name` |
| 7 | dpi_category | DPI traffic categories | `controller/site/category` |

Instance IDs are managed by `pmdaCache` with dict-based storage, providing
persistent ID assignment across PMDA restarts.

## Grace Period and Pruning

Devices and clients that disappear from poll results are not immediately
removed from instance domains. They remain visible (with their last known
values) for `grace_period` seconds (default 300). After that, they are
pruned from the cache.

This prevents metric discontinuities during brief network hiccups or
device reboots.

## PCP Integration Points

- **PMNS**: Static namespace registered at PMDA startup. Metric names
  follow `unifi.<category>.<metric>` dotted notation.
- **Help text**: One-line and long-form help strings for `pminfo -T`.
- **Labels**: Instance-level labels for Grafana filtering (`controller_name`,
  `site_name`, `device_mac`, etc.).
- **Domain number**: Allocated from `domain.h`, assigned by the Install
  script.

## Module Responsibilities

| Module | Responsibility |
|--------|---------------|
| `pmda.py` | Metric registration, fetch/instance/label callbacks |
| `collector.py` | HTTP requests to UniFi API, response parsing |
| `poller.py` | Background thread scheduling, snapshot assembly |
| `snapshot.py` | Immutable dataclass definitions |
| `config.py` | INI config parsing, validation, env var override |
| `instances.py` | Instance naming, grace period tracking, cardinality caps |
| `topology.py` | Graph discovery from device uplink tables |
| `cli.py` | `unifi2dot` CLI entry point |
| `setup.py` | `pcp-pmda-unifi-setup` deployment entry point |
