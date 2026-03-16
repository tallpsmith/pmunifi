# pmrep Views Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a `pmrep-unifi.conf` file containing eleven named view sections for CLI monitoring of UniFi infrastructure, installed alongside the existing PMDA deploy artifacts.

**Architecture:** Single INI config file using standard pmrep.conf(5) compact metricspec syntax. Each view is a `[section]` with per-section option overrides for rate views. The file is packaged as deploy data and installed to `/etc/pcp/pmrep/` during `pcp-pmda-unifi-setup install`.

**Tech Stack:** pmrep.conf(5) INI format, Python (setup.py changes), pytest

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `src/pcp_pmda_unifi/deploy/pmrep-unifi.conf` | pmrep view definitions (11 sections) |
| Modify | `src/pcp_pmda_unifi/setup.py` | Install conf to `/etc/pcp/pmrep/` during deploy |
| Create | `tests/unit/test_pmrep_conf.py` | Validate conf structure, sections, metric names |
| Modify | `tests/integration/test_deploy.py` | Verify deploy copies pmrep conf to target |

---

## Chunk 1: Config File and Unit Tests

### Task 1: Write unit tests for pmrep conf structure

**Files:**
- Create: `tests/unit/test_pmrep_conf.py`

These tests validate the conf file as a static artifact — parsing it as INI,
checking section names exist, verifying metric references match the PMDA's
registered metrics, and confirming rate views have the correct overrides.

- [ ] **Step 1: Write test scaffolding and section name validation**

```python
"""Tests for pmrep-unifi.conf view definitions.

Validates the config file structure, section names, metric references,
and per-section option overrides without requiring PCP installation.
"""

import configparser
from pathlib import Path

import pytest

CONF_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "pcp_pmda_unifi"
    / "deploy"
    / "pmrep-unifi.conf"
)

EXPECTED_SECTIONS = [
    "unifi-health",
    "unifi-site",
    "unifi-site-traffic",
    "unifi-device-summary",
    "unifi-device-traffic",
    "unifi-switch-detail",
    "unifi-switch-traffic",
    "unifi-switch-ports",
    "unifi-ap-detail",
    "unifi-gateway-health",
    "unifi-gateway-traffic",
]

# Views that contain counter metrics and must show rates
RATE_VIEW_SECTIONS = [
    "unifi-site-traffic",
    "unifi-device-traffic",
    "unifi-switch-traffic",
    "unifi-switch-ports",
    "unifi-ap-detail",
    "unifi-gateway-traffic",
]

# Views that are one-shot snapshots
ONESHOT_SECTIONS = [
    "unifi-health",
    "unifi-site",
    "unifi-device-summary",
    "unifi-switch-detail",
    "unifi-gateway-health",
]


@pytest.fixture()
def conf():
    """Parse the pmrep-unifi.conf file."""
    assert CONF_PATH.exists(), f"Config file not found: {CONF_PATH}"
    parser = configparser.ConfigParser()
    parser.read(str(CONF_PATH))
    return parser


class TestConfStructure:
    """The conf file parses as valid INI with all expected sections."""

    def test_parses_as_valid_ini(self, conf):
        assert len(conf.sections()) > 0

    @pytest.mark.parametrize("section", EXPECTED_SECTIONS)
    def test_has_expected_section(self, conf, section):
        assert section in conf.sections(), f"Missing section: [{section}]"

    def test_has_exactly_expected_sections(self, conf):
        view_sections = [s for s in conf.sections() if s != "options"]
        assert sorted(view_sections) == sorted(EXPECTED_SECTIONS)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/unit/test_pmrep_conf.py -v`
Expected: FAIL — config file does not exist yet

- [ ] **Step 3: Write rate view override tests**

Append to `tests/unit/test_pmrep_conf.py`:

```python
class TestRateViewOverrides:
    """Rate views must override samples and interval for meaningful output."""

    @pytest.mark.parametrize("section", RATE_VIEW_SECTIONS)
    def test_rate_view_has_samples_2(self, conf, section):
        assert conf.get(section, "samples") == "2", (
            f"[{section}] must set samples = 2 for rate conversion"
        )

    @pytest.mark.parametrize("section", RATE_VIEW_SECTIONS)
    def test_rate_view_has_interval_5s(self, conf, section):
        assert conf.get(section, "interval") == "5s", (
            f"[{section}] must set interval = 5s"
        )

    @pytest.mark.parametrize("section", ONESHOT_SECTIONS)
    def test_oneshot_view_has_samples_1(self, conf, section):
        val = conf.get(section, "samples", fallback="1")
        assert val == "1", (
            f"[{section}] should default to samples = 1 (one-shot)"
        )
```

- [ ] **Step 4: Write metric name cross-reference tests**

Append to `tests/unit/test_pmrep_conf.py`:

```python
# All valid metric names from the PMDA — any key containing a dot in a
# view section is a metric reference (per pmrep.conf(5) spec).
VALID_METRIC_PREFIXES = (
    "unifi.controller.",
    "unifi.site.",
    "unifi.device.",
    "unifi.switch.port.",
    "unifi.ap.",
    "unifi.gateway.",
    "unifi.client.",
    "unifi.dpi.",
)

# Options that are NOT metrics (pmrep section-level settings)
PMREP_OPTIONS = {
    "header", "unitinfo", "globals", "timestamp", "samples", "interval",
    "delay", "type", "type_prefer", "ignore_incompat", "ignore_unknown",
    "instances", "live_filter", "rank", "colxrow", "width", "precision",
    "delimiter", "repeat_header", "dynamic_header", "separate_header",
    "instinfo", "omit_flat", "include_labels", "timefmt", "space_scale",
    "count_scale", "time_scale", "extheader", "fixed_header",
    "space_scale_force", "count_scale_force", "time_scale_force",
    "width_force", "precision_force", "names_change", "limit_filter",
    "limit_filter_force", "invert_filter", "predicate", "sort_metric",
    "overall_rank", "overall_rank_alt", "interpol", "source", "output",
    "speclocal", "derived", "version", "extcsv", "include_texts",
}


class TestMetricReferences:
    """Every metric key in a view section must be a valid PMDA metric name."""

    @pytest.mark.parametrize("section", EXPECTED_SECTIONS)
    def test_all_metric_keys_are_valid(self, conf, section):
        for key in conf.options(section):
            if key in PMREP_OPTIONS:
                continue
            # Compact form: key is the metric name (contains a dot)
            if "." not in key:
                continue
            assert any(key.startswith(p) for p in VALID_METRIC_PREFIXES), (
                f"[{section}] has unknown metric: {key}"
            )


class TestViewsUseColxrow:
    """All views should use colxrow for instance name as row label."""

    @pytest.mark.parametrize("section", EXPECTED_SECTIONS)
    def test_view_has_colxrow(self, conf, section):
        assert conf.has_option(section, "colxrow"), (
            f"[{section}] should set colxrow for instance-as-row output"
        )


class TestViewsDisableGlobals:
    """All views should set globals = no to avoid mixing in unrelated metrics."""

    @pytest.mark.parametrize("section", EXPECTED_SECTIONS)
    def test_view_disables_globals(self, conf, section):
        assert conf.get(section, "globals") == "no", (
            f"[{section}] should set globals = no"
        )
```

- [ ] **Step 5: Run all tests to confirm they fail**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/unit/test_pmrep_conf.py -v`
Expected: FAIL — config file still does not exist

- [ ] **Step 6: Commit test file**

```bash
git add tests/unit/test_pmrep_conf.py
git commit -m "Add unit tests for pmrep view config structure

Validate INI parsing, section names, rate view overrides,
metric name cross-references, and colxrow/globals settings."
```

### Task 2: Create the pmrep-unifi.conf file

**Files:**
- Create: `src/pcp_pmda_unifi/deploy/pmrep-unifi.conf`

Write the full config file using pmrep.conf(5) compact metricspec format.
The compact form is: `metric.name = label,instances,unit,type,width`
where trailing empty fields can be omitted.

Per the system pmrep configs (e.g., `vmstat.conf`), each section sets its
own display options (`header`, `unitinfo`, `globals`, `timestamp`, `colxrow`).

- [ ] **Step 1: Write the config file**

```ini
#
# pmrep(1) configuration file for UniFi PMDA - see pmrep.conf(5)
#
# Views for CLI monitoring of UniFi network infrastructure.
# Usage: pmrep :unifi-site
#        pmrep :unifi-switch-ports -i ".*USW-Pro-48.*"
#        pmrep -t 5s :unifi-site-traffic   (override interval)
#

# Compact metric specifications are of form (see pmrep(1)):
#pcp.metric.name = label,instances,unit/scale,type,width,precision,limit


#
# 1. PMDA & Controller Health (one-shot)
#
[unifi-health]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 1
colxrow = "Controller"
unifi.controller.up              = Up,,,,4
unifi.controller.version         = Version,,,,12
unifi.controller.poll_duration_ms = Poll ms,,,,8
unifi.controller.poll_errors     = Errors,,,,8
unifi.controller.last_poll       = Last Poll,,,,12
unifi.controller.sites_polled    = Sites,,,,6
unifi.controller.devices_discovered = Devices,,,,8
unifi.controller.clients_discovered = Clients,,,,8


#
# 2. Site Status & Counts (one-shot)
#
[unifi-site]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 1
colxrow = "Site"
unifi.site.status    = Status,,,,10
unifi.site.num_ap    = APs,,,,4
unifi.site.num_sw    = Switches,,,,8
unifi.site.num_gw    = Gateways,,,,8
unifi.site.num_sta   = Clients,,,,8
unifi.site.num_user  = Users,,,,6
unifi.site.num_guest = Guests,,,,6


#
# 3. Site Throughput (rate — 2 samples, 5s interval)
#
[unifi-site-traffic]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 2
interval = 5s
colxrow = "Site"
unifi.site.wan.rx_bytes  = WAN RX,,KB,,10
unifi.site.wan.tx_bytes  = WAN TX,,KB,,10
unifi.site.lan.rx_bytes  = LAN RX,,KB,,10
unifi.site.lan.tx_bytes  = LAN TX,,KB,,10
unifi.site.wlan.rx_bytes = WLAN RX,,KB,,10
unifi.site.wlan.tx_bytes = WLAN TX,,KB,,10


#
# 4. All Devices Triage (one-shot)
#
[unifi-device-summary]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 1
colxrow = "Device"
unifi.device.name         = Name,,,,20
unifi.device.type         = Type,,,,5
unifi.device.model        = Model,,,,16
unifi.device.ip           = IP,,,,16
unifi.device.state        = State,,,,6
unifi.device.uptime       = Uptime,,,,10
unifi.device.user_num_sta = Users,,,,6
unifi.device.guest_num_sta = Guests,,,,6
unifi.device.temperature  = Temp,,,,6
unifi.device.version      = Version,,,,12


#
# 5. Per-Device Throughput (rate — 2 samples, 5s interval)
#
[unifi-device-traffic]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 2
interval = 5s
colxrow = "Device"
unifi.device.name     = Name,,,,20
unifi.device.type     = Type,,,,5
unifi.device.rx_bytes = RX,,KB,,10
unifi.device.tx_bytes = TX,,KB,,10


#
# 6. Switch Status (one-shot)
#    Usage: pmrep :unifi-switch-detail -i ".*USW.*"
#
[unifi-switch-detail]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 1
colxrow = "Device"
unifi.device.name         = Name,,,,20
unifi.device.model        = Model,,,,16
unifi.device.state        = State,,,,6
unifi.device.uptime       = Uptime,,,,10
unifi.device.num_ports    = Ports,,,,6
unifi.device.user_num_sta = Users,,,,6
unifi.device.temperature  = Temp,,,,6


#
# 7. Switch Aggregate Throughput (rate — 2 samples, 5s interval)
#    Usage: pmrep :unifi-switch-traffic -i ".*USW.*"
#
[unifi-switch-traffic]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 2
interval = 5s
colxrow = "Device"
unifi.device.name     = Name,,,,20
unifi.device.rx_bytes = RX,,KB,,10
unifi.device.tx_bytes = TX,,KB,,10


#
# 8. Per-Port Troubleshooting (rate — 2 samples, 5s interval)
#    Usage: pmrep :unifi-switch-ports -i ".*USW-Pro-48.*"
#
[unifi-switch-ports]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 2
interval = 5s
colxrow = "Port"
unifi.switch.port.up           = Up,,,,3
unifi.switch.port.speed        = Speed,,,,6
unifi.switch.port.full_duplex  = Dplx,,,,5
unifi.switch.port.rx_bytes     = RX,,KB,,10
unifi.switch.port.tx_bytes     = TX,,KB,,10
unifi.switch.port.rx_packets   = RX Pkt,,,,10
unifi.switch.port.tx_packets   = TX Pkt,,,,10
unifi.switch.port.rx_errors    = RX Err,,,,8
unifi.switch.port.tx_errors    = TX Err,,,,8
unifi.switch.port.rx_dropped   = RX Drop,,,,8
unifi.switch.port.tx_dropped   = TX Drop,,,,8
unifi.switch.port.mac_count    = MACs,,,,6
unifi.switch.port.satisfaction = Satis,,,,6
unifi.switch.port.poe.power    = PoE W,,,,6


#
# 9. AP Radio Performance (rate — 2 samples, 5s interval)
#    Usage: pmrep :unifi-ap-detail -i ".*LobbyAP.*"
#
[unifi-ap-detail]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 2
interval = 5s
colxrow = "Radio"
unifi.ap.radio_type  = Radio,,,,6
unifi.ap.channel     = Chan,,,,5
unifi.ap.num_sta     = Clients,,,,8
unifi.ap.rx_bytes    = RX,,KB,,10
unifi.ap.tx_bytes    = TX,,KB,,10
unifi.ap.tx_dropped  = TX Drop,,,,8
unifi.ap.tx_retries  = TX Retry,,,,9
unifi.ap.satisfaction = Satis,,,,6


#
# 10. Gateway Status & Resources (one-shot)
#
[unifi-gateway-health]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 1
colxrow = "Gateway"
unifi.gateway.wan_ip      = WAN IP,,,,16
unifi.gateway.wan_up      = WAN Up,,,,6
unifi.gateway.wan_speed   = Speed,,,,6
unifi.gateway.wan_latency = Latency,,,,8
unifi.gateway.cpu         = CPU,,,,6
unifi.gateway.mem         = Mem,,,,6
unifi.gateway.temperature = Temp,,,,6
unifi.gateway.uptime      = Uptime,,,,10


#
# 11. Gateway Throughput & Errors (rate — 2 samples, 5s interval)
#
[unifi-gateway-traffic]
header = yes
unitinfo = yes
globals = no
timestamp = yes
samples = 2
interval = 5s
colxrow = "Gateway"
unifi.gateway.wan_rx_bytes   = WAN RX,,KB,,10
unifi.gateway.wan_tx_bytes   = WAN TX,,KB,,10
unifi.gateway.wan_rx_errors  = WAN RX Err,,,,10
unifi.gateway.wan_tx_errors  = WAN TX Err,,,,10
unifi.gateway.wan_rx_dropped = WAN RX Drop,,,,12
unifi.gateway.wan_tx_dropped = WAN TX Drop,,,,12
unifi.gateway.lan_rx_bytes   = LAN RX,,KB,,10
unifi.gateway.lan_tx_bytes   = LAN TX,,KB,,10
```

- [ ] **Step 2: Run unit tests to verify they pass**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/unit/test_pmrep_conf.py -v`
Expected: All tests PASS

- [ ] **Step 3: Run ruff to check for any issues**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi/src && ruff check .`
Expected: No new errors (conf file is not Python, ruff ignores it)

- [ ] **Step 4: Commit the config file**

```bash
git add src/pcp_pmda_unifi/deploy/pmrep-unifi.conf
git commit -m "Add pmrep view definitions for UniFi monitoring

Eleven named views covering controller health, site status,
device triage, switch ports, AP radios, and gateway health.
Rate views default to 2 samples at 5s for meaningful output."
```

---

## Chunk 2: Deploy Integration and Documentation

### Task 3: Write integration test for deploy installing pmrep conf

**Files:**
- Modify: `tests/integration/test_deploy.py`

The existing `TestDeployToPmdasDir` tests verify that `deploy_to_pmdas_dir()`
copies artifacts to a target dir. We need a new test class to verify the
pmrep conf is also installed.

- [ ] **Step 1: Write failing integration test**

Add to `tests/integration/test_deploy.py`:

```python
class TestDeployPmrepConf:
    """deploy_to_pmdas_dir also installs pmrep-unifi.conf to the pmrep config dir."""

    def test_installs_pmrep_conf(self, tmp_path):
        """pmrep conf should be copied to the pmrep config directory."""
        pmdas_dir = tmp_path / "pmdas" / "unifi"
        pmrep_dir = tmp_path / "pmrep"
        pmrep_dir.mkdir(parents=True)

        deploy_to_pmdas_dir(pmdas_dir, pmrep_conf_dir=pmrep_dir)

        conf_file = pmrep_dir / "pmrep-unifi.conf"
        assert conf_file.exists(), "pmrep-unifi.conf not installed"

    def test_pmrep_conf_is_valid_ini(self, tmp_path):
        """Installed pmrep conf should parse as valid INI."""
        pmdas_dir = tmp_path / "pmdas" / "unifi"
        pmrep_dir = tmp_path / "pmrep"
        pmrep_dir.mkdir(parents=True)

        deploy_to_pmdas_dir(pmdas_dir, pmrep_conf_dir=pmrep_dir)

        parser = configparser.ConfigParser()
        parser.read(str(pmrep_dir / "pmrep-unifi.conf"))
        assert "unifi-health" in parser.sections()

    def test_skips_pmrep_install_when_dir_missing(self, tmp_path):
        """If pmrep_conf_dir is None, skip pmrep conf installation."""
        pmdas_dir = tmp_path / "pmdas" / "unifi"
        deploy_to_pmdas_dir(pmdas_dir, pmrep_conf_dir=None)
        # Should not raise — just skips pmrep install
        assert pmdas_dir.exists()
```

Also add `import configparser` to the test file imports.

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/integration/test_deploy.py::TestDeployPmrepConf -v`
Expected: FAIL — `deploy_to_pmdas_dir()` doesn't accept `pmrep_conf_dir` yet

- [ ] **Step 3: Commit the failing test**

```bash
git add tests/integration/test_deploy.py
git commit -m "Add integration tests for pmrep conf deployment

Tests verify pmrep-unifi.conf is installed to the pmrep config
directory during deploy, and gracefully skipped when dir is None."
```

### Task 4: Update setup.py to install pmrep conf during deploy

**Files:**
- Modify: `src/pcp_pmda_unifi/setup.py`

Add `pmrep_conf_dir` parameter to `deploy_to_pmdas_dir()` and a helper to
copy the pmrep conf file. The default value auto-detects `/etc/pcp/pmrep/`
via `$PCP_SYSCONF_DIR` (consistent with PCP's own config discovery).

- [ ] **Step 1: Add pmrep conf install to deploy_to_pmdas_dir**

In `setup.py`, update `deploy_to_pmdas_dir` signature:

```python
def deploy_to_pmdas_dir(
    target_dir: Path,
    pmrep_conf_dir: Optional[Path] = ...,
) -> None:
```

Where `...` is a sentinel meaning "auto-detect". The auto-detection logic:

```python
_UNSET = object()

def deploy_to_pmdas_dir(target_dir: Path, pmrep_conf_dir: object = _UNSET) -> None:
    """Copy deploy artifacts and generate the launcher script.

    This is the core of `pcp-pmda-unifi-setup install`.  Separated from
    main() so integration tests can call it with a tmp_path.
    """
    target_dir.mkdir(parents=True, exist_ok=True)

    _copy_deploy_artifacts(target_dir)
    _generate_launcher(target_dir)
    _set_executable_permissions(target_dir)
    _install_pmrep_conf(_resolve_pmrep_dir(pmrep_conf_dir))
```

Add the new functions:

```python
def _resolve_pmrep_dir(pmrep_conf_dir: object) -> Optional[Path]:
    """Determine the pmrep config directory.

    When called from tests, an explicit Path or None is passed.
    In production, auto-detects from PCP_SYSCONF_DIR.
    """
    if pmrep_conf_dir is not _UNSET:
        return pmrep_conf_dir  # type: ignore[return-value]
    sysconf = os.environ.get("PCP_SYSCONF_DIR", "/etc/pcp")
    candidate = Path(sysconf) / "pmrep"
    return candidate if candidate.is_dir() else None


def _install_pmrep_conf(pmrep_dir: Optional[Path]) -> None:
    """Copy pmrep-unifi.conf to the pmrep config directory."""
    if pmrep_dir is None:
        return
    source = _resource_files("pcp_pmda_unifi").joinpath("deploy", "pmrep-unifi.conf")
    dest = pmrep_dir / "pmrep-unifi.conf"
    dest.write_bytes(source.read_bytes())
```

Also add `from typing import Optional` to the imports if not already present.

- [ ] **Step 2: Run integration tests to verify they pass**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/integration/test_deploy.py -v`
Expected: All tests PASS (including existing tests — the signature change
must be backwards-compatible via the `_UNSET` sentinel default)

- [ ] **Step 3: Run full unit test suite to check for regressions**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/unit/ -v`
Expected: All tests PASS

- [ ] **Step 4: Run ruff**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi/src && ruff check .`
Expected: Clean

- [ ] **Step 5: Commit the setup.py changes**

```bash
git add src/pcp_pmda_unifi/setup.py
git commit -m "Install pmrep-unifi.conf to PCP pmrep config dir during deploy

Auto-detects /etc/pcp/pmrep/ via PCP_SYSCONF_DIR. Gracefully
skips if the directory doesn't exist (PCP not installed)."
```

### Task 5: Update install instructions to mention pmrep views

**Files:**
- Modify: `src/pcp_pmda_unifi/setup.py` (print message only)

- [ ] **Step 1: Add pmrep views to post-install instructions**

Update `_print_install_instructions` in `setup.py`:

```python
def _print_install_instructions(target: Path) -> None:
    """Tell the user what to do next after deploying files."""
    print(f"PMDA files deployed to {target}")
    print("")
    print("Next steps:")
    print(f"  cd {target}")
    print("  sudo ./Install")
    print("")
    print("For non-interactive install:")
    print("  sudo -E ./Install -e")
    print("")
    print("pmrep views available after install:")
    print("  pmrep :unifi-health          # PMDA/controller status")
    print("  pmrep :unifi-site            # Site overview")
    print("  pmrep :unifi-device-summary  # All devices")
    print("  pmrep :unifi-switch-ports -i '.*USW.*'  # Switch ports")
    print("  pmrep :unifi-ap-detail       # AP radios")
    print("  pmrep :unifi-gateway-health  # Gateway status")
```

- [ ] **Step 2: Run full test suite**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/ -v -m "not e2e"`
Expected: All tests PASS

- [ ] **Step 3: Commit**

```bash
git add src/pcp_pmda_unifi/setup.py
git commit -m "Show available pmrep views in post-install instructions"
```

### Task 6: Final verification

- [ ] **Step 1: Run full test suite**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m pytest tests/ -v -m "not e2e"`
Expected: All tests PASS

- [ ] **Step 2: Run ruff on entire src**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi/src && ruff check .`
Expected: Clean

- [ ] **Step 3: Verify conf file is included in package build**

Run: `cd /Volumes/My\ Shared\ Files/pmunfi && python -m build --wheel 2>&1 | tail -5 && unzip -l dist/*.whl | grep pmrep`
Expected: `pmrep-unifi.conf` appears in the wheel contents under `pcp_pmda_unifi/deploy/`

- [ ] **Step 4: Final commit if any cleanup needed, then done**
