"""Command-line entry point for ftplib_gui."""

from __future__ import annotations

import argparse

from ftplib_gui.__about__ import __description__, __version__
from ftplib_gui.app import main as app_main
from ftplib_gui.logging_utils import app_data_dir, log_file_path
from ftplib_gui.profiles import ProfileStore
from ftplib_gui.upgrade_integration import add_commands, run_command


def _add_gui_arguments(parser: argparse.ArgumentParser) -> None:
    """Attach the GUI launch options to a parser."""
    parser.add_argument("--host", help="Pre-fill the host name on launch")
    parser.add_argument("--port", type=int, help="Port (default: 21)")
    parser.add_argument("--user", help="Pre-fill the username")
    parser.add_argument(
        "--protocol",
        choices=["ftp", "ftps"],
        help="Pre-select the protocol",
    )
    passive_group = parser.add_mutually_exclusive_group()
    passive_group.add_argument(
        "--passive",
        dest="passive",
        action="store_true",
        default=None,
        help="Use PASV mode (default)",
    )
    passive_group.add_argument(
        "--active",
        dest="active",
        action="store_true",
        help="Use active (PORT) mode",
    )
    parser.add_argument("--local-dir", dest="local_dir", help="Initial local directory")
    parser.add_argument("--remote-dir", dest="remote_dir", help="Initial remote directory")
    parser.add_argument("--profile", help="Saved profile name to load on launch")
    parser.add_argument("--debug", action="store_true", help="Enable verbose logging")


def _print_paths(selection: str) -> None:
    """Print one or more filesystem paths used by the app."""
    paths = {
        "app-data": app_data_dir(),
        "profiles": app_data_dir() / "profiles.json",
        "log-file": log_file_path(),
    }
    if selection == "all":
        for name, path in paths.items():
            print(f"{name}: {path}")
        return
    print(f"{selection}: {paths[selection]}")


def _list_profiles() -> None:
    """Print saved connection profiles in a terminal-friendly format."""
    profiles = ProfileStore().load()
    if not profiles:
        print("No saved profiles.")
        return
    for profile in profiles:
        username = f"{profile.username}@" if profile.username else ""
        print(f"{profile.name}: {profile.protocol.upper()} {username}{profile.host}:{profile.port}")


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser used by :func:`main`."""
    parser = argparse.ArgumentParser(
        prog="ftplib_gui",
        description=__description__,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    _add_gui_arguments(parser)

    subparsers = parser.add_subparsers(dest="command")

    gui_parser = subparsers.add_parser("gui", help="Launch the desktop FTP/FTPS client")
    _add_gui_arguments(gui_parser)

    paths_parser = subparsers.add_parser("paths", help="Print app data, profile, and log file paths")
    paths_parser.add_argument(
        "selection",
        nargs="?",
        choices=["all", "app-data", "profiles", "log-file"],
        default="all",
        help="Which path to print (default: all)",
    )

    subparsers.add_parser("profiles", help="List saved connection profiles")
    add_commands(subparsers)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the ftplib_gui CLI and launch the GUI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if (result := run_command(args)) is not None:
        return result

    if args.command == "paths":
        _print_paths(args.selection)
        return 0

    if args.command == "profiles":
        _list_profiles()
        return 0

    app_main(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
