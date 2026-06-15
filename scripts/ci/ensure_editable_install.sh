#!/usr/bin/env bash
# Ensure monorepo editable install when examples run outside a prepared venv.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../hypervisor_root.sh
source "$SCRIPT_DIR/../hypervisor_root.sh"
ROOT="$HYPERVISOR_ROOT"

if [[ -z "${PY:-}" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
  elif command -v python >/dev/null 2>&1; then
    PY="python"
  else
    PY="python3"
  fi
fi

if "$PY" -c "import touri, uri2run, uri3, uri2ops, uri2flow, uri2verify, uri2pact, urigen, urish, hypervisor, generator" 2>/dev/null; then
  exit 0
fi

echo "Installing workspace packages (editable)…" >&2
"$PY" -m pip install -q --no-deps -e "$ROOT"
