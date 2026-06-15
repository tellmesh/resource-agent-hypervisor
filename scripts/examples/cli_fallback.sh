#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../hypervisor_root.sh
source "$SCRIPT_DIR/../hypervisor_root.sh"
ROOT="$HYPERVISOR_ROOT"
TELLMESH_ROOT="$(cd "$ROOT/../../tellmesh" && pwd)"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
for pkg in uri3 nl2uri uri2flow uri2ops touri uri2voice uri2pact uri2run uri2verify urigen urish resource-agent-hypervisor resource-agent-factory hypervisor-dashboard; do
  if [[ -d "$TELLMESH_ROOT/$pkg" ]]; then
    export PYTHONPATH="$TELLMESH_ROOT/$pkg${PYTHONPATH:+:$PYTHONPATH}"
  fi
done
if [[ -d "$ROOT/.venv/bin" ]]; then
  export PATH="$ROOT/.venv/bin${PATH:+:$PATH}"
fi

run_cli() {
  local name="$1"
  shift

  if command -v "$name" >/dev/null 2>&1; then
    "$name" "$@"
    return $?
  fi

  case "$name" in
    uri3) python -m uri3.cli "$@" ;;
    uri2ops) python -m uri2ops.cli "$@" ;;
    uri2flow) python -m uri2flow.cli "$@" ;;
    uri2run) python -m uri2run.cli "$@" ;;
    uri2verify) python -m uri2verify.cli "$@" ;;
    urigen) python -m urigen.cli "$@" ;;
    touri) python -m touri.cli "$@" ;;
    nl2uri) python -m nl2uri.cli "$@" ;;
    nl2a) python -m nl2a.cli "$@" ;;
    hypervisor) python -m hypervisor.cli "$@" ;;
    uri|urish|taskinity) python -m urish.cli "$@" ;;
    *) echo "unknown cli: $name" >&2; return 127 ;;
  esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  if [[ $# -lt 1 ]]; then
    echo "usage: $0 <cli-name> [args...]" >&2
    exit 2
  fi
  run_cli "$@"
fi
