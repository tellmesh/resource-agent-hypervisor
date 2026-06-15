from __future__ import annotations

from typing import Any

from uri3.resolvers.ssh_resolver import parse_ssh_uri
from uri3.scanner.http_scanner import health_scan_ok, scan_http
from uri3.scanner.ssh_scanner import scan_ssh


def verify_remote_deployment(
    deployment,
    *,
    root=None,
    check_health: bool = True,
) -> dict[str, Any]:
    del root
    ssh_ref = parse_ssh_uri(deployment.target_uri)
    ssh_items = scan_ssh(deployment.target_uri)
    payload: dict[str, Any] = {
        "id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "target_uri": deployment.target_uri,
        "ssh_scan": [item.__dict__ for item in ssh_items],
        "ssh_ok": any(item.kind == "ssh_connectivity" and item.status == "reachable" for item in ssh_items),
        "remote_path_ok": any(item.kind == "remote_path" and item.status == "present" for item in ssh_items),
    }
    if check_health and deployment.health_uri:
        http_items = scan_http(deployment.health_uri)
        payload["health_scan"] = [item.__dict__ for item in http_items]
        payload["health_ok"] = health_scan_ok(http_items)
    else:
        payload["health_scan"] = []
        payload["health_ok"] = None
    payload["verified"] = payload["ssh_ok"] and payload["remote_path_ok"] and (
        payload["health_ok"] is None or payload["health_ok"]
    )
    payload["ssh_host"] = ssh_ref["host"]
    return payload
