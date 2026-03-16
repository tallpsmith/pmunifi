# Quickstart: UniFi PCP PMDA

## Prerequisites

- PCP installed (`pcp`, `pcp-libs-python` / `python3-pcp`)
- Python 3.8+
- Network access to a UniFi Controller running Network Application 9.0+
- A UniFi API key (generate at Network > Settings > Control Plane > Integrations)

## Install from PyPI

```bash
# Install the package
pip install pcp-pmda-unifi

# Deploy PMDA files to $PCP_PMDAS_DIR/unifi/
sudo pcp-pmda-unifi-setup install

# Run the interactive installer
cd /var/lib/pcp/pmdas/unifi
sudo ./Install
```

The Install script will:
1. Prompt for controller URL and API key
2. Test connectivity and validate authentication
3. Discover available sites and let you choose which to monitor
4. Write `unifi.conf`
5. Register the PMDA with PMCD

## Non-Interactive Install

```bash
export UNIFI_URL=https://192.168.1.1
export UNIFI_API_KEY=your-api-key-here
export UNIFI_SITES=all
cd /var/lib/pcp/pmdas/unifi
sudo -E ./Install -e
```

## Verify

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

## Companion Tool: unifi2dot

```bash
# Generate DOT topology graph
unifi2dot --url https://192.168.1.1 --api-key YOUR_KEY --site default -o network.dot

# Generate JSON graph
unifi2dot --url https://192.168.1.1 --api-key YOUR_KEY --site default --format json -o network.json

# Render with Graphviz
dot -Tpng network.dot -o network.png
```

## Remove

```bash
cd /var/lib/pcp/pmdas/unifi
sudo ./Remove
```

This deregisters the PMDA from PMCD but preserves `unifi.conf`.

## Development Setup

```bash
git clone https://github.com/you/pcp-pmda-unifi.git
cd pcp-pmda-unifi
pip install -e ".[dev]"
pytest -m "not e2e"
```
