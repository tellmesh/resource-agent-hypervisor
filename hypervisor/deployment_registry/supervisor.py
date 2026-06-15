from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.health_uri import command_port_from_runtime
from hypervisor.deployment_registry.inspection.pipeline import (
    build_inspection_report,
    gather_inspection_context,
    probe_agent_endpoints,
)
from hypervisor.deployment_registry.lifecycle import restart_agent, run_agent
from hypervisor.deployment_registry.port_utils import find_free_port
from hypervisor.deployment_registry.selector import resolve_deployment
from hypervisor.paths import find_repo_root


def _lifecycle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from uri3.results.envelope import enrich_lifecycle_dict

    return enrich_lifecycle_dict(payload)


def _repo_root(root: str | Path) -> Path:
    return Path(root) if str(root) != "." else find_repo_root()


def inspect_agent(
    selector: str,
    *,
    root: str | Path = ".",
    timeout: float = 2.0,
    log_limit: int = 20,
) -> dict[str, Any]:
    """Inspect process, health, card and recent error logs for one deployment."""
    repo = _repo_root(root)
    deployment = resolve_deployment(selector, root=repo)
    context = gather_inspection_context(deployment, repo=repo)
    health, card, logs = probe_agent_endpoints(
        context,
        repo=repo,
        timeout=timeout,
        log_limit=log_limit,
    )
    payload = build_inspection_report(context, health=health, card=card, logs=logs)
    return _lifecycle_payload(payload)


def _runtime_command_port(inspection: dict[str, Any]) -> int | None:
    state = inspection.get("runtime_state") or {}
    plan = inspection.get("run_plan") or {}
    return command_port_from_runtime(state, plan) or plan.get("port")


def _auto_repair_plan(inspection: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    readiness = inspection.get("agent_readiness") or {}
    action = readiness.get("recommended_action", "restart")
    port = _runtime_command_port(inspection)

    if action == "rebind_port":
        current_port = port or 8101
        return "rebind_port", {"port": find_free_port(int(current_port))}
    if action == "observe":
        return "sync_health", {}
    if action == "none":
        return "reuse", {"port": port} if port else {}
    return "restart", {"port": port} if port else {}


def _apply_repair(
    selector: str,
    *,
    root: Path,
    strategy: str,
    params: dict[str, Any],
    detach: bool = True,
) -> dict[str, Any]:
    port = params.get("port")
    if strategy == "sync_health":
        return run_agent(selector, root=root, detach=detach, if_running="reuse", port=port)
    if strategy == "reuse":
        return run_agent(selector, root=root, detach=detach, if_running="reuse", port=port)
    if strategy in {"rebind_port", "restart"}:
        return restart_agent(selector, root=root, detach=detach, port=port)
    raise ValueError(f"unsupported repair strategy: {strategy}")


def ensure_agent_healthy(
    selector: str,
    *,
    root: str | Path = ".",
    port: int | None = None,
    repair: str = "auto",
    timeout: float = 2.0,
    log_limit: int = 20,
    max_attempts: int = 3,
    settle_seconds: float = 0.5,
) -> dict[str, Any]:
    """Run bounded inspect → repair → re-probe loop until healthy or attempts exhausted."""
    repo = _repo_root(root)
    if settle_seconds > 0:
        time.sleep(settle_seconds)
    before = inspect_agent(selector, root=repo, timeout=timeout, log_limit=log_limit)
    if before.get("ok"):
        return _lifecycle_payload(
            {
                "ok": True,
                "id": before["id"],
                "status": "healthy",
                "repair": repair,
                "attempts": 0,
                "actions": [],
                "before": before,
                "after": before,
            }
        )

    actions: list[dict[str, Any]] = []
    current = before
    attempts = 0
    while attempts < max_attempts and not current.get("ok"):
        if repair == "auto":
            strategy, params = _auto_repair_plan(current)
        elif repair in {"restart", "reuse", "sync_health"}:
            strategy, params = repair, {"port": port} if port is not None else {}
        else:
            raise ValueError("repair must be one of: auto, restart, reuse, sync_health")

        if port is not None:
            params = {**params, "port": port}
        action = _apply_repair(selector, root=repo, strategy=strategy, params=params)
        actions.append({"strategy": strategy, "params": params, "result": action})
        time.sleep(settle_seconds)
        current = inspect_agent(selector, root=repo, timeout=timeout, log_limit=log_limit)
        attempts += 1

    return _lifecycle_payload(
        {
            "ok": bool(current.get("ok")),
            "id": current["id"],
            "status": "healthy" if current.get("ok") else "degraded",
            "repair": repair,
            "attempts": attempts,
            "actions": actions,
            "before": before,
            "after": current,
        }
    )


def supervise_agent(
    selector: str,
    *,
    root: str | Path = ".",
    repair: str = "none",
    timeout: float = 2.0,
    log_limit: int = 20,
    settle_seconds: float = 0.5,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Inspect an agent and optionally run a bounded repair loop."""
    if repair not in {"none", "restart", "reuse", "sync_health", "auto"}:
        raise ValueError("repair must be one of: none, restart, reuse, sync_health, auto")

    if repair == "none":
        before = inspect_agent(selector, root=root, timeout=timeout, log_limit=log_limit)
        if before.get("ok"):
            return _lifecycle_payload(
                {
                    "ok": True,
                    "id": before["id"],
                    "status": "healthy",
                    "actions": [],
                    "before": before,
                    "after": before,
                }
            )
        return _lifecycle_payload(
            {
                "ok": False,
                "id": before["id"],
                "status": "blocked",
                "reason": ("service is not healthy; run with --repair auto or --repair restart"),
                "actions": [],
                "before": before,
                "after": before,
            }
        )

    return ensure_agent_healthy(
        selector,
        root=root,
        repair=repair,
        timeout=timeout,
        log_limit=log_limit,
        max_attempts=max_attempts,
        settle_seconds=settle_seconds,
    )
