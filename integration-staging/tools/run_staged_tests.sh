#!/usr/bin/env bash
# Run the staged Phase A test suite from the staging root (plan section 14).
#
# Only staged tests under integration-staging/tests run here; the original test
# suite is never collected or executed. No package is installed into the shared
# venv. Bytecode, pytest temp and pytest cache all land inside staging.
set -u

STAGING="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(dirname "$STAGING")"
PY="$WORKSPACE/examdata/.venv/Scripts/python.exe"

mkdir -p "$STAGING/runtime/pytest-temp" "$STAGING/runtime/pytest-cache" \
         "$STAGING/runtime/tmp" "$STAGING/runtime/home"

cd "$STAGING" || exit 1
export PYTHONDONTWRITEBYTECODE=1
export PYTHONIOENCODING=utf-8
exec "$PY" -m pytest -c pytest.ini tests \
  --basetemp runtime/pytest-temp \
  -o cache_dir=runtime/pytest-cache "$@"
