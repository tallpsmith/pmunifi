"""PCP PMDA for Ubiquiti UniFi network infrastructure monitoring."""

__version__ = "0.1.0"

# PCP bindings are checked at PMDA startup, not at import time.
# This allows unit tests and the unifi2dot companion tool to run
# without PCP installed.
