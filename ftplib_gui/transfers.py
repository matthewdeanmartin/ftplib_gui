"""Background transfer queue.

A single worker thread pulls :class:`TransferJob` instances off a queue,
executes them via :class:`FTPClientService`, and pushes
:class:`UIEvent` notifications onto a UI-bound queue that the Tk main
thread polls.
"""

from __future__ import annotations

import pathlib
import queue
import threading
import time
from typing import Any

from ftplib_gui.ftp_client import FTPClientService, TransferCancelled
from ftplib_gui.logging_utils import get_logger
from ftplib_gui.models import TransferJob, UIEvent


def format_size(num_bytes: int | None) -> str:
    """Render a byte count as a short human string."""
    if num_bytes is None:
        return "?"
    if num_bytes < 1024:
        return f"{num_bytes} B"
    units = ["KB", "MB", "GB", "TB"]
    value = float(num_bytes)
    for unit in units:
        value /= 1024
        if value < 1024:
            return f"{value:.1f} {unit}"
    return f"{value:.1f} PB"


def format_speed(bytes_done: int, elapsed_seconds: float) -> str:
    """Render an instantaneous transfer rate."""
    if elapsed_seconds <= 0:
        return "—"
    return format_size(int(bytes_done / elapsed_seconds)) + "/s"


def format_eta(total: int | None, bytes_done: int, elapsed_seconds: float) -> str:
    """Render a remaining-time estimate, or ``—`` if unknown."""
    if total is None or total <= 0 or elapsed_seconds <= 0 or bytes_done <= 0:
        return "—"
    rate = bytes_done / elapsed_seconds
    if rate <= 0:
        return "—"
    remaining = max(0, total - bytes_done)
    seconds = int(remaining / rate)
    if seconds < 60:
        return f"{seconds}s"
    if seconds < 3600:
        return f"{seconds // 60}m{seconds % 60:02d}s"
    return f"{seconds // 3600}h{(seconds % 3600) // 60:02d}m"


class TransferManager:
    """Single-worker queue executor for upload/download jobs.

    The manager owns the worker thread; jobs are submitted with
    :meth:`enqueue_upload` / :meth:`enqueue_download` and progress is
    delivered via the ``ui_queue`` provided to the constructor.
    """

    def __init__(self, ftp_service: FTPClientService, ui_queue: queue.Queue[UIEvent]) -> None:
        self._ftp = ftp_service
        self._ui = ui_queue
        self._jobs: queue.Queue[TransferJob | None] = queue.Queue()
        self._index: dict[str, TransferJob] = {}
        self._lock = threading.RLock()
        self._worker: threading.Thread | None = None
        self._stopped = threading.Event()
        self._log = get_logger()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start the worker thread (idempotent)."""
        if self._worker is not None and self._worker.is_alive():
            return
        self._stopped.clear()
        self._worker = threading.Thread(target=self._run, name="ftplib-gui-worker", daemon=True)
        self._worker.start()

    def stop(self) -> None:
        """Stop the worker thread after the current job finishes."""
        self._stopped.set()
        self._jobs.put(None)  # wake worker
        if self._worker is not None:
            self._worker.join(timeout=2.0)
            self._worker = None

    # ------------------------------------------------------------------
    # enqueue
    # ------------------------------------------------------------------
    def enqueue_upload(self, local_path: pathlib.Path, remote_path: str) -> TransferJob:
        """Queue an upload job and return its :class:`TransferJob`."""
        job = TransferJob(
            direction="upload",
            source=str(local_path),
            destination=remote_path,
            size=local_path.stat().st_size if local_path.exists() else None,
        )
        return self._enqueue(job)

    def enqueue_download(self, remote_path: str, local_path: pathlib.Path) -> TransferJob:
        """Queue a download job and return its :class:`TransferJob`."""
        size = self._ftp.size(remote_path) if self._ftp.is_connected() else None
        job = TransferJob(
            direction="download",
            source=remote_path,
            destination=str(local_path),
            size=size,
        )
        return self._enqueue(job)

    def _enqueue(self, job: TransferJob) -> TransferJob:
        with self._lock:
            self._index[job.id] = job
        self._jobs.put(job)
        self._emit("transfer_enqueued", {"job": job})
        return job

    # ------------------------------------------------------------------
    # control
    # ------------------------------------------------------------------
    def cancel(self, job_id: str) -> None:
        """Cancel a queued or running job."""
        with self._lock:
            job = self._index.get(job_id)
        if job is None:
            return
        job.cancel_event.set()
        if job.status == "queued":
            job.status = "cancelled"
            self._emit("transfer_cancelled", {"job": job})

    def retry(self, job_id: str) -> TransferJob | None:
        """Re-enqueue a failed/cancelled job as a fresh job."""
        with self._lock:
            old = self._index.get(job_id)
        if old is None or old.status not in ("failed", "cancelled"):
            return None
        new_job = TransferJob(
            direction=old.direction,
            source=old.source,
            destination=old.destination,
            size=old.size,
        )
        return self._enqueue(new_job)

    def clear_completed(self) -> list[str]:
        """Drop completed/cancelled/failed jobs from the index. Returns removed ids."""
        with self._lock:
            removed = [jid for jid, j in self._index.items() if j.status in ("completed", "cancelled", "failed")]
            for jid in removed:
                del self._index[jid]
        return removed

    def jobs(self) -> list[TransferJob]:
        """Snapshot of all known jobs in insertion order."""
        with self._lock:
            return list(self._index.values())

    # ------------------------------------------------------------------
    # worker
    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stopped.is_set():
            try:
                job = self._jobs.get(timeout=0.5)
            except queue.Empty:
                continue
            if job is None:
                break
            if job.cancel_event.is_set():
                job.status = "cancelled"
                self._emit("transfer_cancelled", {"job": job})
                continue
            self._run_job(job)

    def _run_job(self, job: TransferJob) -> None:
        job.status = "running"
        job.started_at = time.monotonic()
        self._emit("transfer_started", {"job": job})

        last_emit = 0.0
        emit_interval = 0.1  # seconds — keep UI updates lightweight

        def progress(delta: int) -> None:
            nonlocal last_emit
            job.bytes_done += delta
            now = time.monotonic()
            if now - last_emit >= emit_interval:
                last_emit = now
                self._emit("transfer_progress", {"job": job})

        try:
            if job.direction == "upload":
                self._ftp.upload_file(
                    local_path=job.source,
                    remote_path=job.destination,
                    progress_callback=progress,
                    cancel_event=job.cancel_event,
                )
            else:
                self._ftp.download_file(
                    remote_path=job.source,
                    local_path=job.destination,
                    progress_callback=progress,
                    cancel_event=job.cancel_event,
                )
        except TransferCancelled:
            job.status = "cancelled"
            job.finished_at = time.monotonic()
            self._emit("transfer_cancelled", {"job": job})
            return
        except Exception as exc:  # pylint: disable=broad-exception-caught
            job.status = "failed"
            job.error = str(exc)
            job.finished_at = time.monotonic()
            self._log.exception("Transfer failed: %s", exc)
            self._emit("transfer_failed", {"job": job, "error": str(exc)})
            return

        job.status = "completed"
        job.finished_at = time.monotonic()
        self._emit("transfer_completed", {"job": job})

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _emit(self, event_type: str, payload: dict[str, Any]) -> None:
        self._ui.put(UIEvent(type=event_type, payload=payload))
