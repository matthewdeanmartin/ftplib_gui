from __future__ import annotations

import queue
import time
from unittest.mock import MagicMock

import pytest

from ftplib_gui.transfers import TransferManager, format_size


def test_format_size():
    assert format_size(None) == "?"
    assert format_size(500) == "500 B"
    assert format_size(1024) == "1.0 KB"
    assert format_size(1024*1024) == "1.0 MB"

@pytest.fixture
def transfer_mgr():
    ftp = MagicMock()
    ui_q = queue.Queue()
    mgr = TransferManager(ftp, ui_q)
    return mgr, ftp, ui_q

def test_enqueue_upload(transfer_mgr, tmp_path):
    mgr, _, ui_q = transfer_mgr
    f = tmp_path / "test.txt"
    f.write_text("hello")

    job = mgr.enqueue_upload(f, "/remote.txt")
    assert job.direction == "upload"
    assert job.size == 5
    assert job.status == "queued"

    event = ui_q.get_nowait()
    assert event.type == "transfer_enqueued"
    assert event.payload["job"] == job

def test_enqueue_download(transfer_mgr):
    mgr, ftp, ui_q = transfer_mgr
    ftp.is_connected.return_value = True
    ftp.size.return_value = 100

    job = mgr.enqueue_download("/remote.txt", "local.txt")
    assert job.direction == "download"
    assert job.size == 100

    event = ui_q.get_nowait()
    assert event.type == "transfer_enqueued"

def test_cancel_queued(transfer_mgr, tmp_path):
    mgr, _, _ = transfer_mgr
    f = tmp_path / "test.txt"
    f.write_text("x")
    job = mgr.enqueue_upload(f, "/remote")

    mgr.cancel(job.id)
    assert job.status == "cancelled"
    assert job.cancel_event.is_set()

def test_clear_completed(transfer_mgr, tmp_path):
    mgr, _, _ = transfer_mgr
    f = tmp_path / "test.txt"
    f.write_text("x")
    job = mgr.enqueue_upload(f, "/remote")

    job.status = "completed"
    removed = mgr.clear_completed()
    assert job.id in removed
    assert len(mgr.jobs()) == 0

def test_worker_loop_upload(transfer_mgr, tmp_path):
    mgr, ftp, _ = transfer_mgr
    f = tmp_path / "upload.txt"
    f.write_text("data")

    # Mock upload_file to call progress
    def mock_upload(local_path, remote_path, progress_callback, cancel_event, blocksize=8192):
        progress_callback(4)

    ftp.upload_file.side_effect = mock_upload

    mgr.start()
    try:
        job = mgr.enqueue_upload(f, "/remote.txt")

        # Wait for completion (busy wait for simplicity in unit test)
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline and job.status != "completed":
            time.sleep(0.01)

        assert job.status == "completed"
        assert job.bytes_done == 4
        ftp.upload_file.assert_called_once()
    finally:
        mgr.stop()
