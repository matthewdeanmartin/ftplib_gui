"""Embedded FTP server control tab.

Lets the user spin up a local pyftpdlib server, manage in-memory user
accounts, watch the server log, and copy a user's credentials straight
into the connection bar so they can immediately try the client side.
"""

from __future__ import annotations

import pathlib
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from ftplib_gui.server import ServerConfig, ServerUser


class ServerTab(ttk.Frame):  # pylint: disable=too-many-ancestors,too-many-instance-attributes
    """Tab UI for starting/stopping the embedded FTP server and managing users."""

    def __init__(
        self,
        master: tk.Misc,
        on_start: Callable[[ServerConfig], None],
        on_stop: Callable[[], None],
        on_use_in_client: Callable[[ServerUser, str, int], None],
    ) -> None:
        super().__init__(master, padding=4)
        self._on_start = on_start
        self._on_stop = on_stop
        self._on_use_in_client = on_use_in_client

        self.host_var = tk.StringVar(value="127.0.0.1")
        self.port_var = tk.StringVar(value="2121")
        self.all_interfaces_var = tk.BooleanVar(value=False)
        self.allow_anonymous_var = tk.BooleanVar(value=False)
        self.anon_dir_var = tk.StringVar(value=str(pathlib.Path.home()))
        self.status_var = tk.StringVar(value="Stopped")

        self._users: list[ServerUser] = []
        self._running = False

        self._build()
        self._wire_all_interfaces_toggle()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        # --- Listener config -----------------------------------------
        listen_frame = ttk.LabelFrame(self, text="Listener", padding=6)
        listen_frame.pack(fill="x", padx=4, pady=4)

        ttk.Label(listen_frame, text="Host:").grid(row=0, column=0, sticky="w", padx=2)
        self.host_entry = ttk.Entry(listen_frame, textvariable=self.host_var, width=18)
        self.host_entry.grid(row=0, column=1, padx=2)

        ttk.Label(listen_frame, text="Port:").grid(row=0, column=2, sticky="w", padx=2)
        self.port_entry = ttk.Entry(listen_frame, textvariable=self.port_var, width=8)
        self.port_entry.grid(row=0, column=3, padx=2)

        self.all_interfaces_check = ttk.Checkbutton(
            listen_frame,
            text="Bind all interfaces (0.0.0.0)",
            variable=self.all_interfaces_var,
        )
        self.all_interfaces_check.grid(row=0, column=4, padx=8)

        self.start_btn = ttk.Button(listen_frame, text="Start Server", command=self._click_start)
        self.start_btn.grid(row=0, column=5, padx=4)
        self.stop_btn = ttk.Button(listen_frame, text="Stop Server", command=self._click_stop, state="disabled")
        self.stop_btn.grid(row=0, column=6, padx=2)

        ttk.Label(listen_frame, text="Status:").grid(row=1, column=0, sticky="w", padx=2, pady=(6, 0))
        self.status_label = ttk.Label(listen_frame, textvariable=self.status_var, foreground="grey25")
        self.status_label.grid(row=1, column=1, columnspan=4, sticky="w", padx=2, pady=(6, 0))

        # --- Anonymous access ----------------------------------------
        anon_frame = ttk.LabelFrame(self, text="Anonymous Access", padding=6)
        anon_frame.pack(fill="x", padx=4, pady=4)
        self.anon_check = ttk.Checkbutton(anon_frame, text="Allow anonymous logins", variable=self.allow_anonymous_var)
        self.anon_check.grid(row=0, column=0, padx=2, sticky="w")
        ttk.Label(anon_frame, text="Home dir:").grid(row=0, column=1, sticky="w", padx=(12, 2))
        self.anon_dir_entry = ttk.Entry(anon_frame, textvariable=self.anon_dir_var, width=42)
        self.anon_dir_entry.grid(row=0, column=2, padx=2)
        ttk.Button(anon_frame, text="Browse…", command=self._browse_anon_dir).grid(row=0, column=3, padx=2)

        # --- Users ---------------------------------------------------
        users_frame = ttk.LabelFrame(self, text="Users (session-only — not saved to disk)", padding=6)
        users_frame.pack(fill="both", expand=False, padx=4, pady=4)

        toolbar = ttk.Frame(users_frame)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="Add User…", command=self._add_user).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Remove", command=self._remove_user).pack(side="left", padx=2)
        ttk.Button(toolbar, text="Use in Client", command=self._use_in_client).pack(side="left", padx=8)

        columns = ("username", "homedir", "perm")
        self.users_tree = ttk.Treeview(users_frame, columns=columns, show="headings", height=6)
        self.users_tree.heading("username", text="Username")
        self.users_tree.heading("homedir", text="Home Directory")
        self.users_tree.heading("perm", text="Permissions")
        self.users_tree.column("username", width=140, anchor="w")
        self.users_tree.column("homedir", width=380, anchor="w")
        self.users_tree.column("perm", width=120, anchor="w")
        ysb = ttk.Scrollbar(users_frame, orient="vertical", command=self.users_tree.yview)
        self.users_tree.configure(yscrollcommand=ysb.set)
        self.users_tree.pack(side="left", fill="both", expand=True, pady=4)
        ysb.pack(side="right", fill="y", pady=4)

        # --- Server log ----------------------------------------------
        log_frame = ttk.LabelFrame(self, text="Server Log", padding=6)
        log_frame.pack(fill="both", expand=True, padx=4, pady=4)

        log_toolbar = ttk.Frame(log_frame)
        log_toolbar.pack(fill="x")
        ttk.Button(log_toolbar, text="Clear", command=self.clear_log).pack(side="left", padx=2)

        self.log_text = tk.Text(log_frame, height=10, wrap="none", state="disabled")
        log_ysb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_ysb.set)
        self.log_text.pack(side="left", fill="both", expand=True, pady=4)
        log_ysb.pack(side="right", fill="y", pady=4)

    # ------------------------------------------------------------------
    def _wire_all_interfaces_toggle(self) -> None:
        def update(*_: object) -> None:
            if self.all_interfaces_var.get():
                self.host_var.set("0.0.0.0")
                self.host_entry.configure(state="disabled")
            else:
                if self.host_var.get() == "0.0.0.0":
                    self.host_var.set("127.0.0.1")
                self.host_entry.configure(state="normal" if not self._running else "disabled")

        self.all_interfaces_var.trace_add("write", update)

    # ------------------------------------------------------------------
    def _browse_anon_dir(self) -> None:
        chosen = filedialog.askdirectory(
            title="Anonymous home directory",
            initialdir=self.anon_dir_var.get() or str(pathlib.Path.home()),
        )
        if chosen:
            self.anon_dir_var.set(chosen)

    def _add_user(self) -> None:
        username = simpledialog.askstring("Add User", "Username:", parent=self)
        if not username:
            return
        if any(u.username == username for u in self._users):
            messagebox.showerror("Add User", f"A user named {username!r} already exists.", parent=self)
            return
        password = simpledialog.askstring("Add User", f"Password for {username!r}:", parent=self, show="*")
        if password is None:
            return
        homedir = filedialog.askdirectory(
            title=f"Home directory for {username}",
            initialdir=str(pathlib.Path.home()),
            parent=self,
        )
        if not homedir:
            return
        user = ServerUser(username=username, password=password, homedir=homedir)
        self._users.append(user)
        self.users_tree.insert("", "end", iid=username, values=(username, homedir, user.perm))

    def _remove_user(self) -> None:
        selection = self.users_tree.selection()
        if not selection:
            return
        for username in selection:
            self._users = [u for u in self._users if u.username != username]
            self.users_tree.delete(username)

    def _use_in_client(self) -> None:
        selection = self.users_tree.selection()
        if not selection:
            messagebox.showinfo("Use in Client", "Select a user row first.", parent=self)
            return
        username = selection[0]
        user = next((u for u in self._users if u.username == username), None)
        if user is None:
            return
        host = self.host_var.get() or "127.0.0.1"
        if host in {"0.0.0.0", ""}:
            host = "127.0.0.1"
        try:
            port = int(self.port_var.get() or "2121")
        except ValueError:
            port = 2121
        self._on_use_in_client(user, host, port)

    # ------------------------------------------------------------------
    def _click_start(self) -> None:
        try:
            port = int(self.port_var.get())
        except ValueError:
            messagebox.showerror("Start Server", "Port must be an integer.", parent=self)
            return
        if not self._users and not self.allow_anonymous_var.get():
            messagebox.showerror(
                "Start Server",
                "Add at least one user, or enable anonymous access, before starting.",
                parent=self,
            )
            return

        anon_home = self.anon_dir_var.get().strip() if self.allow_anonymous_var.get() else None
        if self.allow_anonymous_var.get() and not anon_home:
            messagebox.showerror("Start Server", "Pick an anonymous home directory.", parent=self)
            return

        config = ServerConfig(
            host=self.host_var.get() or "127.0.0.1",
            port=port,
            users=list(self._users),
            allow_anonymous=self.allow_anonymous_var.get(),
            anonymous_homedir=anon_home,
        )
        self._on_start(config)

    def _click_stop(self) -> None:
        self._on_stop()

    # ------------------------------------------------------------------
    # public API for the controller
    # ------------------------------------------------------------------
    def append_log(self, message: str) -> None:
        """Append a single line to the embedded server log."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        line_count = int(self.log_text.index("end-1c").split(".", maxsplit=1)[0])
        if line_count > 5000:
            self.log_text.delete("1.0", f"{line_count - 5000}.0")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def clear_log(self) -> None:
        """Empty the embedded server log."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def set_running(self, running: bool, listening_on: str | None = None) -> None:
        """Reflect server-running state in button enable/disable and status label."""
        self._running = running
        self.start_btn.configure(state="disabled" if running else "normal")
        self.stop_btn.configure(state="normal" if running else "disabled")
        edit_state = "disabled" if running else "normal"
        self.host_entry.configure(state="disabled" if (running or self.all_interfaces_var.get()) else "normal")
        self.port_entry.configure(state=edit_state)
        self.all_interfaces_check.configure(state=edit_state)
        if running and listening_on:
            self.status_var.set(f"Running — listening on {listening_on}")
            self.status_label.configure(foreground="forest green")
        elif running:
            self.status_var.set("Running")
            self.status_label.configure(foreground="forest green")
        else:
            self.status_var.set("Stopped")
            self.status_label.configure(foreground="grey25")
