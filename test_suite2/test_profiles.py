from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ftplib_gui.models import ConnectionProfile
from ftplib_gui.profiles import ProfileStore


@pytest.fixture
def profile_file(tmp_path):
    return tmp_path / "profiles.json"

@pytest.fixture
def store(profile_file):
    return ProfileStore(path=profile_file)

def test_load_empty(store):
    assert store.load() == []

def test_load_malformed(store, profile_file):
    profile_file.write_text("invalid json")
    assert store.load() == []

def test_save_and_load(store, profile_file):
    p1 = ConnectionProfile(name="test1", host="example.com")
    p2 = ConnectionProfile(name="test2", host="ftp.example.com", port=2121)

    store.save([p1, p2])

    loaded = store.load()
    assert len(loaded) == 2
    assert loaded[0].name == "test1"
    assert loaded[1].port == 2121

def test_upsert(store):
    p1 = ConnectionProfile(name="test1", host="example.com")
    store.upsert(p1)

    p1_updated = ConnectionProfile(name="test1", host="updated.com")
    store.upsert(p1_updated)

    loaded = store.load()
    assert len(loaded) == 1
    assert loaded[0].host == "updated.com"

def test_delete(store):
    p1 = ConnectionProfile(name="test1", host="example.com")
    store.upsert(p1)

    assert store.delete("test1") is True
    assert store.load() == []
    assert store.delete("test1") is False

@patch("ftplib_gui.profiles._try_import_keyring")
def test_keyring_available(mock_keyring, store):
    mock_keyring.return_value = MagicMock()
    assert store.keyring_available() is True

    mock_keyring.return_value = None
    assert store.keyring_available() is False

@patch("ftplib_gui.profiles._try_import_keyring")
def test_read_write_password(mock_keyring, store):
    mock_k = MagicMock()
    mock_keyring.return_value = mock_k

    profile = ConnectionProfile(name="test", host="ex.com", username="user", password="pwd", save_password=True)

    # Write
    store.save([profile])
    mock_k.set_password.assert_called_once()

    # Read
    mock_k.get_password.return_value = "pwd"
    loaded = store.load()
    assert loaded[0].password == "pwd"

    # Delete
    profile.save_password = False
    store.save([profile])
    mock_k.delete_password.assert_called_once()
