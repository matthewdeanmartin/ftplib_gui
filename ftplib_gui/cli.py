"""Command-line entry point for ftplib_gui."""

from __future__ import annotations

import argparse

from ftplib_gui.__about__ import __version__
from ftplib_gui.app import main as app_main


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser used by :func:`main`."""
    parser = argparse.ArgumentParser(
        prog="ftplib_gui",
        description="A GUI front-end for Python's ftplib",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
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
    return parser


def main(argv: list[str] | None = None) -> None:
    """Run the ftplib_gui CLI and launch the GUI."""
    parser = build_parser()
    args = parser.parse_args(argv)

    app_main(args)


if __name__ == "__main__":
    main()
