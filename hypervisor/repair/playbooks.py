from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from hypervisor.deployment_registry.health_uri import command_port_from_runtime
from hypervisor.deployment_registry.lifecycle import restart_agent, stop_agent
from hypervisor.deployment_registry.port_utils import find_free_port, port_from_http_uri
from hypervisor.deployment_registry.runtime_state import clear_runtime_state, load_runtime_state
from hypervisor.deployment_registry.supervisor import inspect_agent
from hypervisor.paths import find_repo_root


def _repo_root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else find_repo_root()


def _playbook_sync_health_uri(selector: str, repo: Path) -> dict[str, Any]:
    inspection = inspect_agent(selector, root=repo)
    effective = str(inspection.get("effective_health_uri") or "")
    deployment_id = str(inspection.get("id") or selector)
    if not effective:
        return {
            "ok": False,
            "playbook": "sync_health_uri",
            "status": "no_effective_health_uri",
            "inspection": inspection,
        }
    from hypervisor.deployment_registry.registry_sync import sync_deployment_health_uri

    synced = sync_deployment_health_uri(deployment_id, effective, root=repo)
    return {"ok": True, "playbook": "sync_health_uri", "status": "synced", **synced}


def _playbook_restart_agent(selector: str, repo: Path) -> dict[str, Any]:
    return restart_agent(selector, root=repo, detach=True)


def _playbook_clear_stale_runtime(selector: str, repo: Path) -> dict[str, Any]:
    stop_agent(selector, root=repo)
    deployment_id = selector if "." in selector else f"{selector}.local"
    clear_runtime_state(deployment_id, repo)
    return {"ok": True, "playbook": "clear_stale_runtime", "status": "cleared"}


def _playbook_rebind_port(selector: str, repo: Path) -> dict[str, Any]:
    state = load_runtime_state(selector, repo) or {}
    plan = {"command_string": state.get("command", "")}
    current_port = command_port_from_runtime(state, plan) or port_from_http_uri(
        str(state.get("health_uri") or "")
    )
    rebound = find_free_port(int(current_port or 8101))
    result = restart_agent(selector, root=repo, detach=True, port=rebound)
    if result.get("ok") is not False:
        from hypervisor.deployment_registry.registry_sync import sync_deployment_port

        deployment_id = str(result.get("deployment_id") or selector)
        try:
            result["registry_sync"] = sync_deployment_port(
                deployment_id, rebound, root=repo
            )
        except Exception as exc:
            result["registry_sync"] = {
                "ok": False,
                "error": str(exc),
                "error_type": type(exc).__name__,
            }
    return result


def _playbook_inspect(selector: str, repo: Path) -> dict[str, Any]:
    return inspect_agent(selector, root=repo)


def _playbook_requires_approval(playbook: str) -> dict[str, Any]:
    return {
        "ok": False,
        "playbook": playbook,
        "status": "blocked",
        "reason": "requires approval",
    }


def _playbook_not_implemented(playbook: str) -> dict[str, Any]:
    return {"ok": False, "playbook": playbook, "status": "not_implemented"}


# Dispatch table for playbooks. Keeps apply_playbook thin (low CC) and makes
# adding new playbooks a matter of registering a handler.
PLAYBOOK_HANDLERS: dict[str, Callable[[str, Path], dict[str, Any]]] = {
    "sync_health_uri": _playbook_sync_health_uri,
    "restart_agent": _playbook_restart_agent,
    "clear_stale_runtime": _playbook_clear_stale_runtime,
    "rebind_port": _playbook_rebind_port,
    "verify_effective_port": _playbook_inspect,
    "read_logs": _playbook_inspect,
    "check_process": _playbook_inspect,
}

_REQUIRES_APPROVAL = {
    "regenerate_agent",
    "modify_deployment_registry",
    "register_repair_capability",
}


def apply_playbook(
    playbook: str,
    *,
    selector: str,
    root: str | Path | None = None,
    approved: bool = False,
) -> dict[str, Any]:
    repo = _repo_root(root)
    if playbook in PLAYBOOK_HANDLERS:
        return PLAYBOOK_HANDLERS[playbook](selector, repo)
    if playbook in _REQUIRES_APPROVAL:
        if not approved:
            return _playbook_requires_approval(playbook)
        return _playbook_not_implemented(playbook)
    return {"ok": False, "playbook": playbook, "status": "unknown_playbook"}


def apply_playbook_sequence(
    playbooks: list[str],
    *,
    selector: str,
    root: str | Path | None = None,
    approved: bool = False,
) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for playbook in playbooks:
        results.append(apply_playbook(playbook, selector=selector, root=root, approved=approved))
    return results
