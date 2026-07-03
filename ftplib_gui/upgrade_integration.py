"""Helpers for embedding do_i_need_to_upgrade into ftplib_gui."""

from __future__ import annotations

import argparse
import sys
from typing import Any

try:
    from do_i_need_to_upgrade import add_check_command, add_upgrade_command, run_if_upgrade_command
    from do_i_need_to_upgrade.api import check_for_updates
    from do_i_need_to_upgrade.report import Report
    from do_i_need_to_upgrade.settings import Settings

    HAS_UPGRADE_SUPPORT = True
except ImportError:
    add_check_command = None
    add_upgrade_command = None
    run_if_upgrade_command = None
    check_for_updates = None
    Report = Any
    Settings = Any
    HAS_UPGRADE_SUPPORT = False

DIST_NAME = "ftplib_gui"
CHECK_UPDATES_COMMAND = "check-updates"
UPGRADE_COMMAND = "upgrade"


def settings() -> Settings:
    """Return ftplib_gui's embedded update-check settings."""
    return Settings(dist_name=DIST_NAME, position="start", notify="return-only")


def add_commands(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Register integrated do_i_need_to_upgrade subcommands."""
    if not HAS_UPGRADE_SUPPORT:
        return
    active_settings = settings()
    assert add_upgrade_command is not None
    assert add_check_command is not None
    add_upgrade_command(subparsers, DIST_NAME, command=UPGRADE_COMMAND, settings=active_settings)
    add_check_command(subparsers, DIST_NAME, command=CHECK_UPDATES_COMMAND, settings=active_settings)


def run_command(args: argparse.Namespace) -> int | None:
    """Dispatch integrated update-related subcommands."""
    if not HAS_UPGRADE_SUPPORT:
        return None
    assert run_if_upgrade_command is not None
    return run_if_upgrade_command(args)


def startup_report() -> Report | None:
    """Kick off the background refresh and return the current cache-backed report."""
    if not HAS_UPGRADE_SUPPORT:
        return None
    assert check_for_updates is not None
    report = check_for_updates(settings=settings())
    return report if not report.is_empty else None


def exit_report() -> Report | None:
    """Read the refreshed cache on exit without doing more network I/O."""
    if not HAS_UPGRADE_SUPPORT:
        return None
    assert check_for_updates is not None
    report = check_for_updates(settings=settings().replace(allow_network=False, notify="return-only"))
    return report if not report.is_empty else None


def render_notice(report: Report | None) -> str:
    """Render a user-facing update notice for stderr."""
    if report is None:
        return ""
    return report.render_text(stream=sys.stderr)


__all__ = [
    "CHECK_UPDATES_COMMAND",
    "DIST_NAME",
    "HAS_UPGRADE_SUPPORT",
    "UPGRADE_COMMAND",
    "add_commands",
    "exit_report",
    "render_notice",
    "run_command",
    "settings",
    "startup_report",
]
