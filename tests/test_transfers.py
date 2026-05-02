"""Tests for transfer formatting helpers and TransferManager state machine."""

from __future__ import annotations

import pathlib
import queue
import threading
import time
from typing import Callable

from ftplib_gui.models import UIEvent
from ftplib_gui.transfers import (
    TransferManager,
    format_eta,
    format_size,
    format_speed,
)


# ---------------------------------------------------------------------------
# format helpers
# ---------------------------------------------------------------------------
def test_format_size_handles_units() -> None:
    assert format_size(None) == "?"
    assert format_size(0) == "0 B"
    assert format_size(512) == "512 B"
    assert format_size(2048).endswith("KB")
    assert format_size(5 * 1024 * 1024).endswith("MB")
    assert format_size(3 * 1024**3).endswith("GB")


def test_format_speed_zero_elapsed_is_dash() -> None:
    assert format_speed(100, 0) == "—"
    assert format_speed(1024, 1.0).endswith("/s")


def test_format_eta_unknown_when_total_missing() -> None:
    assert format_eta(None, 100, 1.0) == "—"
    assert format_eta(0, 0, 0) == "—"
    eta = format_eta(2048, 1024, 1.0)
    assert eta.endswith("s") or "m" in eta


# ---------------------------------------------------------------------------
# TransferManager
# ---------------------------------------------------------------------------
class FakeFTP:
    """Stand-in FTPClientService for unit tests."""

    def __init__(self) -> None:
        self.uploaded: list[tuple[str, str]] = []
        self.downloaded: list[tuple[str, str]] = []
        self.fail = False

    def is_connected(self) -> bool:
        return True

    def size(self, _path: str) -> int:
        return 100

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Callable[[int], None],
        cancel_event: threading.Event,
        blocksize: int = 8192,
    ) -> None:
        if self.fail:
            raise RuntimeError("boom")
        for _ in range(5):
            if cancel_event.is_set():
                from ftplib_gui.ftp_client import TransferCancelled

                raise TransferCancelled()
            progress_callback(20)
        self.uploaded.append((local_path, remote_path))

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int], None],
        cancel_event: threading.Event,
        blocksize: int = 8192,
    ) -> None:
        for _ in range(5):
            progress_callback(20)
        self.downloaded.append((remote_path, local_path))


def _drain(q: queue.Queue[UIEvent], timeout: float = 2.0) -> list[UIEvent]:
    end = time.monotonic() + timeout
    events: list[UIEvent] = []
    while time.monotonic() < end:
        try:
            events.append(q.get(timeout=0.1))
        except queue.Empty:
            continue
    return events


def test_upload_completes_and_emits_events(tmp_path: pathlib.Path) -> None:
    src = tmp_path / "f.bin"
    src.write_bytes(b"x" * 100)

    ftp = FakeFTP()
    ui_q: queue.Queue[UIEvent] = queue.Queue()
    mgr = TransferManager(ftp, ui_q)
    mgr.start()
    try:
        job = mgr.enqueue_upload(src, "/remote/f.bin")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and job.status not in ("completed", "failed", "cancelled"):
            time.sleep(0.02)
    finally:
        mgr.stop()

    assert job.status == "completed"
    assert ftp.uploaded == [(str(src), "/remote/f.bin")]
    assert job.bytes_done == 100

    events = []
    while not ui_q.empty():
        events.append(ui_q.get_nowait())
    types = {e.type for e in events}
    assert "transfer_enqueued" in types
    assert "transfer_started" in types
    assert "transfer_completed" in types


def test_failed_upload_is_marked_failed(tmp_path: pathlib.Path) -> None:
    src = tmp_path / "f.bin"
    src.write_bytes(b"x" * 50)

    ftp = FakeFTP()
    ftp.fail = True
    ui_q: queue.Queue[UIEvent] = queue.Queue()
    mgr = TransferManager(ftp, ui_q)
    mgr.start()
    try:
        job = mgr.enqueue_upload(src, "/r")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and job.status not in ("completed", "failed", "cancelled"):
            time.sleep(0.02)
    finally:
        mgr.stop()

    assert job.status == "failed"
    assert job.error == "boom"


def test_clear_completed_returns_finished_ids(tmp_path: pathlib.Path) -> None:
    src = tmp_path / "f.bin"
    src.write_bytes(b"x" * 20)
    ftp = FakeFTP()
    ui_q: queue.Queue[UIEvent] = queue.Queue()
    mgr = TransferManager(ftp, ui_q)
    mgr.start()
    try:
        job = mgr.enqueue_upload(src, "/r")
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and job.status != "completed":
            time.sleep(0.02)
    finally:
        mgr.stop()

    removed = mgr.clear_completed()
    assert job.id in removed
    assert mgr.jobs() == []
