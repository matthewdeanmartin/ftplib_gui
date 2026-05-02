"""Embedded FTP server backed by pyftpdlib.

Optional dependency: this module imports pyftpdlib lazily so the rest of
the app keeps working even when it is not installed. Use
:func:`is_available` to detect availability before constructing
:class:`EmbeddedFTPServer`.

The server runs ``serve_forever`` on a background thread. Users are kept
in-memory only (no on-disk persistence) per the deliberate "session-only"
choice — passwords on disk are a footgun for a tool you spin up to
experiment with.
"""

from __future__ import annotations

import contextlib
import logging
import threading
from dataclasses import dataclass, field
from typing import Callable


def is_available() -> bool:
    """Return True when pyftpdlib can be imported."""
    try:
        import pyftpdlib  # noqa: F401  pylint: disable=import-outside-toplevel,unused-import
    except ImportError:
        return False
    return True


@dataclass
class ServerUser:
    """A single in-memory user the embedded server will accept."""

    username: str
    password: str
    homedir: str
    perm: str = "elradfmwMT"  # full permissions by default; see pyftpdlib docs


@dataclass
class ServerConfig:
    """User-supplied configuration for the embedded FTP server."""

    host: str = "127.0.0.1"
    port: int = 2121
    users: list[ServerUser] = field(default_factory=list)
    allow_anonymous: bool = False
    anonymous_homedir: str | None = None


class EmbeddedFTPServer:
    """Lifecycle wrapper around ``pyftpdlib.servers.FTPServer``.

    The server runs on a background thread; ``start`` returns once the
    socket is bound, ``stop`` closes the listener and joins the thread.
    Server-side log records are forwarded to ``log_callback`` so the GUI
    can display them in real time.
    """

    def __init__(self, log_callback: Callable[[str], None] | None = None) -> None:
        self._log_callback = log_callback
        self._server: object | None = None
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._handler_logger: logging.Logger | None = None
        self._gui_handler: logging.Handler | None = None
        self.config: ServerConfig | None = None

    # ------------------------------------------------------------------
    @property
    def running(self) -> bool:
        """True while the background server thread is alive."""
        return self._thread is not None and self._thread.is_alive()

    # ------------------------------------------------------------------
    def start(self, config: ServerConfig) -> None:
        """Bind a listener and start serving on a background thread.

        Raises ``RuntimeError`` if already running or pyftpdlib is missing,
        and ``OSError`` if the bind fails.
        """
        with self._lock:
            if self.running:
                raise RuntimeError("Server is already running.")

            from pyftpdlib.authorizers import (  # pylint: disable=import-outside-toplevel
                DummyAuthorizer,
            )
            from pyftpdlib.handlers import FTPHandler  # pylint: disable=import-outside-toplevel
            from pyftpdlib.servers import FTPServer  # pylint: disable=import-outside-toplevel

            authorizer = DummyAuthorizer()
            for user in config.users:
                authorizer.add_user(user.username, user.password, user.homedir, perm=user.perm)
            if config.allow_anonymous and config.anonymous_homedir:
                authorizer.add_anonymous(config.anonymous_homedir)

            handler = FTPHandler
            handler.authorizer = authorizer
            handler.banner = "ftplib-gui embedded server ready."

            server = FTPServer((config.host, config.port), handler)
            server.max_cons = 32
            server.max_cons_per_ip = 8

            self._attach_log_bridge()

            self._server = server
            self.config = config

            thread = threading.Thread(
                target=self._run,
                args=(server,),
                name="ftplib-gui-server",
                daemon=True,
            )
            self._thread = thread
            thread.start()
            self._emit(f"Server listening on {config.host}:{config.port}")

    def stop(self, timeout: float = 5.0) -> None:
        """Close the listener and join the server thread."""
        with self._lock:
            server = self._server
            thread = self._thread
            if server is None or thread is None:
                return
            try:
                server.close_all()  # type: ignore[attr-defined]
            except Exception as exc:  # pylint: disable=broad-exception-caught
                self._emit(f"Error during shutdown: {exc}")
            self._server = None
            self._thread = None
            self._detach_log_bridge()

        thread.join(timeout=timeout)
        self._emit("Server stopped.")

    # ------------------------------------------------------------------
    def _run(self, server: object) -> None:
        try:
            server.serve_forever(timeout=1.0, blocking=True, handle_exit=False)  # type: ignore[attr-defined]
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._emit(f"Server crashed: {exc}")

    def _emit(self, message: str) -> None:
        if self._log_callback is not None:
            self._log_callback(message)

    # ------------------------------------------------------------------
    def _attach_log_bridge(self) -> None:
        """Forward pyftpdlib's logger output to the GUI log callback."""
        if self._log_callback is None:
            return
        logger = logging.getLogger("pyftpdlib")
        callback = self._log_callback

        class _GuiHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                with contextlib.suppress(Exception):
                    callback(self.format(record))

        handler = _GuiHandler()
        handler.setFormatter(logging.Formatter("%(asctime)s [pyftpdlib] %(message)s", "%H:%M:%S"))
        logger.addHandler(handler)
        if logger.level == logging.NOTSET or logger.level > logging.INFO:
            logger.setLevel(logging.INFO)
        self._handler_logger = logger
        self._gui_handler = handler

    def _detach_log_bridge(self) -> None:
        if self._handler_logger is not None and self._gui_handler is not None:
            self._handler_logger.removeHandler(self._gui_handler)
        self._handler_logger = None
        self._gui_handler = None
