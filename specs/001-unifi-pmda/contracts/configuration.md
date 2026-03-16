# Contract: Configuration File

**Type**: User → PMDA (INI file, read at startup)

## File Location

```
$PCP_PMDAS_DIR/unifi/unifi.conf
```

Ownership: `root:pcp`, mode `0640` (FR-024).

## Format

INI-style, parsed by Python `configparser` (case-sensitive keys).

## Sections

### `[global]`

| Key | Type | Default | Description |
|---|---|---|---|
| `poll_interval` | int | `30` | Seconds between poll cycles (minimum 10) |
| `max_clients` | int | `1000` | Soft cap on tracked clients (0 = unlimited) |
| `grace_period` | int | `300` | Seconds before pruning disappeared instances |
| `enable_dpi` | bool | `false` | Enable DPI category metrics |
| `log_level` | str | `warning` | Python logging level |

### `[controller:NAME]`

One or more sections, each defining a UniFi controller connection. `NAME` is used as the controller prefix in instance names.

| Key | Type | Required | Default | Description |
|---|---|---|---|---|
| `url` | str | yes | — | Controller base URL (e.g., `https://192.168.1.1`) |
| `api_key` | str | yes | — | UniFi API key |
| `sites` | str | no | `all` | Comma-separated site names, or `all` |
| `is_udm` | bool | no | `true` | Prepend `/proxy/network` to API paths |
| `verify_ssl` | bool | no | `true` | Verify SSL certificates |
| `ca_cert` | str | no | — | Path to custom CA certificate bundle |
| `poll_interval` | int | no | global | Per-controller poll interval override |

## Environment Variable Override (FR-006)

For non-interactive installation (`./Install -e`):

| Env Var | Maps To |
|---|---|
| `UNIFI_URL` | `[controller:default].url` |
| `UNIFI_API_KEY` | `[controller:default].api_key` |
| `UNIFI_SITES` | `[controller:default].sites` |
| `UNIFI_IS_UDM` | `[controller:default].is_udm` |
| `UNIFI_VERIFY_SSL` | `[controller:default].verify_ssl` |
| `UNIFI_POLL_INTERVAL` | `[global].poll_interval` |

## Validation Rules

- `url` MUST start with `https://` (or `http://` for testing)
- `api_key` MUST be non-empty
- `poll_interval` MUST be >= 10
- `max_clients` MUST be >= 0
- `grace_period` MUST be >= 0
- At least one `[controller:*]` section MUST exist
- `NAME` in `[controller:NAME]` MUST be alphanumeric + hyphens only
- `sites` value `all` is the literal string; otherwise comma-separated site slugs

## Command-Line Options

The PMDA supports standard PCP command-line flags:

| Flag | Description | Default |
|---|---|---|
| `-d domain` | PMDA domain number | From `domain.h` |
| `-l logfile` | Log file path | `$PCP_LOG_DIR/pmcd/unifi.log` |
| `-c configfile` | Configuration file path | `$PCP_PMDAS_DIR/unifi/unifi.conf` |
| `-U username` | Run as this user | `pcp` |
| `-r refresh` | Override refresh interval (seconds) | `30` |

Command-line values override configuration file values where applicable.

## Install Script Modes

| Mode | Invocation | Behaviour |
|---|---|---|
| Interactive | `./Install` | Prompts for URL, API key, site selection; validates; writes config |
| Non-interactive | `./Install -e` | Reads from environment variables; no prompts |
| Upgrade | `./Install -u` | Preserves existing `unifi.conf`; updates code, PMNS, help text; re-registers with PMCD |

## Example

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
