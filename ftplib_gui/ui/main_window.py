"""Top-level Tk window that composes all of the UI panels."""

from __future__ import annotations

import contextlib
import tkinter as tk
from tkinter import ttk
from typing import TYPE_CHECKING

from ftplib_gui.ui.connection_bar import ConnectionBar
from ftplib_gui.ui.file_browser import LocalBrowser, RemoteBrowser
from ftplib_gui.ui.log_panel import LogPanel
from ftplib_gui.ui.transfer_queue import TransferQueueView

if TYPE_CHECKING:
    from ftplib_gui.app import AppController


class MainWindow:
    """Owns the root Tk window and forwards menu/keyboard actions to the controller."""

    def __init__(self, controller: AppController) -> None:
        self.controller = controller
        self.root = tk.Tk()
        self.root.title("ftplib-gui")
        self.root.geometry("1200x800")

        self._build_menu()
        self._build_layout()
        self._bind_shortcuts()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New Connection", command=self.controller.action_new_connection)
        file_menu.add_command(label="Open Connection Profile…", command=self.controller.action_open_profile)
        file_menu.add_command(label="Save Current Profile…", command=self.controller.action_save_profile)
        file_menu.add_separator()
        file_menu.add_command(label="Disconnect", command=self.controller.action_disconnect)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close, accelerator="Ctrl+Q")
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Rename", command=self.controller.action_rename, accelerator="F2")
        edit_menu.add_command(label="Delete", command=self.controller.action_delete, accelerator="Del")
        edit_menu.add_command(label="New Folder", command=self.controller.action_new_folder)
        edit_menu.add_command(label="Refresh", command=self.controller.action_refresh, accelerator="F5")
        menubar.add_cascade(label="Edit", menu=edit_menu)

        transfer_menu = tk.Menu(menubar, tearoff=0)
        transfer_menu.add_command(label="Upload Selected", command=self.controller.action_upload, accelerator="Ctrl+U")
        transfer_menu.add_command(
            label="Download Selected", command=self.controller.action_download, accelerator="Ctrl+D"
        )
        transfer_menu.add_command(label="Cancel Selected Transfer", command=self.controller.action_cancel_transfer)
        transfer_menu.add_command(label="Clear Completed Transfers", command=self.controller.action_clear_completed)
        menubar.add_cascade(label="Transfer", menu=transfer_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        self.show_log_var = tk.BooleanVar(value=True)
        view_menu.add_checkbutton(
            label="Show Log Panel",
            variable=self.show_log_var,
            command=self._toggle_log,
        )
        self.show_hidden_var = tk.BooleanVar(value=False)
        view_menu.add_checkbutton(
            label="Show Hidden Files",
            variable=self.show_hidden_var,
            command=self._toggle_hidden,
        )
        view_menu.add_command(label="Refresh Local", command=self.controller.action_refresh_local)
        view_menu.add_command(label="Refresh Remote", command=self.controller.action_refresh_remote)
        menubar.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About", command=self.controller.action_about)
        help_menu.add_command(label="Python ftplib Documentation", command=self.controller.action_open_docs)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_layout(self) -> None:
        self.connection_bar = ConnectionBar(
            self.root,
            on_connect=self.controller.connect,
            on_disconnect=self.controller.disconnect,
        )
        self.connection_bar.pack(fill="x")

        # Vertical split: top (browsers) | middle (queue) | bottom (log)
        self.main_paned = ttk.PanedWindow(self.root, orient="vertical")
        self.main_paned.pack(fill="both", expand=True)

        # Browsers (horizontal split)
        browsers_frame = ttk.Frame(self.main_paned)
        browsers_paned = ttk.PanedWindow(browsers_frame, orient="horizontal")
        browsers_paned.pack(fill="both", expand=True)

        self.local_browser = LocalBrowser(
            browsers_paned,
            service=self.controller.local_service,
            on_selection_change=self.controller.on_local_selection,
        )
        self.remote_browser = RemoteBrowser(
            browsers_paned,
            on_navigate=self.controller.navigate_remote,
            on_refresh=self.controller.action_refresh_remote,
            on_selection_change=self.controller.on_remote_selection,
        )
        browsers_paned.add(self.local_browser, weight=1)
        browsers_paned.add(self.remote_browser, weight=1)
        self.main_paned.add(browsers_frame, weight=4)

        # Transfer queue
        self.transfer_view = TransferQueueView(
            self.main_paned,
            on_cancel=self.controller.cancel_transfer,
            on_retry=self.controller.retry_transfer,
            on_clear_completed=self.controller.action_clear_completed,
        )
        self.main_paned.add(self.transfer_view, weight=2)

        # Log
        self.log_panel = LogPanel(self.main_paned)
        self.main_paned.add(self.log_panel, weight=1)

        # Status bar
        self.status_var = tk.StringVar(value="Disconnected")
        status = ttk.Label(self.root, textvariable=self.status_var, relief="sunken", anchor="w")
        status.pack(fill="x", side="bottom")

    def _bind_shortcuts(self) -> None:
        self.root.bind("<F5>", lambda _e: self.controller.action_refresh())
        self.root.bind("<F2>", lambda _e: self.controller.action_rename())
        self.root.bind("<Delete>", lambda _e: self.controller.action_delete())
        self.root.bind("<Control-u>", lambda _e: self.controller.action_upload())
        self.root.bind("<Control-d>", lambda _e: self.controller.action_download())
        self.root.bind("<Control-l>", lambda _e: self.local_browser.path_entry.focus_set())
        self.root.bind("<Control-r>", lambda _e: self.remote_browser.path_entry.focus_set())
        self.root.bind("<Control-q>", lambda _e: self._on_close())

    # ------------------------------------------------------------------
    def _on_close(self) -> None:
        self.controller.shutdown()
        self.root.destroy()

    def _toggle_log(self) -> None:
        if self.show_log_var.get():
            with contextlib.suppress(tk.TclError):
                self.main_paned.add(self.log_panel, weight=1)
        else:
            with contextlib.suppress(tk.TclError):
                self.main_paned.forget(self.log_panel)

    def _toggle_hidden(self) -> None:
        self.local_browser.set_show_hidden(self.show_hidden_var.get())

    # ------------------------------------------------------------------
    def set_status(self, message: str) -> None:
        """Update the status bar text."""
        self.status_var.set(message)
