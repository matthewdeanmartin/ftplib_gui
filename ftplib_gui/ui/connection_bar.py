"""Top-of-window connection toolbar."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from ftplib_gui.models import ConnectionProfile


class ConnectionBar(ttk.Frame):
    """Toolbar holding host/port/credentials and connect/disconnect buttons."""

    def __init__(
        self,
        master: tk.Misc,
        on_connect: Callable[[ConnectionProfile], None],
        on_disconnect: Callable[[], None],
    ) -> None:
        super().__init__(master, padding=4)
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

        self.host_var = tk.StringVar()
        self.port_var = tk.StringVar(value="21")
        self.user_var = tk.StringVar()
        self.password_var = tk.StringVar()
        self.protocol_var = tk.StringVar(value="ftp")
        self.passive_var = tk.BooleanVar(value=True)
        self.anonymous_var = tk.BooleanVar(value=False)
        self.verify_tls_var = tk.BooleanVar(value=True)

        self._build()
        self._wire_anonymous_toggle()
        self._wire_protocol_toggle()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        row = 0
        ttk.Label(self, text="Host:").grid(row=row, column=0, sticky="w", padx=2)
        self.host_entry = ttk.Entry(self, textvariable=self.host_var, width=22)
        self.host_entry.grid(row=row, column=1, padx=2)

        ttk.Label(self, text="Port:").grid(row=row, column=2, sticky="w", padx=2)
        self.port_entry = ttk.Entry(self, textvariable=self.port_var, width=6)
        self.port_entry.grid(row=row, column=3, padx=2)

        ttk.Label(self, text="User:").grid(row=row, column=4, sticky="w", padx=2)
        self.user_entry = ttk.Entry(self, textvariable=self.user_var, width=14)
        self.user_entry.grid(row=row, column=5, padx=2)

        ttk.Label(self, text="Password:").grid(row=row, column=6, sticky="w", padx=2)
        self.password_entry = ttk.Entry(self, textvariable=self.password_var, show="*", width=14)
        self.password_entry.grid(row=row, column=7, padx=2)

        ttk.Label(self, text="Protocol:").grid(row=row, column=8, sticky="w", padx=2)
        self.protocol_combo = ttk.Combobox(
            self,
            textvariable=self.protocol_var,
            values=["ftp", "ftps"],
            width=6,
            state="readonly",
        )
        self.protocol_combo.grid(row=row, column=9, padx=2)

        self.passive_check = ttk.Checkbutton(self, text="Passive", variable=self.passive_var)
        self.passive_check.grid(row=row, column=10, padx=4)

        self.anonymous_check = ttk.Checkbutton(self, text="Anonymous", variable=self.anonymous_var)
        self.anonymous_check.grid(row=row, column=11, padx=4)

        self.verify_check = ttk.Checkbutton(self, text="Verify TLS", variable=self.verify_tls_var)
        self.verify_check.grid(row=row, column=12, padx=4)

        self.connect_btn = ttk.Button(self, text="Connect", command=self._click_connect)
        self.connect_btn.grid(row=row, column=13, padx=4)

        self.disconnect_btn = ttk.Button(self, text="Disconnect", command=self._click_disconnect, state="disabled")
        self.disconnect_btn.grid(row=row, column=14, padx=2)

    def _wire_anonymous_toggle(self) -> None:
        def update(*_: object) -> None:
            state = "disabled" if self.anonymous_var.get() else "normal"
            self.user_entry.configure(state=state)
            self.password_entry.configure(state=state)

        self.anonymous_var.trace_add("write", update)
        update()

    def _wire_protocol_toggle(self) -> None:
        def update(*_: object) -> None:
            state = "normal" if self.protocol_var.get() == "ftps" else "disabled"
            self.verify_check.configure(state=state)

        self.protocol_var.trace_add("write", update)
        update()

    # ------------------------------------------------------------------
    def _click_connect(self) -> None:
        try:
            port = int(self.port_var.get() or "21")
        except ValueError:
            port = 21
        profile = ConnectionProfile(
            name=self.host_var.get() or "ad-hoc",
            host=self.host_var.get(),
            port=port,
            protocol=self.protocol_var.get(),
            username=self.user_var.get(),
            password=self.password_var.get(),
            anonymous=self.anonymous_var.get(),
            passive=self.passive_var.get(),
            verify_tls=self.verify_tls_var.get(),
        )
        self._on_connect(profile)

    def _click_disconnect(self) -> None:
        self._on_disconnect()

    # ------------------------------------------------------------------
    def set_connected(self, connected: bool) -> None:
        """Enable/disable controls based on the connection state."""
        edit_state = "disabled" if connected else "normal"
        self.host_entry.configure(state=edit_state)
        self.port_entry.configure(state=edit_state)
        self.protocol_combo.configure(state="disabled" if connected else "readonly")
        self.passive_check.configure(state=edit_state)
        self.anonymous_check.configure(state=edit_state)
        if not connected:
            self._wire_anonymous_toggle()
            self._wire_protocol_toggle()
        else:
            self.user_entry.configure(state="disabled")
            self.password_entry.configure(state="disabled")
            self.verify_check.configure(state="disabled")
        self.connect_btn.configure(state="disabled" if connected else "normal")
        self.disconnect_btn.configure(state="normal" if connected else "disabled")

    def populate(self, profile: ConnectionProfile) -> None:
        """Pre-fill the toolbar with values from a saved profile."""
        self.host_var.set(profile.host)
        self.port_var.set(str(profile.port))
        self.user_var.set(profile.username)
        self.password_var.set(profile.password)
        self.protocol_var.set(profile.protocol)
        self.passive_var.set(profile.passive)
        self.anonymous_var.set(profile.anonymous)
        self.verify_tls_var.set(profile.verify_tls)

    def get_profile(self) -> Optional[ConnectionProfile]:
        """Return the profile currently shown in the toolbar."""
        if not self.host_var.get():
            return None
        try:
            port = int(self.port_var.get() or "21")
        except ValueError:
            return None
        return ConnectionProfile(
            name=self.host_var.get(),
            host=self.host_var.get(),
            port=port,
            protocol=self.protocol_var.get(),
            username=self.user_var.get(),
            password=self.password_var.get(),
            anonymous=self.anonymous_var.get(),
            passive=self.passive_var.get(),
            verify_tls=self.verify_tls_var.get(),
        )
