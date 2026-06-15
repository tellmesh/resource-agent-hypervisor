from __future__ import annotations

from typing import Any

from hypervisor.deployment_registry.env_config import load_deployments_uri_config, load_runtime_uri_config
from hypervisor.deployment_registry.env_merge import materialize_env_values, merge_runtime_defaults


def build_deployment_env_map(
    deployment_id: str,
    agent_ref: str,
    deployment_env: dict[str, Any] | None,
    *,
    root,
) -> dict[str, Any]:
    deployments_cfg = load_deployments_uri_config(root)
    runtime_cfg = load_runtime_uri_config(root)
    merged: dict[str, Any] = {}
    merged.update(deployments_cfg.get("defaults", {}).get("env") or {})
    agent_id = agent_ref.removeprefix("agent://")
    agent_runtime = (runtime_cfg.get("agents") or {}).get(agent_id) or {}
    merge_runtime_defaults(
        merged,
        agent_runtime=agent_runtime,
        runtime_defaults=runtime_cfg.get("defaults") or {},
    )
    per_deployment = (deployments_cfg.get("deployments") or {}).get(deployment_id) or {}
    merged.update(per_deployment.get("env") or {})
    merged.update(deployment_env or {})
    return merged


def resolve_deployment_env(
    deployment_id: str,
    agent_ref: str,
    deployment_env: dict[str, Any] | None = None,
    *,
    root=None,
    resolve_secrets: bool = True,
) -> dict[str, str]:
    merged = build_deployment_env_map(deployment_id, agent_ref, deployment_env, root=root)
    return materialize_env_values(merged, resolve_secrets=resolve_secrets)


def default_log_uri(deployment_id: str, agent_ref: str, *, root=None) -> str:
    runtime_cfg = load_runtime_uri_config(root)
    agent_id = agent_ref.removeprefix("agent://")
    agent_runtime = (runtime_cfg.get("agents") or {}).get(agent_id) or {}
    stream = agent_runtime.get("log_stream") or runtime_cfg.get("defaults", {}).get("log_stream") or "hypervisor"
    return f"log://{stream}?grep={deployment_id}"
