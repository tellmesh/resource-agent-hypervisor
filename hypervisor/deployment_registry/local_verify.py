from __future__ import annotations

from typing import Any

from hypervisor.deployment_registry.models import AgentDeployment
from hypervisor.deployment_registry.runtime_state import load_runtime_state, runtime_status
from hypervisor.paths import find_repo_root
from uri3.scanner.http_scanner import health_scan_ok, scan_http


def verify_local_deployment(
    deployment: AgentDeployment,
    *,
    root=None,
    check_health: bool = True,
) -> dict[str, Any]:
    repo = root or find_repo_root()
    runtime = runtime_status(deployment.id, repo)
    state = load_runtime_state(deployment.id, repo)
    payload: dict[str, Any] = {
        "id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "target_uri": deployment.target_uri,
        "runtime_status": runtime,
        "local_target_ok": deployment.target_uri.startswith("local://"),
    }
    if state:
        payload["runtime_state"] = state
    if check_health and deployment.health_uri:
        http_items = scan_http(deployment.health_uri)
        payload["health_scan"] = [item.__dict__ for item in http_items]
        payload["health_ok"] = health_scan_ok(http_items)
    else:
        payload["health_scan"] = []
        payload["health_ok"] = None
    payload["verified"] = payload["local_target_ok"] and (
        payload["health_ok"] is None or payload["health_ok"]
    )
    return payload
