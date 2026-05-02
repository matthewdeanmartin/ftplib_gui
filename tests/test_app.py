from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from ftplib_gui.app import AppController
from ftplib_gui.models import ConnectionProfile, UIEvent


@pytest.fixture
def app():
    with patch("ftplib_gui.app.MainWindow"), patch("ftplib_gui.app.attach_gui_sink"):
        args = argparse.Namespace(debug=False)
        controller = AppController(args=args)
        return controller


def test_handle_connected(app):
    profile = ConnectionProfile(name="test", host="localhost")
    event = UIEvent("connected", {"profile": profile, "cwd": "/", "entries": []})

    app._handle_event(event)
    assert app._connected is True
    app.window.remote_browser.show_entries.assert_called_once_with("/", [])


def test_handle_connection_failed(app):
    event = UIEvent("connection_failed", {"error": "timeout"})

    with patch("ftplib_gui.app.messagebox.showerror") as mock_err:
        app._handle_event(event)
        assert app._connected is False
        mock_err.assert_called_once()


def test_apply_cli_args_profile(app):
    app._args = argparse.Namespace(profile="myprofile")
    p1 = ConnectionProfile(name="myprofile", host="localhost")

    with patch.object(app.profile_store, "load", return_value=[p1]):
        app._apply_cli_args()
        app.window.connection_bar.populate.assert_called_once_with(p1)


def test_apply_cli_args_host(app):
    app._args = argparse.Namespace(host="ftp.site.com", port=2121, protocol="ftps")

    app._apply_cli_args()
    # Should create an ad-hoc profile
    call_args = app.window.connection_bar.populate.call_args[0][0]
    assert call_args.host == "ftp.site.com"
    assert call_args.port == 2121
    assert call_args.protocol == "ftps"


def test_submit_ftp(app):
    mock_func = MagicMock()
    app._submit_ftp(mock_func)

    # Manually pull from queue since we don't want to start the thread
    job = app._ftp_jobs.get_nowait()
    assert job == mock_func


def test_refresh_status_disconnected(app):
    app._connected = False
    app._refresh_status()
    app.window.set_status.assert_called_with("Disconnected")
