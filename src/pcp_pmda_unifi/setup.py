"""Setup entry point for the UniFi PCP PMDA.

Deploys PMDA files to $PCP_PMDAS_DIR/unifi/ so the user can then
run ./Install to register the PMDA with PMCD.

Usage:
    pcp-pmda-unifi-setup install
    pcp-pmda-unifi-setup uninstall
"""

import argparse
import os
import shutil
from pathlib import Path
from typing import Optional

# Python 3.8 compat: importlib.resources.files() arrived in 3.9
try:
    from importlib.resources import files as _resource_files
except ImportError:
    from importlib_resources import files as _resource_files  # type: ignore[no-redef]


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LAUNCHER_SCRIPT = """\
#!/usr/bin/env pmpython
from pcp_pmda_unifi.pmda import run
run()
"""

DEPLOY_ARTIFACTS = ["Install", "Remove", "unifi.conf.sample"]

EXECUTABLE_PERMISSIONS = 0o755

_UNSET = object()


# ---------------------------------------------------------------------------
# Deploy logic
# ---------------------------------------------------------------------------


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


def _copy_deploy_artifacts(target_dir: Path) -> None:
    """Copy Install, Remove, and sample config from package data."""
    deploy_pkg = _resource_files("pcp_pmda_unifi").joinpath("deploy")
    for filename in DEPLOY_ARTIFACTS:
        source = deploy_pkg.joinpath(filename)
        dest = target_dir / filename
        # importlib.resources returns Traversable; read and write to handle
        # both filesystem and zip-packaged distributions
        dest.write_bytes(source.read_bytes())


def _generate_launcher(target_dir: Path) -> None:
    """Write the pmdaunifi.python launcher that PCP will invoke."""
    launcher = target_dir / "pmdaunifi.python"
    launcher.write_text(LAUNCHER_SCRIPT)


def _set_executable_permissions(target_dir: Path) -> None:
    """Make Install, Remove, and the launcher executable."""
    executables = ["Install", "Remove", "pmdaunifi.python"]
    for filename in executables:
        filepath = target_dir / filename
        filepath.chmod(EXECUTABLE_PERMISSIONS)


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
    """Copy pmrep-unifi.conf to the pmrep config directory.

    Silently skips if the directory is not writable (e.g. auto-detected
    system dir without root privileges).
    """
    if pmrep_dir is None:
        return
    source = _resource_files("pcp_pmda_unifi").joinpath("deploy", "pmrep-unifi.conf")
    dest = pmrep_dir / "pmrep-unifi.conf"
    try:
        dest.write_bytes(source.read_bytes())
    except PermissionError:
        pass


# ---------------------------------------------------------------------------
# Uninstall
# ---------------------------------------------------------------------------


def _remove_pmdas_dir(target_dir: Path) -> None:
    """Remove the PMDA directory.  Leaves unifi.conf if it exists."""
    if target_dir.exists():
        shutil.rmtree(target_dir)
        print(f"Removed {target_dir}")
    else:
        print(f"Nothing to remove: {target_dir} does not exist")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _determine_target_dir() -> Path:
    """Figure out where PCP expects PMDAs to live."""
    pcp_pmdas_dir = os.environ.get("PCP_PMDAS_DIR", "/var/lib/pcp/pmdas")
    return Path(pcp_pmdas_dir) / "unifi"


def main() -> None:
    """Entry point for the pcp-pmda-unifi-setup console script."""
    parser = argparse.ArgumentParser(
        description="Deploy or remove the UniFi PCP PMDA files"
    )
    parser.add_argument(
        "action",
        choices=["install", "uninstall"],
        help="install: copy files to PCP_PMDAS_DIR; uninstall: remove them",
    )
    args = parser.parse_args()

    target = _determine_target_dir()

    if args.action == "install":
        deploy_to_pmdas_dir(target)
        _print_install_instructions(target)
    elif args.action == "uninstall":
        _remove_pmdas_dir(target)


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


if __name__ == "__main__":
    main()
