#!/usr/bin/env bash
# Architecture gate: boundary tests + uri3 doctor governance checks.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../hypervisor_root.sh
source "$SCRIPT_DIR/../hypervisor_root.sh"
ROOT="$HYPERVISOR_ROOT"
cd "$ROOT"

PY="${PY:-python}"
if [ -x "${ROOT}/.venv/bin/python" ]; then
  PY="${ROOT}/.venv/bin/python"
fi
TELLMESH_ROOT="$(cd "$ROOT/.." && pwd)"
PACKAGE_PATHS=(
  "$TELLMESH_ROOT/hypervisor"
  "$TELLMESH_ROOT/uri3"
  "$TELLMESH_ROOT/nl2uri"
  "$TELLMESH_ROOT/uri2flow"
  "$TELLMESH_ROOT/uri2ops"
  "$TELLMESH_ROOT/touri"
  "$TELLMESH_ROOT/uri2voice"
  "$TELLMESH_ROOT/uri2pact"
  "$TELLMESH_ROOT/uri2run"
  "$TELLMESH_ROOT/uri2verify"
  "$TELLMESH_ROOT/urigen"
  "$TELLMESH_ROOT/urish"
  "$TELLMESH_ROOT/resource-agent-hypervisor"
  "$TELLMESH_ROOT/resource-agent-factory"
  "$TELLMESH_ROOT/hypervisor-dashboard"
)
PACKAGE_PYTHONPATH="$(IFS=:; echo "${PACKAGE_PATHS[*]}"):${ROOT}/examples/21_touri_voice"
export PYTHONPATH="${PACKAGE_PYTHONPATH}${PYTHONPATH:+:${PYTHONPATH}}"

if [ -x "${ROOT}/.venv/bin/pytest" ]; then
  PYTEST="${ROOT}/.venv/bin/pytest"
  URI3="${ROOT}/.venv/bin/uri3"
else
  PYTEST="pytest"
  URI3="uri3"
fi

echo "== architecture tests =="
"$PYTEST" tests/architecture -q

echo "== uri3 doctor =="
export DOCTOR_JSON="$("$URI3" doctor --json)"
echo "$DOCTOR_JSON"
"$PY" <<'PY'
import json
import os
import sys

payload = json.loads(os.environ["DOCTOR_JSON"])
checks = payload.get("checks") or []
failed = [item for item in checks if not item.get("ok")]
if payload.get("ok"):
    print(f"uri3 doctor ok ({len(checks)} checks)")
    sys.exit(0)
print("uri3 doctor FAILED")
for item in failed:
    detail = item.get("violation_count") or item.get("failures") or item.get("errors") or item.get("mismatches")
    print(f"  - {item.get('id')}: {detail}")
sys.exit(1)
PY

echo "== artifact schemas =="
"$PY" -m hypervisor.cli artifacts schemas

echo "== artifact lifecycle coverage =="
"$PY" -m hypervisor.cli artifacts lifecycle --report-only --sample-limit 20

echo "architecture gate: ok"
