from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from hypervisor.deployment_registry.health_uri import health_uri_for_port, port_from_http_uri
from hypervisor.deployment_registry.loader import load_deployment_registry
from hypervisor.deployment_registry.models import AgentDeployment, DeploymentDeclared
from hypervisor.deployment_registry.writer import save_deployment_registry, upsert_deployment


def card_uri_for_port(port: int) -> str:
    return f"http://localhost:{port}/.well-known/agent-card.json"


def deployment_with_port(deployment: AgentDeployment, port: int) -> AgentDeployment:
    health_uri = health_uri_for_port(port)
    card_uri = card_uri_for_port(port)
    declared = deployment.declared
    target_uri = declared.target_uri if declared else deployment.target_uri
    new_declared = DeploymentDeclared(
        target_uri=target_uri,
        preferred_port=port,
        health_uri=health_uri,
        card_uri=card_uri,
    )
    return replace(
        deployment,
        health_uri=health_uri,
        card_uri=card_uri,
        declared=new_declared,
    )


def sync_deployment_port(
    deployment_id: str,
    port: int,
    *,
    root: str | Path = ".",
) -> dict[str, object]:
    """Persist effective runtime port into the deployment registry."""
    repo = Path(root)
    registry = load_deployment_registry(repo)
    deployment = registry.by_id(deployment_id)
    if deployment is None:
        raise LookupError(f"deployment not found: {deployment_id}")
    updated = deployment_with_port(deployment, port)
    upsert_deployment(registry, updated)
    save_deployment_registry(registry)
    return {
        "ok": True,
        "deployment_id": deployment_id,
        "port": port,
        "health_uri": updated.health_uri,
        "card_uri": updated.card_uri,
    }


def sync_deployment_health_uri(
    deployment_id: str,
    health_uri: str,
    *,
    root: str | Path = ".",
) -> dict[str, object]:
    port = port_from_http_uri(health_uri)
    if port is None:
        raise ValueError(f"cannot infer port from health URI: {health_uri}")
    return sync_deployment_port(deployment_id, port, root=root)
