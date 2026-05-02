#!/usr/bin/env bash
set -euo pipefail
source ./.bitrab-ci-scripts/setup.sh
uv run isort --check-only ftplib_gui tests
uv run black --check ftplib_gui tests
uv run ruff check --quiet ftplib_gui tests
uv run pylint --score=n --reports=n --rcfile=.pylintrc ftplib_gui
uv run pylint --score=n --reports=n --rcfile=.pylintrc_tests tests
