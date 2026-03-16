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
    GracePeriodTracker,
    controller_instance_name,
    device_instance_name,
    gateway_instance_name,
    site_instance_name,
    switch_port_instance_name,
)
from pcp_pmda_unifi.poller import ControllerPoller
from pcp_pmda_unifi.snapshot import (
    DeviceMeta,
    GatewayData,
    HealthData,
    PortData,
    SiteData,
    Snapshot,
)

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

INDOM_SITE = 0
INDOM_DEVICE = 1
INDOM_SWITCH_PORT = 2
INDOM_GATEWAY = 5
INDOM_CONTROLLER = 6

# ---------------------------------------------------------------------------
# Cluster numbers (must match data-model.md cluster allocation)
# ---------------------------------------------------------------------------

CLUSTER_SITE = 0
CLUSTER_DEVICE = 1
CLUSTER_SWITCH_PORT = 2
CLUSTER_GATEWAY = 6
CLUSTER_CONTROLLER = 9

# ---------------------------------------------------------------------------
# Metric definitions — (pmns_name, item_number, pm_type, pm_sem, attr_name)
#
# These are declarative so registration is a loop, not 19 copy-pasted calls.
# attr_name maps to the PortData or controller_health dict field.
# ---------------------------------------------------------------------------

# Guard: only reference c_api constants when PCP is available
if HAS_PCP:
    # -- Cluster 0: site metrics (indom: site) --------------------------------
    SITE_METRICS: List[Tuple[str, int, int, int, str]] = [
        ("unifi.site.status",           0,  c_api.PM_TYPE_STRING, c_api.PM_SEM_INSTANT,  "status"),
        ("unifi.site.num_sta",          1,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "num_sta"),
        ("unifi.site.num_user",         2,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "num_user"),
        ("unifi.site.num_guest",        3,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "num_guest"),
        ("unifi.site.num_ap",           4,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "num_ap"),
        ("unifi.site.num_sw",           5,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "num_sw"),
        ("unifi.site.num_gw",           6,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "num_gw"),
        # WAN/LAN/WLAN byte counters — sourced from gateway device's wan1/lan
        # interfaces for the site.  PM_SEM_COUNTER with raw gateway counters
        # per constitution ("export raw counter values only").
        ("unifi.site.wan.rx_bytes",     7,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_rx_bytes"),
        ("unifi.site.wan.tx_bytes",     8,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_tx_bytes"),
        ("unifi.site.lan.rx_bytes",     9,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "lan_rx_bytes"),
        ("unifi.site.lan.tx_bytes",     10, c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "lan_tx_bytes"),
        ("unifi.site.lan.num_user",     11, c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "lan_num_user"),
        ("unifi.site.lan.num_guest",    12, c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "lan_num_guest"),
        ("unifi.site.wlan.rx_bytes",    13, c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wlan_rx_bytes"),
        ("unifi.site.wlan.tx_bytes",    14, c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wlan_tx_bytes"),
    ]

    # -- Cluster 1: device metrics (indom: device) ----------------------------
    DEVICE_METRICS: List[Tuple[str, int, int, int, str]] = [
        ("unifi.device.name",           0,  c_api.PM_TYPE_STRING, c_api.PM_SEM_DISCRETE, "name"),
        ("unifi.device.mac",            1,  c_api.PM_TYPE_STRING, c_api.PM_SEM_DISCRETE, "mac"),
        ("unifi.device.ip",             2,  c_api.PM_TYPE_STRING, c_api.PM_SEM_INSTANT,  "ip"),
        ("unifi.device.model",          3,  c_api.PM_TYPE_STRING, c_api.PM_SEM_DISCRETE, "model"),
        ("unifi.device.type",           4,  c_api.PM_TYPE_STRING, c_api.PM_SEM_DISCRETE, "device_type"),
        ("unifi.device.version",        5,  c_api.PM_TYPE_STRING, c_api.PM_SEM_INSTANT,  "version"),
        ("unifi.device.state",          6,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "state"),
        ("unifi.device.uptime",         7,  c_api.PM_TYPE_U64,    c_api.PM_SEM_INSTANT,  "uptime"),
        ("unifi.device.adopted",        8,  c_api.PM_TYPE_U32,    c_api.PM_SEM_DISCRETE, "adopted"),
        ("unifi.device.rx_bytes",       9,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "rx_bytes"),
        ("unifi.device.tx_bytes",       10, c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "tx_bytes"),
        ("unifi.device.temperature",    11, c_api.PM_TYPE_FLOAT,  c_api.PM_SEM_INSTANT,  "temperature"),
        ("unifi.device.user_num_sta",   12, c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "user_num_sta"),
        ("unifi.device.guest_num_sta",  13, c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "guest_num_sta"),
        ("unifi.device.num_ports",      14, c_api.PM_TYPE_U32,    c_api.PM_SEM_DISCRETE, "num_ports"),
    ]

    # -- Cluster 2: switch port metrics (indom: switch_port) ------------------
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

    # -- Cluster 6: gateway metrics (indom: gateway) --------------------------
    GATEWAY_METRICS: List[Tuple[str, int, int, int, str]] = [
        ("unifi.gateway.wan_ip",          0,  c_api.PM_TYPE_STRING, c_api.PM_SEM_INSTANT,  "wan_ip"),
        ("unifi.gateway.wan_rx_bytes",    1,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_rx_bytes"),
        ("unifi.gateway.wan_tx_bytes",    2,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_tx_bytes"),
        ("unifi.gateway.wan_rx_packets",  3,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_rx_packets"),
        ("unifi.gateway.wan_tx_packets",  4,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_tx_packets"),
        ("unifi.gateway.wan_rx_dropped",  5,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_rx_dropped"),
        ("unifi.gateway.wan_tx_dropped",  6,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_tx_dropped"),
        ("unifi.gateway.wan_rx_errors",   7,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_rx_errors"),
        ("unifi.gateway.wan_tx_errors",   8,  c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "wan_tx_errors"),
        ("unifi.gateway.wan_up",          9,  c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "wan_up"),
        ("unifi.gateway.wan_speed",       10, c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "wan_speed"),
        ("unifi.gateway.wan_latency",     11, c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "wan_latency"),
        ("unifi.gateway.lan_rx_bytes",    12, c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "lan_rx_bytes"),
        ("unifi.gateway.lan_tx_bytes",    13, c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "lan_tx_bytes"),
        ("unifi.gateway.uptime",          14, c_api.PM_TYPE_U64,    c_api.PM_SEM_INSTANT,  "uptime"),
        ("unifi.gateway.cpu",             15, c_api.PM_TYPE_FLOAT,  c_api.PM_SEM_INSTANT,  "cpu"),
        ("unifi.gateway.mem",             16, c_api.PM_TYPE_FLOAT,  c_api.PM_SEM_INSTANT,  "mem"),
        ("unifi.gateway.temperature",     17, c_api.PM_TYPE_FLOAT,  c_api.PM_SEM_INSTANT,  "temperature"),
    ]

    # -- Cluster 9: controller metrics (indom: controller) --------------------
    CONTROLLER_METRICS: List[Tuple[str, int, int, int, str]] = [
        ("unifi.controller.up",                 0, c_api.PM_TYPE_U32,    c_api.PM_SEM_INSTANT,  "up"),
        ("unifi.controller.poll_duration_ms",   1, c_api.PM_TYPE_FLOAT,  c_api.PM_SEM_INSTANT,  "poll_duration_ms"),
        ("unifi.controller.poll_errors",        2, c_api.PM_TYPE_U64,    c_api.PM_SEM_COUNTER,  "poll_errors"),
        ("unifi.controller.last_poll",          3, c_api.PM_TYPE_U64,    c_api.PM_SEM_INSTANT,  "last_poll"),
        ("unifi.controller.version",            4, c_api.PM_TYPE_STRING, c_api.PM_SEM_DISCRETE, "version"),
        ("unifi.controller.devices_discovered", 5, c_api.PM_TYPE_U32,   c_api.PM_SEM_INSTANT,  "devices_discovered"),
        ("unifi.controller.clients_discovered", 6, c_api.PM_TYPE_U32,   c_api.PM_SEM_INSTANT,  "clients_discovered"),
        ("unifi.controller.sites_polled",       7, c_api.PM_TYPE_U32,   c_api.PM_SEM_INSTANT,  "sites_polled"),
    ]
else:
    SITE_METRICS = []
    DEVICE_METRICS = []
    SWITCH_PORT_METRICS = []
    GATEWAY_METRICS = []
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
            self._site_instances: List = []
            self._device_instances: List = []
            self._switch_port_instances: List = []
            self._gateway_instances: List = []
            self._controller_instances: List = []

            # Instance-to-data lookup caches — rebuilt in pre-fetch
            self._site_data_by_inst: Dict[int, Tuple[SiteData, Optional[GatewayData]]] = {}
            self._device_meta_by_inst: Dict[int, DeviceMeta] = {}
            self._port_data_by_inst: Dict[int, PortData] = {}
            self._gateway_data_by_inst: Dict[int, Tuple[GatewayData, int]] = {}
            self._controller_health_by_inst: Dict[int, Dict] = {}

            # Grace period trackers for dynamic indoms
            self._site_tracker = GracePeriodTracker()
            self._device_tracker = GracePeriodTracker()
            self._switch_port_tracker = GracePeriodTracker()
            self._gateway_tracker = GracePeriodTracker()

            self._register_indoms()
            self._register_site_metrics()
            self._register_device_metrics()
            self._register_switch_port_metrics()
            self._register_gateway_metrics()
            self._register_controller_metrics()

            self.set_fetch_callback(self._fetch_callback)
            self.set_fetch(self._pre_fetch)

            self._configure_from_cli()

        # -- Instance domain registration ------------------------------------

        def _register_indoms(self) -> None:
            """Register all instance domains for the PMDA."""
            self._site_indom = self.indom(INDOM_SITE)
            self._device_indom = self.indom(INDOM_DEVICE)
            self._switch_port_indom = self.indom(INDOM_SWITCH_PORT)
            self._gateway_indom = self.indom(INDOM_GATEWAY)
            self._controller_indom = self.indom(INDOM_CONTROLLER)
            self.add_indom(pmdaIndom(self._site_indom, []))
            self.add_indom(pmdaIndom(self._device_indom, []))
            self.add_indom(pmdaIndom(self._switch_port_indom, []))
            self.add_indom(pmdaIndom(self._gateway_indom, []))
            self.add_indom(pmdaIndom(self._controller_indom, []))

        # -- Metric registration ---------------------------------------------

        def _register_metrics_for_cluster(
            self, metrics_list: list, cluster: int, indom: int, description: str,
        ) -> None:
            """Register all metrics in a cluster with a given indom."""
            for pmns_name, item, pm_type, pm_sem, _attr in metrics_list:
                pmid = self.pmid(cluster, item)
                units = _units_for_metric(pmns_name, pm_sem)
                self.add_metric(
                    pmns_name,
                    pmdaMetric(pmid, pm_type, indom, pm_sem, units),
                    description,
                )

        def _register_site_metrics(self) -> None:
            """Register all 15 site metrics in cluster 0."""
            self._register_metrics_for_cluster(
                SITE_METRICS, CLUSTER_SITE, self._site_indom,
                "UniFi site health metric",
            )

        def _register_device_metrics(self) -> None:
            """Register all 15 device metrics in cluster 1."""
            self._register_metrics_for_cluster(
                DEVICE_METRICS, CLUSTER_DEVICE, self._device_indom,
                "UniFi device metric",
            )

        def _register_switch_port_metrics(self) -> None:
            """Register all 19 switch port metrics in cluster 2."""
            self._register_metrics_for_cluster(
                SWITCH_PORT_METRICS, CLUSTER_SWITCH_PORT, self._switch_port_indom,
                "UniFi switch port metric",
            )

        def _register_gateway_metrics(self) -> None:
            """Register all 18 gateway metrics in cluster 6."""
            self._register_metrics_for_cluster(
                GATEWAY_METRICS, CLUSTER_GATEWAY, self._gateway_indom,
                "UniFi gateway metric",
            )

        def _register_controller_metrics(self) -> None:
            """Register all 8 controller health metrics in cluster 9."""
            self._register_metrics_for_cluster(
                CONTROLLER_METRICS, CLUSTER_CONTROLLER, self._controller_indom,
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

            self._rebuild_site_instances()
            self._rebuild_device_instances()
            self._rebuild_switch_port_instances()
            self._rebuild_gateway_instances()
            self._rebuild_controller_instances()

            self.replace_indom(self._site_indom, self._site_instances)
            self.replace_indom(self._device_indom, self._device_instances)
            self.replace_indom(self._switch_port_indom, self._switch_port_instances)
            self.replace_indom(self._gateway_indom, self._gateway_instances)
            self.replace_indom(self._controller_indom, self._controller_instances)

            self._warn_if_fetch_too_slow(fetch_start)

        def _rebuild_site_instances(self) -> None:
            """Walk all snapshots and build site instance lists."""
            instances = []
            site_data_by_inst: Dict[int, Tuple[SiteData, Optional[GatewayData]]] = {}
            inst_id = 0

            for poller in self._pollers:
                snapshot = poller.snapshot
                if snapshot is None:
                    continue

                for site_name, site_data in snapshot.sites.items():
                    inst_name = site_instance_name(
                        snapshot.controller_name, site_name,
                    )
                    # Find the first gateway in this site for WAN/LAN byte counters
                    site_gateway = self._find_site_gateway(site_data)
                    instances.append(pmdaInstid(inst_id, inst_name))
                    site_data_by_inst[inst_id] = (site_data, site_gateway)
                    inst_id += 1

            self._site_instances = instances
            self._site_data_by_inst = site_data_by_inst

        def _find_site_gateway(self, site_data: SiteData) -> Optional[GatewayData]:
            """Return the first gateway device's GatewayData for a site."""
            for device in site_data.devices.values():
                if device.gateway is not None:
                    return device.gateway
            return None

        def _rebuild_device_instances(self) -> None:
            """Walk all snapshots and build device instance lists."""
            instances = []
            device_meta_by_inst: Dict[int, DeviceMeta] = {}
            inst_id = 0

            for poller in self._pollers:
                snapshot = poller.snapshot
                if snapshot is None:
                    continue

                for site_name, site_data in snapshot.sites.items():
                    for _mac, device in site_data.devices.items():
                        inst_name = device_instance_name(
                            snapshot.controller_name,
                            site_name,
                            device.meta.name or device.meta.mac,
                        )
                        instances.append(pmdaInstid(inst_id, inst_name))
                        device_meta_by_inst[inst_id] = device.meta
                        inst_id += 1

            self._device_instances = instances
            self._device_meta_by_inst = device_meta_by_inst

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

        def _rebuild_gateway_instances(self) -> None:
            """Walk all snapshots and build gateway instance lists."""
            instances = []
            gateway_data_by_inst: Dict[int, Tuple[GatewayData, int]] = {}
            inst_id = 0

            for poller in self._pollers:
                snapshot = poller.snapshot
                if snapshot is None:
                    continue

                for site_name, site_data in snapshot.sites.items():
                    for _mac, device in site_data.devices.items():
                        if device.gateway is None:
                            continue
                        inst_name = gateway_instance_name(
                            snapshot.controller_name,
                            site_name,
                            device.meta.name or device.meta.mac,
                        )
                        # Store gateway data alongside device uptime
                        instances.append(pmdaInstid(inst_id, inst_name))
                        gateway_data_by_inst[inst_id] = (
                            device.gateway, device.meta.uptime,
                        )
                        inst_id += 1

            self._gateway_instances = instances
            self._gateway_data_by_inst = gateway_data_by_inst

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
            if cluster == CLUSTER_SITE:
                return self._fetch_site(item, inst)
            if cluster == CLUSTER_DEVICE:
                return self._fetch_device(item, inst)
            if cluster == CLUSTER_SWITCH_PORT:
                return self._fetch_switch_port(item, inst)
            if cluster == CLUSTER_GATEWAY:
                return self._fetch_gateway(item, inst)
            if cluster == CLUSTER_CONTROLLER:
                return self._fetch_controller(item, inst)
            return [c_api.PM_ERR_PMID, 0]

        # -- Cluster 0: site fetch -------------------------------------------

        def _fetch_site(self, item: int, inst: int) -> list:
            """Fetch a single site-level metric value."""
            entry = self._site_data_by_inst.get(inst)
            if entry is None:
                if not self._site_data_by_inst:
                    return [c_api.PM_ERR_AGAIN, 0]
                return [c_api.PM_ERR_INST, 0]

            if item < 0 or item >= len(SITE_METRICS):
                return [c_api.PM_ERR_PMID, 0]

            site_data, site_gateway = entry
            attr_name = SITE_METRICS[item][4]
            return self._extract_site_value(site_data, site_gateway, attr_name)

        def _extract_site_value(
            self, site_data: SiteData, gw: Optional[GatewayData], attr_name: str,
        ) -> list:
            """Aggregate site metrics from health subsystems and gateway."""
            health_map = {h.subsystem: h for h in site_data.health}

            # Aggregated counts from health subsystems
            if attr_name == "status":
                return [self._worst_site_status(site_data.health), 1]
            if attr_name == "num_sta":
                return [sum(h.num_sta for h in site_data.health), 1]
            if attr_name == "num_user":
                return [sum(h.num_user for h in site_data.health), 1]
            if attr_name == "num_guest":
                return [sum(h.num_guest for h in site_data.health), 1]
            if attr_name == "num_ap":
                wlan = health_map.get("wlan")
                return [wlan.num_ap if wlan else 0, 1]
            if attr_name == "num_sw":
                lan = health_map.get("lan")
                return [lan.num_sw if lan else 0, 1]
            if attr_name == "num_gw":
                wan = health_map.get("wan")
                return [wan.num_gw if wan else 0, 1]

            # LAN user/guest counts from health
            if attr_name == "lan_num_user":
                lan = health_map.get("lan")
                return [lan.num_user if lan else 0, 1]
            if attr_name == "lan_num_guest":
                lan = health_map.get("lan")
                return [lan.num_guest if lan else 0, 1]

            # Byte counters — sourced from gateway device's raw counters
            if attr_name in (
                "wan_rx_bytes", "wan_tx_bytes",
                "lan_rx_bytes", "lan_tx_bytes",
            ):
                if gw is None:
                    return [c_api.PM_ERR_VALUE, 0]
                value = getattr(gw, attr_name, None)
                if value is None:
                    return [c_api.PM_ERR_VALUE, 0]
                return [value, 1]

            # WLAN byte counters — sum device-level rx/tx for all APs in site
            if attr_name == "wlan_rx_bytes":
                total = sum(
                    d.meta.rx_bytes for d in site_data.devices.values()
                    if d.meta.device_type == "uap"
                )
                return [total, 1]
            if attr_name == "wlan_tx_bytes":
                total = sum(
                    d.meta.tx_bytes for d in site_data.devices.values()
                    if d.meta.device_type == "uap"
                )
                return [total, 1]

            return [c_api.PM_ERR_PMID, 0]

        def _worst_site_status(self, health_list: List[HealthData]) -> str:
            """Return the worst status across all health subsystems.

            Priority: unknown > blocked > error > warn > ok.
            """
            priority = {"ok": 0, "warn": 1, "error": 2, "blocked": 3, "unknown": 4}
            worst = "ok"
            for h in health_list:
                status = h.status or "unknown"
                if priority.get(status, 4) > priority.get(worst, 0):
                    worst = status
            return worst

        # -- Cluster 1: device fetch -----------------------------------------

        def _fetch_device(self, item: int, inst: int) -> list:
            """Fetch a single device-level metric value."""
            meta = self._device_meta_by_inst.get(inst)
            if meta is None:
                if not self._device_meta_by_inst:
                    return [c_api.PM_ERR_AGAIN, 0]
                return [c_api.PM_ERR_INST, 0]

            if item < 0 or item >= len(DEVICE_METRICS):
                return [c_api.PM_ERR_PMID, 0]

            attr_name = DEVICE_METRICS[item][4]
            return self._extract_dataclass_value(meta, attr_name)

        # -- Cluster 2: switch port fetch ------------------------------------

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
            return self._extract_dataclass_value(port_data, attr_name)

        # -- Cluster 6: gateway fetch ----------------------------------------

        def _fetch_gateway(self, item: int, inst: int) -> list:
            """Fetch a single gateway metric value."""
            entry = self._gateway_data_by_inst.get(inst)
            if entry is None:
                if not self._gateway_data_by_inst:
                    return [c_api.PM_ERR_AGAIN, 0]
                return [c_api.PM_ERR_INST, 0]

            if item < 0 or item >= len(GATEWAY_METRICS):
                return [c_api.PM_ERR_PMID, 0]

            gw_data, device_uptime = entry
            attr_name = GATEWAY_METRICS[item][4]

            # uptime comes from the device meta, not GatewayData
            if attr_name == "uptime":
                return [device_uptime, 1]

            return self._extract_dataclass_value(gw_data, attr_name)

        # -- Cluster 9: controller fetch -------------------------------------

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

        # -- Shared value extraction -----------------------------------------

        def _extract_dataclass_value(self, obj: Any, attr_name: str) -> list:
            """Pull a named attribute from a dataclass and coerce for PCP."""
            value = getattr(obj, attr_name, None)
            if value is None:
                return [c_api.PM_ERR_VALUE, 0]
            if isinstance(value, bool):
                value = int(value)
            return [value, 1]

        # -- Label callbacks --------------------------------------------------

        def _label_callback(self, ident: int, label_type: int) -> str:
            """Return JSON labels for the domain, indom, or instance."""
            if label_type == c_api.PM_LABEL_DOMAIN:
                return json.dumps({"agent": "unifi"})
            # Instance-level labels are emitted per-indom in future phases
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
