from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.env import default_log_uri, resolve_deployment_env
from hypervisor.deployment_registry.run_plans import build_run_plan
from hypervisor.deployment_registry.runtime_state import load_runtime_state, runtime_status
from hypervisor.deployment_registry.selector import resolve_deployment
from hypervisor.deployment_registry.status import resolve_status
from hypervisor.paths import find_repo_root


def _lifecycle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from uri3.results.envelope import enrich_lifecycle_dict

    return enrich_lifecycle_dict(payload)


def _repo_root(root: str | Path) -> Path:
    return Path(root) if str(root) != "." else find_repo_root()


def agent_status(
    selector: str,
    *,
    root: str | Path = ".",
    check_health: bool = True,
) -> dict[str, Any]:
    repo = _repo_root(root)
    deployment = resolve_deployment(selector, root=repo)
    status = resolve_status(deployment, check_health=check_health)
    runtime = runtime_status(deployment.id, repo)
    payload = {
        "id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "target_uri": deployment.target_uri,
        "status": status,
        "runtime_status": runtime,
        "health_uri": deployment.health_uri,
        "card_uri": deployment.card_uri,
        "env": resolve_deployment_env(
            deployment.id,
            deployment.agent_ref,
            deployment.env,
            root=repo,
            resolve_secrets=False,
        ),
    }
    state = load_runtime_state(deployment.id, repo)
    if state:
        payload["runtime_state"] = state
    if deployment.target_uri.startswith("local://") or deployment.target_uri.startswith("ssh://"):
        try:
            payload["run_plan"] = build_run_plan(deployment, root=repo)
        except (ValueError, FileNotFoundError):
            payload["run_plan"] = None
    return _lifecycle_payload(payload)


def agent_logs_uri(selector: str, *, root: str | Path = ".") -> str:
    repo = _repo_root(root)
    deployment = resolve_deployment(selector, root=root)
    state = load_runtime_state(deployment.id, repo)
    if state and state.get("log_uri"):
        return str(state["log_uri"])
    return default_log_uri(deployment.id, deployment.agent_ref, root=repo)
