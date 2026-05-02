"""Data models used by the ftplib_gui application."""

from __future__ import annotations

import pathlib
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class ConnectionProfile:
    """A saved set of connection parameters for an FTP/FTPS server."""

    name: str
    host: str
    port: int = 21
    protocol: str = "ftp"  # "ftp" or "ftps"
    username: str = ""
    password: str = ""
    anonymous: bool = False
    passive: bool = True
    verify_tls: bool = True
    default_local_dir: str | None = None
    default_remote_dir: str | None = None
    save_password: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly dict, excluding the password."""
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol,
            "username": self.username,
            "anonymous": self.anonymous,
            "passive": self.passive,
            "verify_tls": self.verify_tls,
            "default_local_dir": self.default_local_dir,
            "default_remote_dir": self.default_remote_dir,
            "save_password": self.save_password,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ConnectionProfile:
        """Create a profile from a dict (password is never read here)."""
        return cls(
            name=data["name"],
            host=data["host"],
            port=int(data.get("port", 21)),
            protocol=data.get("protocol", "ftp"),
            username=data.get("username", ""),
            anonymous=bool(data.get("anonymous", False)),
            passive=bool(data.get("passive", True)),
            verify_tls=bool(data.get("verify_tls", True)),
            default_local_dir=data.get("default_local_dir"),
            default_remote_dir=data.get("default_remote_dir"),
            save_password=bool(data.get("save_password", False)),
        )


@dataclass
class RemoteEntry:
    """A directory entry returned by the remote FTP server."""

    name: str
    path: str
    is_dir: bool
    size: int | None = None
    modified: datetime | None = None
    permissions: str | None = None


@dataclass
class LocalEntry:
    """A directory entry on the local filesystem."""

    name: str
    path: pathlib.Path
    is_dir: bool
    size: int | None = None
    modified: datetime | None = None


@dataclass
class TransferJob:
    """A queued transfer (upload or download)."""

    direction: str  # "upload" or "download"
    source: str
    destination: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    size: int | None = None
    bytes_done: int = 0
    status: str = "queued"  # queued, running, completed, failed, cancelled
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)


@dataclass
class UIEvent:
    """An event sent from a worker thread to the Tk main thread."""

    type: str
    payload: dict[str, Any] = field(default_factory=dict)
