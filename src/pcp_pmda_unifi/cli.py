"""CLI entry point for the unifi2dot companion tool (US5).

Discovers UniFi network topology from the controller API and exports
it as Graphviz DOT or JSON.  Each edge is annotated with the PCP
switch-port metric instance name for live data overlay.

Usage:
    unifi2dot --url https://unifi.local --api-key KEY --site default
    unifi2dot --url https://unifi.local --api-key KEY --site default --format json -o topo.json
"""

import argparse
import sys
from typing import Optional, Sequence

from pcp_pmda_unifi.collector import UnifiApiError, UnifiClient, UnifiConnectionError
from pcp_pmda_unifi.topology import discover_topology, to_dot, to_json


def build_parser() -> argparse.ArgumentParser:
    """Construct the argparse parser for unifi2dot."""
    parser = argparse.ArgumentParser(
        prog="unifi2dot",
        description="Discover UniFi network topology and export as DOT or JSON.",
    )
    parser.add_argument(
        "--url", required=True,
        help="UniFi controller URL (e.g. https://192.168.1.1)",
    )
    parser.add_argument(
        "--api-key", required=True,
        help="UniFi API key for authentication",
    )
    parser.add_argument(
        "--site", required=True,
        help="UniFi site name (e.g. 'default')",
    )
    parser.add_argument(
        "--format", choices=["dot", "json"], default="dot",
        help="Output format (default: dot)",
    )
    parser.add_argument(
        "-o", "--output", default=None,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--controller", default="main",
        help="Controller name for PCP instance name prefix (default: main)",
    )

    # UDM flag: default True, --no-udm sets False
    parser.add_argument(
        "--no-udm", dest="is_udm", action="store_false", default=True,
        help="Disable /proxy/network prefix (for non-UDM controllers)",
    )
    parser.add_argument(
        "--no-verify-ssl", dest="verify_ssl", action="store_false", default=True,
        help="Skip SSL certificate verification",
    )

    return parser


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Entry point: fetch devices, discover topology, write output."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        client = UnifiClient(
            url=args.url,
            api_key=args.api_key,
            is_udm=args.is_udm,
            verify_ssl=args.verify_ssl,
        )
        devices = client.fetch_devices(args.site)
    except UnifiConnectionError as exc:
        print(f"Connection error: {exc}", file=sys.stderr)
        sys.exit(1)
    except UnifiApiError as exc:
        print(f"API error: {exc}", file=sys.stderr)
        sys.exit(1)

    links = discover_topology(
        devices, controller=args.controller, site=args.site,
    )

    output = to_json(links, devices) if args.format == "json" else to_dot(links, devices)

    if args.output:
        with open(args.output, "w") as fh:
            fh.write(output)
    else:
        print(output, end="")
