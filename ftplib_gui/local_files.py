"""Local filesystem operations used by the GUI."""

from __future__ import annotations

import os
import pathlib
import shutil
from collections.abc import Iterable
from datetime import datetime

from ftplib_gui.models import LocalEntry


class LocalFileService:
    """Thin wrapper around :mod:`pathlib` / :mod:`os` operations."""

    def home(self) -> pathlib.Path:
        """Return the user's home directory."""
        return pathlib.Path.home()

    def listdir(self, path: pathlib.Path, show_hidden: bool = False) -> list[LocalEntry]:
        """List the entries inside ``path``.

        Skips entries whose ``stat()`` fails (e.g. broken symlinks).
        """
        entries: list[LocalEntry] = []
        with os.scandir(path) as it:
            for entry in it:
                if not show_hidden and entry.name.startswith("."):
                    continue
                try:
                    info = entry.stat()
                except OSError:
                    continue
                entries.append(
                    LocalEntry(
                        name=entry.name,
                        path=pathlib.Path(entry.path),
                        is_dir=entry.is_dir(),
                        size=info.st_size if entry.is_file() else None,
                        modified=datetime.fromtimestamp(info.st_mtime),
                    )
                )
        entries.sort(key=lambda e: (not e.is_dir, e.name.lower()))
        return entries

    def mkdir(self, path: pathlib.Path) -> None:
        """Create a directory; fail if it already exists."""
        path.mkdir(parents=False, exist_ok=False)

    def delete(self, path: pathlib.Path) -> None:
        """Delete a file or recursively delete a directory."""
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        else:
            path.unlink()

    def rename(self, old_path: pathlib.Path, new_path: pathlib.Path) -> None:
        """Rename a file or directory."""
        old_path.rename(new_path)

    def iter_files(self, paths: Iterable[pathlib.Path]) -> Iterable[pathlib.Path]:
        """Yield only the file paths from ``paths``."""
        for p in paths:
            if p.is_file():
                yield p
