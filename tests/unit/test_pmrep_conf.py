"""Tests for pmrep-unifi.conf structure and correctness.

Validates the pmrep config as a static artifact: parses as INI,
checks section names, verifies metric references match the PMDA's
registered namespaces, and confirms rate views have correct overrides.
"""

import configparser
from pathlib import Path

import pytest

CONF_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "pcp_pmda_unifi"
    / "deploy"
    / "pmrep-unifi.conf"
)

# All view sections the conf file must define (no more, no fewer).
EXPECTED_SECTIONS = [
    "unifi-health",
    "unifi-site",
    "unifi-site-traffic",
    "unifi-device-summary",
    "unifi-device-traffic",
    "unifi-switch-detail",
    "unifi-switch-traffic",
    "unifi-switch-ports",
    "unifi-ap-detail",
    "unifi-gateway-health",
    "unifi-gateway-traffic",
]

# Views that show rate-converted counters (samples=2, interval=5s).
RATE_SECTIONS = [
    "unifi-site-traffic",
    "unifi-device-traffic",
    "unifi-switch-traffic",
    "unifi-switch-ports",
    "unifi-ap-detail",
    "unifi-gateway-traffic",
]

# Views that show instantaneous gauges (samples=1, oneshot).
ONESHOT_SECTIONS = [
    "unifi-health",
    "unifi-site",
    "unifi-device-summary",
    "unifi-switch-detail",
    "unifi-gateway-health",
]

# All valid unifi.* metric prefixes registered in the PMDA.
VALID_METRIC_PREFIXES = (
    "unifi.site.",
    "unifi.device.",
    "unifi.switch.port.",
    "unifi.ap.",
    "unifi.gateway.",
    "unifi.dpi.",
    "unifi.client.",
    "unifi.controller.",
)

# Comprehensive set of pmrep section-level options (not metric references).
PMREP_OPTIONS = {
    "header",
    "unitinfo",
    "globals",
    "timestamp",
    "width",
    "precision",
    "delimiter",
    "repeat_header",
    "colxrow",
    "separate_header",
    "timefmt",
    "interpol",
    "count_scale",
    "space_scale",
    "time_scale",
    "output",
    "interval",
    "samples",
    "type",
    "ignore_incompat",
    "instances",
    "live_filter",
    "predicate",
    "sort_metric",
    "names",
    "names_change",
    "omit_flat",
    "include_labels",
    "include_texts",
    "column",
    "overall_rank",
    "overall_rank_alt",
    "rank",
    "limit_filter",
    "limit_filter_force",
    "invert_filter",
    "text_label",
}


@pytest.fixture()
def conf():
    """Parse the pmrep conf file and return a ConfigParser instance."""
    assert CONF_PATH.exists(), f"Config file not found: {CONF_PATH}"
    parser = configparser.ConfigParser()
    parser.read(str(CONF_PATH))
    return parser


# ---------------------------------------------------------------------------
# TestConfStructure
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestConfStructure:
    """The conf file is valid INI with exactly the expected view sections."""

    def test_parses_as_valid_ini(self, conf):
        """Config has at least one section (not empty / malformed)."""
        assert len(conf.sections()) > 0

    @pytest.mark.parametrize("section", EXPECTED_SECTIONS)
    def test_has_expected_section(self, conf, section):
        """Each required view section exists in the config."""
        assert conf.has_section(section), f"Missing section: [{section}]"

    def test_has_exactly_expected_sections(self, conf):
        """No unexpected sections exist (aside from 'options')."""
        view_sections = [s for s in conf.sections() if s != "options"]
        assert sorted(view_sections) == sorted(EXPECTED_SECTIONS)


# ---------------------------------------------------------------------------
# TestRateViewOverrides
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRateViewOverrides:
    """Rate-converted views need samples=2 and interval=5s."""

    @pytest.mark.parametrize("section", RATE_SECTIONS)
    def test_rate_view_has_samples_2(self, conf, section):
        """Rate views must request 2 samples to compute a delta."""
        assert conf.get(section, "samples") == "2"

    @pytest.mark.parametrize("section", RATE_SECTIONS)
    def test_rate_view_interval_exceeds_poll_default(self, conf, section):
        """Rate views interval (15s) exceeds default poll_interval (10s)."""
        assert conf.get(section, "interval") == "15s"



# ---------------------------------------------------------------------------
# TestOneshotViewDefaults
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestOneshotViewDefaults:
    """One-shot views must set samples=1 for instant snapshot output."""

    @pytest.mark.parametrize("section", ONESHOT_SECTIONS)
    def test_oneshot_view_has_samples_1(self, conf, section):
        """Instant/gauge views only need a single sample."""
        assert conf.get(section, "samples") == "1"


# ---------------------------------------------------------------------------
# TestMetricReferences
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMetricReferences:
    """Every dotted key that isn't a pmrep option must be a valid unifi.* metric."""

    def test_all_metric_keys_are_valid(self, conf):
        """Keys containing a dot that aren't pmrep options start with a valid prefix."""
        bad_keys = []
        for section in conf.sections():
            if section == "options":
                continue
            for key in conf.options(section):
                if "." not in key:
                    continue
                if key in PMREP_OPTIONS:
                    continue
                if not key.startswith(VALID_METRIC_PREFIXES):
                    bad_keys.append(f"[{section}] {key}")
        assert bad_keys == [], f"Invalid metric references: {bad_keys}"


# ---------------------------------------------------------------------------
# TestViewsUseColxrow
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestViewsUseColxrow:
    """All views must set colxrow for instance-per-column layout."""

    @pytest.mark.parametrize("section", EXPECTED_SECTIONS)
    def test_view_has_colxrow(self, conf, section):
        """The view sets colxrow to an instance-identifying metric."""
        value = conf.get(section, "colxrow", fallback="")
        assert value.strip(), f"[{section}] colxrow must be set to a non-empty value"


# ---------------------------------------------------------------------------
# TestViewsDisableGlobals
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestViewsDisableGlobals:
    """All views must disable globals to avoid cluttering output."""

    @pytest.mark.parametrize("section", EXPECTED_SECTIONS)
    def test_view_disables_globals(self, conf, section):
        """The view sets globals = no."""
        assert conf.get(section, "globals") == "no", (
            f"[{section}] globals should be 'no'"
        )
