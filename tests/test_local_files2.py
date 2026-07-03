from __future__ import annotations

import pathlib
from unittest.mock import patch

import pytest

from ftplib_gui.local_files import LocalFileService


def test_home():
    service = LocalFileService()
    with patch("pathlib.Path.home", return_value=pathlib.Path("/home/user")):
        assert service.home() == pathlib.Path("/home/user")


def test_listdir(tmp_path):
    service = LocalFileService()
    (tmp_path / "dir").mkdir()
    (tmp_path / "file.txt").write_text("hello")
    (tmp_path / ".hidden").write_text("secret")

    # Non-hidden
    entries = service.listdir(tmp_path, show_hidden=False)
    # dir comes before file.txt due to sorting
    assert len(entries) == 2
    assert entries[0].name == "dir"
    assert entries[0].is_dir is True
    assert entries[1].name == "file.txt"
    assert entries[1].is_dir is False
    assert entries[1].size == 5

    # Hidden
    entries_all = service.listdir(tmp_path, show_hidden=True)
    assert len(entries_all) == 3
    assert any(e.name == ".hidden" for e in entries_all)


def test_listdir_os_error(tmp_path):
    service = LocalFileService()
    (tmp_path / "broken").mkdir()

    class BrokenDirEntry:
        name = "broken"
        path = str(tmp_path / "broken")

        def stat(self):
            raise OSError("Permission denied")

    class FakeScandir:
        def __enter__(self):
            return iter([BrokenDirEntry()])

        def __exit__(self, exc_type, exc, tb):
            return False

    with patch("os.scandir", return_value=FakeScandir()):
        entries = service.listdir(tmp_path)
        assert not entries


def test_mkdir(tmp_path):
    service = LocalFileService()
    new_dir = tmp_path / "new_dir"
    service.mkdir(new_dir)
    assert new_dir.is_dir()

    # Fail if exists
    with pytest.raises(FileExistsError):
        service.mkdir(new_dir)


def test_delete_file(tmp_path):
    service = LocalFileService()
    f = tmp_path / "test.txt"
    f.write_text("data")
    service.delete(f)
    assert not f.exists()


def test_delete_dir(tmp_path):
    service = LocalFileService()
    d = tmp_path / "subdir"
    d.mkdir()
    (d / "inner.txt").write_text("inner")
    service.delete(d)
    assert not d.exists()


def test_rename(tmp_path):
    service = LocalFileService()
    f = tmp_path / "old.txt"
    f.write_text("data")
    new_f = tmp_path / "new.txt"
    service.rename(f, new_f)
    assert not f.exists()
    assert new_f.exists()


def test_iter_files(tmp_path):
    service = LocalFileService()
    f1 = tmp_path / "f1.txt"
    f1.write_text("1")
    d1 = tmp_path / "d1"
    d1.mkdir()
    f2 = tmp_path / "f2.txt"
    f2.write_text("2")

    paths = [f1, d1, f2]
    files = list(service.iter_files(paths))
    assert len(files) == 2
    assert f1 in files
    assert f2 in files
    assert d1 not in files
