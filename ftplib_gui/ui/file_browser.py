"""Local and remote file-browser widgets.

Both browsers are :class:`ttk.Treeview` panes with a header bar
(path entry + nav buttons) and a small action toolbar. The local
browser drives the local filesystem directly; the remote browser
delegates everything to callbacks supplied by the application
controller, so the actual FTP work happens off the Tk main thread.
"""

from __future__ import annotations

import pathlib
import tkinter as tk
from datetime import datetime
from tkinter import ttk
from typing import Callable, Optional

from ftplib_gui.local_files import LocalFileService
from ftplib_gui.models import LocalEntry, RemoteEntry
from ftplib_gui.transfers import format_size


def _fmt_dt(dt: Optional[datetime]) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


class LocalBrowser(ttk.Frame):
    """Pane for browsing the local filesystem."""

    def __init__(
        self,
        master: tk.Misc,
        service: LocalFileService,
        on_selection_change: Optional[Callable[[list[LocalEntry]], None]] = None,
    ) -> None:
        super().__init__(master, padding=2)
        self._service = service
        self._on_selection_change = on_selection_change
        self._entries: dict[str, LocalEntry] = {}
        self._cwd: pathlib.Path = service.home()
        self._show_hidden = False

        self.path_var = tk.StringVar()
        self._build()
        self.refresh()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Local:").pack(side="left")
        self.path_entry = ttk.Entry(header, textvariable=self.path_var)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.path_entry.bind("<Return>", lambda _e: self._navigate_to(self.path_var.get()))

        ttk.Button(header, text="Up", command=self.go_up).pack(side="left", padx=2)
        ttk.Button(header, text="Home", command=self.go_home).pack(side="left", padx=2)
        ttk.Button(header, text="Refresh", command=self.refresh).pack(side="left", padx=2)
        ttk.Button(header, text="Choose…", command=self._choose_folder).pack(side="left", padx=2)

        columns = ("size", "modified", "type")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("modified", text="Modified")
        self.tree.heading("type", text="Type")
        self.tree.column("#0", width=240, anchor="w")
        self.tree.column("size", width=80, anchor="e")
        self.tree.column("modified", width=140, anchor="w")
        self.tree.column("type", width=80, anchor="w")

        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Return>", self._on_double_click)

    # ------------------------------------------------------------------
    @property
    def cwd(self) -> pathlib.Path:
        """Return the directory currently displayed."""
        return self._cwd

    def selected(self) -> list[LocalEntry]:
        """Return the entries currently highlighted in the tree."""
        return [self._entries[i] for i in self.tree.selection() if i in self._entries]

    def set_show_hidden(self, value: bool) -> None:
        """Toggle visibility of dot-files."""
        self._show_hidden = value
        self.refresh()

    def refresh(self) -> None:
        """Reload the current directory."""
        self.path_var.set(str(self._cwd))
        self.tree.delete(*self.tree.get_children())
        self._entries.clear()
        try:
            entries = self._service.listdir(self._cwd, show_hidden=self._show_hidden)
        except OSError as exc:
            self.tree.insert("", "end", text=f"<error: {exc}>")
            return
        for entry in entries:
            iid = str(entry.path)
            self._entries[iid] = entry
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=("📁 " if entry.is_dir else "") + entry.name,
                values=(
                    format_size(entry.size) if entry.size is not None else "",
                    _fmt_dt(entry.modified),
                    "Folder" if entry.is_dir else "File",
                ),
            )

    def go_up(self) -> None:
        """Navigate to the parent directory."""
        parent = self._cwd.parent
        if parent != self._cwd:
            self._cwd = parent
            self.refresh()

    def go_home(self) -> None:
        """Navigate to the user's home directory."""
        self._cwd = self._service.home()
        self.refresh()

    def navigate_to(self, path: pathlib.Path) -> None:
        """Public entry point for navigation."""
        self._cwd = path
        self.refresh()

    def _navigate_to(self, raw: str) -> None:
        candidate = pathlib.Path(raw).expanduser()
        if candidate.is_dir():
            self._cwd = candidate
            self.refresh()

    def _choose_folder(self) -> None:
        from tkinter import filedialog

        chosen = filedialog.askdirectory(initialdir=str(self._cwd))
        if chosen:
            self._cwd = pathlib.Path(chosen)
            self.refresh()

    def _on_double_click(self, _event: tk.Event) -> None:
        sel = self.selected()
        if len(sel) == 1 and sel[0].is_dir:
            self._cwd = sel[0].path
            self.refresh()

    def _on_select(self, _event: tk.Event) -> None:
        if self._on_selection_change is not None:
            self._on_selection_change(self.selected())


class RemoteBrowser(ttk.Frame):
    """Pane that displays the remote working directory."""

    def __init__(
        self,
        master: tk.Misc,
        on_navigate: Callable[[str], None],
        on_refresh: Callable[[], None],
        on_selection_change: Optional[Callable[[list[RemoteEntry]], None]] = None,
    ) -> None:
        super().__init__(master, padding=2)
        self._on_navigate = on_navigate
        self._on_refresh = on_refresh
        self._on_selection_change = on_selection_change
        self._entries: dict[str, RemoteEntry] = {}
        self._cwd: str = "/"

        self.path_var = tk.StringVar(value="/")
        self._build()
        self.set_connected(False)

    # ------------------------------------------------------------------
    def _build(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x")
        ttk.Label(header, text="Remote:").pack(side="left")
        self.path_entry = ttk.Entry(header, textvariable=self.path_var)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=4)
        self.path_entry.bind("<Return>", lambda _e: self._on_navigate(self.path_var.get()))

        self.up_btn = ttk.Button(header, text="Up", command=self.go_up)
        self.up_btn.pack(side="left", padx=2)
        self.root_btn = ttk.Button(header, text="Root", command=lambda: self._on_navigate("/"))
        self.root_btn.pack(side="left", padx=2)
        self.refresh_btn = ttk.Button(header, text="Refresh", command=self._on_refresh)
        self.refresh_btn.pack(side="left", padx=2)

        columns = ("size", "modified", "type", "perms")
        self.tree = ttk.Treeview(self, columns=columns, show="tree headings", selectmode="extended")
        self.tree.heading("#0", text="Name")
        self.tree.heading("size", text="Size")
        self.tree.heading("modified", text="Modified")
        self.tree.heading("type", text="Type")
        self.tree.heading("perms", text="Permissions")
        self.tree.column("#0", width=240, anchor="w")
        self.tree.column("size", width=80, anchor="e")
        self.tree.column("modified", width=140, anchor="w")
        self.tree.column("type", width=80, anchor="w")
        self.tree.column("perms", width=100, anchor="w")

        ysb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ysb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        ysb.pack(side="right", fill="y")

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)
        self.tree.bind("<Return>", self._on_double_click)

    # ------------------------------------------------------------------
    @property
    def cwd(self) -> str:
        """Return the remote directory currently displayed."""
        return self._cwd

    def selected(self) -> list[RemoteEntry]:
        """Return the entries currently highlighted in the tree."""
        return [self._entries[i] for i in self.tree.selection() if i in self._entries]

    def go_up(self) -> None:
        """Navigate to the parent of the current remote directory."""
        if self._cwd in ("", "/"):
            return
        parent = self._cwd.rsplit("/", 1)[0] or "/"
        self._on_navigate(parent)

    def show_entries(self, cwd: str, entries: list[RemoteEntry]) -> None:
        """Replace the displayed entries (called from the Tk main thread)."""
        self._cwd = cwd
        self.path_var.set(cwd)
        self.tree.delete(*self.tree.get_children())
        self._entries.clear()
        for entry in entries:
            iid = entry.path
            self._entries[iid] = entry
            self.tree.insert(
                "",
                "end",
                iid=iid,
                text=("📁 " if entry.is_dir else "") + entry.name,
                values=(
                    format_size(entry.size) if entry.size is not None else "",
                    _fmt_dt(entry.modified),
                    "Folder" if entry.is_dir else "File",
                    entry.permissions or "",
                ),
            )

    def show_disconnected(self) -> None:
        """Clear the remote pane and show a placeholder."""
        self._cwd = "/"
        self.path_var.set("")
        self.tree.delete(*self.tree.get_children())
        self._entries.clear()
        self.tree.insert("", "end", text="(Not connected)")

    def set_connected(self, connected: bool) -> None:
        """Enable or disable the remote toolbar buttons."""
        state = "normal" if connected else "disabled"
        for btn in (self.up_btn, self.root_btn, self.refresh_btn):
            btn.configure(state=state)
        self.path_entry.configure(state=state)
        if not connected:
            self.show_disconnected()

    # ------------------------------------------------------------------
    def _on_double_click(self, _event: tk.Event) -> None:
        sel = self.selected()
        if len(sel) == 1 and sel[0].is_dir:
            self._on_navigate(sel[0].path)

    def _on_select(self, _event: tk.Event) -> None:
        if self._on_selection_change is not None:
            self._on_selection_change(self.selected())
