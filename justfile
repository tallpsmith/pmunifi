# pcp-pmda-unifi developer workflows
# Requires: just, uv
# Install: brew install just uv

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

# Serve docs locally
docs:
    uvx --with mkdocs-material mkdocs serve --config-file docs/mkdocs.yml

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .mypy_cache .ruff_cache .pytest_cache {{ venv_dir }}
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
