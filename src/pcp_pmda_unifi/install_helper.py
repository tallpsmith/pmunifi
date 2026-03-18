"""Install helper for the UniFi PCP PMDA.

Provides Python functions called by the Install shell script to handle
the heavy lifting: connectivity validation, site discovery, and config
file generation.  Keeps shell scripting minimal while Python does the
real work.

Usage from shell:
    pmpython -m pcp_pmda_unifi.install_helper --validate URL API_KEY [flags]
    pmpython -m pcp_pmda_unifi.install_helper --discover URL API_KEY [flags]
    pmpython -m pcp_pmda_unifi.install_helper --generate-config [args]
    pmpython -m pcp_pmda_unifi.install_helper --env-config
"""

import argparse
import json
import os
import sys
import warnings
from typing import Dict, List, Optional, Tuple

import requests.exceptions
import urllib3

from pcp_pmda_unifi.collector import (
    UnifiAuthenticationError,
    UnifiClient,
    UnifiConnectionError,
)

# ---------------------------------------------------------------------------
# Connectivity validation
# ---------------------------------------------------------------------------


def validate_controller_connectivity(
    url: str,
    api_key: str,
    is_udm: bool = True,
    verify_ssl: bool = True,
) -> Tuple[bool, str]:
    """Test whether we can reach the controller and authenticate.

    Returns (True, success_message) or (False, error_description).
    SSL errors get a specific hint about verify_ssl=false because self-signed
    certs are the norm on UniFi OS devices.
    """
    client = UnifiClient(url, api_key, is_udm=is_udm, verify_ssl=verify_ssl)
    try:
        sysinfo = client.fetch_sysinfo("default")
        version = sysinfo[0].get("version", "unknown") if sysinfo else "unknown"
        return True, f"Connected. Controller version: {version}"
    except UnifiAuthenticationError:
        return False, "Authentication failed. Check your API key and permissions."
    except requests.exceptions.SSLError:
        return False, (
            "SSL certificate verification failed. "
            "If this controller uses a self-signed certificate, "
            "set verify_ssl=false."
        )
    except UnifiConnectionError as exc:
        return False, f"Connection failed: {exc}"
    except Exception as exc:
        return False, f"Unexpected error: {exc}"


# ---------------------------------------------------------------------------
# Site discovery
# ---------------------------------------------------------------------------


def discover_sites(
    url: str,
    api_key: str,
    is_udm: bool = True,
    verify_ssl: bool = True,
) -> List[Dict]:
    """Fetch the list of sites visible to this API key.

    Returns the raw list of site dicts from the controller API.
    """
    client = UnifiClient(url, api_key, is_udm=is_udm, verify_ssl=verify_ssl)
    return client.discover_sites()


# ---------------------------------------------------------------------------
# Config file generation
# ---------------------------------------------------------------------------


def generate_config(
    controller_name: str,
    url: str,
    api_key: str,
    sites: Optional[List[Dict]] = None,
    is_udm: bool = True,
    verify_ssl: bool = True,
    poll_interval: int = 10,
) -> str:
    """Build a valid INI config string for unifi.conf.

    The sites parameter is a list of dicts with at least a 'name' key.
    If None or empty, defaults to 'all'.
    """
    sites_value = _format_sites_value(sites)

    lines = [
        "[global]",
        f"poll_interval = {poll_interval}",
        "max_clients = 1000",
        "grace_period = 300",
        "enable_dpi = false",
        "",
        f"[controller:{controller_name}]",
        f"url = {url}",
        f"api_key = {api_key}",
        f"sites = {sites_value}",
        f"is_udm = {str(is_udm).lower()}",
        f"verify_ssl = {str(verify_ssl).lower()}",
        "",
    ]
    return "\n".join(lines)


def _format_sites_value(sites: Optional[List[Dict]]) -> str:
    """Turn a list of site dicts into a comma-separated string, or 'all'."""
    if not sites:
        return "all"
    names = [s.get("name", "") for s in sites if s.get("name")]
    return ",".join(names) if names else "all"


# ---------------------------------------------------------------------------
# Non-interactive config from environment variables
# ---------------------------------------------------------------------------


def build_config_from_env() -> Optional[str]:
    """Read UNIFI_* env vars and generate a config string.

    Returns None if the two required vars (UNIFI_URL, UNIFI_API_KEY) are
    not both present.  This powers the `./Install -e` non-interactive mode.
    """
    url = os.environ.get("UNIFI_URL")
    api_key = os.environ.get("UNIFI_API_KEY")

    if not url or not api_key:
        return None

    sites_raw = os.environ.get("UNIFI_SITES", "all")
    is_udm = _env_bool("UNIFI_IS_UDM", default=True)
    verify_ssl = _env_bool("UNIFI_VERIFY_SSL", default=True)
    poll_interval = int(os.environ.get("UNIFI_POLL_INTERVAL", "10"))

    # Convert sites string to list-of-dicts format expected by generate_config
    if sites_raw.strip().lower() == "all":
        sites = None
    else:
        sites = [{"name": s.strip()} for s in sites_raw.split(",") if s.strip()]

    return generate_config(
        controller_name="default",
        url=url,
        api_key=api_key,
        sites=sites,
        is_udm=is_udm,
        verify_ssl=verify_ssl,
        poll_interval=poll_interval,
    )


def _env_bool(var_name: str, default: bool = True) -> bool:
    """Read an env var as a boolean, defaulting if unset."""
    raw = os.environ.get(var_name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "yes", "1", "on")


# ---------------------------------------------------------------------------
# CLI entry point — called by Install shell script
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UniFi PMDA install helper"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--validate", action="store_true",
        help="Test controller connectivity",
    )
    group.add_argument(
        "--discover", action="store_true",
        help="Discover available sites",
    )
    group.add_argument(
        "--generate-config", action="store_true",
        help="Generate unifi.conf from arguments",
    )
    group.add_argument(
        "--env-config", action="store_true",
        help="Generate config from UNIFI_* environment variables",
    )

    parser.add_argument("--url", help="Controller URL")
    parser.add_argument("--api-key", help="API key")
    parser.add_argument("--is-udm", default="true", help="UniFi OS device (true/false)")
    parser.add_argument("--verify-ssl", default="true", help="Verify SSL (true/false)")
    parser.add_argument("--sites", help="Comma-separated site names")
    parser.add_argument("--controller-name", default="default", help="Controller section name")
    parser.add_argument("--poll-interval", type=int, default=10, help="Poll interval in seconds")

    return parser


def main() -> None:
    """CLI entry point for use by the Install shell script."""
    parser = _build_parser()
    args = parser.parse_args()

    is_udm = args.is_udm.lower() in ("true", "yes", "1")
    verify_ssl = args.verify_ssl.lower() in ("true", "yes", "1")

    if not verify_ssl:
        warnings.filterwarnings("ignore", category=urllib3.exceptions.InsecureRequestWarning)

    if args.validate:
        _handle_validate(args.url, args.api_key, is_udm, verify_ssl)
    elif args.discover:
        _handle_discover(args.url, args.api_key, is_udm, verify_ssl)
    elif args.generate_config:
        _handle_generate_config(args, is_udm, verify_ssl)
    elif args.env_config:
        _handle_env_config()


def _handle_validate(url: str, api_key: str, is_udm: bool, verify_ssl: bool) -> None:
    ok, msg = validate_controller_connectivity(url, api_key, is_udm, verify_ssl)
    print(msg)
    sys.exit(0 if ok else 1)


def _handle_discover(url: str, api_key: str, is_udm: bool, verify_ssl: bool) -> None:
    try:
        sites = discover_sites(url, api_key, is_udm, verify_ssl)
        print(json.dumps(sites))
    except Exception as exc:
        print(f"Error discovering sites: {exc}", file=sys.stderr)
        sys.exit(1)


def _handle_generate_config(args: argparse.Namespace, is_udm: bool, verify_ssl: bool) -> None:
    sites = None
    if args.sites:
        sites = [{"name": s.strip()} for s in args.sites.split(",")]

    config = generate_config(
        controller_name=args.controller_name,
        url=args.url,
        api_key=args.api_key,
        sites=sites,
        is_udm=is_udm,
        verify_ssl=verify_ssl,
        poll_interval=args.poll_interval,
    )
    print(config)


def _handle_env_config() -> None:
    config = build_config_from_env()
    if config is None:
        print("UNIFI_URL and UNIFI_API_KEY must be set", file=sys.stderr)
        sys.exit(1)
    print(config)


if __name__ == "__main__":
    main()
