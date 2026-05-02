"""Application controller wiring services to the UI.

The controller owns long-lived service instances and orchestrates work
between worker threads (FTP, transfers) and the Tk main thread. All
network operations are dispatched onto a single background executor
thread; UI updates happen via :class:`UIEvent` messages drained from
``self._ui_queue``.
"""

from __future__ import annotations

import argparse
import contextlib
import pathlib
import posixpath
import queue
import sys
import threading
import webbrowser
from tkinter import messagebox, simpledialog
from typing import Any, Callable

from ftplib_gui.__about__ import __version__
from ftplib_gui.ftp_client import FTPClientService
from ftplib_gui.local_files import LocalFileService
from ftplib_gui.logging_utils import attach_gui_sink, configure_logging, get_logger
from ftplib_gui.models import ConnectionProfile, LocalEntry, RemoteEntry, UIEvent
from ftplib_gui.profiles import ProfileStore
from ftplib_gui.transfers import TransferManager
from ftplib_gui.ui.main_window import MainWindow

PYTHON_FTPLIB_DOC_URL = "https://docs.python.org/3/library/ftplib.html"


class AppController:
    """Mediator between the UI, services, and worker threads."""

    def __init__(self, args: argparse.Namespace | None = None) -> None:
        self._args = args
        self._log = get_logger()

        self.local_service = LocalFileService()
        self.ftp_service = FTPClientService()
        self.profile_store = ProfileStore()

        self._ui_queue: queue.Queue[UIEvent] = queue.Queue()
        self._log_queue: queue.Queue[str] = queue.Queue()

        self.transfer_manager = TransferManager(self.ftp_service, self._ui_queue)

        # Background executor for non-transfer FTP work (connect, listdir, mkdir, rm, rename).
        # A single thread keeps things simple and matches the spec ("one transfer at a time").
        self._ftp_jobs: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self._ftp_thread = threading.Thread(target=self._run_ftp_jobs, daemon=True, name="ftplib-gui-ftp")

        self.window: MainWindow = MainWindow(self)
        self._connected = False
        self._local_selection: list[LocalEntry] = []
        self._remote_selection: list[RemoteEntry] = []

        # Plumb logging into the GUI panel via the log queue (so worker threads
        # don't touch Tk widgets directly).
        attach_gui_sink(self._log_queue.put)

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        """Start background threads, drain loops, and the Tk main loop."""
        self.transfer_manager.start()
        self._ftp_thread.start()
        self._poll_ui_events()
        self._poll_log_messages()
        self._apply_cli_args()
        self.window.root.mainloop()

    def shutdown(self) -> None:
        """Stop worker threads and tear down the FTP connection."""
        self.transfer_manager.stop()
        self._ftp_jobs.put(None)
        with contextlib.suppress(Exception):
            self.ftp_service.disconnect()

    # ------------------------------------------------------------------
    # CLI bootstrap
    # ------------------------------------------------------------------
    def _apply_cli_args(self) -> None:
        args = self._args
        if args is None:
            return

        if getattr(args, "local_dir", None):
            try:
                self.window.local_browser.navigate_to(pathlib.Path(args.local_dir).expanduser())
            except OSError as exc:
                self._log.warning("Could not navigate to %s: %s", args.local_dir, exc)

        profile_to_use: ConnectionProfile | None = None
        if getattr(args, "profile", None):
            for profile in self.profile_store.load():
                if profile.name == args.profile:
                    profile_to_use = profile
                    break
            if profile_to_use is None:
                self._log.warning("Profile %r not found", args.profile)

        host = getattr(args, "host", None)
        if host:
            profile_to_use = ConnectionProfile(
                name=host,
                host=host,
                port=getattr(args, "port", None) or 21,
                protocol=getattr(args, "protocol", None) or "ftp",
                username=getattr(args, "user", None) or "",
                passive=not getattr(args, "active", False),
            )

        if profile_to_use is not None:
            self.window.connection_bar.populate(profile_to_use)
            if getattr(args, "remote_dir", None):
                profile_to_use.default_remote_dir = args.remote_dir

    # ------------------------------------------------------------------
    # connect / disconnect
    # ------------------------------------------------------------------
    def connect(self, profile: ConnectionProfile) -> None:
        """Connect using the supplied profile (runs on a worker thread)."""
        if not profile.host:
            messagebox.showerror("Connect", "A host name is required.")
            return

        if profile.protocol == "ftps" and not profile.verify_tls:
            ok = messagebox.askokcancel(
                "TLS Verification Disabled",
                "TLS certificate verification is disabled. Your connection may be vulnerable to interception.\n\n"
                "Proceed?",
            )
            if not ok:
                return

        self.window.connection_bar.set_connected(True)  # disables fields during attempt
        self.window.set_status(f"Connecting to {profile.host}…")
        self._submit_ftp(lambda: self._connect_blocking(profile))

    def _connect_blocking(self, profile: ConnectionProfile) -> None:
        try:
            self.ftp_service.connect(profile)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._log.exception("Connection failed: %s", exc)
            self._ui_queue.put(UIEvent("connection_failed", {"error": str(exc)}))
            return

        try:
            initial = profile.default_remote_dir or self.ftp_service.pwd()
            if profile.default_remote_dir:
                self.ftp_service.cwd(profile.default_remote_dir)
            entries = self.ftp_service.listdir()
            cwd = self.ftp_service.pwd()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._log.exception("Initial listing failed: %s", exc)
            self._ui_queue.put(UIEvent("connection_failed", {"error": str(exc)}))
            with contextlib.suppress(Exception):
                self.ftp_service.disconnect()
            return

        self._ui_queue.put(
            UIEvent("connected", {"profile": profile, "cwd": cwd, "entries": entries, "initial": initial})
        )

    def disconnect(self) -> None:
        """Disconnect from the FTP server."""
        self._submit_ftp(self._disconnect_blocking)

    def _disconnect_blocking(self) -> None:
        try:
            self.ftp_service.disconnect()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._log.exception("Disconnect failed: %s", exc)
        self._ui_queue.put(UIEvent("disconnected", {}))

    # ------------------------------------------------------------------
    # remote navigation
    # ------------------------------------------------------------------
    def navigate_remote(self, path: str) -> None:
        """Change remote working directory and refresh the listing."""
        if not self._connected:
            return
        self._submit_ftp(lambda: self._navigate_remote_blocking(path))

    def _navigate_remote_blocking(self, path: str) -> None:
        try:
            self.ftp_service.cwd(path)
            cwd = self.ftp_service.pwd()
            entries = self.ftp_service.listdir()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._ui_queue.put(UIEvent("error", {"error": str(exc), "where": "navigate_remote"}))
            return
        self._ui_queue.put(UIEvent("remote_list_loaded", {"cwd": cwd, "entries": entries}))

    def _refresh_remote_blocking(self) -> None:
        try:
            cwd = self.ftp_service.pwd()
            entries = self.ftp_service.listdir()
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._ui_queue.put(UIEvent("error", {"error": str(exc), "where": "refresh_remote"}))
            return
        self._ui_queue.put(UIEvent("remote_list_loaded", {"cwd": cwd, "entries": entries}))

    # ------------------------------------------------------------------
    # selection callbacks
    # ------------------------------------------------------------------
    def on_local_selection(self, entries: list[LocalEntry]) -> None:
        """Cache the local selection and update the status bar."""
        self._local_selection = entries
        self._refresh_status()

    def on_remote_selection(self, entries: list[RemoteEntry]) -> None:
        """Cache the remote selection and update the status bar."""
        self._remote_selection = entries
        self._refresh_status()

    # ------------------------------------------------------------------
    # menu/keyboard actions
    # ------------------------------------------------------------------
    def action_new_connection(self) -> None:
        """Clear the connection bar so the user can enter a fresh profile."""
        if self._connected:
            self.disconnect()
        self.window.connection_bar.populate(ConnectionProfile(name="", host=""))

    def action_open_profile(self) -> None:
        """Pick a saved profile and load it into the connection bar."""
        profiles = self.profile_store.load()
        if not profiles:
            messagebox.showinfo("Profiles", "No saved profiles.")
            return
        names = "\n".join(f"- {p.name} ({p.host})" for p in profiles)
        chosen = simpledialog.askstring(
            "Open Profile",
            f"Available profiles:\n{names}\n\nEnter profile name:",
        )
        if not chosen:
            return
        for profile in profiles:
            if profile.name == chosen:
                self.window.connection_bar.populate(profile)
                return
        messagebox.showerror("Open Profile", f"No profile named {chosen!r}.")

    def action_save_profile(self) -> None:
        """Save the current connection-bar values as a named profile."""
        profile = self.window.connection_bar.get_profile()
        if profile is None:
            messagebox.showerror("Save Profile", "Fill in the connection details first.")
            return
        name = simpledialog.askstring("Save Profile", "Profile name:", initialvalue=profile.name)
        if not name:
            return
        profile.name = name
        # Don't persist password unless user explicitly opts in via keyring.
        if profile.password and self.profile_store.keyring_available():
            if messagebox.askyesno(
                "Save Password",
                "Store the password in your OS keyring for this profile?",
            ):
                profile.save_password = True
        else:
            profile.password = ""
        self.profile_store.upsert(profile)
        self._log.info("Saved profile %r", name)

    def action_disconnect(self) -> None:
        """Menu wrapper for :meth:`disconnect`."""
        if self._connected:
            self.disconnect()

    def action_rename(self) -> None:
        """Rename the focused selection (local or remote)."""
        focus = self.window.root.focus_get()
        if focus is not None and self._is_descendant(focus, self.window.remote_browser):
            self._rename_remote()
        else:
            self._rename_local()

    def _rename_local(self) -> None:
        if len(self._local_selection) != 1:
            messagebox.showinfo("Rename", "Select exactly one local item.")
            return
        entry = self._local_selection[0]
        new = simpledialog.askstring("Rename", "New name:", initialvalue=entry.name)
        if not new or new == entry.name:
            return
        try:
            self.local_service.rename(entry.path, entry.path.with_name(new))
        except OSError as exc:
            messagebox.showerror("Rename", str(exc))
        self.window.local_browser.refresh()

    def _rename_remote(self) -> None:
        if not self._connected or len(self._remote_selection) != 1:
            messagebox.showinfo("Rename", "Select exactly one remote item.")
            return
        entry = self._remote_selection[0]
        new = simpledialog.askstring("Rename", "New name:", initialvalue=entry.name)
        if not new or new == entry.name:
            return
        new_path = posixpath.join(self.window.remote_browser.cwd, new)
        self._submit_ftp(lambda: self._remote_rename_blocking(entry.path, new_path))

    def _remote_rename_blocking(self, old_path: str, new_path: str) -> None:
        try:
            self.ftp_service.rename(old_path, new_path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._ui_queue.put(UIEvent("error", {"error": str(exc), "where": "rename"}))
            return
        self._refresh_remote_blocking()

    def action_delete(self) -> None:
        """Delete the focused selection (local or remote)."""
        focus = self.window.root.focus_get()
        if focus is not None and self._is_descendant(focus, self.window.remote_browser):
            self._delete_remote()
        else:
            self._delete_local()

    def _delete_local(self) -> None:
        if not self._local_selection:
            return
        names = ", ".join(e.name for e in self._local_selection)
        if not messagebox.askyesno("Delete", f"Delete {names}?"):
            return
        for entry in self._local_selection:
            try:
                self.local_service.delete(entry.path)
            except OSError as exc:
                messagebox.showerror("Delete", str(exc))
        self.window.local_browser.refresh()

    def _delete_remote(self) -> None:
        if not self._connected or not self._remote_selection:
            return
        names = ", ".join(e.name for e in self._remote_selection)
        if not messagebox.askyesno("Delete", f"Delete remote {names}?"):
            return
        targets = list(self._remote_selection)
        self._submit_ftp(lambda: self._remote_delete_blocking(targets))

    def _remote_delete_blocking(self, entries: list[RemoteEntry]) -> None:
        for entry in entries:
            try:
                if entry.is_dir:
                    self.ftp_service.rmdir(entry.path)
                else:
                    self.ftp_service.delete_file(entry.path)
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._ui_queue.put(UIEvent("error", {"error": str(exc), "where": "delete"}))
        self._refresh_remote_blocking()

    def action_new_folder(self) -> None:
        """Create a new folder in the focused pane."""
        focus = self.window.root.focus_get()
        if focus is not None and self._is_descendant(focus, self.window.remote_browser):
            self._mkdir_remote()
        else:
            self._mkdir_local()

    def _mkdir_local(self) -> None:
        name = simpledialog.askstring("New Folder", "Folder name:")
        if not name:
            return
        try:
            self.local_service.mkdir(self.window.local_browser.cwd / name)
        except OSError as exc:
            messagebox.showerror("New Folder", str(exc))
        self.window.local_browser.refresh()

    def _mkdir_remote(self) -> None:
        if not self._connected:
            return
        name = simpledialog.askstring("New Remote Folder", "Folder name:")
        if not name:
            return
        target = posixpath.join(self.window.remote_browser.cwd, name)
        self._submit_ftp(lambda: self._remote_mkdir_blocking(target))

    def _remote_mkdir_blocking(self, path: str) -> None:
        try:
            self.ftp_service.mkdir(path)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._ui_queue.put(UIEvent("error", {"error": str(exc), "where": "mkdir"}))
            return
        self._refresh_remote_blocking()

    def action_refresh(self) -> None:
        """Refresh whichever pane currently has focus."""
        focus = self.window.root.focus_get()
        if focus is not None and self._is_descendant(focus, self.window.remote_browser):
            self.action_refresh_remote()
        else:
            self.action_refresh_local()

    def action_refresh_local(self) -> None:
        """Reload the local pane."""
        self.window.local_browser.refresh()

    def action_refresh_remote(self) -> None:
        """Reload the remote pane."""
        if self._connected:
            self._submit_ftp(self._refresh_remote_blocking)

    def action_upload(self) -> None:
        """Queue uploads for every selected local file."""
        if not self._connected:
            messagebox.showinfo("Upload", "Connect first.")
            return
        files = [e for e in self._local_selection if not e.is_dir]
        if not files:
            messagebox.showinfo("Upload", "Select one or more local files.")
            return
        remote_dir = self.window.remote_browser.cwd
        for entry in files:
            remote_path = posixpath.join(remote_dir, entry.name)
            self.transfer_manager.enqueue_upload(entry.path, remote_path)

    def action_download(self) -> None:
        """Queue downloads for every selected remote file."""
        if not self._connected:
            messagebox.showinfo("Download", "Connect first.")
            return
        files = [e for e in self._remote_selection if not e.is_dir]
        if not files:
            messagebox.showinfo("Download", "Select one or more remote files.")
            return
        local_dir = self.window.local_browser.cwd
        for entry in files:
            local_path = local_dir / entry.name
            self.transfer_manager.enqueue_download(entry.path, local_path)

    def action_cancel_transfer(self) -> None:
        """Cancel the highlighted transfer row."""
        jid = self.window.transfer_view.selected_id()
        if jid:
            self.transfer_manager.cancel(jid)

    def action_clear_completed(self) -> None:
        """Drop completed/cancelled/failed jobs from the queue view."""
        removed = self.transfer_manager.clear_completed()
        self.window.transfer_view.remove_jobs(removed)

    def action_about(self) -> None:
        """Display an About dialog."""
        messagebox.showinfo(
            "About ftplib-gui",
            f"ftplib-gui {__version__}\n\nA stdlib-only FTP/FTPS GUI client.",
        )

    def action_open_docs(self) -> None:
        """Open the Python ``ftplib`` documentation in a browser."""
        webbrowser.open(PYTHON_FTPLIB_DOC_URL)

    def cancel_transfer(self, job_id: str) -> None:
        """Cancel a transfer by id (called from the queue toolbar)."""
        self.transfer_manager.cancel(job_id)

    def retry_transfer(self, job_id: str) -> None:
        """Re-queue a failed transfer (called from the queue toolbar)."""
        self.transfer_manager.retry(job_id)

    # ------------------------------------------------------------------
    # event polling
    # ------------------------------------------------------------------
    def _poll_ui_events(self) -> None:
        try:
            while True:
                event = self._ui_queue.get_nowait()
                self._handle_event(event)
        except queue.Empty:
            pass
        self.window.root.after(100, self._poll_ui_events)

    def _poll_log_messages(self) -> None:
        try:
            while True:
                msg = self._log_queue.get_nowait()
                self.window.log_panel.append(msg)
        except queue.Empty:
            pass
        self.window.root.after(150, self._poll_log_messages)

    def _handle_event(self, event: UIEvent) -> None:
        if event.type == "connected":
            self._connected = True
            self.window.connection_bar.set_connected(True)
            self.window.remote_browser.set_connected(True)
            entries = event.payload.get("entries", [])
            cwd = event.payload.get("cwd", "/")
            self.window.remote_browser.show_entries(cwd, entries)
            profile = event.payload.get("profile")
            if profile is not None and profile.default_local_dir:
                with contextlib.suppress(OSError):
                    self.window.local_browser.navigate_to(pathlib.Path(profile.default_local_dir).expanduser())
            self._refresh_status()
        elif event.type == "connection_failed":
            self._connected = False
            self.window.connection_bar.set_connected(False)
            self.window.remote_browser.set_connected(False)
            messagebox.showerror("Connection failed", event.payload.get("error", "Unknown error"))
            self._refresh_status()
        elif event.type == "disconnected":
            self._connected = False
            self.window.connection_bar.set_connected(False)
            self.window.remote_browser.set_connected(False)
            self._refresh_status()
        elif event.type == "remote_list_loaded":
            self.window.remote_browser.show_entries(event.payload["cwd"], event.payload["entries"])
            self._refresh_status()
        elif event.type in {
            "transfer_enqueued",
            "transfer_started",
            "transfer_progress",
            "transfer_completed",
            "transfer_failed",
            "transfer_cancelled",
        }:
            job = event.payload.get("job")
            if job is not None:
                self.window.transfer_view.upsert_job(job)
            if event.type == "transfer_completed":
                # Refresh the affected pane
                if job is not None and job.direction == "download":
                    self.window.local_browser.refresh()
                elif job is not None and job.direction == "upload":
                    self.action_refresh_remote()
            elif event.type == "transfer_failed":
                self._log.error("Transfer failed: %s", event.payload.get("error"))
            self._refresh_status()
        elif event.type == "error":
            messagebox.showerror("Error", event.payload.get("error", "Unknown error"))

    # ------------------------------------------------------------------
    # FTP executor
    # ------------------------------------------------------------------
    def _submit_ftp(self, func: Callable[[], None]) -> None:
        self._ftp_jobs.put(func)

    def _run_ftp_jobs(self) -> None:
        while True:
            job = self._ftp_jobs.get()
            if job is None:
                break
            try:
                job()
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._log.exception("Background FTP job failed: %s", exc)
                self._ui_queue.put(UIEvent("error", {"error": str(exc), "where": "ftp_job"}))

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _is_descendant(widget: Any, ancestor: Any) -> bool:
        node = widget
        while node is not None:
            if node is ancestor:
                return True
            node = getattr(node, "master", None)
        return False

    def _refresh_status(self) -> None:
        if not self._connected:
            self.window.set_status("Disconnected")
            return
        profile = self.ftp_service.profile
        host = profile.host if profile else "?"
        active = sum(1 for j in self.transfer_manager.jobs() if j.status == "running")
        self.window.set_status(
            f"Connected to {host} | Remote: {self.window.remote_browser.cwd} | "
            f"{len(self._local_selection)} local / {len(self._remote_selection)} remote selected | "
            f"{active} transfer(s) running"
        )


# ----------------------------------------------------------------------
# entry point
# ----------------------------------------------------------------------
def main(args: argparse.Namespace | None = None) -> None:
    """Launch the GUI."""
    debug = bool(args and getattr(args, "debug", False))
    configure_logging(debug=debug)

    try:
        controller = AppController(args=args)
    except ImportError as exc:  # tkinter missing
        # Without tkinter we have no GUI to fall back to; print to stderr.
        print(
            "This Python installation does not include tkinter. Please install a Python build with Tk support.",
            file=sys.stderr,
        )
        raise SystemExit(1) from exc

    controller.start()
