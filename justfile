# pcp-pmda-unifi developer workflows
# Install: brew install just

venv_dir := env("VENV_DIR", ".venv")
python := venv_dir / "bin/python"

# List available recipes
default:
    @just --list

# Create virtualenv and install everything
# --system-site-packages gives access to PCP bindings installed by the OS package manager
setup:
    python3 -m venv --system-site-packages {{ venv_dir }}
    {{ venv_dir }}/bin/pip install --upgrade pip
    {{ venv_dir }}/bin/pip install -e ".[test,dev]"
    @echo "\nReady. Run: just test"

# Run tests
test:
    {{ python }} -m pytest tests/unit/ tests/integration/ -v

# Run tests with coverage
test-cov:
    {{ python }} -m pytest tests/unit/ --cov=pcp_pmda_unifi --cov-report=term-missing

# Lint and typecheck
check:
    {{ python }} -m ruff check src/ tests/
    {{ python }} -m mypy src/pcp_pmda_unifi/ --ignore-missing-imports

# Clean build artifacts
clean:
    rm -rf build/ dist/ *.egg-info .mypy_cache .ruff_cache .pytest_cache
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
