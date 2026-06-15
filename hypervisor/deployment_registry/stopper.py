from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.health_uri import port_from_command, port_from_http_uri
from hypervisor.deployment_registry.process_discovery import (
    command_matches_plan,
    pids_listening_on_port,
    terminate_pid,
)
from hypervisor.deployment_registry.run_executor import build_agent_run_plan
from hypervisor.deployment_registry.runtime_state import (
    clear_runtime_state,
    is_process_alive,
    load_runtime_state,
    now_iso,
    save_runtime_state,
    state_command,
    state_pid,
)
from hypervisor.deployment_registry.selector import resolve_deployment
from hypervisor.events import emit_result_event
from hypervisor.paths import find_repo_root


def _lifecycle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from uri3.results.envelope import enrich_lifecycle_dict

    return enrich_lifecycle_dict(payload)


def _repo_root(root: str | Path) -> Path:
    return Path(root) if str(root) != "." else find_repo_root()


def _safe_stop_plan(deployment, *, repo: Path) -> dict[str, Any]:
    try:
        return build_agent_run_plan(deployment, repo=repo, port=None, host="0.0.0.0", reload=False)
    except (FileNotFoundError, ValueError):
        return {}


def _state_health_uri(state: dict[str, Any]) -> str:
    network = state.get("network") or {}
    if isinstance(network, dict) and network.get("effective_health_uri"):
        return str(network["effective_health_uri"])
    return str(state.get("health_uri") or "")


def _candidate_stop_ports(state: dict[str, Any], plan: dict[str, Any]) -> set[int]:
    ports: set[int] = set()
    command_port = port_from_command(state_command(state))
    if command_port is not None:
        ports.add(command_port)
    health_port = port_from_http_uri(_state_health_uri(state))
    if health_port is not None:
        ports.add(health_port)
    plan_port = plan.get("port")
    if isinstance(plan_port, int):
        ports.add(plan_port)
    return ports


def _terminate_matching_agent_processes(
    state: dict[str, Any],
    plan: dict[str, Any],
    *,
    timeout: float,
) -> dict[str, Any]:
    pids: set[int] = set()
    skipped: list[dict[str, Any]] = []
    runtime_pid = state_pid(state)
    if isinstance(runtime_pid, int) and is_process_alive(runtime_pid):
        if not plan or command_matches_plan(runtime_pid, plan):
            pids.add(runtime_pid)
        else:
            skipped.append({"pid": runtime_pid, "reason": "runtime_pid_command_mismatch"})

    for port in _candidate_stop_ports(state, plan):
        for pid in pids_listening_on_port(port):
            if not plan or command_matches_plan(pid, plan):
                pids.add(pid)
            else:
                skipped.append({"pid": pid, "port": port, "reason": "listener_command_mismatch"})

    terminated: list[int] = []
    failed: list[int] = []
    for pid in sorted(pids):
        if terminate_pid(pid, timeout=timeout):
            terminated.append(pid)
        else:
            failed.append(pid)
    return {"terminated_pids": terminated, "failed_pids": failed, "skipped": skipped}


def _emit_stop_result(
    deployment,
    result_core: dict[str, Any],
    *,
    repo: Path,
    extra_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = _lifecycle_payload(result_core)
    emit_result_event(
        "stop-agent",
        deployment.id,
        result,
        root=repo,
        success_code="AGENT_STOP_COMPLETED",
        failure_code="AGENT_STOP_FAILED",
        success_message=f"{deployment.id} stop-agent completed",
        failure_message=f"{deployment.id} stop-agent failed",
        extra_fields=extra_fields or {},
    )
    return result


def _stop_docker_deployment(deployment, *, repo: Path) -> dict[str, Any]:
    from hypervisor.deployment_registry.docker_runner import stop_docker_deployment

    result = stop_docker_deployment(deployment, root=repo)
    emit_result_event(
        "stop-agent",
        deployment.id,
        result,
        root=repo,
        success_code="AGENT_STOP_COMPLETED",
        failure_code="AGENT_STOP_FAILED",
        success_message=f"{deployment.id} stop-agent completed",
        failure_message=f"{deployment.id} stop-agent failed",
        extra_fields={"target_uri": deployment.target_uri},
    )
    return result


def _stop_without_runtime_state(deployment, plan: dict[str, Any], *, repo: Path, timeout: float):
    stopped_without_state = _terminate_matching_agent_processes({}, plan, timeout=timeout)
    if stopped_without_state["terminated_pids"]:
        return _emit_stop_result(
            deployment,
            {
                "id": deployment.id,
                "status": "stopped",
                "message": "Matching agent process discovered without runtime state; stopped",
                **stopped_without_state,
            },
            repo=repo,
            extra_fields={"terminated_pids": stopped_without_state.get("terminated_pids")},
        )
    return _emit_stop_result(
        deployment,
        {"id": deployment.id, "status": "stopped", "message": "No runtime state found"},
        repo=repo,
    )


def _stop_with_runtime_state(
    deployment,
    state: dict[str, Any],
    plan: dict[str, Any],
    *,
    repo: Path,
    timeout: float,
) -> dict[str, Any]:
    pid = state_pid(state)
    stop_result = _terminate_matching_agent_processes(state, plan, timeout=timeout)
    if stop_result["failed_pids"]:
        return _emit_stop_result(
            deployment,
            {
                "ok": False,
                "id": deployment.id,
                "status": "failed",
                "message": "Failed to stop one or more matching agent processes",
                **stop_result,
            },
            repo=repo,
        )
    if stop_result["terminated_pids"]:
        reported_pid = pid
        if reported_pid not in stop_result["terminated_pids"]:
            reported_pid = stop_result["terminated_pids"][0]
        stopped = {
            "id": deployment.id,
            "pid": reported_pid,
            "status": "stopped",
            "stopped_at": now_iso(),
            **stop_result,
        }
        save_runtime_state(deployment.id, stopped, repo)
        return _emit_stop_result(
            deployment,
            stopped,
            repo=repo,
            extra_fields={"terminated_pids": stop_result.get("terminated_pids")},
        )
    if not is_process_alive(pid):
        clear_runtime_state(deployment.id, repo)
        return _emit_stop_result(
            deployment,
            {
                "id": deployment.id,
                "status": "stopped",
                "message": "Process not alive; state cleared",
                **stop_result,
            },
            repo=repo,
        )
    return _emit_stop_result(
        deployment,
        {
            "ok": False,
            "id": deployment.id,
            "status": "failed",
            "message": (
                "Runtime PID is alive but does not match the deployment command; not stopped"
            ),
            **stop_result,
        },
        repo=repo,
    )


def stop_agent(
    selector: str,
    *,
    root: str | Path = ".",
    timeout: float = 5.0,
) -> dict[str, Any]:
    repo = _repo_root(root)
    deployment = resolve_deployment(selector, root=repo)
    if deployment.target_uri.startswith("docker://"):
        return _stop_docker_deployment(deployment, repo=repo)
    plan = _safe_stop_plan(deployment, repo=repo)
    state = load_runtime_state(deployment.id, repo)
    if not state:
        return _stop_without_runtime_state(deployment, plan, repo=repo, timeout=timeout)
    return _stop_with_runtime_state(deployment, state, plan, repo=repo, timeout=timeout)
