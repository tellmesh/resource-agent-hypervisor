from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.lifecycle_status import (
    agent_logs_uri as agent_logs_uri,
)
from hypervisor.deployment_registry.lifecycle_status import (
    agent_status as agent_status,
)
from hypervisor.deployment_registry.process import start_process
from hypervisor.deployment_registry.run_executor import (
    attach_started_process,
    build_agent_run_plan,
    load_or_clear_runtime_state,
    persist_rebound_port,
    prepare_runtime_env,
    process_start_failure_payload,
    rebind_plan_port_if_busy,
    resolve_running_mode,
    reuse_existing_process_plan,
    sync_runtime_health_uri,
    validate_run_dependencies,
    verify_process_alive,
    write_runtime_state_after_start,
)
from hypervisor.deployment_registry.runtime_state import (
    clear_runtime_state,
    is_process_alive,
    save_runtime_state,
)
from hypervisor.deployment_registry.selector import resolve_deployment
from hypervisor.deployment_registry.stopper import stop_agent
from hypervisor.events import emit_operation_event, emit_result_event
from hypervisor.paths import find_repo_root


def _lifecycle_payload(payload: dict[str, Any]) -> dict[str, Any]:
    from uri3.results.envelope import enrich_lifecycle_dict

    return enrich_lifecycle_dict(payload)


def _repo_root(root: str | Path) -> Path:
    return Path(root) if str(root) != "." else find_repo_root()


def _validate_run_agent_options(
    *,
    if_running: str | None,
    wait_healthy: bool,
    supervise_repair: str,
) -> None:
    if if_running not in {None, "reuse", "restart", "fail"}:
        raise ValueError("--if-running must be one of: reuse, restart, fail")
    if wait_healthy and supervise_repair not in {"auto", "restart", "reuse", "sync_health"}:
        raise ValueError("--supervise-repair must be one of: auto, restart, reuse, sync_health")


def _finalize_run_plan(
    plan_dict: dict[str, Any],
    *,
    selector: str,
    repo: Path,
    port: int | None,
    wait_healthy: bool,
    detach: bool,
    dry_run: bool,
    supervise_repair: str,
) -> dict[str, Any]:
    payload = _lifecycle_payload(plan_dict)
    if not (wait_healthy and detach and not dry_run):
        return payload

    from hypervisor.deployment_registry.supervisor import ensure_agent_healthy

    supervision = ensure_agent_healthy(
        selector,
        root=repo,
        port=port,
        repair=supervise_repair,
    )
    payload["supervision"] = supervision
    payload["service_healthy"] = supervision.get("ok")
    if not supervision.get("ok"):
        payload["ok"] = False
        payload["service_result_status"] = "failed"
    return payload


def _load_active_runtime_state(selector: str, deployment, *, repo: Path) -> dict[str, Any] | None:
    existing = load_or_clear_runtime_state(deployment.id, repo)
    if existing and not is_process_alive(existing.get("pid")):
        stop_agent(selector, root=repo)
        clear_runtime_state(deployment.id, repo)
        return None
    return existing


def _sync_reused_runtime_state(
    deployment_id: str,
    existing: dict[str, Any],
    plan: dict[str, Any],
    *,
    repo: Path,
) -> None:
    if plan["health_uri"] == existing.get("health_uri"):
        return
    save_runtime_state(
        deployment_id,
        sync_runtime_health_uri(existing, plan["health_uri"]),
        repo,
    )


def _resolve_running_process(
    selector: str,
    deployment,
    existing: dict[str, Any] | None,
    plan: dict[str, Any],
    *,
    repo: Path,
    if_running: str | None,
    detach: bool,
    port: int | None,
) -> tuple[dict[str, Any] | None, dict[str, Any], dict[str, Any] | None]:
    if not existing or not is_process_alive(existing.get("pid")):
        return existing, plan, None

    running_mode = resolve_running_mode(
        if_running=if_running,
        detach=detach,
        port=port,
        existing=existing,
        plan=plan,
        deployment_id=deployment.id,
    )
    if running_mode == "restart":
        stop_agent(selector, root=repo)
        clear_runtime_state(deployment.id, repo)
        return None, plan, None
    if running_mode == "reuse":
        reused_plan = reuse_existing_process_plan(existing, plan, port=port)
        _sync_reused_runtime_state(deployment.id, existing, reused_plan, repo=repo)
        return existing, reused_plan, reused_plan
    if running_mode == "fail":
        raise RuntimeError(
            f"Agent {deployment.id} already running with pid {existing['pid']}. "
            "Use hypervisor stop-agent first or --if-running reuse|restart."
        )
    raise ValueError("--if-running must be one of: reuse, restart, fail")


def _run_non_local_target(
    deployment,
    *,
    repo: Path,
    plan: dict[str, Any] | None = None,
    wait_healthy: bool = False,
) -> dict[str, Any] | None:
    if deployment.target_uri.startswith("ssh://"):
        from hypervisor.deployment_registry.ssh_run import apply_ssh_run_plan

        if plan is None:
            raise ValueError("SSH run plan missing")
        result = apply_ssh_run_plan(plan, wait_healthy=wait_healthy)
        return _lifecycle_payload({**plan, **result})
    if deployment.target_uri.startswith("docker://"):
        from hypervisor.deployment_registry.docker_runner import apply_docker_deploy

        return apply_docker_deploy(deployment, root=repo)
    return None


def _start_local_process(
    deployment,
    plan: dict[str, Any],
    *,
    repo: Path,
    host: str,
    port: int | None,
    detach: bool,
) -> dict[str, Any]:
    dependency_error = validate_run_dependencies(plan)
    if dependency_error:
        return process_start_failure_payload(
            deployment.id,
            process_pid=0,
            plan=plan,
            error=dependency_error,
        )
    runtime_env = prepare_runtime_env(deployment, repo=repo)
    process = start_process(plan, root=repo, detach=detach, runtime_env=runtime_env)
    if not (detach and process is not None):
        return plan
    if not verify_process_alive(process.pid):
        return process_start_failure_payload(deployment.id, process_pid=process.pid, plan=plan)
    write_runtime_state_after_start(
        deployment,
        plan,
        process_pid=process.pid,
        runtime_env=runtime_env,
        host=host,
        requested_port=port,
        repo=repo,
    )
    try:
        registry_sync = persist_rebound_port(deployment, plan, repo=repo)
    except Exception as exc:
        registry_sync = {"ok": False, "error": str(exc), "error_type": type(exc).__name__}
    if registry_sync:
        plan["registry_sync"] = registry_sync
    return attach_started_process(plan, process.pid)


def _is_process_start_failure(payload: dict[str, Any]) -> bool:
    return payload.get("ok") is False and payload.get("result_type") == "lifecycle"


def _resolve_initial_run_plan(
    selector: str,
    deployment,
    *,
    repo: Path,
    port: int | None,
    host: str,
    reload: bool,
    if_running: str | None,
    detach: bool,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    existing = _load_active_runtime_state(selector, deployment, repo=repo)
    plan = build_agent_run_plan(deployment, repo=repo, port=port, host=host, reload=reload)
    _, plan, ready_plan = _resolve_running_process(
        selector,
        deployment,
        existing,
        plan,
        repo=repo,
        if_running=if_running,
        detach=detach,
        port=port,
    )
    if ready_plan is not None:
        return ready_plan, plan
    return None, rebind_plan_port_if_busy(deployment, plan, repo=repo, host=host, reload=reload)


def _execute_run_agent_plan(
    deployment,
    plan: dict[str, Any],
    finalize,
    *,
    repo: Path,
    host: str,
    port: int | None,
    detach: bool,
    wait_healthy: bool = False,
) -> dict[str, Any]:
    target_result = _run_non_local_target(
        deployment,
        repo=repo,
        plan=plan,
        wait_healthy=wait_healthy,
    )
    if target_result is not None:
        return target_result
    plan = _start_local_process(deployment, plan, repo=repo, host=host, port=port, detach=detach)
    if _is_process_start_failure(plan):
        return _lifecycle_payload(plan)
    return finalize(plan)


def _emit_run_agent_result(
    deployment,
    result: dict[str, Any],
    *,
    repo: Path,
    success_code: str,
    success_message: str,
    extra_fields: dict[str, Any] | None = None,
) -> None:
    """Centralized emission for run-agent success/failure events (thins orchestrator)."""
    emit_result_event(
        "run-agent",
        deployment.id,
        result,
        root=repo,
        success_code=success_code,
        failure_code="AGENT_RUN_FAILED",
        success_message=success_message,
        failure_message=f"{deployment.id} run-agent failed",
        extra_fields=extra_fields or {},
    )


def run_agent(
    selector: str,
    *,
    root: str | Path = ".",
    port: int | None = None,
    host: str = "0.0.0.0",
    reload: bool = False,
    dry_run: bool = False,
    detach: bool = False,
    if_running: str | None = None,
    wait_healthy: bool = False,
    supervise_repair: str = "auto",
) -> dict[str, Any]:
    _validate_run_agent_options(
        if_running=if_running,
        wait_healthy=wait_healthy,
        supervise_repair=supervise_repair,
    )
    repo = _repo_root(root)
    deployment = resolve_deployment(selector, root=repo)

    def finalize(plan_dict: dict[str, Any]) -> dict[str, Any]:
        return _finalize_run_plan(
            plan_dict,
            selector=selector,
            repo=repo,
            port=port,
            wait_healthy=wait_healthy,
            detach=detach,
            dry_run=dry_run,
            supervise_repair=supervise_repair,
        )

    ready_plan, plan = _resolve_initial_run_plan(
        selector,
        deployment,
        repo=repo,
        port=port,
        host=host,
        reload=reload,
        if_running=if_running,
        detach=detach,
    )
    if ready_plan is not None:
        result = finalize(ready_plan)
        _emit_run_agent_result(
            deployment,
            result,
            repo=repo,
            success_code="AGENT_RUN_REUSED",
            success_message=f"{deployment.id} run-agent reused existing process",
            extra_fields={"target_uri": deployment.target_uri, "port": result.get("port")},
        )
        return result
    if dry_run:
        result = _lifecycle_payload(plan)
        emit_operation_event(
            "AGENT_RUN_PLANNED",
            f"{deployment.id} run-agent dry-run plan created",
            root=repo,
            selector=deployment.id,
            operation="run-agent",
            target_uri=deployment.target_uri,
            port=plan.get("port"),
            module=plan.get("module"),
        )
        return result
    result = _execute_run_agent_plan(
        deployment,
        plan,
        finalize,
        repo=repo,
        host=host,
        port=port,
        detach=detach,
        wait_healthy=wait_healthy,
    )
    _emit_run_agent_result(
        deployment,
        result,
        repo=repo,
        success_code="AGENT_RUN_COMPLETED",
        success_message=f"{deployment.id} run-agent completed",
        extra_fields={
            "target_uri": deployment.target_uri,
            "port": result.get("port"),
            "pid": result.get("pid"),
            "service_healthy": result.get("service_healthy"),
        },
    )
    return result


def restart_agent(
    selector: str,
    *,
    root: str | Path = ".",
    port: int | None = None,
    host: str = "0.0.0.0",
    reload: bool = False,
    detach: bool = True,
) -> dict[str, Any]:
    repo = _repo_root(root)
    deployment = resolve_deployment(selector, root=repo)
    stop_agent(selector, root=repo)
    clear_runtime_state(deployment.id, repo)
    result = run_agent(
        selector,
        root=repo,
        port=port,
        host=host,
        reload=reload,
        detach=detach,
        if_running="fail",
    )
    emit_result_event(
        "restart-agent",
        deployment.id,
        result,
        root=repo,
        success_code="AGENT_RESTART_COMPLETED",
        failure_code="AGENT_RESTART_FAILED",
        success_message=f"{deployment.id} restart-agent completed",
        failure_message=f"{deployment.id} restart-agent failed",
        extra_fields={"port": result.get("port"), "pid": result.get("pid")},
    )
    return result
