#!/usr/bin/env bash
# Smoke test: exercises the CLI arg parser and verifies basic invocations exit cleanly.
# Counts successes and failures; exits non-zero if any check failed.
# Source an already-active venv before running, or call via `uv run bash scripts/basic_checks.sh`.

set -ou pipefail

PASS=0
FAIL=0
CLI_PYTHON="${PYTHON:-python}"

run_cli() {
    "$CLI_PYTHON" -m ftplib_gui "$@"
}

check() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "  PASS: $desc"
        ((PASS++))
    else
        echo "  FAIL: $desc  (cmd: $*)"
        ((FAIL++))
    fi
}

check_fails() {
    local desc="$1"
    shift
    if "$@" > /dev/null 2>&1; then
        echo "  FAIL: $desc  (expected non-zero exit, got 0)"
        ((FAIL++))
    else
        echo "  PASS: $desc"
        ((PASS++))
    fi
}

echo "=== ftplib_gui basic_checks ==="
echo ""
echo "using: ${CLI_PYTHON} -m ftplib_gui"
echo ""

echo "--- global flags ---"
check "ftplib_gui --help"    run_cli --help
check "ftplib_gui --version" run_cli --version

echo "--- subcommands ---"
check "ftplib_gui gui --help"      run_cli gui --help
check "ftplib_gui paths --help"    run_cli paths --help
check "ftplib_gui profiles --help" run_cli profiles --help
check "ftplib_gui paths"           run_cli paths
check "ftplib_gui profiles"        run_cli profiles

echo ""
echo "=== Results: ${PASS} passed, ${FAIL} failed ==="

if [ "$FAIL" -gt 0 ]; then
    exit 1
fi
