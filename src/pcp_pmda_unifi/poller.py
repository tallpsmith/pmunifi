"""Background poller thread for a single UniFi controller.

Periodically calls the UniFi API, builds an immutable Snapshot, and
atomically swaps it for the PMDA dispatch thread to read.  The poller
never blocks the fetch callback — the GIL guarantees atomic reference
assignment for the snapshot swap.

Usage:
    from pcp_pmda_unifi.poller import ControllerPoller
    poller = ControllerPoller("main", client, sites=["default"])
    poller.start()
    snap = poller.snapshot  # None until first successful poll
"""

import logging
import threading
import time
from typing import Dict, List, Optional

from pcp_pmda_unifi.collector import UnifiClient
from pcp_pmda_unifi.snapshot import SiteData, Snapshot, build_snapshot_from_api

log = logging.getLogger(__name__)


class ControllerPoller(threading.Thread):
    """Daemon thread that polls one UniFi controller on a schedule.

    Builds a Snapshot each cycle and swaps it atomically.  On error,
    retains the previous snapshot and increments the error counter so
    the PMDA can keep serving stale-but-valid data.
    """

    def __init__(
        self,
        controller_name: str,
        client: UnifiClient,
        sites: List[str],
        poll_interval: int = 30,
        max_clients: int = 1000,
        enable_dpi: bool = False,
    ):
        super().__init__(name=f"poller-{controller_name}")
        self.daemon = True
        self.controller_name = controller_name
        self._client = client
        self._sites = sites
        self.poll_interval = poll_interval
        self._max_clients = max_clients
        self._enable_dpi = enable_dpi

        self._snapshot: Optional[Snapshot] = None
        self._poll_duration_ms: float = 0.0
        self._poll_errors: int = 0
        self._last_poll_timestamp: float = 0.0
        self._controller_up: bool = False
        self._stop_event = threading.Event()

    # -- Public properties ----------------------------------------------------

    @property
    def snapshot(self) -> Optional[Snapshot]:
        """Return the latest snapshot, or None before first successful poll."""
        return self._snapshot

    @property
    def controller_health(self) -> Dict:
        """Return a status dict for controller health metrics (cluster 9)."""
        snap = self._snapshot
        return {
            "up": 1 if self._controller_up else 0,
            "poll_duration_ms": self._poll_duration_ms,
            "poll_errors": self._poll_errors,
            "last_poll": int(self._last_poll_timestamp),
            "version": snap.controller_version if snap else "",
            "devices_discovered": snap.devices_discovered if snap else 0,
            "clients_discovered": snap.clients_discovered if snap else 0,
            "sites_polled": snap.sites_polled if snap else 0,
        }

    # -- Thread lifecycle -----------------------------------------------------

    def run(self) -> None:
        """Main loop: poll immediately, then sleep between cycles."""
        log.info("Poller started for controller '%s'", self.controller_name)
        while not self._stop_event.is_set():
            self.poll_once()
            self._stop_event.wait(timeout=self.poll_interval)
        log.info("Poller stopped for controller '%s'", self.controller_name)

    def stop(self) -> None:
        """Signal the poller to stop after the current cycle."""
        self._stop_event.set()

    # -- Single poll cycle ----------------------------------------------------

    def poll_once(self) -> None:
        """Perform one full poll cycle across all configured sites.

        On success: builds a new Snapshot and atomically swaps it in.
        On failure: retains the previous snapshot, increments error count.
        """
        start_time = time.monotonic()
        try:
            new_snapshot = self._poll_all_sites()
            self._snapshot = new_snapshot
            self._controller_up = True
            self._last_poll_timestamp = time.time()
            self._record_poll_duration(start_time)
            log.debug(
                "Poll complete for '%s': %d devices, %d clients",
                self.controller_name,
                new_snapshot.devices_discovered,
                new_snapshot.clients_discovered,
            )
        except Exception:
            self._poll_errors += 1
            self._controller_up = False
            self._record_poll_duration(start_time)
            log.exception(
                "Poll failed for controller '%s' (error #%d)",
                self.controller_name,
                self._poll_errors,
            )

    # -- Internal helpers -----------------------------------------------------

    def _poll_all_sites(self) -> Snapshot:
        """Fetch data from all configured sites and merge into one Snapshot."""
        merged_sites: Dict[str, SiteData] = {}
        total_devices = 0
        total_clients = 0

        for site_name in self._sites:
            site_snapshot = self._poll_single_site(site_name)
            for name, site_data in site_snapshot.sites.items():
                merged_sites[name] = site_data
            total_devices += site_snapshot.devices_discovered
            total_clients += site_snapshot.clients_discovered

        return Snapshot(
            timestamp=time.time(),
            controller_name=self.controller_name,
            sites=merged_sites,
            devices_discovered=total_devices,
            clients_discovered=total_clients,
            sites_polled=len(self._sites),
        )

    def _poll_single_site(self, site_name: str) -> Snapshot:
        """Fetch devices, clients, health, and optionally DPI for one site."""
        devices_data = self._client.fetch_devices(site_name)
        clients_data = self._client.fetch_clients(site_name)
        health_data = self._client.fetch_health(site_name)

        dpi_data = None
        if self._enable_dpi:
            dpi_data = self._client.fetch_dpi(site_name)

        return build_snapshot_from_api(
            controller_name=self.controller_name,
            site_name=site_name,
            devices_data=devices_data,
            clients_data=clients_data,
            health_data=health_data,
            dpi_data=dpi_data,
            max_clients=self._max_clients,
        )

    def _record_poll_duration(self, start_time: float) -> None:
        """Calculate and store the poll duration in milliseconds."""
        elapsed_seconds = time.monotonic() - start_time
        self._poll_duration_ms = elapsed_seconds * 1000.0
