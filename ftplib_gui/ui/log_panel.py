"""Read-only text log panel."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


class LogPanel(ttk.Frame):
    """A scrollable, read-only :class:`tkinter.Text` that holds log records."""

    MAX_LINES = 5000

    def __init__(self, master: tk.Misc) -> None:
        super().__init__(master, padding=2)
        self._build()

    def _build(self) -> None:
        toolbar = ttk.Frame(self)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="Log").pack(side="left", padx=4)
        ttk.Button(toolbar, text="Clear", command=self.clear).pack(side="left", padx=2)

        self.text = tk.Text(self, height=8, wrap="none", state="disabled")
        ysb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=ysb.set)
        self.text.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

    def append(self, message: str) -> None:
        """Append a single line; auto-scroll to bottom."""
        self.text.configure(state="normal")
        self.text.insert("end", message + "\n")
        # Trim if too long
        line_count = int(self.text.index("end-1c").split(".")[0])
        if line_count > self.MAX_LINES:
            self.text.delete("1.0", f"{line_count - self.MAX_LINES}.0")
        self.text.see("end")
        self.text.configure(state="disabled")

    def clear(self) -> None:
        """Empty the log panel."""
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")
