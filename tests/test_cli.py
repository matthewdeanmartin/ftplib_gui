"""Smoke tests for the CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

import ftplib_gui
from ftplib_gui import app
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
        rc = main([])
    assert rc == 0
    app_main.assert_called_once()


def test_paths_command_prints_known_paths(capsys: pytest.CaptureFixture[str]) -> None:
    """The paths subcommand prints all managed filesystem locations."""
    app_data_path = Path("tmp") / "ftplib-gui"
    log_path = app_data_path / "logs" / "app.log"
    with (
        patch("ftplib_gui.cli.app_data_dir", return_value=app_data_path),
        patch("ftplib_gui.cli.log_file_path", return_value=log_path),
    ):
        rc = main(["paths"])

    assert rc == 0
    out = capsys.readouterr().out
    assert f"app-data: {app_data_path}" in out
    assert f"profiles: {app_data_path / 'profiles.json'}" in out
    assert f"log-file: {log_path}" in out


def test_profiles_command_lists_saved_profiles(capsys: pytest.CaptureFixture[str]) -> None:
    """The profiles subcommand prints saved connection profiles."""
    profile = ConnectionProfile(name="demo", host="ftp.example.com", port=2121, protocol="ftps", username="alice")
    with patch("ftplib_gui.cli.ProfileStore") as store_cls:
        store_cls.return_value.load.return_value = [profile]
        rc = main(["profiles"])

    assert rc == 0
    out = capsys.readouterr().out
    assert "demo: FTPS alice@ftp.example.com:2121" in out


def test_upgrade_command_dispatches() -> None:
    """The integrated upgrade subcommand should return its dispatcher exit code."""
    with patch("ftplib_gui.cli.run_command", return_value=10) as dispatcher:
        rc = main(["upgrade", "--check"])

    assert rc == 10
    dispatcher.assert_called_once()


def test_app_main_prints_distinct_startup_and_exit_notices(capsys: pytest.CaptureFixture[str]) -> None:
    """The GUI wrapper should print startup and shutdown notices to stderr."""
    startup_marker = object()
    exit_marker = object()

    def fake_render_notice(report: object | None) -> str:
        if report is startup_marker:
            return "startup notice"
        if report is exit_marker:
            return "exit notice"
        return ""

    with (
        patch("ftplib_gui.app.configure_logging"),
        patch("ftplib_gui.app.AppController") as controller_cls,
        patch("ftplib_gui.app.startup_report", return_value=startup_marker),
        patch("ftplib_gui.app.exit_report", return_value=exit_marker),
        patch("ftplib_gui.app.render_notice", side_effect=fake_render_notice),
    ):
        rc = app.main()

    assert rc == 0
    controller_cls.return_value.start.assert_called_once()
    assert capsys.readouterr().err == "startup notice\nexit notice\n"
