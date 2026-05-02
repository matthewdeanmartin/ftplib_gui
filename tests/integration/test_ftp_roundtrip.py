"""Round-trip tests against a live FTP server backend."""

from __future__ import annotations

import pathlib
import threading
import time

import pytest

from ftplib_gui.ftp_client import FTPClientService
from ftplib_gui.models import ConnectionProfile

from .conftest import RunningServer


def _profile(server: RunningServer) -> ConnectionProfile:
    return ConnectionProfile(
        name="it",
        host=server.host,
        port=server.port,
        username=server.user,
        password=server.password,
        passive=True,
    )


def test_connect_and_list(ftp_server: RunningServer) -> None:
    (ftp_server.root / "hello.txt").write_text("hi", encoding="utf-8")
    (ftp_server.root / "subdir").mkdir()

    svc = FTPClientService()
    svc.connect(_profile(ftp_server))
    try:
        entries = svc.listdir()
        names = {e.name for e in entries}
        assert "hello.txt" in names
        assert "subdir" in names
        sub = next(e for e in entries if e.name == "subdir")
        assert sub.is_dir
    finally:
        svc.disconnect()


def test_upload_and_download_roundtrip(ftp_server: RunningServer, tmp_path: pathlib.Path) -> None:
    payload = b"the quick brown fox " * 100  # 2,000 bytes
    src = tmp_path / "in.bin"
    src.write_bytes(payload)

    svc = FTPClientService()
    svc.connect(_profile(ftp_server))
    try:
        cancel = threading.Event()
        progress: list[int] = []
        svc.upload_file(
            local_path=str(src),
            remote_path="uploaded.bin",
            progress_callback=progress.append,
            cancel_event=cancel,
        )
        assert sum(progress) == len(payload)
        assert (ftp_server.root / "uploaded.bin").read_bytes() == payload

        dest = tmp_path / "out.bin"
        svc.download_file(
            remote_path="uploaded.bin",
            local_path=str(dest),
            progress_callback=lambda _b: None,
            cancel_event=cancel,
        )
        assert dest.read_bytes() == payload
    finally:
        svc.disconnect()


def test_mkdir_rename_delete(ftp_server: RunningServer) -> None:
    svc = FTPClientService()
    svc.connect(_profile(ftp_server))
    try:
        svc.mkdir("new_dir")
        assert (ftp_server.root / "new_dir").is_dir()

        svc.rename("new_dir", "renamed_dir")
        assert (ftp_server.root / "renamed_dir").is_dir()
        assert not (ftp_server.root / "new_dir").exists()

        svc.rmdir("renamed_dir")
        assert not (ftp_server.root / "renamed_dir").exists()
    finally:
        svc.disconnect()


def test_transfer_manager_drives_uploads(ftp_server: RunningServer, tmp_path: pathlib.Path) -> None:
    """End-to-end test through TransferManager + FTPClientService."""
    import queue

    from ftplib_gui.models import UIEvent
    from ftplib_gui.transfers import TransferManager

    src = tmp_path / "queued.bin"
    src.write_bytes(b"abc" * 500)

    svc = FTPClientService()
    svc.connect(_profile(ftp_server))
    ui_q: queue.Queue[UIEvent] = queue.Queue()
    mgr = TransferManager(svc, ui_q)
    mgr.start()
    try:
        job = mgr.enqueue_upload(src, "queued.bin")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and job.status not in ("completed", "failed", "cancelled"):
            time.sleep(0.02)
        assert job.status == "completed", job.error
        assert (ftp_server.root / "queued.bin").read_bytes() == src.read_bytes()
    finally:
        mgr.stop()
        svc.disconnect()


@pytest.mark.parametrize("anonymous", [False])  # pyftpdlib's anonymous needs a separate user
def test_login_failure_raises(ftp_server: RunningServer, anonymous: bool) -> None:
    bad = _profile(ftp_server)
    bad.password = "wrong"
    bad.anonymous = anonymous
    svc = FTPClientService()
    with pytest.raises(Exception):
        svc.connect(bad)
