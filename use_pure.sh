#!/usr/bin/env bash
# Re-apply the pure_python_with_quality_gates cookiecutter template to this project.
# Generates into a temp dir and copies the result over the current directory,
# overwriting template-managed files but preserving .git and anything not in the template.
set -euo pipefail

TEMPLATE="${TEMPLATE:-C:/github/pure_python_with_quality_gates}"
PROJECT_SLUG="${PROJECT_SLUG:-ftplib_gui}"
PROJECT_NAME="${PROJECT_NAME:-FTPLib GUI}"
PROJECT_DESCRIPTION="${PROJECT_DESCRIPTION:-A GUI front-end for Python's ftplib}"
GITHUB_REPO="${GITHUB_REPO:-$PROJECT_SLUG}"
READTHEDOCS_SLUG="${READTHEDOCS_SLUG:-$PROJECT_SLUG}"

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

cookiecutter "$TEMPLATE" \
  --no-input \
  --output-dir "$TMPDIR" \
  project_slug="$PROJECT_SLUG" \
  project_name="$PROJECT_NAME" \
  project_description="$PROJECT_DESCRIPTION" \
  github_repo="$GITHUB_REPO" \
  readthedocs_slug="$READTHEDOCS_SLUG"

cp -rf "$TMPDIR/$PROJECT_SLUG/." "$(dirname "$0")/"

echo "Template applied to $(dirname "$0")"
