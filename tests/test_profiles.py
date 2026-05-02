"""Tests for the on-disk profile store."""

from __future__ import annotations

import json
import pathlib

from ftplib_gui.models import ConnectionProfile
from ftplib_gui.profiles import ProfileStore


def make_store(tmp_path: pathlib.Path) -> ProfileStore:
    return ProfileStore(path=tmp_path / "profiles.json")


def test_load_missing_file_returns_empty(tmp_path: pathlib.Path) -> None:
    store = make_store(tmp_path)
    assert not store.load()


def test_save_and_load_roundtrip(tmp_path: pathlib.Path) -> None:
    store = make_store(tmp_path)
    profile = ConnectionProfile(
        name="ex",
        host="ftp.example.com",
        port=2121,
        protocol="ftps",
        username="alice",
        password="should-not-persist",
        passive=False,
    )
    store.save([profile])

    raw = json.loads(store.path.read_text(encoding="utf-8"))
    assert raw["profiles"][0]["name"] == "ex"
    assert "password" not in raw["profiles"][0]

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].name == "ex"
    assert loaded[0].host == "ftp.example.com"
    assert loaded[0].password == ""
    assert loaded[0].passive is False


def test_upsert_replaces_existing(tmp_path: pathlib.Path) -> None:
    store = make_store(tmp_path)
    a = ConnectionProfile(name="a", host="h1")
    b = ConnectionProfile(name="b", host="h2")
    store.save([a, b])

    updated = ConnectionProfile(name="b", host="new-host")
    store.upsert(updated)

    loaded = {p.name: p for p in store.load()}
    assert loaded["b"].host == "new-host"
    assert loaded["a"].host == "h1"


def test_delete_removes_profile(tmp_path: pathlib.Path) -> None:
    store = make_store(tmp_path)
    store.save([ConnectionProfile(name="a", host="h1"), ConnectionProfile(name="b", host="h2")])
    assert store.delete("a") is True
    remaining = [p.name for p in store.load()]
    assert remaining == ["b"]
    assert store.delete("missing") is False


def test_load_ignores_corrupt_file(tmp_path: pathlib.Path) -> None:
    store = make_store(tmp_path)
    store.path.write_text("{ not json", encoding="utf-8")
    assert not store.load()
