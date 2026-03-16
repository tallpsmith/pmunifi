# Configuration

The PMDA reads its configuration from an INI-style file at:

```
$PCP_PMDAS_DIR/unifi/unifi.conf
```

Ownership should be `root:pcp`, mode `0640` (the file contains API keys).
Parsed by Python `configparser` with case-sensitive keys.

## Global Section

```ini
[global]
poll_interval = 30
max_clients = 1000
grace_period = 300
enable_dpi = false
log_level = warning
```

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `poll_interval` | int | `30` | Seconds between poll cycles (minimum 10) |
| `max_clients` | int | `1000` | Soft cap on tracked clients (0 = unlimited) |
| `grace_period` | int | `300` | Seconds before pruning disappeared instances |
| `enable_dpi` | bool | `false` | Enable DPI category metrics |
| `log_level` | str | `warning` | Python logging level |

## Controller Sections

One or more `[controller:NAME]` sections. `NAME` is an alphanumeric
identifier (hyphens allowed) used as a prefix in instance names.

```ini
[controller:main]
url = https://192.168.1.1
api_key = abc123-your-api-key-here
sites = all
is_udm = true
verify_ssl = true
```

| Key | Type | Required | Default | Description |
|-----|------|----------|---------|-------------|
| `url` | str | yes | -- | Controller base URL |
| `api_key` | str | yes | -- | UniFi API key |
| `sites` | str | no | `all` | Comma-separated site names, or `all` |
| `is_udm` | bool | no | `true` | Prepend `/proxy/network` to API paths |
| `verify_ssl` | bool | no | `true` | Verify SSL certificates |
| `ca_cert` | str | no | -- | Path to custom CA certificate bundle |
| `poll_interval` | int | no | global | Per-controller poll interval override |

## Multi-Controller Example

```ini
[global]
poll_interval = 30
max_clients = 1000
grace_period = 300
enable_dpi = false

[controller:main]
url = https://192.168.1.1
api_key = abc123-your-api-key-here
sites = all
is_udm = true
verify_ssl = true

[controller:branch]
url = https://10.0.0.1
api_key = def456-branch-api-key
sites = warehouse,office
is_udm = false
verify_ssl = false
poll_interval = 60
```

## Environment Variable Override

For non-interactive installation (`./Install -e`), these environment
variables create a single `[controller:default]` section:

| Variable | Maps To |
|----------|---------|
| `UNIFI_URL` | `[controller:default].url` |
| `UNIFI_API_KEY` | `[controller:default].api_key` |
| `UNIFI_SITES` | `[controller:default].sites` |
| `UNIFI_IS_UDM` | `[controller:default].is_udm` |
| `UNIFI_VERIFY_SSL` | `[controller:default].verify_ssl` |
| `UNIFI_POLL_INTERVAL` | `[global].poll_interval` |

## Command-Line Options

The PMDA accepts standard PCP command-line flags that override config
file values:

| Flag | Description | Default |
|------|-------------|---------|
| `-d domain` | PMDA domain number | From `domain.h` |
| `-l logfile` | Log file path | `$PCP_LOG_DIR/pmcd/unifi.log` |
| `-c configfile` | Configuration file path | `$PCP_PMDAS_DIR/unifi/unifi.conf` |
| `-U username` | Run as this user | `pcp` |
| `-r refresh` | Override refresh interval (seconds) | `30` |

## Validation Rules

- `url` must start with `https://` (or `http://` for testing)
- `api_key` must be non-empty
- `poll_interval` must be >= 10
- `max_clients` must be >= 0
- `grace_period` must be >= 0
- At least one `[controller:*]` section must exist
- `NAME` in `[controller:NAME]` must be alphanumeric + hyphens only
- `sites` value `all` is a literal keyword; otherwise comma-separated site slugs

## Install Script Modes

| Mode | Invocation | Behaviour |
|------|------------|-----------|
| Interactive | `./Install` | Prompts for URL, API key, site selection; validates; writes config |
| Non-interactive | `./Install -e` | Reads from environment variables; no prompts |
| Upgrade | `./Install -u` | Preserves existing `unifi.conf`; updates code, PMNS, help text |
