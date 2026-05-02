"""Tests for the local filesystem service."""

from __future__ import annotations

import pathlib

from ftplib_gui.local_files import LocalFileService


def test_listdir_sorts_dirs_first(tmp_path: pathlib.Path) -> None:
    (tmp_path / "b_file.txt").write_text("x")
    (tmp_path / "a_file.txt").write_text("x")
    (tmp_path / "z_dir").mkdir()
    (tmp_path / "m_dir").mkdir()

    entries = LocalFileService().listdir(tmp_path)
    names = [e.name for e in entries]
    assert names == ["m_dir", "z_dir", "a_file.txt", "b_file.txt"]
    assert entries[0].is_dir
    assert not entries[2].is_dir


def test_listdir_show_hidden_toggle(tmp_path: pathlib.Path) -> None:
    (tmp_path / ".secret").write_text("x")
    (tmp_path / "visible").write_text("x")
    svc = LocalFileService()
    assert {e.name for e in svc.listdir(tmp_path)} == {"visible"}
    assert {e.name for e in svc.listdir(tmp_path, show_hidden=True)} == {".secret", "visible"}


def test_mkdir_delete_rename(tmp_path: pathlib.Path) -> None:
    svc = LocalFileService()

    new_dir = tmp_path / "new"
    svc.mkdir(new_dir)
    assert new_dir.is_dir()

    renamed = tmp_path / "renamed"
    svc.rename(new_dir, renamed)
    assert renamed.is_dir()
    assert not new_dir.exists()

    svc.delete(renamed)
    assert not renamed.exists()


def test_delete_recursively_removes_directory(tmp_path: pathlib.Path) -> None:
    svc = LocalFileService()
    (tmp_path / "d").mkdir()
    (tmp_path / "d" / "f.txt").write_text("hi")
    svc.delete(tmp_path / "d")
    assert not (tmp_path / "d").exists()
