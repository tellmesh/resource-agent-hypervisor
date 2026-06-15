from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from dataclasses import replace

from hypervisor.deployment_registry.loader import default_registry_path, load_deployment_registry
from hypervisor.deployment_registry.models import AgentDeployment, DeploymentDeclared, DeploymentRegistry
from hypervisor.deployment_registry.writer import save_deployment_registry, upsert_deployment

# Domain-specific ports moved to domains/* or per-agent config (P1 domain_vocabulary cleanup).
# Generic infer falls back to 8101 or health_uri port.
DEFAULT_AGENT_PORTS: dict[str, int] = {}


def infer_port(deployment: AgentDeployment) -> int:
    health_uri = deployment.health_uri
    if health_uri:
        parsed = urlparse(health_uri)
        if parsed.port:
            return parsed.port
    agent_id = deployment.agent_ref.removeprefix("agent://")
    return DEFAULT_AGENT_PORTS.get(agent_id, 8101)


def deployment_id_for_agent(agent_id: str, *, suffix: str = "local") -> str:
    return f"{agent_id}.{suffix}"


def infer_health_uri(target_uri: str, agent_id: str) -> str | None:
    parsed = urlparse(target_uri)
    if parsed.scheme in {"http", "https"}:
        base = target_uri.rstrip("/")
        return f"{base}/health"
    if parsed.scheme in {"local", "docker"}:
        port = DEFAULT_AGENT_PORTS.get(agent_id, 8101)
        return f"http://localhost:{port}/health"
    return None


def infer_card_uri(agent: dict[str, Any], agent_id: str, *, target_uri: str | None = None) -> str | None:
    if target_uri and str(target_uri).startswith("local://"):
        port = DEFAULT_AGENT_PORTS.get(agent_id, 8101)
        return f"http://localhost:{port}/.well-known/agent-card.json"
    card_uri = agent.get("card_uri")
    if isinstance(card_uri, str) and card_uri.startswith("http"):
        return card_uri
    port = DEFAULT_AGENT_PORTS.get(agent_id)
    if port:
        return f"http://localhost:{port}/.well-known/agent-card.json"
    return card_uri if isinstance(card_uri, str) else None


def deployment_from_uri_tree(tree: dict[str, Any]) -> AgentDeployment | None:
    deployment_block = tree.get("deployment") or {}
    default = deployment_block.get("default") if isinstance(deployment_block, dict) else None
    if not isinstance(default, dict) or not default.get("uri"):
        return None

    agent = tree.get("agent") or {}
    agent_id = str(agent.get("id") or "unknown-agent")
    agent_ref = str(agent.get("uri") or f"agent://{agent_id}")
    target_uri = str(default["uri"])
    health_uri = infer_health_uri(target_uri, agent_id)
    card_uri = infer_card_uri(agent, agent_id, target_uri=target_uri)
    declared = None
    if str(target_uri).startswith("local://") and health_uri and card_uri:
        port = urlparse(health_uri).port or DEFAULT_AGENT_PORTS.get(agent_id, 8101)
        declared = DeploymentDeclared(
            target_uri=target_uri,
            preferred_port=port,
            health_uri=health_uri,
            card_uri=card_uri,
        )

    return AgentDeployment(
        id=deployment_id_for_agent(agent_id),
        agent_ref=agent_ref,
        target_uri=target_uri,
        card_uri=card_uri,
        health_uri=health_uri,
        declared=declared,
        status="generated",
        metadata={"source": "uri_tree", "domain_id": tree.get("domain", {}).get("id")},
    )


def _merge_uri_tree_deployment(existing: AgentDeployment, incoming: AgentDeployment) -> AgentDeployment:
    metadata = dict(existing.metadata or {})
    metadata.update(incoming.metadata or {})
    if existing.metadata and existing.metadata.get("contract"):
        metadata["contract"] = existing.metadata["contract"]

    health_uri = incoming.health_uri or existing.health_uri
    card_uri = incoming.card_uri or existing.card_uri
    declared = incoming.declared or existing.declared
    if existing.health_uri and existing.health_uri.startswith("http"):
        health_uri = existing.health_uri
        card_uri = existing.card_uri or card_uri
        declared = existing.declared or declared

    return replace(
        incoming,
        health_uri=health_uri,
        card_uri=card_uri,
        declared=declared,
        metadata=metadata or None,
    )


def sync_from_uri_tree(
    tree: dict[str, Any],
    *,
    root: str | Path = ".",
    path: str | Path | None = None,
) -> AgentDeployment | None:
    deployment = deployment_from_uri_tree(tree)
    if deployment is None:
        return None
    registry = load_deployment_registry(root, path=path)
    existing = registry.by_id(deployment.id)
    if existing is not None:
        deployment = _merge_uri_tree_deployment(existing, deployment)
    upsert_deployment(registry, deployment)
    save_deployment_registry(registry)
    return deployment


def resolve_status(
    deployment: AgentDeployment,
    *,
    check_health: bool = False,
    timeout: float = 2.0,
) -> str:
    if not check_health:
        return deployment.status

    health_uri = deployment.health_uri
    if not health_uri or not health_uri.startswith("http"):
        return deployment.status if deployment.status in {"running", "stopped", "failed"} else "generated"

    try:
        response = httpx.get(health_uri, timeout=timeout)
        response.raise_for_status()
        payload = response.json() if "json" in response.headers.get("content-type", "") else {}
        if isinstance(payload, dict) and payload.get("ok") is True:
            return "running"
        return "deployed"
    except Exception:
        if deployment.status == "running":
            return "failed"
        return deployment.status if deployment.status != "running" else "stopped"


def list_deployments(registry: DeploymentRegistry | None = None, *, root: str | Path = ".") -> list[AgentDeployment]:
    registry = registry or load_deployment_registry(root)
    return list(registry.deployments)


def get_deployment_for_agent(
    agent_ref: str,
    *,
    registry: DeploymentRegistry | None = None,
    root: str | Path = ".",
) -> AgentDeployment | None:
    registry = registry or load_deployment_registry(root)
    matches = registry.by_agent_ref(agent_ref)
    return matches[0] if matches else None


def registry_summary(registry: DeploymentRegistry | None = None, *, root: str | Path = ".") -> list[dict[str, Any]]:
    registry = registry or load_deployment_registry(root)
    return [
        {
            "id": item.id,
            "agent_ref": item.agent_ref,
            "target_uri": item.target_uri,
            "target_scheme": urlparse(item.target_uri).scheme or None,
            "status": item.status,
            "card_uri": item.card_uri,
            "health_uri": item.health_uri,
        }
        for item in registry.deployments
    ]
