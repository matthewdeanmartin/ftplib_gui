"""Smoke tests for the CLI entry point."""

import ftplib_gui
from ftplib_gui.__about__ import __version__


def test_import() -> None:
    """Package can be imported."""
    assert ftplib_gui.__version__ == __version__


def test_version() -> None:
    """Package exposes a version string."""
    assert isinstance(__version__, str)
    assert __version__
