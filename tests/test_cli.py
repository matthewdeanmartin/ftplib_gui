"""Smoke tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import ftplib_gui
from ftplib_gui.__about__ import __version__
from ftplib_gui.cli import main
from ftplib_gui.models import ConnectionProfile


def test_import() -> None:
    """Package can be imported."""
    assert ftplib_gui.__version__ == __version__


def test_version() -> None:
    """Package exposes a version string."""
    assert __version__ is not None


def test_main_launches_gui_by_default() -> None:
    """No subcommand keeps the existing launch behavior."""
    with patch("ftplib_gui.cli.app_main") as app_main:
        main([])
    app_main.assert_called_once()


def test_paths_command_prints_known_paths(capsys: pytest.CaptureFixture[str]) -> None:
    """The paths subcommand prints all managed filesystem locations."""
    with (
        patch("ftplib_gui.cli.app_data_dir", return_value=Path("C:/tmp/ftplib-gui")),
        patch("ftplib_gui.cli.log_file_path", return_value=Path("C:/tmp/ftplib-gui/logs/app.log")),
    ):
        main(["paths"])

    out = capsys.readouterr().out
    assert "app-data: C:\\tmp\\ftplib-gui" in out
    assert "profiles: C:\\tmp\\ftplib-gui\\profiles.json" in out
    assert "log-file: C:\\tmp\\ftplib-gui\\logs\\app.log" in out


def test_profiles_command_lists_saved_profiles(capsys: pytest.CaptureFixture[str]) -> None:
    """The profiles subcommand prints saved connection profiles."""
    profile = ConnectionProfile(name="demo", host="ftp.example.com", port=2121, protocol="ftps", username="alice")
    with patch("ftplib_gui.cli.ProfileStore") as store_cls:
        store_cls.return_value.load.return_value = [profile]
        main(["profiles"])

    out = capsys.readouterr().out
    assert "demo: FTPS alice@ftp.example.com:2121" in out
