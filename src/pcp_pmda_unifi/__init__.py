"""PCP PMDA for Ubiquiti UniFi network infrastructure monitoring."""

try:
    from pcp_pmda_unifi._version import __version__
except ModuleNotFoundError:
    __version__ = "0.0.0+unknown"

# PCP bindings are checked at PMDA startup, not at import time.
# This allows unit tests and the unifi2dot companion tool to run
# without PCP installed.
