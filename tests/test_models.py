"""Tests for the dataclass models."""

from ftplib_gui.models import ConnectionProfile


def test_connection_profile_to_dict_excludes_password() -> None:
    profile = ConnectionProfile(
        name="example",
        host="ftp.example.com",
        username="alice",
        password="hunter2",
    )
    data = profile.to_dict()
    assert "password" not in data
    assert data["name"] == "example"
    assert data["username"] == "alice"


def test_connection_profile_roundtrip() -> None:
    profile = ConnectionProfile(
        name="ex",
        host="ftp",
        port=2121,
        protocol="ftps",
        username="u",
        anonymous=False,
        passive=False,
        verify_tls=False,
    )
    restored = ConnectionProfile.from_dict(profile.to_dict())
    assert restored.name == profile.name
    assert restored.host == profile.host
    assert restored.port == profile.port
    assert restored.protocol == profile.protocol
    assert restored.username == profile.username
    assert restored.passive == profile.passive
    assert restored.verify_tls == profile.verify_tls
    assert restored.password == ""  # never persisted in dict
