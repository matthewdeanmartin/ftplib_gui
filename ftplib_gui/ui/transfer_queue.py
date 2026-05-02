"""Bottom transfer-queue treeview."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Callable, Literal

from ftplib_gui.models import TransferJob
from ftplib_gui.transfers import format_eta, format_size, format_speed


class TransferQueueView(ttk.Frame):  # pylint: disable=too-many-ancestors
    """Displays transfer status with cancel / retry / clear actions."""

    def __init__(
        self,
        master: tk.Misc,
        on_cancel: Callable[[str], None],
        on_retry: Callable[[str], None],
        on_clear_completed: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=2)
        self._on_cancel = on_cancel
        self._on_retry = on_retry
        self._on_clear_completed = on_clear_completed

        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Transfers").pack(side="left", padx=4)
        ttk.Button(toolbar, text="Cancel", command=self._cancel_selected).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Retry", command=self._retry_selected).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Clear Completed", command=self._on_clear_completed).pack(side="left", padx=2)

        columns = ("direction", "source", "destination", "size", "progress", "status", "speed", "eta")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="extended", height=6)

        column_configs: list[tuple[str, str, int, Literal["nw", "n", "ne", "w", "center", "e", "sw", "s", "se"]]] = [
            ("direction", "Direction", 80, "w"),
            ("source", "Source", 220, "w"),
            ("destination", "Destination", 220, "w"),
            ("size", "Size", 80, "e"),
            ("progress", "Progress", 90, "e"),
            ("status", "Status", 90, "w"),
            ("speed", "Speed", 90, "e"),
            ("eta", "ETA", 70, "e"),
        ]

        for col, label, width, anchor in column_configs:
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width, anchor=anchor)

        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

    def upsert_job(self, job: TransferJob) -> None:
        """Insert or update a row for the given job."""
        progress = "—"
        if job.size and job.size > 0:
            pct = int(job.bytes_done / job.size * 100)
            progress = f"{pct}%"
        elif job.bytes_done:
            progress = format_size(job.bytes_done)

        elapsed = 0.0
        if job.started_at is not None:
            end = job.finished_at if job.finished_at is not None else time.monotonic()
            elapsed = max(0.0, end - job.started_at)

        speed = format_speed(job.bytes_done, elapsed) if job.status == "running" else ""
        eta = format_eta(job.size, job.bytes_done, elapsed) if job.status == "running" else ""

        values = (
            job.direction,
            job.source,
            job.destination,
            format_size(job.size),
            progress,
            job.status,
            speed,
            eta,
        )
        if self.tree.exists(job.id):
            self.tree.item(job.id, values=values)
        else:
            self.tree.insert("", "end", iid=job.id, values=values)

    def remove_jobs(self, job_ids: list[str]) -> None:
        """Remove rows for the given job ids."""
        for jid in job_ids:
            if self.tree.exists(jid):
                self.tree.delete(jid)

    def selected_id(self) -> str | None:
        """Return the first selected job id, if any."""
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _cancel_selected(self) -> None:
        jid = self.selected_id()
        if jid is not None:
            self._on_cancel(jid)

    def _retry_selected(self) -> None:
        jid = self.selected_id()
        if jid is not None:
            self._on_retry(jid)
