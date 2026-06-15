from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from hypervisor.deployment_registry.models import (
    AgentDeployment,
    DeploymentDeclared,
    DeploymentRegistry,
    DeploymentRuntimeView,
)


def default_registry_path(root: str | Path = ".") -> Path:
    return Path(root) / "deployments" / "agent_deployments.yaml"


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"deployments": []}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {"deployments": []}


def _port_from_uri(uri: str | None) -> int | None:
    if not uri:
        return None
    parsed = urlparse(uri)
    return parsed.port


def _parse_declared(item: dict[str, Any]) -> DeploymentDeclared:
    declared = dict(item.get("declared") or {})
    return DeploymentDeclared(
        target_uri=str(declared.get("target_uri") or item["target_uri"]),
        preferred_port=declared.get("preferred_port") or _port_from_uri(
            declared.get("health_uri") or item.get("health_uri")
        ),
        health_uri=declared.get("health_uri") or item.get("health_uri"),
        card_uri=declared.get("card_uri") or item.get("card_uri"),
    )


def _parse_runtime(item: dict[str, Any]) -> DeploymentRuntimeView | None:
    runtime = item.get("runtime")
    if not isinstance(runtime, dict):
        return None
    return DeploymentRuntimeView(
        effective_port=runtime.get("effective_port"),
        effective_health_uri=runtime.get("effective_health_uri"),
        pid=runtime.get("pid"),
        lifecycle_status=str(runtime.get("lifecycle_status") or "unknown"),
        health_status=str(runtime.get("health_status") or "unknown"),
        deployment_status=str(runtime.get("deployment_status") or "unknown"),
        service_result_status=str(runtime.get("service_result_status") or "unknown"),
    )


def _parse_deployment(item: dict[str, Any]) -> AgentDeployment:
    declared = _parse_declared(item)
    return AgentDeployment(
        id=str(item["id"]),
        agent_ref=str(item["agent_ref"]),
        target_uri=str(item["target_uri"]),
        card_uri=item.get("card_uri") or declared.card_uri,
        health_uri=item.get("health_uri") or declared.health_uri,
        status=str(item.get("status", "generated")),
        env=dict(item.get("env") or {}),
        metadata=dict(item.get("metadata") or {}),
        declared=declared,
        runtime=_parse_runtime(item),
    )


def load_deployment_registry(
    root: str | Path = ".",
    *,
    path: str | Path | None = None,
) -> DeploymentRegistry:
    root = Path(root)
    registry_path = Path(path) if path else default_registry_path(root)
    raw = _read_yaml(registry_path)
    deployments = [_parse_deployment(item) for item in raw.get("deployments") or [] if isinstance(item, dict)]
    return DeploymentRegistry(root=root, path=registry_path, deployments=deployments, raw=raw)
