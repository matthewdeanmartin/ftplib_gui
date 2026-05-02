# FTPLib GUI

<!-- TODO (generated from template — delete this block once done)
  - [ ] Register project on Read the Docs and point it at mkdocs.yml
  - [ ] Set up PyPI OIDC trusted publishing (no token needed) for publish_to_pypi.yml
-->

[![PyPI version](https://badge.fury.io/py/ftplib_gui.svg)](https://badge.fury.io/py/ftplib_gui)
[![Build and Test](https://github.com/matthewdeanmartin/ftplib_gui/actions/workflows/build.yml/badge.svg)](https://github.com/matthewdeanmartin/ftplib_gui/actions/workflows/build.yml)

FTPLib GUI is a desktop FTP and FTPS client built on Python's standard-library `ftplib`, with a Tkinter interface for browsing local and remote files, queuing uploads and downloads, saving reusable connection profiles, and launching an optional embedded test server while you work.

## Installation

```bash
pipx install ftplib_gui
```

Or with pip:

```bash
pip install ftplib_gui
```

## Usage

```bash
ftplib_gui --help
ftplib_gui gui --host ftp.example.com --user alice
ftplib_gui paths
ftplib_gui profiles
```

## Contributing

See [CONTRIBUTING.md](docs/extending/CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE).

## Changelog

See [CHANGELOG.md](CHANGELOG.md).
