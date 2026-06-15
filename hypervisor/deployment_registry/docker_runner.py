from __future__ import annotations

from typing import Any

from hypervisor.deployment_registry.models import AgentDeployment
from hypervisor.paths import find_repo_root
from uri3.docker.controller import control_docker
from uri3.resolvers.docker_resolver import parse_docker_uri
from uri3.scanner.docker_scanner import scan_docker
from uri3.scanner.http_scanner import health_scan_ok, scan_http


def docker_uri_for_deployment(deployment: AgentDeployment) -> str:
    parsed = parse_docker_uri(deployment.target_uri)
    return deployment.target_uri if parsed.kind == "stack" else f"docker://stack/{deployment.id.split('.', 1)[0]}"


def build_docker_deploy_plan(deployment: AgentDeployment, *, root=None) -> dict[str, Any]:
    repo = root or find_repo_root()
    generate_uri = f"docker://generate/{deployment.agent_ref.removeprefix('agent://')}?action=generate"
    generate_plan = control_docker(generate_uri, root=repo, payload={"dry_run": True})
    up_uri = deployment.target_uri if deployment.target_uri.startswith("docker://") else docker_uri_for_deployment(deployment)
    if "action=" not in up_uri:
        up_uri = f"{up_uri}?action=up"
    up_plan = control_docker(up_uri, root=repo, payload={"dry_run": True})
    return {
        "deployment_id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "target_uri": deployment.target_uri,
        "steps": [
            {"action": "generate", "uri": generate_uri, "plan": generate_plan},
            {"action": "up", "uri": up_uri, "plan": up_plan},
        ],
    }


def build_docker_control_plan(deployment: AgentDeployment, action: str, *, root=None) -> dict[str, Any]:
    base = deployment.target_uri.split("?", 1)[0]
    uri = f"{base}?action={action}&dry_run=1"
    return control_docker(uri, root=root or find_repo_root())


def apply_docker_deploy(deployment: AgentDeployment, *, root=None) -> dict[str, Any]:
    repo = root or find_repo_root()
    agent_id = deployment.agent_ref.removeprefix("agent://")
    generated = control_docker(f"docker://generate/{agent_id}?action=generate", root=repo)
    up_uri = deployment.target_uri if "action=" in deployment.target_uri else f"{deployment.target_uri}?action=up"
    started = control_docker(up_uri, root=repo)
    return {"generate": generated, "up": started, "ok": bool(started.get("ok"))}


def stop_docker_deployment(deployment: AgentDeployment, *, root=None, remove_volumes: bool = False) -> dict[str, Any]:
    uri = deployment.target_uri
    separator = "&" if "?" in uri else "?"
    down_uri = f"{uri}{separator}action=down"
    if remove_volumes:
        down_uri += "&remove_volumes=1"
    return control_docker(down_uri, root=root or find_repo_root())


def verify_docker_deployment(deployment: AgentDeployment, *, check_health: bool = True, root=None) -> dict[str, Any]:
    scan_uri = deployment.target_uri.split("?", 1)[0]
    docker_items = scan_docker(scan_uri)
    payload: dict[str, Any] = {
        "id": deployment.id,
        "docker_scan": [item.__dict__ for item in docker_items],
        "docker_ok": any(item.status in {"running", "stopped"} and item.kind == "compose_stack" for item in docker_items),
    }
    if check_health and deployment.health_uri:
        http_items = scan_http(deployment.health_uri)
        payload["health_scan"] = [item.__dict__ for item in http_items]
        payload["health_ok"] = health_scan_ok(http_items)
    else:
        payload["health_ok"] = None
    payload["verified"] = payload["docker_ok"] and (payload["health_ok"] is None or payload["health_ok"])
    return payload
