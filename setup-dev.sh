#!/usr/bin/env bash
# Development tools for ./run-tests.sh, in .venv. pip refuses any package that does not match the hashes
# in requirements-dev.txt, which is exported from uv.lock:
#   uv lock && uv export --frozen --no-emit-project --group dev --format requirements-txt -o requirements-dev.txt
set -euo pipefail
cd "$(dirname "$0")"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet --require-hashes -r requirements-dev.txt
