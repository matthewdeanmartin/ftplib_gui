"""Tests for the FTP client service.

These exercise the listing parser and verify that the service emits the
right calls on a mock :class:`ftplib.FTP`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ftplib_gui.ftp_client import FTPClientService, parse_unix_list_line
from ftplib_gui.models import ConnectionProfile


# ---------------------------------------------------------------------------
# LIST parser
# ---------------------------------------------------------------------------
def test_parse_unix_file_line() -> None:
    entry = parse_unix_list_line("-rw-r--r-- 1 user group 1024 Jan 01 12:00 file.txt")
    assert entry is not None
    assert entry.name == "file.txt"
    assert entry.size == 1024
    assert entry.is_dir is False
    assert entry.permissions is not None and entry.permissions.startswith("-")


def test_parse_unix_dir_line() -> None:
    entry = parse_unix_list_line("drwxr-xr-x 2 user group 4096 Jan 01 12:00 folder")
    assert entry is not None
    assert entry.name == "folder"
    assert entry.is_dir is True


def test_parse_symlink_strips_target() -> None:
    entry = parse_unix_list_line("lrwxrwxrwx 1 user group 7 Jan 01 12:00 link -> target")
    assert entry is not None
    assert entry.name == "link"


def test_parse_returns_none_on_garbage() -> None:
    assert parse_unix_list_line("not an ftp listing") is None


# ---------------------------------------------------------------------------
# Service-level (mocked ftplib)
# ---------------------------------------------------------------------------
def test_connect_plain_ftp() -> None:
    profile = ConnectionProfile(name="x", host="h", port=21, username="u", password="p")
    svc = FTPClientService()

    with patch("ftplib_gui.ftp_client.ftplib.FTP") as ftp_cls:
        ftp = MagicMock()
        ftp_cls.return_value = ftp
        svc.connect(profile)

    ftp.connect.assert_called_once_with(host="h", port=21, timeout=30)
    ftp.login.assert_called_once_with(user="u", passwd="p")
    ftp.set_pasv.assert_called_once_with(True)


def test_connect_ftps_calls_prot_p() -> None:
    profile = ConnectionProfile(name="x", host="h", port=21, protocol="ftps", username="u", password="p")
    svc = FTPClientService()

    with patch("ftplib_gui.ftp_client.ftplib.FTP_TLS") as ftps_cls:
        ftp = MagicMock()
        ftps_cls.return_value = ftp
        svc.connect(profile)

    ftp.login.assert_called_once_with(user="u", passwd="p")
    ftp.prot_p.assert_called_once()


def test_connect_anonymous() -> None:
    profile = ConnectionProfile(name="x", host="h", anonymous=True)
    svc = FTPClientService()

    with patch("ftplib_gui.ftp_client.ftplib.FTP") as ftp_cls:
        ftp = MagicMock()
        ftp_cls.return_value = ftp
        svc.connect(profile)

    ftp.login.assert_called_once_with(user="anonymous", passwd="anonymous@")


def test_passive_false_propagates() -> None:
    profile = ConnectionProfile(name="x", host="h", passive=False)
    svc = FTPClientService()

    with patch("ftplib_gui.ftp_client.ftplib.FTP") as ftp_cls:
        ftp = MagicMock()
        ftp_cls.return_value = ftp
        svc.connect(profile)

    ftp.set_pasv.assert_called_once_with(False)


def test_filesystem_ops_pass_through() -> None:
    svc = FTPClientService()
    fake = MagicMock()
    svc._ftp = fake  # type: ignore[attr-defined]

    svc.mkdir("/a")
    fake.mkd.assert_called_once_with("/a")

    svc.rmdir("/a")
    fake.rmd.assert_called_once_with("/a")

    svc.delete_file("/a/b")
    fake.delete.assert_called_once_with("/a/b")

    svc.rename("/a", "/b")
    fake.rename.assert_called_once_with("/a", "/b")
