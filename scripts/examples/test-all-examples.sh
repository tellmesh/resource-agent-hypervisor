#!/usr/bin/env bash
# Run all hypervisor examples via shared catalog runner (tests/examples/shell_runner.py).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$ROOT/tests/examples/shell_runner.py" --root "$ROOT"
