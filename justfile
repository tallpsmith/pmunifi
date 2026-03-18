# pcp-pmda-unifi developer workflows
# Requires: just, uv
# Install: brew install just uv

set dotenv-load

venv_dir := env("VENV_DIR", ".venv")

# List available recipes
default:
    @just --list

# Create virtualenv and install everything
# --system-site-packages gives access to PCP bindings installed by the OS package manager
setup:
    uv venv --system-site-packages {{ venv_dir }}
    uv pip install --python {{ venv_dir }}/bin/python -e ".[test,dev]"
    @echo "\nReady. Run: just test"

# Run unit + integration tests
test:
    uv run --active pytest tests/unit/ tests/integration/ -v

# Run unit tests with coverage
test-cov:
    uv run --active pytest tests/unit/ --cov=pcp_pmda_unifi --cov-report=term-missing

# Lint and typecheck
check:
    uvx ruff check src/ tests/
    uv run --active mypy src/pcp_pmda_unifi/ --ignore-missing-imports

# Build sdist and wheel
build:
    uv build

# Build wheel, install into a fresh venv, deploy PMDA files, and register
# Simulates a full PyPI install without publishing a release
#
# Set these env vars in .env (loaded automatically via dotenv-load):
#   UNIFI_URL         - controller URL        (e.g. https://10.120.1.1)
#   UNIFI_API_KEY     - API key
#   UNIFI_IS_UDM      - true/false            (default: true)
#   UNIFI_VERIFY_SSL  - true/false            (default: true)
#   UNIFI_SITES       - comma-separated names (default: all)
#   UNIFI_POLL_INTERVAL - seconds             (default: 10)
trial-install: clean-dist build
    #!/usr/bin/env bash
    set -euo pipefail
    trial_dir="${TRIAL_VENV:-/tmp/pcp-pmda-unifi-trial}"
    if [[ -z "$trial_dir" || "$trial_dir" == "/" || "$trial_dir" == "/tmp" ]]; then
        echo "ERROR: TRIAL_VENV resolved to '$trial_dir' — refusing to sudo rm -rf that." >&2
        exit 1
    fi
    echo "Removing previous trial venv at $trial_dir (requires sudo)..."
    sudo rm -rf "$trial_dir"
    uv venv "$trial_dir"
    uv pip install --python "$trial_dir/bin/python" dist/pcp_pmda_unifi-*.whl
    sudo "$trial_dir/bin/pcp-pmda-unifi-setup" install
    cd /var/lib/pcp/pmdas/unifi && sudo -E ./Install -e

# Remove old wheels/sdists before a fresh build
clean-dist:
    rm -rf dist/

# Serve docs locally
docs:
    uvx --with mkdocs-material mkdocs serve --config-file docs/mkdocs.yml

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .mypy_cache .ruff_cache .pytest_cache {{ venv_dir }}
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
