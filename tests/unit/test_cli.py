"""Tests for the unifi2dot CLI argument parsing (US5 - T047).

Tests the argparse setup only, not actual execution against a controller.
"""

import pytest

from pcp_pmda_unifi.cli import build_parser


class TestCliArgs:
    """Verify argparse configuration for the unifi2dot companion tool."""

    def test_url_is_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_api_key_is_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["--url", "https://unifi.local"])

    def test_site_is_required(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "--url", "https://unifi.local",
                "--api-key", "secret",
            ])

    def test_all_required_args_parse_successfully(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
        ])
        assert args.url == "https://unifi.local"
        assert args.api_key == "secret"
        assert args.site == "default"

    def test_format_defaults_to_dot(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
        ])
        assert args.format == "dot"

    def test_format_accepts_json(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
            "--format", "json",
        ])
        assert args.format == "json"

    def test_format_rejects_invalid_value(self):
        parser = build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "--url", "https://unifi.local",
                "--api-key", "secret",
                "--site", "default",
                "--format", "xml",
            ])

    def test_output_file_option(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
            "-o", "/tmp/topology.dot",
        ])
        assert args.output == "/tmp/topology.dot"

    def test_output_defaults_to_none(self):
        """None means stdout."""
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
        ])
        assert args.output is None

    def test_is_udm_flag_defaults_true(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
        ])
        assert args.is_udm is True

    def test_no_udm_flag(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
            "--no-udm",
        ])
        assert args.is_udm is False

    def test_no_verify_ssl_flag_exists(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
            "--no-verify-ssl",
        ])
        assert args.verify_ssl is False

    def test_verify_ssl_defaults_true(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
        ])
        assert args.verify_ssl is True

    def test_controller_name_option(self):
        """Controller name for instance name prefix."""
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
            "--controller", "branch",
        ])
        assert args.controller == "branch"

    def test_controller_name_defaults_to_main(self):
        parser = build_parser()
        args = parser.parse_args([
            "--url", "https://unifi.local",
            "--api-key", "secret",
            "--site", "default",
        ])
        assert args.controller == "main"
