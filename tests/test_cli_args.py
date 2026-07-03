"""Tests for the CLI argument parser."""

from __future__ import annotations

import pytest

from ftplib_gui.cli import build_parser


def test_default_no_args() -> None:
    args = build_parser().parse_args([])
    assert args.command is None
    assert args.host is None
    assert args.port is None
    assert args.protocol is None
    assert args.debug is False


def test_host_and_port() -> None:
    args = build_parser().parse_args(["--host", "ftp.example.com", "--port", "2121"])
    assert args.host == "ftp.example.com"
    assert args.port == 2121


def test_protocol_choice_validated() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--protocol", "scp"])


def test_active_and_passive_are_exclusive() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(["--active", "--passive"])


def test_local_and_remote_dirs() -> None:
    args = build_parser().parse_args(["--local-dir", "/tmp/x", "--remote-dir", "/pub", "--profile", "ex"])
    assert args.local_dir == "/tmp/x"
    assert args.remote_dir == "/pub"
    assert args.profile == "ex"


def test_gui_subcommand_accepts_launch_options() -> None:
    args = build_parser().parse_args(["gui", "--host", "ftp.example.com", "--port", "2121"])
    assert args.command == "gui"
    assert args.host == "ftp.example.com"
    assert args.port == 2121


def test_paths_subcommand_defaults_to_all() -> None:
    args = build_parser().parse_args(["paths"])
    assert args.command == "paths"
    assert args.selection == "all"


def test_profiles_subcommand_parses() -> None:
    args = build_parser().parse_args(["profiles"])
    assert args.command == "profiles"


def test_upgrade_subcommand_parses() -> None:
    args = build_parser().parse_args(["upgrade", "--check"])
    assert args.command == "upgrade"
    assert args._diu_check is True


def test_check_updates_subcommand_parses() -> None:
    args = build_parser().parse_args(["check-updates", "--no-network"])
    assert args.command == "check-updates"
    assert args._diu_no_network is True
