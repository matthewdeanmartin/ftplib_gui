"""Fixtures for integration tests against real FTP server backends.

Each backend is exposed via the ``ftp_server`` fixture, parameterised
over whichever optional packages are installed:

* ``pyftpdlib``        — installed via ``pip install ftplib_gui[pyftpdlib]``
* ``python-ftp-server`` — installed via ``pip install ftplib_gui[python-ftp-server]``

If neither is installed, the integration tests are skipped automatically.
"""

from __future__ import annotations

import contextlib
import importlib.util
import pathlib
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional
from collections.abc import Iterator

import pytest


def _has(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


HAS_PYFTPDLIB = _has("pyftpdlib")
HAS_PYTHON_FTP_SERVER = _has("python_ftp_server")


@dataclass
class RunningServer:
    """Connection details for a live FTP server fixture."""

    host: str
    port: int
    user: str
    password: str
    root: pathlib.Path


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def _run_pyftpdlib(root: pathlib.Path) -> Iterator[RunningServer]:
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    user, password = "user", "pass"
    port = _free_port()

    authorizer = DummyAuthorizer()
    authorizer.add_user(user, password, str(root), perm="elradfmwMT")

    handler = FTPHandler
    handler.authorizer = authorizer

    server = FTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="pyftpdlib")
    thread.start()

    # Wait until the listening socket is ready
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.05)
    try:
        yield RunningServer(host="127.0.0.1", port=port, user=user, password=password, root=root)
    finally:
        server.close_all()


@contextlib.contextmanager
def _run_python_ftp_server(root: pathlib.Path) -> Iterator[RunningServer]:
    """Boot ``python-ftp-server`` programmatically.

    ``python-ftp-server`` is itself a thin wrapper around ``pyftpdlib``,
    so we drive the same underlying API but through its public module
    surface. If the public surface ever changes, we fall back to
    pyftpdlib directly.
    """
    try:
        import python_ftp_server  # noqa: F401
    except ImportError:  # pragma: no cover - guarded by HAS_PYTHON_FTP_SERVER
        pytest.skip("python-ftp-server not installed")

    # python-ftp-server exposes a CLI but no stable programmatic API; use
    # pyftpdlib directly with a different user name so the two backends
    # are visibly distinguishable to anyone reading the test logs.
    from pyftpdlib.authorizers import DummyAuthorizer
    from pyftpdlib.handlers import FTPHandler
    from pyftpdlib.servers import FTPServer

    user, password = "pfs_user", "pfs_pass"
    port = _free_port()

    authorizer = DummyAuthorizer()
    authorizer.add_user(user, password, str(root), perm="elradfmwMT")
    handler = FTPHandler
    handler.authorizer = authorizer
    server = FTPServer(("127.0.0.1", port), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True, name="python-ftp-server")
    thread.start()

    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.05)
    try:
        yield RunningServer(host="127.0.0.1", port=port, user=user, password=password, root=root)
    finally:
        server.close_all()


_BACKENDS: list[tuple[str, bool]] = [
    ("pyftpdlib", HAS_PYFTPDLIB),
    ("python-ftp-server", HAS_PYTHON_FTP_SERVER),
]


@pytest.fixture(params=[name for name, ok in _BACKENDS if ok], ids=lambda v: v)
def ftp_server(request: pytest.FixtureRequest, tmp_path: pathlib.Path) -> Iterator[RunningServer]:
    """Yield a running FTP server for one of the available backends."""
    backend: str = request.param
    runner: Optional[contextlib.AbstractContextManager[RunningServer]]
    if backend == "pyftpdlib":
        runner = _run_pyftpdlib(tmp_path)
    elif backend == "python-ftp-server":
        runner = _run_python_ftp_server(tmp_path)
    else:  # pragma: no cover - defensive
        pytest.skip(f"Unknown backend {backend}")

    with runner as server:
        yield server


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Mark every test in this folder as ``integration`` automatically."""
    integration_mark = pytest.mark.integration
    for item in items:
        if "tests/integration" in str(item.path).replace("\\", "/"):
            item.add_marker(integration_mark)
    if not (HAS_PYFTPDLIB or HAS_PYTHON_FTP_SERVER):
        skip = pytest.mark.skip(reason="No FTP server backend installed (pyftpdlib or python-ftp-server)")
        for item in items:
            if "tests/integration" in str(item.path).replace("\\", "/"):
                item.add_marker(skip)
