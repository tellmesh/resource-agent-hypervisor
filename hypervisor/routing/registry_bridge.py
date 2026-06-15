from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from hypervisor.deployment_registry.loader import load_deployment_registry


def load_runtime_registry(root: Path) -> dict[str, Any]:
    path = root / "config" / "runtime_environments.yaml"
    if not path.is_file():
        return {
            "defaults": {"execution_environment": "local"},
            "environments": {"local": {"label": "local"}},
            "operators": {},
        }
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def resolve_operator_by_scheme(
    scheme: str,
    *,
    root: Path,
) -> tuple[str | None, dict[str, Any]]:
    operators = load_runtime_registry(root).get("operators") or {}
    for deployment_id, operator in operators.items():
        if not isinstance(operator, dict):
            continue
        schemes = {str(item) for item in operator.get("schemes") or []}
        if scheme in schemes:
            return str(deployment_id), operator
    return None, {}


def resolve_operator_deployment(
    deployment_id: str,
    *,
    root: Path,
) -> dict[str, Any] | None:
    """Merge runtime operator config with deployment registry entry when present."""
    operators = load_runtime_registry(root).get("operators") or {}
    operator = operators.get(deployment_id)
    if not isinstance(operator, dict):
        return None

    merged = dict(operator)
    try:
        registry = load_deployment_registry(root=root)
        deployment = registry.by_id(deployment_id)
    except Exception:
        deployment = None
    if deployment is not None:
        merged.setdefault("agent_ref", deployment.agent_ref)
        merged.setdefault("target_uri", deployment.target_uri)
        merged.setdefault("health_uri", deployment.health_uri)
        merged.setdefault("status", deployment.status)
    return merged
