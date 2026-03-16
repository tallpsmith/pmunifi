"""Generate synthetic PCP archives for dashboard testing.

Produces either a real PCP archive (if pcp.LogImport is available) or a
JSON representation of the archive data (as a fallback on dev machines
without PCP installed).

Usage:
    python tests/generate_synthetic_archive.py -o /tmp/unifi-test
    python tests/generate_synthetic_archive.py --switches 5 --ports-per-switch 48 \
        --clients 100 --aps 10 --duration 3600 --interval 30 -o /tmp/unifi-bench

The JSON fallback writes to <output>.json; the PCP archive writes the
standard .0/.meta/.index triple.
"""

import argparse
import json
import math
import random
import time
from typing import Any, Dict, List

# ---------------------------------------------------------------------------
# Metric namespace — mirrors pmda.py cluster layout
# ---------------------------------------------------------------------------

METRIC_NAMESPACE = {
    "unifi.site.status": {"type": "string", "sem": "instant"},
    "unifi.site.num_sta": {"type": "u32", "sem": "instant"},
    "unifi.site.num_ap": {"type": "u32", "sem": "instant"},
    "unifi.site.num_sw": {"type": "u32", "sem": "instant"},
    "unifi.site.num_gw": {"type": "u32", "sem": "instant"},
    "unifi.device.name": {"type": "string", "sem": "discrete"},
    "unifi.device.type": {"type": "string", "sem": "discrete"},
    "unifi.device.state": {"type": "u32", "sem": "instant"},
    "unifi.device.uptime": {"type": "u64", "sem": "instant"},
    "unifi.device.rx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.device.tx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.switch.port.rx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.switch.port.tx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.switch.port.rx_packets": {"type": "u64", "sem": "counter"},
    "unifi.switch.port.tx_packets": {"type": "u64", "sem": "counter"},
    "unifi.switch.port.up": {"type": "u32", "sem": "instant"},
    "unifi.switch.port.speed": {"type": "u32", "sem": "instant"},
    "unifi.switch.port.poe.power": {"type": "float", "sem": "instant"},
    "unifi.client.hostname": {"type": "string", "sem": "instant"},
    "unifi.client.rx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.client.tx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.client.is_wired": {"type": "u32", "sem": "instant"},
    "unifi.ap.channel": {"type": "u32", "sem": "instant"},
    "unifi.ap.num_sta": {"type": "u32", "sem": "instant"},
    "unifi.ap.rx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.ap.tx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.gateway.wan_rx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.gateway.wan_tx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.gateway.cpu": {"type": "float", "sem": "instant"},
    "unifi.gateway.mem": {"type": "float", "sem": "instant"},
    "unifi.controller.up": {"type": "u32", "sem": "instant"},
    "unifi.controller.poll_duration_ms": {"type": "float", "sem": "instant"},
    "unifi.dpi.rx_bytes": {"type": "u64", "sem": "counter"},
    "unifi.dpi.tx_bytes": {"type": "u64", "sem": "counter"},
}


# ---------------------------------------------------------------------------
# Synthetic data generators
# ---------------------------------------------------------------------------


def _generate_instances(
    num_switches: int,
    ports_per_switch: int,
    num_clients: int,
    num_aps: int,
) -> Dict[str, List[str]]:
    """Build instance name lists for each indom."""
    instances: Dict[str, List[str]] = {}

    instances["site"] = ["main/default"]

    devices = []
    for i in range(num_switches):
        devices.append(f"main/default/USW-{i + 1}")
    for i in range(num_aps):
        devices.append(f"main/default/UAP-{i + 1}")
    devices.append("main/default/UDM-Pro")
    instances["device"] = devices

    ports = []
    for i in range(num_switches):
        for p in range(1, ports_per_switch + 1):
            ports.append(f"main/default/USW-{i + 1}::Port{p}")
    instances["switch_port"] = ports

    clients = []
    for i in range(num_clients):
        clients.append(f"main/default/client-{i + 1:04d}")
    instances["client"] = clients

    radios = []
    for i in range(num_aps):
        radios.append(f"main/default/UAP-{i + 1}::ng")
        radios.append(f"main/default/UAP-{i + 1}::na")
    instances["ap_radio"] = radios

    instances["gateway"] = ["main/default/UDM-Pro"]
    instances["controller"] = ["main"]
    instances["dpi_category"] = [
        "main/default/Streaming",
        "main/default/Social-Media",
        "main/default/Web",
        "main/default/Gaming",
    ]

    return instances


def _generate_sample(
    timestamp: float,
    instances: Dict[str, List[str]],
    base_counter: int,
) -> Dict[str, Any]:
    """Generate one sample interval's worth of metric values."""
    sample: Dict[str, Any] = {"timestamp": timestamp, "values": {}}

    # Site metrics
    sample["values"]["unifi.site.status"] = {
        inst: "ok" for inst in instances["site"]
    }
    sample["values"]["unifi.site.num_sta"] = {
        inst: len(instances["client"]) for inst in instances["site"]
    }
    sample["values"]["unifi.site.num_sw"] = {
        inst: sum(1 for d in instances["device"] if "USW" in d)
        for inst in instances["site"]
    }
    sample["values"]["unifi.site.num_ap"] = {
        inst: sum(1 for d in instances["device"] if "UAP" in d)
        for inst in instances["site"]
    }
    sample["values"]["unifi.site.num_gw"] = {
        inst: 1 for inst in instances["site"]
    }

    # Device metrics
    sample["values"]["unifi.device.name"] = {
        inst: inst.split("/")[-1] for inst in instances["device"]
    }
    sample["values"]["unifi.device.state"] = {
        inst: 1 for inst in instances["device"]
    }
    sample["values"]["unifi.device.uptime"] = {
        inst: base_counter + random.randint(86400, 864000)
        for inst in instances["device"]
    }
    for metric in ("unifi.device.rx_bytes", "unifi.device.tx_bytes"):
        sample["values"][metric] = {
            inst: base_counter * random.randint(1000, 50000)
            for inst in instances["device"]
        }

    # Switch port counters — monotonically increasing with some jitter
    for metric in (
        "unifi.switch.port.rx_bytes",
        "unifi.switch.port.tx_bytes",
        "unifi.switch.port.rx_packets",
        "unifi.switch.port.tx_packets",
    ):
        rate = 1_000_000 if "bytes" in metric else 1000
        sample["values"][metric] = {
            inst: base_counter * rate + random.randint(0, rate // 10)
            for inst in instances["switch_port"]
        }

    sample["values"]["unifi.switch.port.up"] = {
        inst: 1 if random.random() > 0.05 else 0
        for inst in instances["switch_port"]
    }
    sample["values"]["unifi.switch.port.speed"] = {
        inst: random.choice([100, 1000, 2500, 10000])
        for inst in instances["switch_port"]
    }
    sample["values"]["unifi.switch.port.poe.power"] = {
        inst: round(random.uniform(0, 30), 1)
        for inst in instances["switch_port"]
    }

    # Client metrics
    sample["values"]["unifi.client.hostname"] = {
        inst: inst.split("/")[-1] for inst in instances["client"]
    }
    sample["values"]["unifi.client.is_wired"] = {
        inst: random.choice([0, 1]) for inst in instances["client"]
    }
    for metric in ("unifi.client.rx_bytes", "unifi.client.tx_bytes"):
        sample["values"][metric] = {
            inst: base_counter * random.randint(100, 10000)
            for inst in instances["client"]
        }

    # AP radio metrics
    sample["values"]["unifi.ap.channel"] = {
        inst: (1 if "ng" in inst else random.choice([36, 44, 149, 157]))
        for inst in instances["ap_radio"]
    }
    sample["values"]["unifi.ap.num_sta"] = {
        inst: random.randint(0, 30) for inst in instances["ap_radio"]
    }
    for metric in ("unifi.ap.rx_bytes", "unifi.ap.tx_bytes"):
        sample["values"][metric] = {
            inst: base_counter * random.randint(5000, 50000)
            for inst in instances["ap_radio"]
        }

    # Gateway metrics
    for metric in ("unifi.gateway.wan_rx_bytes", "unifi.gateway.wan_tx_bytes"):
        sample["values"][metric] = {
            inst: base_counter * random.randint(100000, 500000)
            for inst in instances["gateway"]
        }
    sample["values"]["unifi.gateway.cpu"] = {
        inst: round(15 + 10 * math.sin(base_counter / 100), 1)
        for inst in instances["gateway"]
    }
    sample["values"]["unifi.gateway.mem"] = {
        inst: round(random.uniform(30, 60), 1)
        for inst in instances["gateway"]
    }

    # Controller metrics
    sample["values"]["unifi.controller.up"] = {
        inst: 1 for inst in instances["controller"]
    }
    sample["values"]["unifi.controller.poll_duration_ms"] = {
        inst: round(random.uniform(50, 300), 1)
        for inst in instances["controller"]
    }

    # DPI metrics
    for metric in ("unifi.dpi.rx_bytes", "unifi.dpi.tx_bytes"):
        sample["values"][metric] = {
            inst: base_counter * random.randint(10000, 100000)
            for inst in instances["dpi_category"]
        }

    return sample


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def _write_json_archive(
    output_path: str,
    instances: Dict[str, List[str]],
    samples: List[Dict[str, Any]],
) -> None:
    """Write the archive as a JSON file (fallback when PCP is absent)."""
    archive = {
        "format": "synthetic-pcp-archive-json",
        "version": 1,
        "namespace": METRIC_NAMESPACE,
        "instances": instances,
        "samples": samples,
    }
    path = output_path if output_path.endswith(".json") else output_path + ".json"
    with open(path, "w") as fh:
        json.dump(archive, fh, indent=2)
    print(f"Wrote JSON archive: {path}")
    print(f"  {len(samples)} samples, {sum(len(v) for v in instances.values())} total instances")


def _try_write_pcp_archive(
    output_path: str,
    instances: Dict[str, List[str]],
    samples: List[Dict[str, Any]],
) -> bool:
    """Attempt to write a real PCP archive using pcp.LogImport.

    Returns True if successful, False if PCP LogImport is unavailable.
    """
    try:
        import cpmapi as c_api  # noqa: F401
        from pcp import pmi  # noqa: F401  # LogImport
    except ImportError:
        return False

    # TODO: Full PCP LogImport implementation.
    # This requires mapping each metric to a PMID, defining indoms,
    # and writing timestamped samples via pmi.pmiPutValue / pmi.pmiWrite.
    # For now, return False and fall back to JSON.
    print("PCP LogImport available but full archive writing not yet implemented.")
    print("Falling back to JSON format.")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser for the synthetic archive generator."""
    parser = argparse.ArgumentParser(
        description="Generate synthetic PCP archives for UniFi PMDA dashboard testing.",
    )
    parser.add_argument(
        "-o", "--output", default="unifi-synthetic",
        help="Output path prefix (default: unifi-synthetic)",
    )
    parser.add_argument(
        "--switches", type=int, default=3,
        help="Number of switches (default: 3)",
    )
    parser.add_argument(
        "--ports-per-switch", type=int, default=24,
        help="Ports per switch (default: 24)",
    )
    parser.add_argument(
        "--clients", type=int, default=50,
        help="Number of clients (default: 50)",
    )
    parser.add_argument(
        "--aps", type=int, default=5,
        help="Number of access points (default: 5)",
    )
    parser.add_argument(
        "--duration", type=int, default=3600,
        help="Archive duration in seconds (default: 3600)",
    )
    parser.add_argument(
        "--interval", type=int, default=30,
        help="Sample interval in seconds (default: 30)",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for reproducibility (default: 42)",
    )
    return parser


def main() -> None:
    """Entry point: generate instances, produce samples, write archive."""
    parser = build_parser()
    args = parser.parse_args()

    random.seed(args.seed)

    print(f"Generating synthetic archive: {args.switches} switches x "
          f"{args.ports_per_switch} ports, {args.clients} clients, "
          f"{args.aps} APs")
    print(f"Duration: {args.duration}s, interval: {args.interval}s")

    instances = _generate_instances(
        num_switches=args.switches,
        ports_per_switch=args.ports_per_switch,
        num_clients=args.clients,
        num_aps=args.aps,
    )

    total_instances = sum(len(v) for v in instances.values())
    print(f"Total instances: {total_instances}")

    start_time = time.time()
    samples = []
    num_samples = args.duration // args.interval

    for i in range(num_samples):
        ts = start_time + i * args.interval
        sample = _generate_sample(ts, instances, base_counter=i + 1)
        samples.append(sample)

    # Try PCP archive first, fall back to JSON
    if not _try_write_pcp_archive(args.output, instances, samples):
        _write_json_archive(args.output, instances, samples)


if __name__ == "__main__":
    main()
