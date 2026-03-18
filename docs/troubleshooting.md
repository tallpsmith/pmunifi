# Troubleshooting

## Check PMDA Status

First, verify the PMDA is registered and responding:

```bash
# Is the PMDA registered with PMCD?
pminfo unifi

# Is the controller reachable?
pmval -s1 unifi.controller.up

# Any poll errors?
pmval -s1 unifi.controller.poll_errors

# When was the last successful poll?
pmval -s1 unifi.controller.last_poll_display
```

Check the PMDA log for detailed error messages:

```bash
cat $PCP_LOG_DIR/pmcd/unifi.log
```

Increase log verbosity by setting `log_level = debug` in `unifi.conf`
and restarting the PMDA:

```bash
cd /var/lib/pcp/pmdas/unifi
sudo ./Install -u
```

## Common Issues

### Connection Refused / Timeout

**Symptom**: `unifi.controller.up` returns 0, log shows connection errors.

**Causes**:

- Controller URL is wrong or unreachable from the PCP host
- UniFi Network Application is not running
- Firewall blocking access to the controller port (typically 443)

**Fix**: Verify the URL from the PCP host:

```bash
curl -k -s -o /dev/null -w "%{http_code}" https://192.168.1.1
```

### 401 Unauthorized

**Symptom**: Log shows `401` responses from the controller API.

**Causes**:

- API key is invalid, expired, or revoked
- API key was generated for a different controller

**Fix**: Generate a new API key at Network > Settings > Control Plane >
Integrations. Update `api_key` in `unifi.conf`.

### SSL Certificate Verify Failed

**Symptom**: Log shows `SSLError` or `CERTIFICATE_VERIFY_FAILED`.

**Causes**:

- Controller uses a self-signed certificate (common for UniFi)
- CA certificate is not in the system trust store

**Fix** (choose one):

1. Set `verify_ssl = false` in the controller section (least effort)
2. Provide a CA bundle: `ca_cert = /path/to/ca-bundle.pem`
3. Install the controller's certificate into the system trust store

### No Devices Found

**Symptom**: `pminfo -f unifi.device.name` returns no instances.

**Causes**:

- API key lacks permissions for the selected sites
- `sites` config value doesn't match the controller's site slugs
- Controller has no adopted devices

**Fix**: Verify site names. The `sites` config uses site *slugs*
(e.g., `default`), not display names (e.g., "Default Site"). Check
available sites:

```bash
curl -k -H "X-API-Key: YOUR_KEY" https://192.168.1.1/proxy/network/api/self/sites
```

### Stale Metrics (Values Not Updating)

**Symptom**: Metric values are frozen, `poll_duration_ms` not changing.

**Causes**:

- Poller thread has crashed or is stuck
- Controller is intermittently unreachable
- `poll_interval` is set very high

**Fix**: Check `unifi.controller.poll_errors` — a rising counter means
polls are failing. Review the PMDA log. Restart if needed:

```bash
cd /var/lib/pcp/pmdas/unifi
sudo ./Install -u
```

### Instances Disappearing Unexpectedly

**Symptom**: Devices or clients vanish from `pminfo -f` output, then reappear.

**Cause**: The `grace_period` (default 300 seconds) has expired for instances
that were absent from poll results.

**Fix**: If devices go offline during maintenance windows, increase the
grace period in `unifi.conf`:

```ini
[global]
grace_period = 900
```

### Missing PoE Metrics

**Symptom**: `unifi.switch.port.poe.power` returns `PM_ERR_VALUE` for some ports.

**Cause**: Not all switch ports support PoE. Non-PoE ports and ports where
PoE is disabled will not have PoE metrics.

**This is expected behaviour** — the PMDA returns `PM_ERR_VALUE` for metrics
that don't apply to a given instance.

### Missing Temperature Metrics

**Symptom**: `unifi.device.temperature` returns `PM_ERR_VALUE`.

**Cause**: Not all UniFi devices have temperature sensors. Older or
lower-end models may not report this value.

**This is expected behaviour.**

### High Memory Usage

**Symptom**: The PMDA process uses more memory than expected.

**Cause**: Large number of tracked clients. The default `max_clients`
is 1000 per controller.

**Fix**: Lower the cap in `unifi.conf`:

```ini
[global]
max_clients = 500
```

### PMDA Fails to Start

**Symptom**: `pminfo unifi` returns "Unknown metric name" after Install.

**Fix**: Check PMCD status and the PMDA log:

```bash
sudo systemctl status pmcd
cat $PCP_LOG_DIR/pmcd/unifi.log
```

Common causes:

- Missing Python dependency (`requests` not installed)
- PCP Python bindings not available (`pcp-libs-python` or `python3-pcp`
  package not installed)
- Syntax error in `unifi.conf`

### macOS: `ModuleNotFoundError: No module named 'pcp_pmda_unifi'`

**Symptom**: `sudo ./Install` fails with `ModuleNotFoundError` for
`pcp_pmda_unifi`.

**Cause**: The package was pip-installed into a virtual environment, but
`pmpython` (PCP's Python wrapper) resolves to the system Python which
can't see venv-installed packages.

**Fix**: Re-run `pcp-pmda-unifi-setup install` using the venv's Python.
The setup script detects the venv and records its site-packages path so
`pmpython` can find the module:

```bash
sudo /path/to/your/venv/bin/pcp-pmda-unifi-setup install
cd /var/lib/pcp/pmdas/unifi
sudo ./Install
```
