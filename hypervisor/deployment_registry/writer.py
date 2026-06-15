from __future__ import annotations

from pathlib import Path

import yaml

from hypervisor.deployment_registry.loader import default_registry_path, load_deployment_registry
from hypervisor.deployment_registry.models import AgentDeployment, DeploymentRegistry


def save_deployment_registry(registry: DeploymentRegistry) -> Path:
    payload = {
        "deployments": [item.to_dict() for item in registry.deployments],
    }
    registry.path.parent.mkdir(parents=True, exist_ok=True)
    registry.path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    registry.raw = payload
    return registry.path


def upsert_deployment(
    registry: DeploymentRegistry,
    deployment: AgentDeployment,
) -> DeploymentRegistry:
    updated = [item for item in registry.deployments if item.id != deployment.id]
    updated.append(deployment)
    updated.sort(key=lambda item: item.id)
    registry.deployments = updated
    return registry


def remove_deployment(registry: DeploymentRegistry, deployment_id: str) -> DeploymentRegistry:
    registry.deployments = [item for item in registry.deployments if item.id != deployment_id]
    return registry


def write_deployment_registry(
    deployments: list[AgentDeployment],
    *,
    root: str | Path = ".",
    path: str | Path | None = None,
) -> Path:
    registry = load_deployment_registry(root, path=path)
    registry.deployments = deployments
    return save_deployment_registry(registry)
