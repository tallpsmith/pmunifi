# Contract: PCP Metric Interface

**Type**: PMDA ↔ PCP tools (pmval, pmrep, pminfo, Grafana via pmproxy)

The PMDA exposes metrics via the PCP PMDA protocol. PCP tools consume these metrics through PMCD. This contract defines what consumers can depend on.

## Metric Naming

All metrics live under the `unifi` namespace:

```
unifi.<entity>.<field>
unifi.<entity>.<sub-entity>.<field>
```

Examples:
- `unifi.switch.port.rx_bytes`
- `unifi.site.num_sta`
- `unifi.controller.up`

**Stability guarantee**: Metric names are stable within a major version. Metrics may be added in minor versions. Removal requires a major version bump.

## Instance Domain Naming

Instance names use hierarchical `/` separators with `::` delimiting the sub-entity:

```
{controller}/{site}/{device}::Port{N}    # switch_port indom
{controller}/{site}/{device}::{radio}    # ap_radio indom
{controller}/{site}/{device}              # device indom
{controller}/{site}/{device}              # gateway indom (ugw/udm devices only)
{controller}/{site}                       # site indom
{controller}                              # controller indom
{controller}/{site}/{hostname_or_mac}     # client indom
{controller}/{site}/{category}            # dpi_category indom
```

Examples:
- `main/default/USW-Pro-48-Rack1::Port24`
- `main/default/UAP-AC-Pro-Lobby::na`
- `main/default`
- `main`

**Stability guarantee**: Instance name format is stable. Instance *values* are dynamic (devices appear/disappear).

## Semantic Contract

| Semantic | Meaning for Consumers |
|---|---|
| `PM_SEM_COUNTER` | Value increases monotonically. Tools compute rate (Δvalue/Δtime). Counter resets (device reboot) are handled by PCP. |
| `PM_SEM_INSTANT` | Value is meaningful only at fetch time. No interpolation. |
| `PM_SEM_DISCRETE` | Value changes infrequently. Tools carry forward the last known value. |

## Type Contract

| Type | Metrics |
|---|---|
| `PM_TYPE_U64` | All byte/packet/error/drop counters, uptime, last_poll timestamp |
| `PM_TYPE_U32` | Integer instant values (num_sta, speed, state, port_idx, boolean flags) |
| `PM_TYPE_S32` | Signed instant values (signal dBm) |
| `PM_TYPE_FLOAT` | PoE measurements (power, voltage, current), temperature, CPU/mem %, poll_duration_ms |
| `PM_TYPE_STRING` | Metadata (hostname, model, firmware, MAC, IP, OUI, poe_class, site status, WAN IP) |

## Units Contract

| Unit | Metrics |
|---|---|
| `PM_SPACE_BYTE` | All `*_bytes` counters |
| `PM_TIME_SEC` | uptime |
| `PM_TIME_MSEC` | poll_duration_ms |
| dimensionless | counts, booleans, percentages, string metadata |

## Label Contract

Every instance carries labels (JSON key-value pairs) as defined in the data model. Consumers can filter and group by label values. Label keys are stable within a major version.

## Error Behaviour

| Condition | PMDA Response |
|---|---|
| Controller unreachable | Serve last successful snapshot. `unifi.controller.up` = 0. |
| Unknown metric requested | Return `PM_ERR_PMID` |
| Unknown instance requested | Return `PM_ERR_INST` |
| No data yet (startup) | Return `PM_ERR_AGAIN` |
| Field not applicable (e.g., signal for wired client, temperature on unsupported device) | Return `PM_ERR_VALUE` |

## Fetch Performance

- Target: < 4 seconds for full fetch at 2,400 switch port instances
- The fetch callback performs zero network I/O — reads from in-memory snapshot only
- Fetch performance is bounded by instance count × per-instance lookup time
