# Contract: UniFi API Client

**Type**: PMDA → UniFi Controller (HTTP REST API)

The PMDA's poller threads consume the UniFi Controller REST API to collect device, port, client, and site metrics. This contract defines the API surface the client depends on.

## Authentication

- Method: API key via `X-API-Key` HTTP header
- Requires: UniFi Network Application 9.0+
- No session management, no cookies, no login endpoint

```
X-API-Key: {api_key}
Accept: application/json
```

## Base URL Construction

```
# UniFi OS (UDM, UDR, UCG) — is_udm = true
https://{host}/proxy/network/api/s/{site}/...

# Standalone controller — is_udm = false
https://{host}/api/s/{site}/...

# Site listing (both)
https://{host}[/proxy/network]/api/self/sites
```

## Response Envelope

All endpoints return:

```json
{
  "meta": {"rc": "ok"},
  "data": [...]
}
```

- `meta.rc == "ok"` → success; iterate `data` array
- `meta.rc == "error"` → failure; `meta.msg` contains error description
- `data` is always an array, even for single-item responses

## Endpoints Consumed

### Site Discovery

```
GET /api/self/sites
→ data[]: {name, desc, _id, attr_hidden_id, attr_no_delete}
```

### Device Stats

```
GET /api/s/{site}/stat/device
→ data[]: {mac, name, ip, model, type, version, state, uptime, adopted,
           port_table[], uplink{}, radio_table[], system-stats{}}
```

### Client Stats

```
GET /api/s/{site}/stat/sta
→ data[]: {mac, hostname, ip, oui, is_wired, sw_mac, sw_port,
           rx_bytes, tx_bytes, rx_packets, tx_packets, uptime,
           signal, network, last_seen}
```

### Site Health

```
GET /api/s/{site}/stat/health
→ data[]: {subsystem, status, num_sta, num_user, num_guest,
           num_ap, num_sw, num_gw, wan_ip, latency,
           rx_bytes-r, tx_bytes-r, ...}
```

Subsystems: `wan`, `lan`, `wlan`, `vpn`. Each has a `status` field (`ok`, `warning`, `error`).

### System Info

```
GET /api/s/{site}/stat/sysinfo
→ data[]: {version, build, hostname, name, ip_addrs[], ...}
```

Polled at startup and every 300s. Provides `unifi.controller.version`.

### Port Configuration

```
GET /api/s/{site}/rest/portconf
→ data[]: {_id, name, port_security_mac_address[], ...}
```

Polled at startup and every 300s. Informational — used by Install script for site discovery context. Not directly mapped to metrics.

### DPI Stats (opt-in)

```
POST /api/s/{site}/stat/sitedpi
Body: {"type": "by_cat"}
→ data[]: {mac, by_cat[]: {cat, rx_bytes, tx_bytes, rx_packets, tx_packets}}
```

Polled every 300s when `enable_dpi = true`.

## Error Handling

| HTTP Status | Meaning | Client Action |
|---|---|---|
| 200 | Success | Parse `data` array |
| 401 | Invalid/revoked API key | Log error, set controller.up=0, retry next cycle |
| 403 | Insufficient permissions | Log error, set controller.up=0 |
| 404 | Endpoint not found / wrong path | Log error (likely is_udm misconfigured) |
| 429 | Rate limited | Log warning, back off, retry next cycle |
| 5xx | Server error | Log error, retain last snapshot, retry next cycle |
| Connection error | Controller unreachable | Log error, retain last snapshot, retry next cycle |

## SSL/TLS

- Default: `verify_ssl = true`
- Self-signed certificates: `verify_ssl = false` (with explicit opt-in)
- Custom CA bundle: `ca_cert = /path/to/ca-bundle.crt`

## Defensive Parsing

All field access uses `.get(field, default)` pattern:
- Missing counter fields default to `0`
- Missing string fields default to `""`
- Missing object fields (port_table, radio_table) default to `[]`
- Unknown/new fields are silently ignored

This protects against UniFi firmware updates changing the JSON schema.
