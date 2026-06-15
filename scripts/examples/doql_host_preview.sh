#!/usr/bin/env bash
# Refresh DOQL environment registry with live host probe (cron, ports, examples).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

export ENV2LLM_HOST_PROBE=1

if [[ -d "${HOME}/github/semcod/env2llm/src/env2llm" ]]; then
  ENVCMD=(python3 -m env2llm.cli)
  export PYTHONPATH="${HOME}/github/semcod/env2llm/src${PYTHONPATH:+:$PYTHONPATH}"
elif command -v env2llm >/dev/null 2>&1; then
  ENVCMD=(env2llm)
elif python3 -c "import env2llm" 2>/dev/null; then
  ENVCMD=(python3 -m env2llm.cli)
else
  # Editable install from semcod/env2llm when developing locally.
  ENVCMD=(python3 -m env2llm.cli)
  export PYTHONPATH="${HOME}/github/semcod/env2llm/src${PYTHONPATH:+:$PYTHONPATH}"
fi

REGISTRY="$("${ENVCMD[@]}" "$ROOT" --probe-host --format json 2>/dev/null | tail -1)"
if [[ ! -f "$REGISTRY" ]]; then
  REGISTRY="$ROOT/.nlp2dsl/registry/environment.doql.less"
fi

echo "DOQL registry: $REGISTRY"
echo

if [[ -f "$ROOT/.nlp2dsl/registry/environment.doql.less" ]]; then
  grep -E "^(host |host_cron|host_endpoint|host_port|host_process|host_container|host_agent|schedules|cron_taskinity|capabilities_)" \
    "$ROOT/.nlp2dsl/registry/environment.doql.less" 2>/dev/null | head -60 || true
fi

echo
echo "JSON host slice:"
python3 - <<'PY' "$ROOT/.nlp2dsl/registry/environment.json" 2>/dev/null || true
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file():
    p = Path(sys.argv[1]).with_suffix(".json")
    alt = Path(sys.argv[1]).parent / "environment.json"
    p = alt if alt.is_file() else p
if not p.is_file():
    print("(no environment.json — use env2llm -f json)")
    raise SystemExit(0)
data = json.loads(p.read_text(encoding="utf-8"))
host = data.get("host") or {}
print(json.dumps({
    "host": host,
    "schedules": data.get("schedules") or [],
    "capabilities": [c for c in (data.get("capabilities") or []) if str(c).startswith("host_")],
    "counts": {
        "endpoints": len(host.get("endpoints") or []),
        "ports": len(host.get("ports") or []),
        "processes": len(host.get("processes") or []),
        "containers": len(host.get("containers") or []),
        "agents": len(host.get("agents") or []),
    },
    "agents": [
        {
            "id": item.get("id"),
            "ok": item.get("ok"),
            "runtime_status": item.get("runtime_status"),
            "effective_health_uri": item.get("effective_health_uri"),
            "recommended_action": item.get("recommended_action"),
        }
        for item in (host.get("agents") or [])
    ],
    "data_host": {k: v for k, v in (data.get("data") or {}).items() if k.startswith("host.")},
}, indent=2, ensure_ascii=False))
PY
