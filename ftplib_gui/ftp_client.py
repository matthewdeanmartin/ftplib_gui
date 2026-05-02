"""FTP/FTPS client service used by the GUI.

Wraps :mod:`ftplib` so the rest of the application can talk to a remote
server in protocol-agnostic terms. All blocking calls in this module are
expected to be run from worker threads.
"""

from __future__ import annotations

import ftplib
import posixpath
import re
import ssl
import threading
from datetime import datetime
from typing import Callable, Optional

from ftplib_gui.logging_utils import get_logger
from ftplib_gui.models import ConnectionProfile, RemoteEntry


class TransferCancelled(Exception):
    """Raised inside transfer callbacks when the user cancels."""


# Unix-style LIST line, e.g.:
# -rw-r--r-- 1 user group 1024 Jan 01 12:00 file.txt
# drwxr-xr-x 2 user group 4096 Jan 01 12:00 folder
_LIST_RE = re.compile(
    r"^(?P<perm>[\-dlpscbD][rwxstST\-]{9})\s+"
    r"\d+\s+\S+\s+\S+\s+"
    r"(?P<size>\d+)\s+"
    r"(?P<mon>\w{3})\s+(?P<day>\d{1,2})\s+"
    r"(?P<rest>\S+)\s+"
    r"(?P<name>.+)$"
)

_MONTHS = {
    "Jan": 1,
    "Feb": 2,
    "Mar": 3,
    "Apr": 4,
    "May": 5,
    "Jun": 6,
    "Jul": 7,
    "Aug": 8,
    "Sep": 9,
    "Oct": 10,
    "Nov": 11,
    "Dec": 12,
}


def parse_unix_list_line(line: str, now: Optional[datetime] = None) -> Optional[RemoteEntry]:
    """Parse a single Unix-style ``LIST`` output line.

    Returns ``None`` if the line could not be parsed.
    """
    match = _LIST_RE.match(line.strip())
    if not match:
        return None

    perm = match.group("perm")
    size = int(match.group("size"))
    name = match.group("name")
    if " -> " in name:  # symlink target
        name = name.split(" -> ", 1)[0]
    mon = _MONTHS.get(match.group("mon"))
    day = int(match.group("day"))
    rest = match.group("rest")

    modified: Optional[datetime] = None
    if mon is not None:
        anchor = now or datetime.now()
        try:
            if ":" in rest:
                hour, minute = rest.split(":", 1)
                modified = datetime(anchor.year, mon, day, int(hour), int(minute))
                if modified > anchor:
                    modified = modified.replace(year=anchor.year - 1)
            else:
                modified = datetime(int(rest), mon, day)
        except ValueError:
            modified = None

    return RemoteEntry(
        name=name,
        path=name,  # caller will join with cwd
        is_dir=perm.startswith("d"),
        size=size,
        modified=modified,
        permissions=perm,
    )


class FTPClientService:
    """Synchronous FTP/FTPS service. Not thread-safe by itself.

    Calls should be serialised by the :class:`TransferManager` and the
    Tk event loop — a single worker thread does all FTP work.
    """

    def __init__(self) -> None:
        self._ftp: Optional[ftplib.FTP] = None
        self._profile: Optional[ConnectionProfile] = None
        self._lock = threading.RLock()
        self._log = get_logger()

    # ------------------------------------------------------------------
    # connection lifecycle
    # ------------------------------------------------------------------
    def connect(self, profile: ConnectionProfile) -> None:
        """Open a new FTP/FTPS session using the given profile."""
        with self._lock:
            self._close_quietly()

            is_tls = profile.protocol == "ftps"
            if is_tls:
                if profile.verify_tls:
                    context = ssl.create_default_context()
                else:
                    context = ssl._create_unverified_context()
                ftp: ftplib.FTP = ftplib.FTP_TLS(context=context)
            else:
                ftp = ftplib.FTP()

            self._log.info("Connecting to %s:%s (%s)", profile.host, profile.port, profile.protocol)
            ftp.connect(host=profile.host, port=profile.port, timeout=30)

            if profile.anonymous:
                ftp.login(user="anonymous", passwd="anonymous@")
            else:
                ftp.login(user=profile.username, passwd=profile.password)

            if is_tls:
                ftp.prot_p()  # type: ignore[attr-defined]

            ftp.set_pasv(profile.passive)

            self._ftp = ftp
            self._profile = profile
            self._log.info("Logged in as %s", profile.username if not profile.anonymous else "anonymous")

    def disconnect(self) -> None:
        """Close the active FTP session, if any."""
        with self._lock:
            self._close_quietly()
            self._profile = None

    def _close_quietly(self) -> None:
        if self._ftp is None:
            return
        try:
            self._ftp.quit()
        except Exception:
            try:
                self._ftp.close()
            except Exception:
                pass
        self._ftp = None

    def is_connected(self) -> bool:
        """True if the underlying socket appears alive."""
        with self._lock:
            return self._ftp is not None and self._ftp.sock is not None

    @property
    def profile(self) -> Optional[ConnectionProfile]:
        """Return the active profile, or ``None`` if not connected."""
        return self._profile

    # ------------------------------------------------------------------
    # navigation
    # ------------------------------------------------------------------
    def pwd(self) -> str:
        """Return the current remote working directory."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            return self._ftp.pwd()

    def cwd(self, path: str) -> None:
        """Change the remote working directory."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            self._ftp.cwd(path)
            self._log.info("CWD %s", path)

    def cdup(self) -> None:
        """Move up one remote directory level."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            self._ftp.cwd("..")

    # ------------------------------------------------------------------
    # listing
    # ------------------------------------------------------------------
    def listdir(self, path: Optional[str] = None) -> list[RemoteEntry]:
        """List remote entries, preferring ``MLSD`` and falling back to ``LIST``/``NLST``."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            cwd = path or self._ftp.pwd()
            entries: list[RemoteEntry] = []

            # 1) MLSD
            try:
                for name, facts in self._ftp.mlsd(cwd):
                    entry_type = facts.get("type")
                    if entry_type in ("cdir", "pdir"):
                        continue
                    is_dir = entry_type == "dir"
                    size = int(facts["size"]) if "size" in facts else None
                    modify = facts.get("modify")
                    modified: Optional[datetime] = None
                    if modify:
                        try:
                            modified = datetime.strptime(modify[:14], "%Y%m%d%H%M%S")
                        except ValueError:
                            modified = None
                    entries.append(
                        RemoteEntry(
                            name=name,
                            path=posixpath.join(cwd, name),
                            is_dir=is_dir,
                            size=size,
                            modified=modified,
                            permissions=facts.get("unix.mode") or facts.get("perm"),
                        )
                    )
                return entries
            except (ftplib.error_perm, ftplib.error_proto, ftplib.error_temp):
                self._log.debug("MLSD not available, falling back to LIST")

            # 2) LIST (Unix-style parsing)
            lines: list[str] = []
            try:
                self._ftp.retrlines(f"LIST {cwd}" if path else "LIST", lines.append)
                for line in lines:
                    parsed = parse_unix_list_line(line)
                    if parsed is None:
                        continue
                    if parsed.name in (".", ".."):
                        continue
                    parsed.path = posixpath.join(cwd, parsed.name)
                    entries.append(parsed)
                if entries:
                    return entries
            except ftplib.all_errors:
                self._log.debug("LIST failed, falling back to NLST")

            # 3) NLST: names only
            try:
                names = self._ftp.nlst(cwd) if path else self._ftp.nlst()
            except ftplib.all_errors as exc:
                self._log.warning("NLST failed: %s", exc)
                return entries

            for name in names:
                base = posixpath.basename(name) or name
                if base in (".", ".."):
                    continue
                entries.append(
                    RemoteEntry(
                        name=base,
                        path=posixpath.join(cwd, base),
                        is_dir=False,  # unknown; do not probe by default
                    )
                )
            return entries

    # ------------------------------------------------------------------
    # transfers
    # ------------------------------------------------------------------
    def size(self, remote_path: str) -> Optional[int]:
        """Return the size of ``remote_path`` in bytes, or ``None`` if unknown."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            try:
                return self._ftp.size(remote_path)
            except ftplib.all_errors:
                return None

    def download_file(
        self,
        remote_path: str,
        local_path: str,
        progress_callback: Callable[[int], None],
        cancel_event: threading.Event,
        blocksize: int = 8192,
    ) -> None:
        """Download ``remote_path`` to ``local_path`` using ``RETR``."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None

            with open(local_path, "wb") as fh:

                def callback(block: bytes) -> None:
                    if cancel_event.is_set():
                        raise TransferCancelled()
                    fh.write(block)
                    progress_callback(len(block))

                try:
                    self._ftp.retrbinary(f"RETR {remote_path}", callback, blocksize=blocksize)
                except TransferCancelled:
                    self._log.info("Download cancelled: %s", remote_path)
                    self._reset_after_cancel()
                    raise

    def upload_file(
        self,
        local_path: str,
        remote_path: str,
        progress_callback: Callable[[int], None],
        cancel_event: threading.Event,
        blocksize: int = 8192,
    ) -> None:
        """Upload ``local_path`` to ``remote_path`` using ``STOR``."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None

            with open(local_path, "rb") as fh:

                def callback(block: bytes) -> None:
                    if cancel_event.is_set():
                        raise TransferCancelled()
                    progress_callback(len(block))

                try:
                    self._ftp.storbinary(f"STOR {remote_path}", fh, blocksize=blocksize, callback=callback)
                except TransferCancelled:
                    self._log.info("Upload cancelled: %s", local_path)
                    self._reset_after_cancel()
                    raise

    def _reset_after_cancel(self) -> None:
        """Close the data connection after a cancelled transfer."""
        try:
            assert self._ftp is not None
            self._ftp.close()
        except Exception:
            pass
        self._ftp = None

    # ------------------------------------------------------------------
    # filesystem ops
    # ------------------------------------------------------------------
    def mkdir(self, path: str) -> None:
        """Create a remote directory."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            self._ftp.mkd(path)
            self._log.info("MKD %s", path)

    def rmdir(self, path: str) -> None:
        """Remove an empty remote directory."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            self._ftp.rmd(path)
            self._log.info("RMD %s", path)

    def delete_file(self, path: str) -> None:
        """Delete a remote file."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            self._ftp.delete(path)
            self._log.info("DELE %s", path)

    def rename(self, old_path: str, new_path: str) -> None:
        """Rename or move a remote entry."""
        with self._lock:
            self._require_connected()
            assert self._ftp is not None
            self._ftp.rename(old_path, new_path)
            self._log.info("RNFR/RNTO %s -> %s", old_path, new_path)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _require_connected(self) -> None:
        if self._ftp is None:
            raise ConnectionError("Not connected to an FTP server")
