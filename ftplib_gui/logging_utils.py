"""Logging helpers for ftplib_gui.

Configures a logger that writes to a rotating file under
``~/.ftplib-gui/logs/app.log`` and exposes a callable handler that the
GUI can use to render log records in the log panel.
"""

from __future__ import annotations

import logging
import logging.handlers
import pathlib
from typing import Callable

LOGGER_NAME = "ftplib_gui"

_GUI_HANDLER: GuiLogHandler | None = None


def app_data_dir() -> pathlib.Path:
    """Return ``~/.ftplib-gui`` (creating it on first use)."""
    path = pathlib.Path.home() / ".ftplib-gui"
    path.mkdir(parents=True, exist_ok=True)
    return path


def log_file_path() -> pathlib.Path:
    """Return the rotating log file path."""
    logs = app_data_dir() / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    return logs / "app.log"


class GuiLogHandler(logging.Handler):
    """A logging handler that forwards formatted records to a callback.

    The callback is typically the GUI log panel's ``append`` method. The
    callback is invoked with a single ``str`` argument and must be
    thread-safe — usually by pushing the message onto a queue that the
    Tk main thread polls.
    """

    def __init__(self, sink: Callable[[str], None]) -> None:
        super().__init__()
        self.sink = sink

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - trivial
        try:
            msg = self.format(record)
            self.sink(msg)
        except Exception:  # pylint: disable=broad-exception-caught
            self.handleError(record)


def configure_logging(debug: bool = False) -> logging.Logger:
    """Configure the root ``ftplib_gui`` logger.

    Sets up a rotating file handler. The GUI handler is attached
    separately by :func:`attach_gui_sink` once the UI is alive.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    # Prevent double-configuration
    for handler in list(logger.handlers):
        if getattr(handler, "_ftplib_gui_managed", False):
            logger.removeHandler(handler)

    fmt = logging.Formatter(
        fmt="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file_path(),
        maxBytes=1_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    # pylint: disable=attribute-defined-outside-init,protected-access
    file_handler._ftplib_gui_managed = True  # type: ignore[attr-defined]
    logger.addHandler(file_handler)

    return logger


def attach_gui_sink(sink: Callable[[str], None]) -> GuiLogHandler:
    """Attach a GUI sink so log records also flow into the log panel."""
    global _GUI_HANDLER  # pylint: disable=global-statement
    logger = logging.getLogger(LOGGER_NAME)
    if _GUI_HANDLER is not None:
        logger.removeHandler(_GUI_HANDLER)

    handler = GuiLogHandler(sink)
    handler.setFormatter(
        logging.Formatter(
            fmt="[%(asctime)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    # pylint: disable=attribute-defined-outside-init,protected-access
    handler._ftplib_gui_managed = True  # type: ignore[attr-defined]
    logger.addHandler(handler)
    _GUI_HANDLER = handler
    return handler


def get_logger() -> logging.Logger:
    """Return the application's logger."""
    return logging.getLogger(LOGGER_NAME)
