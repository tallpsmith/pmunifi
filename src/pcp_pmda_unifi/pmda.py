"""PCP Performance Metrics Domain Agent for UniFi network infrastructure.

Exposes switch port counters, controller health, and (eventually) device,
client, AP, and gateway metrics via the PCP PMDA protocol.  All data is
served from in-memory snapshots built by background poller threads — the
fetch callback does zero network I/O.

The PCP Python bindings are optional at import time so that development
and testing can happen on machines without PCP installed.

Usage (launched by PMCD):
    python -c "from pcp_pmda_unifi.pmda import run; run()"
"""

import json
import logging
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from pcp_pmda_unifi.collector import UnifiClient
from pcp_pmda_unifi.config import PmdaConfig, parse_config
from pcp_pmda_unifi.instances import (
    controller_instance_name,
    switch_port_instance_name,
)
from pcp_pmda_unifi.poller import ControllerPoller
from pcp_pmda_unifi.snapshot import PortData, Snapshot

# ---------------------------------------------------------------------------
# Conditional PCP imports — missing on macOS dev machines
# ---------------------------------------------------------------------------

try:
    from pcp.pmda import PMDA, pmdaIndom, pmdaInstid, pmdaMetric
    from pcp import pmapi
    from cpmda import PMDA_FETCH_NOVALUES
    import cpmapi as c_api
    HAS_PCP = True
except ImportError:
    HAS_PCP = False

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Indom serial numbers (must match data-model.md)
# ---------------------------------------------------------------------------

INDOM_SWITCH_PORT = 2
INDOM_CONTROLLER = 6

# ---------------------------------------------------------------------------
# Cluster numbers (must match data-model.md cluster allocation)
# ---------------------------------------------------------------------------

CLUSTER_SWITCH_PORT = 2
CLUSTER_CONTROLLER = 9

# ---------------------------------------------------------------------------
# Metric definitions — (pmns_name, item_number, pm_type, pm_sem, attr_name)
#
# These are declarative so registration is a loop, not 19 copy-pasted calls.
# attr_name maps to the PortData or controller_health dict field.
# ---------------------------------------------------------------------------

# Guard: only reference c_api constants when PCP is available
if HAS_PCP:
    SWITCH_PORT_METRICS: List[Tuple[str, int, int, int, str]] = [
        ("unifi.switch.port.rx_bytes",      0,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "rx_bytes"),
        ("unifi.switch.port.tx_bytes",      1,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "tx_bytes"),
        ("unifi.switch.port.rx_packets",    2,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "rx_packets"),
        ("unifi.switch.port.tx_packets",    3,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "tx_packets"),
        ("unifi.switch.port.rx_errors",     4,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "rx_errors"),
        ("unifi.switch.port.tx_errors",     5,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "tx_errors"),
        ("unifi.switch.port.rx_dropped",    6,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "rx_dropped"),
        ("unifi.switch.port.tx_dropped",    7,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "tx_dropped"),
        ("unifi.switch.port.rx_broadcast",  8,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "rx_broadcast"),
        ("unifi.switch.port.tx_broadcast",  9,  c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "tx_broadcast"),
        ("unifi.switch.port.rx_multicast",  10, c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "rx_multicast"),
        ("unifi.switch.port.tx_multicast",  11, c_api.PM_TYPE_U64, c_api.PM_SEM_COUNTER, "tx_multicast"),
        ("unifi.switch.port.up",            12, c_api.PM_TYPE_U32, c_api.PM_SEM_INSTANT, "up"),
        ("unifi.switch.port.enable",        13, c_api.PM_TYPE_U32, c_api.PM_SEM_INSTANT, "enable"),
        ("unifi.switch.port.speed",         14, c_api.PM_TYPE_U32, c_api.PM_SEM_INSTANT, "speed"),
        ("unifi.switch.port.full_duplex",   15, c_api.PM_TYPE_U32, c_api.PM_SEM_INSTANT, "full_duplex"),
        ("unifi.switch.port.is_uplink",     16, c_api.PM_TYPE_U32, c_api.PM_SEM_INSTANT, "is_uplink"),
        ("unifi.switch.port.satisfaction",  17, c_api.PM_TYPE_U32, c_api.PM_SEM_INSTANT, "satisfaction"),
        ("unifi.switch.port.mac_count",     18, c_api.PM_TYPE_U32, c_api.PM_SEM_INSTANT, "mac_count"),
    ]

    CONTROLLER_METRICS: List[Tuple[str, int, int, int, str]] = [
        ("unifi.controller.up",               0, c_api.PM_TYPE_U32,   c_api.PM_SEM_INSTANT, "up"),
        ("unifi.controller.poll_duration_ms",  1, c_api.PM_TYPE_FLOAT, c_api.PM_SEM_INSTANT, "poll_duration_ms"),
        ("unifi.controller.poll_errors",       2, c_api.PM_TYPE_U64,   c_api.PM_SEM_COUNTER, "poll_errors"),
        ("unifi.controller.last_poll",         3, c_api.PM_TYPE_U64,   c_api.PM_SEM_INSTANT, "last_poll"),
    ]
else:
    SWITCH_PORT_METRICS = []
    CONTROLLER_METRICS = []


# ---------------------------------------------------------------------------
# PCP units helper
# ---------------------------------------------------------------------------


def _units_for_metric(pmns_name: str, pm_sem: int) -> Any:
    """Build pmUnits for a metric based on its name and semantic type.

    Byte counters get PM_SPACE_BYTE; everything else is dimensionless.
    """
    if not HAS_PCP:
        return None

    if pmns_name.endswith("_bytes"):
        return pmapi.pmUnits(1, 0, 0, c_api.PM_SPACE_BYTE, 0, 0)
    if pmns_name.endswith("_duration_ms"):
        return pmapi.pmUnits(0, 1, 0, 0, c_api.PM_TIME_MSEC, 0)
    # dimensionless for counts, booleans, percentages
    return pmapi.pmUnits(0, 0, 0, 0, 0, 0)


# ---------------------------------------------------------------------------
# PMDA class
# ---------------------------------------------------------------------------


if HAS_PCP:

    class UnifiPMDA(PMDA):
        """Performance Metrics Domain Agent for UniFi network infrastructure."""

        def __init__(self, name: str, domain: int):
            super().__init__(name, domain)

            self._pollers: List[ControllerPoller] = []
            self._config: Optional[PmdaConfig] = None

            # Instance domain tables — rebuilt each pre-fetch from live snapshots
            self._switch_port_instances: List = []
            self._controller_instances: List = []

            # Instance-to-data lookup caches — rebuilt in pre-fetch
            self._port_data_by_inst: Dict[int, PortData] = {}
            self._controller_health_by_inst: Dict[int, Dict] = {}

            self._register_indoms()
            self._register_switch_port_metrics()
            self._register_controller_metrics()

            self.set_fetch_callback(self._fetch_callback)
            self.set_fetch(self._pre_fetch)

            self._configure_from_cli()

        # -- Instance domain registration ------------------------------------

        def _register_indoms(self) -> None:
            """Register the switch_port and controller instance domains."""
            self._switch_port_indom = self.indom(INDOM_SWITCH_PORT)
            self._controller_indom = self.indom(INDOM_CONTROLLER)
            self.add_indom(pmdaIndom(self._switch_port_indom, []))
            self.add_indom(pmdaIndom(self._controller_indom, []))

        # -- Metric registration ---------------------------------------------

        def _register_switch_port_metrics(self) -> None:
            """Register all 19 switch port metrics in cluster 2."""
            for pmns_name, item, pm_type, pm_sem, _attr in SWITCH_PORT_METRICS:
                pmid = self.pmid(CLUSTER_SWITCH_PORT, item)
                units = _units_for_metric(pmns_name, pm_sem)
                self.add_metric(
                    pmns_name,
                    pmdaMetric(pmid, pm_type, self._switch_port_indom, pm_sem, units),
                    "UniFi switch port metric",
                )

        def _register_controller_metrics(self) -> None:
            """Register all 4 controller health metrics in cluster 9."""
            for pmns_name, item, pm_type, pm_sem, _attr in CONTROLLER_METRICS:
                pmid = self.pmid(CLUSTER_CONTROLLER, item)
                units = _units_for_metric(pmns_name, pm_sem)
                self.add_metric(
                    pmns_name,
                    pmdaMetric(pmid, pm_type, self._controller_indom, pm_sem, units),
                    "UniFi controller health metric",
                )

        # -- CLI and configuration -------------------------------------------

        def _configure_from_cli(self) -> None:
            """Parse CLI options and load configuration file."""
            self.connect_pmcd()

            config_file = self.pmGetOptionRequired("c")
            if config_file:
                self._load_config(config_file)

        def _load_config(self, config_path: str) -> None:
            """Read the INI config file and start poller threads."""
            try:
                with open(config_path, "r") as fh:
                    ini_content = fh.read()
                self._config = parse_config(ini_content)
            except Exception:
                log.exception("Failed to load config from %s", config_path)
                return

            self._start_pollers()

        def _start_pollers(self) -> None:
            """Create and start a poller thread for each configured controller."""
            if not self._config:
                return

            global_settings = self._config.global_settings

            for ctrl_name, ctrl_cfg in self._config.controllers.items():
                poll_interval = ctrl_cfg.poll_interval or global_settings.poll_interval
                client = UnifiClient(
                    url=ctrl_cfg.url,
                    api_key=ctrl_cfg.api_key,
                    is_udm=ctrl_cfg.is_udm,
                    verify_ssl=ctrl_cfg.verify_ssl,
                    ca_cert=ctrl_cfg.ca_cert,
                )
                poller = ControllerPoller(
                    controller_name=ctrl_name,
                    client=client,
                    sites=ctrl_cfg.sites,
                    poll_interval=poll_interval,
                    max_clients=global_settings.max_clients,
                )
                poller.start()
                self._pollers.append(poller)
                log.info(
                    "Started poller for controller '%s' (interval=%ds, sites=%s)",
                    ctrl_name, poll_interval, ctrl_cfg.sites,
                )

        # -- Pre-fetch: rebuild instance domains from snapshots ---------------

        def _pre_fetch(self) -> None:
            """Rebuild instance domain tables from current poller snapshots.

            Called by PCP before each batch of fetch callbacks.  We walk
            all pollers' snapshots to build the full instance lists.
            """
            fetch_start = time.monotonic()

            self._rebuild_switch_port_instances()
            self._rebuild_controller_instances()

            self.replace_indom(self._switch_port_indom, self._switch_port_instances)
            self.replace_indom(self._controller_indom, self._controller_instances)

            self._warn_if_fetch_too_slow(fetch_start)

        def _rebuild_switch_port_instances(self) -> None:
            """Walk all snapshots and build switch port instance lists."""
            instances = []
            port_data_by_inst = {}
            inst_id = 0

            for poller in self._pollers:
                snapshot = poller.snapshot
                if snapshot is None:
                    continue

                for site_name, site_data in snapshot.sites.items():
                    for _mac, device in site_data.devices.items():
                        if not device.ports:
                            continue
                        for port_idx, port_data in sorted(device.ports.items()):
                            inst_name = switch_port_instance_name(
                                snapshot.controller_name,
                                site_name,
                                device.meta.name or device.meta.mac,
                                port_idx,
                            )
                            instances.append(pmdaInstid(inst_id, inst_name))
                            port_data_by_inst[inst_id] = port_data
                            inst_id += 1

            self._switch_port_instances = instances
            self._port_data_by_inst = port_data_by_inst

        def _rebuild_controller_instances(self) -> None:
            """Build controller instance list — one per poller."""
            instances = []
            health_by_inst = {}

            for inst_id, poller in enumerate(self._pollers):
                inst_name = controller_instance_name(poller.controller_name)
                instances.append(pmdaInstid(inst_id, inst_name))
                health_by_inst[inst_id] = poller.controller_health

            self._controller_instances = instances
            self._controller_health_by_inst = health_by_inst

        def _warn_if_fetch_too_slow(self, start_time: float) -> None:
            """Log a warning if pre-fetch + fetch exceeds the 4s budget (SC-003)."""
            elapsed_ms = (time.monotonic() - start_time) * 1000
            if elapsed_ms > 4000:
                log.warning(
                    "Pre-fetch took %.0fms — exceeds 4s budget (SC-003)",
                    elapsed_ms,
                )

        # -- Fetch callback ---------------------------------------------------

        def _fetch_callback(self, cluster: int, item: int, inst: int) -> list:
            """Return [value, 1] for a metric, or [error_code, 0] on failure.

            This is called by PCP for every (metric, instance) pair in a
            fetch request.  It reads only from the in-memory snapshot —
            zero network I/O.
            """
            if cluster == CLUSTER_SWITCH_PORT:
                return self._fetch_switch_port(item, inst)
            if cluster == CLUSTER_CONTROLLER:
                return self._fetch_controller(item, inst)
            return [c_api.PM_ERR_PMID, 0]

        def _fetch_switch_port(self, item: int, inst: int) -> list:
            """Fetch a single switch port metric value."""
            port_data = self._port_data_by_inst.get(inst)
            if port_data is None:
                if not self._port_data_by_inst:
                    return [c_api.PM_ERR_AGAIN, 0]
                return [c_api.PM_ERR_INST, 0]

            if item < 0 or item >= len(SWITCH_PORT_METRICS):
                return [c_api.PM_ERR_PMID, 0]

            attr_name = SWITCH_PORT_METRICS[item][4]
            return self._extract_port_value(port_data, attr_name)

        def _extract_port_value(self, port_data: PortData, attr_name: str) -> list:
            """Pull a named attribute from PortData and coerce booleans to int."""
            value = getattr(port_data, attr_name, None)
            if value is None:
                return [c_api.PM_ERR_PMID, 0]
            # PCP doesn't understand Python bools — coerce to 0/1
            if isinstance(value, bool):
                value = int(value)
            return [value, 1]

        def _fetch_controller(self, item: int, inst: int) -> list:
            """Fetch a single controller health metric value."""
            health = self._controller_health_by_inst.get(inst)
            if health is None:
                if not self._controller_health_by_inst:
                    return [c_api.PM_ERR_AGAIN, 0]
                return [c_api.PM_ERR_INST, 0]

            if item < 0 or item >= len(CONTROLLER_METRICS):
                return [c_api.PM_ERR_PMID, 0]

            attr_name = CONTROLLER_METRICS[item][4]
            value = health.get(attr_name)
            if value is None:
                return [c_api.PM_ERR_PMID, 0]
            return [value, 1]

        # -- Label callbacks --------------------------------------------------

        def _label_callback(self, ident: int, label_type: int) -> str:
            """Return JSON labels for the domain, indom, or instance."""
            if label_type == c_api.PM_LABEL_DOMAIN:
                return json.dumps({"agent": "unifi"})
            # Instance-level labels would go here in future phases
            return "{}"

    # -- Module-level entry point -----------------------------------------

    def run() -> None:
        """Entry point for the PMDA — called by PMCD or Install script."""
        UnifiPMDA("unifi", 155).run()

else:
    # PCP not installed — provide a stub so imports don't crash tests
    def run() -> None:
        """Stub entry point when PCP is not installed."""
        print("ERROR: PCP Python bindings not installed", file=sys.stderr)
        sys.exit(1)
