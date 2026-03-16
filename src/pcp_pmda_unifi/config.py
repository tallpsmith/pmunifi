"""Configuration parser for the UniFi PCP PMDA.

Parses INI-style configuration with [global] defaults and one or more
[controller:NAME] sections.  Supports environment variable overrides
for headless installation (FR-006).

Usage:
    from pcp_pmda_unifi.config import parse_config
    cfg = parse_config(ini_text)
"""

import configparser
import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

VALID_LOG_LEVELS = frozenset({"debug", "info", "warning", "error", "critical"})
CONTROLLER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
MINIMUM_POLL_INTERVAL = 10


@dataclass
class GlobalSettings:
    """PMDA-wide configuration knobs."""
    poll_interval: int = 30
    max_clients: int = 1000
    grace_period: int = 300
    enable_dpi: bool = False
    log_level: str = "warning"


@dataclass
class ControllerConfig:
    """Connection parameters for a single UniFi controller."""
    name: str
    url: str
    api_key: str
    sites: List[str] = field(default_factory=lambda: ["all"])
    is_udm: bool = True
    verify_ssl: bool = True
    ca_cert: Optional[str] = None
    poll_interval: Optional[int] = None


@dataclass
class PmdaConfig:
    """Top-level configuration returned by parse_config."""
    global_settings: GlobalSettings
    controllers: Dict[str, ControllerConfig]


# ---------------------------------------------------------------------------
# Boolean parsing helper
# ---------------------------------------------------------------------------

_TRUTHY = frozenset({"true", "yes", "1", "on"})
_FALSY = frozenset({"false", "no", "0", "off"})


def _parse_bool(value: str, field_name: str) -> bool:
    """Convert a string to a boolean, raising ValueError on garbage input."""
    normalised = value.strip().lower()
    if normalised in _TRUTHY:
        return True
    if normalised in _FALSY:
        return False
    raise ValueError(f"{field_name} must be a boolean, got '{value}'")


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_global(settings: GlobalSettings) -> None:
    """Enforce numeric bounds and value constraints on global settings."""
    if settings.poll_interval < MINIMUM_POLL_INTERVAL:
        raise ValueError(
            f"poll_interval must be >= {MINIMUM_POLL_INTERVAL}, "
            f"got {settings.poll_interval}"
        )
    if settings.max_clients < 0:
        raise ValueError(
            f"max_clients must be >= 0, got {settings.max_clients}"
        )
    if settings.grace_period < 0:
        raise ValueError(
            f"grace_period must be >= 0, got {settings.grace_period}"
        )
    if settings.log_level.lower() not in VALID_LOG_LEVELS:
        raise ValueError(
            f"log_level must be one of {sorted(VALID_LOG_LEVELS)}, "
            f"got '{settings.log_level}'"
        )


def _validate_controller_name(name: str) -> None:
    """Controller NAME must be alphanumeric, hyphens, or underscores."""
    if not CONTROLLER_NAME_PATTERN.match(name):
        raise ValueError(
            f"Controller name '{name}' is invalid — "
            f"only alphanumeric characters, hyphens, and underscores allowed"
        )


def _validate_controller(ctrl: ControllerConfig) -> None:
    """Enforce required fields and value constraints on a controller."""
    if not ctrl.url:
        raise ValueError(
            f"Controller '{ctrl.name}': url is required"
        )
    if not ctrl.url.startswith("http://") and not ctrl.url.startswith("https://"):
        raise ValueError(
            f"Controller '{ctrl.name}': url must start with http:// or https://"
        )
    if not ctrl.api_key:
        raise ValueError(
            f"Controller '{ctrl.name}': api_key is required"
        )
    if ctrl.poll_interval is not None and ctrl.poll_interval < MINIMUM_POLL_INTERVAL:
        raise ValueError(
            f"Controller '{ctrl.name}': poll_interval must be >= "
            f"{MINIMUM_POLL_INTERVAL}, got {ctrl.poll_interval}"
        )


# ---------------------------------------------------------------------------
# Sites string parsing
# ---------------------------------------------------------------------------


def _parse_sites(raw: str) -> List[str]:
    """Split a comma-separated sites string into a list of trimmed slugs."""
    return [s.strip() for s in raw.split(",") if s.strip()]


# ---------------------------------------------------------------------------
# Environment variable overlay
# ---------------------------------------------------------------------------


def _apply_environment_overrides(parser: configparser.ConfigParser) -> None:
    """Inject UNIFI_* env vars as a [controller:default] section.

    Environment variables take precedence over file-based config for the
    'default' controller only.  This supports non-interactive Install (-e).
    """
    env_url = os.environ.get("UNIFI_URL")
    env_api_key = os.environ.get("UNIFI_API_KEY")

    if not env_url and not env_api_key:
        return

    section = "controller:default"
    if not parser.has_section(section):
        parser.add_section(section)

    if env_url:
        parser.set(section, "url", env_url)
    if env_api_key:
        parser.set(section, "api_key", env_api_key)

    env_sites = os.environ.get("UNIFI_SITES")
    if env_sites:
        parser.set(section, "sites", env_sites)

    env_is_udm = os.environ.get("UNIFI_IS_UDM")
    if env_is_udm:
        parser.set(section, "is_udm", env_is_udm)

    env_verify_ssl = os.environ.get("UNIFI_VERIFY_SSL")
    if env_verify_ssl:
        parser.set(section, "verify_ssl", env_verify_ssl)

    env_poll = os.environ.get("UNIFI_POLL_INTERVAL")
    if env_poll:
        if not parser.has_section("global"):
            parser.add_section("global")
        parser.set("global", "poll_interval", env_poll)


# ---------------------------------------------------------------------------
# Section parsers
# ---------------------------------------------------------------------------


def _parse_global_section(parser: configparser.ConfigParser) -> GlobalSettings:
    """Extract [global] settings with sensible defaults."""
    settings = GlobalSettings()

    if not parser.has_section("global"):
        return settings

    section = dict(parser.items("global"))

    if "poll_interval" in section:
        settings.poll_interval = int(section["poll_interval"])
    if "max_clients" in section:
        settings.max_clients = int(section["max_clients"])
    if "grace_period" in section:
        settings.grace_period = int(section["grace_period"])
    if "enable_dpi" in section:
        settings.enable_dpi = _parse_bool(section["enable_dpi"], "enable_dpi")
    if "log_level" in section:
        settings.log_level = section["log_level"].strip().lower()

    return settings


def _parse_controller_section(
    name: str,
    section: Dict[str, str],
    global_poll: int,
) -> ControllerConfig:
    """Build a ControllerConfig from a raw section dict."""
    url = section.get("url", "")
    api_key = section.get("api_key", "")
    sites = _parse_sites(section.get("sites", "all"))
    is_udm = _parse_bool(section.get("is_udm", "true"), "is_udm")
    verify_ssl = _parse_bool(section.get("verify_ssl", "true"), "verify_ssl")
    ca_cert = section.get("ca_cert") or None

    raw_poll = section.get("poll_interval")
    poll_interval = int(raw_poll) if raw_poll else None

    return ControllerConfig(
        name=name,
        url=url,
        api_key=api_key,
        sites=sites,
        is_udm=is_udm,
        verify_ssl=verify_ssl,
        ca_cert=ca_cert,
        poll_interval=poll_interval,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

CONTROLLER_SECTION_PREFIX = "controller:"


def parse_config(ini_content: str) -> PmdaConfig:
    """Parse an INI configuration string into a validated PmdaConfig.

    Raises ValueError if validation rules are violated (missing required
    fields, out-of-range numerics, malformed controller names).
    """
    parser = configparser.ConfigParser()
    parser.optionxform = str  # type: ignore[assignment]  # preserve case sensitivity
    parser.read_string(ini_content)

    _apply_environment_overrides(parser)

    global_settings = _parse_global_section(parser)
    _validate_global(global_settings)

    controllers: Dict[str, ControllerConfig] = {}
    for section_name in parser.sections():
        if not section_name.startswith(CONTROLLER_SECTION_PREFIX):
            continue

        ctrl_name = section_name[len(CONTROLLER_SECTION_PREFIX):]
        _validate_controller_name(ctrl_name)

        section_dict = dict(parser.items(section_name))
        ctrl = _parse_controller_section(
            ctrl_name, section_dict, global_settings.poll_interval
        )
        _validate_controller(ctrl)
        controllers[ctrl_name] = ctrl

    if not controllers:
        raise ValueError(
            "At least one [controller:NAME] section is required"
        )

    return PmdaConfig(
        global_settings=global_settings,
        controllers=controllers,
    )
