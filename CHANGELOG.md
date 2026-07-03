# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Wired `do_i_need_to_upgrade` into `ftplib_gui` startup and shutdown so update notices appear in the terminal
- Added integrated `ftplib_gui upgrade` and `ftplib_gui check-updates` subcommands

### Changed

- Moved `do_i_need_to_upgrade` support behind the optional `ftplib_gui[all]` extra so the base install stays dependency-light
- Made update integration quietly no-op when the extra is not installed

## [0.1.0] - 2026-05-02

### Added

- Desktop GUI for FTP and FTPS connections built on Python's standard-library `ftplib`
- Side-by-side local and remote file browsers with refresh, rename, delete, and mkdir actions
- Queued uploads and downloads with progress reporting and transfer logging
- Saved connection profiles with optional keyring-backed password storage
- Optional embedded FTP server support for local testing and demos
- Basic command-line helpers for launching the GUI and inspecting local app state
- Cross-platform support

[0.1.0]: https://github.com/matthewdeanmartin/ftplib_gui/releases/tag/v0.1.0
