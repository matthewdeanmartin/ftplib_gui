"""Tests for the CLI argument parser."""

from __future__ import annotations

import pytest

from ftplib_gui.cli import build_parser


def test_default_no_args() -> None:
    args = build_parser().parse_args([])
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
