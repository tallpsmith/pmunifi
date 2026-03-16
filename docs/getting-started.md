# Getting Started

## Prerequisites

- **PCP** installed on the target host (`pcp`, `pcp-libs-python` or `python3-pcp`)
- **Python 3.8+**
- Network access to a UniFi Controller running **Network Application 9.0+**
- A **UniFi API key** (generate at Network > Settings > Control Plane > Integrations)

### Installing PCP

=== "RHEL / CentOS / Fedora"

    ```bash
    sudo dnf install pcp pcp-libs-python
    sudo systemctl enable --now pmcd
    ```

=== "Ubuntu / Debian"

    ```bash
    sudo apt install pcp python3-pcp
    sudo systemctl enable --now pmcd
    ```

## Install from PyPI

```bash
pip install pcp-pmda-unifi
```

Deploy the PMDA files to `$PCP_PMDAS_DIR/unifi/`:

```bash
sudo pcp-pmda-unifi-setup install
```

## Interactive Setup

```bash
cd /var/lib/pcp/pmdas/unifi
sudo ./Install
```

The Install script will:

1. Prompt for controller URL and API key
2. Test connectivity and validate authentication
3. Discover available sites and let you choose which to monitor
4. Write `unifi.conf`
5. Register the PMDA with PMCD

## Non-Interactive Setup

For automation or containers, use environment variables:

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_API_KEY=your-api-key-here
export UNIFI_SITES=all
cd /var/lib/pcp/pmdas/unifi
sudo -E ./Install -e
```

## Verify Installation

```bash
# Check the PMDA is registered
pminfo unifi

# See all switch port metrics
pminfo -f unifi.switch.port.rx_bytes

# Watch per-port byte rates (5-second intervals)
pmrep -t 5 unifi.switch.port.rx_bytes unifi.switch.port.tx_bytes

# Check controller health
pmval unifi.controller.up

# View device inventory
pminfo -f unifi.device.name
```

## Upgrade

To upgrade while preserving your existing `unifi.conf`:

```bash
pip install --upgrade pcp-pmda-unifi
sudo pcp-pmda-unifi-setup install
cd /var/lib/pcp/pmdas/unifi
sudo ./Install -u
```

## Remove

```bash
cd /var/lib/pcp/pmdas/unifi
sudo ./Remove
```

This deregisters the PMDA from PMCD but preserves `unifi.conf`.
