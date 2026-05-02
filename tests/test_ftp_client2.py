from __future__ import annotations

import ftplib
from unittest.mock import MagicMock, patch

from ftplib_gui.ftp_client import FTPClientService, parse_unix_list_line
from ftplib_gui.models import ConnectionProfile


def test_parse_unix_list_line():
    line = "-rw-r--r-- 1 user group 1024 Jan 01 12:00 file.txt"
    entry = parse_unix_list_line(line)
    assert entry is not None
    assert entry.name == "file.txt"
    assert entry.is_dir is False
    assert entry.size == 1024
    assert entry.modified is not None
    assert entry.modified.month == 1
    assert entry.modified.day == 1

    dir_line = "drwxr-xr-x 2 user group 4096 Jan 01 12:00 folder"
    entry = parse_unix_list_line(dir_line)
    assert entry is not None
    assert entry.is_dir is True


@patch("ftplib.FTP")
def test_connect_ftp(mock_ftp_cls):
    mock_ftp = mock_ftp_cls.return_value
    service = FTPClientService()
    profile = ConnectionProfile(name="test", host="localhost")

    service.connect(profile)
    mock_ftp.connect.assert_called_once_with(host="localhost", port=21, timeout=30)
    mock_ftp.login.assert_called_once()
    assert service.is_connected() is True


@patch("ftplib.FTP_TLS")
@patch("ssl.create_default_context")
def test_connect_ftps(mock_ssl_ctx, mock_ftps_cls):
    mock_ftps = mock_ftps_cls.return_value
    service = FTPClientService()
    profile = ConnectionProfile(name="test", host="localhost", protocol="ftps")

    service.connect(profile)
    mock_ftps_cls.assert_called_once()
    mock_ftps.prot_p.assert_called_once()


def test_listdir_mlsd():
    service = FTPClientService()
    service._ftp = MagicMock()
    service._ftp.mlsd.return_value = [
        ("file.txt", {"type": "file", "size": "100", "modify": "20230101120000"}),
        ("subdir", {"type": "dir"}),
    ]

    entries = service.listdir("/")
    assert len(entries) == 2
    assert entries[0].name == "file.txt"
    assert entries[0].size == 100
    assert entries[1].is_dir is True


def test_listdir_list_fallback():
    service = FTPClientService()
    service._ftp = MagicMock()
    service._ftp.mlsd.side_effect = ftplib.error_perm("Not supported")

    def mock_retrlines(cmd, callback):
        callback("-rw-r--r-- 1 user group 1024 Jan 01 12:00 file.txt")

    service._ftp.retrlines.side_effect = mock_retrlines

    entries = service.listdir("/")
    assert len(entries) == 1
    assert entries[0].name == "file.txt"


def test_mkdir():
    service = FTPClientService()
    service._ftp = MagicMock()
    service.mkdir("/test")
    service._ftp.mkd.assert_called_once_with("/test")


def test_delete_file():
    service = FTPClientService()
    service._ftp = MagicMock()
    service.delete_file("/test.txt")
    service._ftp.delete.assert_called_once_with("/test.txt")


def test_rename():
    service = FTPClientService()
    service._ftp = MagicMock()
    service.rename("/old", "/new")
    service._ftp.rename.assert_called_once_with("/old", "/new")
