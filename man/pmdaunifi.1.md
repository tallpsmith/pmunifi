pmdaunifi(1) -- UniFi network infrastructure PMDA for PCP
=========================================================

## NAME

pmdaunifi - Performance Metrics Domain Agent for UniFi network infrastructure

## SYNOPSIS

`$PCP_PMDAS_DIR/unifi/pmda_unifi.python` [`-d` *domain*] [`-l` *logfile*] [`-c` *config*] [`-U` *user*] [`-r` *refresh*]

## DESCRIPTION

**pmdaunifi** is a Performance Metrics Domain Agent (PMDA) that polls
Ubiquiti UniFi controllers via their REST API and exports network
infrastructure metrics through the PCP framework.

Metrics include per-port switch traffic counters, device inventory and
health, gateway WAN/LAN statistics, wireless access point radio
performance, connected client tracking, site-level aggregates, controller
operational health, and optional DPI traffic category breakdowns.

The PMDA uses background poller threads to fetch data from one or more
UniFi controllers. Each poll cycle builds an immutable snapshot that is
atomically swapped into the dispatch path, ensuring the PMCD fetch
callback never blocks on network I/O.

## CONFIGURATION

The configuration file uses INI format, parsed by Python `configparser`
with case-sensitive keys. The default location is:

    $PCP_PMDAS_DIR/unifi/unifi.conf

Ownership should be `root:pcp`, mode `0640`, since the file contains
API keys.

### Global Section

    [global]
    poll_interval = 30       # seconds between polls (minimum 10)
    max_clients = 1000       # soft cap on tracked clients (0 = unlimited)
    grace_period = 300       # seconds before pruning disappeared instances
    enable_dpi = false       # enable DPI category metrics
    log_level = warning      # Python logging level

### Controller Sections

One or more `[controller:NAME]` sections, where NAME is an alphanumeric
identifier (hyphens allowed) used as a prefix in instance names.

    [controller:main]
    url = https://192.168.1.1
    api_key = abc123-your-api-key-here
    sites = all              # comma-separated site names, or "all"
    is_udm = true            # prepend /proxy/network to API paths
    verify_ssl = true        # verify SSL certificates
    ca_cert =                # path to custom CA bundle (optional)
    poll_interval =          # per-controller override (optional)

### Environment Variable Override

For non-interactive installation (`./Install -e`):

| Variable             | Maps To                        |
|----------------------|--------------------------------|
| UNIFI_URL            | [controller:default].url       |
| UNIFI_API_KEY        | [controller:default].api_key   |
| UNIFI_SITES          | [controller:default].sites     |
| UNIFI_IS_UDM         | [controller:default].is_udm    |
| UNIFI_VERIFY_SSL     | [controller:default].verify_ssl|
| UNIFI_POLL_INTERVAL  | [global].poll_interval         |

## COMMAND LINE OPTIONS

`-d` *domain*
:   PMDA domain number (allocated from `domain.h`). Usually assigned
    automatically by the Install script.

`-l` *logfile*
:   Log file path. Default: `$PCP_LOG_DIR/pmcd/unifi.log`.

`-c` *config*
:   Configuration file path. Default: `$PCP_PMDAS_DIR/unifi/unifi.conf`.

`-U` *user*
:   Run the PMDA as this user. Default: `pcp`.

`-r` *refresh*
:   Override the poll refresh interval in seconds. Takes precedence over
    the config file `poll_interval` value.

## INSTALLATION

Install the Python package and deploy PMDA files:

    pip install pcp-pmda-unifi
    sudo pcp-pmda-unifi-setup install

Run the interactive installer:

    cd /var/lib/pcp/pmdas/unifi
    sudo ./Install

The Install script prompts for controller URL and API key, tests
connectivity, discovers available sites, writes `unifi.conf`, and
registers the PMDA with PMCD.

For non-interactive installation:

    export UNIFI_URL=https://192.168.1.1
    export UNIFI_API_KEY=your-api-key-here
    export UNIFI_SITES=all
    cd /var/lib/pcp/pmdas/unifi
    sudo -E ./Install -e

For upgrades (preserves existing configuration):

    cd /var/lib/pcp/pmdas/unifi
    sudo ./Install -u

## REMOVAL

    cd /var/lib/pcp/pmdas/unifi
    sudo ./Remove

This deregisters the PMDA from PMCD but preserves `unifi.conf`.

## METRICS

Metrics are organized into clusters, each backed by an instance domain.

### Cluster 0: Site (`unifi.site.*`)

Site-level aggregates including station counts, WAN/LAN/WLAN byte
counters, and user/guest breakdowns. Instance domain: site
(`controller/site`).

### Cluster 1: Device (`unifi.device.*`)

Device inventory: name, MAC, IP, model, type, firmware version, state,
uptime, adoption status, aggregate traffic, temperature, and connected
station counts. Instance domain: device (`controller/site/device`).

### Cluster 2: Switch Port (`unifi.switch.port.*`)

Per-port traffic counters (bytes, packets, errors, drops, broadcast,
multicast), link state, speed, duplex, uplink flag, satisfaction score,
and MAC count. Instance domain: switch_port
(`controller/site/device::PortN`).

### Cluster 3: Switch Port PoE (`unifi.switch.port.poe.*`)

Power-over-Ethernet metrics: enable, good, power (W), voltage (V),
current (mA), and PoE class. Instance domain: switch_port (shared with
cluster 2).

### Cluster 4: Client (`unifi.client.*`)

Connected client tracking: hostname, IP, MAC, OUI, wired/wireless flag,
connected switch port, traffic counters, uptime, signal strength,
network name, and last-seen timestamp. Instance domain: client
(`controller/site/hostname`).

### Cluster 5: AP Radio (`unifi.ap.*`)

Access point radio interfaces: channel, radio type (ng/na/ax/be),
traffic counters, transmit drops and retries, station count, and
satisfaction score. Instance domain: ap_radio
(`controller/site/device::radio`).

### Cluster 6: Gateway (`unifi.gateway.*`)

Gateway/router metrics: WAN IP, WAN traffic counters (bytes, packets,
drops, errors), WAN link state and speed, WAN latency, LAN aggregate
traffic, uptime, CPU utilisation, memory utilisation, and temperature.
Instance domain: gateway (`controller/site/device`).

### Cluster 8: DPI (`unifi.dpi.*`)

Deep packet inspection traffic categories (opt-in via `enable_dpi`):
rx_bytes and tx_bytes per category. Instance domain: dpi_category
(`controller/site/category`).

### Cluster 9: Controller (`unifi.controller.*`)

Controller operational health: reachability, poll duration, cumulative
poll errors, last successful poll timestamp, software version, and
discovery counts (devices, clients, sites). Instance domain: controller
(`controller_name`).

## FILES

`$PCP_PMDAS_DIR/unifi/`
:   PMDA installation directory containing the Python agent, Install and
    Remove scripts, PMNS, domain.h, and help text.

`$PCP_PMDAS_DIR/unifi/unifi.conf`
:   Configuration file (contains API keys — mode 0640, root:pcp).

`$PCP_LOG_DIR/pmcd/unifi.log`
:   PMDA log file. Verbosity controlled by `log_level` config option.

## ENVIRONMENT

`PCP_PMDAS_DIR`
:   Base directory for PMDA installations (typically `/var/lib/pcp/pmdas`).

`PCP_LOG_DIR`
:   Base directory for PCP log files (typically `/var/log/pcp`).

`UNIFI_URL`
:   Controller URL for non-interactive install.

`UNIFI_API_KEY`
:   API key for non-interactive install.

`UNIFI_SITES`
:   Comma-separated site list or "all" for non-interactive install.

`UNIFI_IS_UDM`
:   Set to "true" for UniFi Dream Machine controllers (non-interactive).

`UNIFI_VERIFY_SSL`
:   Set to "false" to skip SSL certificate verification (non-interactive).

`UNIFI_POLL_INTERVAL`
:   Poll interval override in seconds (non-interactive).

## DIAGNOSTICS

`Connection refused / timeout`
:   The controller URL is unreachable. Verify the URL and that the UniFi
    Network Application is running. Check firewall rules.

`401 Unauthorized`
:   The API key is invalid or has been revoked. Generate a new key at
    Network > Settings > Control Plane > Integrations.

`SSL certificate verify failed`
:   The controller uses a self-signed certificate. Either set
    `verify_ssl = false` in the config, provide a CA bundle via
    `ca_cert`, or install the certificate into the system trust store.

`No devices found`
:   The API key may lack permissions for the selected sites, or the
    controller has no adopted devices. Verify site names match the
    controller's site slugs (not display names).

`Stale metrics (values not updating)`
:   Check `unifi.controller.poll_errors` — a rising counter indicates
    failed poll cycles. Review `$PCP_LOG_DIR/pmcd/unifi.log` for details.
    The PMDA continues serving the last successful snapshot during
    transient failures.

`Instance disappeared unexpectedly`
:   Devices and clients are pruned after the `grace_period` (default
    300 seconds) of not appearing in poll results. Increase the grace
    period if devices go offline temporarily during maintenance windows.

## SEE ALSO

**pmcd**(1), **pminfo**(1), **pmrep**(1), **pmval**(1), **pmlogger**(1),
**PMDA**(3), **pmproxy**(1)

PCP Website: <https://pcp.io>
