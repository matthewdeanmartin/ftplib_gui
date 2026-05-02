"""Connection-profile persistence.

Profiles are stored as JSON under ``~/.ftplib-gui/profiles.json``. By
default the password is *not* persisted. If the optional ``keyring``
extra is installed, callers may opt in to storing the password in the
OS-native credential store.
"""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import pathlib
from typing import Any

from ftplib_gui.logging_utils import app_data_dir, get_logger
from ftplib_gui.models import ConnectionProfile

_KEYRING_SERVICE = "ftplib_gui"


def _try_import_keyring() -> Any:
    """Import ``keyring`` lazily so it stays an optional dependency."""
    try:
        return importlib.import_module("keyring")
    except ImportError:
        return None


class ProfileStore:
    """Load and save :class:`ConnectionProfile` records to disk."""

    def __init__(self, path: pathlib.Path | None = None) -> None:
        self.path = path or (app_data_dir() / "profiles.json")
        self._log = get_logger()

    # ------------------------------------------------------------------
    def load(self) -> list[ConnectionProfile]:
        """Return all stored profiles. Missing / unreadable file → ``[]``."""
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._log.warning("Could not read profiles file %s: %s", self.path, exc)
            return []

        raw_profiles = data.get("profiles", []) if isinstance(data, dict) else []
        profiles: list[ConnectionProfile] = []
        for item in raw_profiles:
            try:
                profile = ConnectionProfile.from_dict(item)
            except (KeyError, TypeError, ValueError) as exc:
                self._log.warning("Skipping malformed profile entry: %s", exc)
                continue
            if profile.save_password:
                stored = self._read_password(profile)
                if stored is not None:
                    profile.password = stored
            profiles.append(profile)
        return profiles

    def save(self, profiles: list[ConnectionProfile]) -> None:
        """Persist the given list of profiles, replacing the file."""
        payload = {"profiles": [p.to_dict() for p in profiles]}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

        # Best-effort POSIX permission tightening (no-op on Windows).
        with contextlib.suppress(OSError, NotImplementedError):
            if hasattr(os, "chmod") and os.name == "posix":
                os.chmod(self.path, 0o600)

        for profile in profiles:
            if profile.save_password and profile.password:
                self._write_password(profile)
            else:
                self._delete_password(profile)

    def upsert(self, profile: ConnectionProfile) -> None:
        """Add or replace a profile by name."""
        profiles = self.load()
        for i, existing in enumerate(profiles):
            if existing.name == profile.name:
                profiles[i] = profile
                break
        else:
            profiles.append(profile)
        self.save(profiles)

    def delete(self, name: str) -> bool:
        """Remove a profile by name. Returns ``True`` if anything was removed."""
        profiles = self.load()
        kept = [p for p in profiles if p.name != name]
        if len(kept) == len(profiles):
            return False
        self.save(kept)
        return True

    # ------------------------------------------------------------------
    # keyring integration (optional)
    # ------------------------------------------------------------------
    def keyring_available(self) -> bool:
        """True if the optional ``keyring`` package is installed."""
        return _try_import_keyring() is not None

    def _keyring_username(self, profile: ConnectionProfile) -> str:
        return f"{profile.name}::{profile.host}::{profile.username}"

    def _read_password(self, profile: ConnectionProfile) -> str | None:
        keyring = _try_import_keyring()
        if keyring is None:
            return None
        try:
            val = keyring.get_password(_KEYRING_SERVICE, self._keyring_username(profile))
            return str(val) if val is not None else None
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._log.warning("Keyring read failed: %s", exc)
            return None

    def _write_password(self, profile: ConnectionProfile) -> None:
        keyring = _try_import_keyring()
        if keyring is None:
            self._log.warning(
                "save_password=True but the 'keyring' extra is not installed; password will not be stored."
            )
            return
        try:
            keyring.set_password(_KEYRING_SERVICE, self._keyring_username(profile), profile.password)
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._log.warning("Keyring write failed: %s", exc)

    def _delete_password(self, profile: ConnectionProfile) -> None:
        keyring = _try_import_keyring()
        if keyring is None:
            return
        with contextlib.suppress(Exception):
            keyring.delete_password(_KEYRING_SERVICE, self._keyring_username(profile))
