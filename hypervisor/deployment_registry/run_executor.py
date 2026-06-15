from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.env import resolve_deployment_env
from hypervisor.deployment_registry.health_uri import (
    port_from_http_uri,
    resolve_effective_health_uri,
)
from hypervisor.deployment_registry.models import AgentDeployment
from hypervisor.deployment_registry.port_utils import find_free_port, is_port_free
from hypervisor.deployment_registry.run_plans import build_run_plan
from hypervisor.deployment_registry.runtime_state import (
    is_process_alive,
    load_runtime_state,
    now_iso,
    save_runtime_state,
)


def load_or_clear_runtime_state(deployment_id: str, repo: Path) -> dict[str, Any] | None:
    return load_runtime_state(deployment_id, repo)


def build_agent_run_plan(
    deployment: AgentDeployment,
    *,
    repo: Path,
    port: int | None,
    host: str,
    reload: bool,
) -> dict[str, Any]:
    return build_run_plan(deployment, root=repo, port=port, host=host, reload=reload)


def rebind_plan_port_if_busy(
    deployment: AgentDeployment,
    plan: dict[str, Any],
    *,
    repo: Path,
    host: str,
    reload: bool,
) -> dict[str, Any]:
    preferred_port = int(plan.get("port") or 8101)
    if is_port_free(preferred_port):
        return plan
    rebound_port = find_free_port(preferred_port)
    rebound = build_run_plan(deployment, root=repo, port=rebound_port, host=host, reload=reload)
    rebound["port_rebound"] = {
        "from": preferred_port,
        "to": rebound_port,
        "reason": "port_in_use",
    }
    return rebound


def resolve_running_mode(
    *,
    if_running: str | None,
    detach: bool,
    port: int | None,
    existing: dict[str, Any],
    plan: dict[str, Any],
    deployment_id: str,
) -> str:
    running_mode = if_running or ("reuse" if detach else "fail")
    existing_port = port_from_http_uri(str(existing.get("health_uri") or ""))
    requested_port = plan.get("port")
    if (
        port is not None
        and existing_port is not None
        and requested_port is not None
        and existing_port != requested_port
    ):
        if running_mode == "reuse":
            return "restart"
        if running_mode == "fail":
            raise RuntimeError(
                f"Agent {deployment_id} already running on port {existing_port}, "
                f"requested port {requested_port}. Use --if-running restart."
            )
    return running_mode


def reuse_existing_process_plan(
    existing: dict[str, Any],
    plan: dict[str, Any],
    *,
    port: int | None,
) -> dict[str, Any]:
    plan = dict(plan)
    plan["pid"] = existing.get("pid")
    plan["health_uri"] = (
        plan.get("health_uri") if port is not None else resolve_effective_health_uri(existing, plan)
    )
    plan["runtime_status"] = "running"
    plan["already_running"] = True
    return plan


def sync_runtime_health_uri(state: dict[str, Any], health_uri: str) -> dict[str, Any]:
    """Update flat and canonical runtime-state health URI fields together."""
    updated = dict(state)
    updated["health_uri"] = health_uri
    network = dict(updated.get("network") or {})
    network["effective_health_uri"] = health_uri
    port = port_from_http_uri(health_uri)
    if port is not None:
        network["effective_port"] = port
    updated["network"] = network
    return updated


def _workspace_pythonpath(repo: Path) -> str:
    import os

    paths = [str(repo.resolve())]
    packages = repo / "packages"
    if packages.is_dir():
        for child in sorted(packages.iterdir()):
            if child.is_dir():
                paths.append(str(child))
    for extra in (
        repo / "agents" / "system" / "hypervisor_dashboard",
        repo / "examples" / "21_touri_voice",
    ):
        if extra.is_dir():
            paths.append(str(extra))
    prefix = os.pathsep.join(paths)
    existing = os.environ.get("PYTHONPATH", "")
    return f"{prefix}{os.pathsep}{existing}" if existing else prefix


def prepare_runtime_env(deployment: AgentDeployment, *, repo: Path) -> dict[str, str]:
    import os

    env = resolve_deployment_env(
        deployment.id,
        deployment.agent_ref,
        deployment.env,
        root=repo,
        resolve_secrets=True,
    )
    workspace_path = _workspace_pythonpath(repo)
    existing_pythonpath = env.get("PYTHONPATH") or ""
    env["PYTHONPATH"] = (
        f"{workspace_path}{os.pathsep}{existing_pythonpath}"
        if existing_pythonpath
        else workspace_path
    )
    role = (deployment.metadata or {}).get("role")
    if role == "desktop_operator":
        for key in (
            "DISPLAY",
            "WAYLAND_DISPLAY",
            "XDG_RUNTIME_DIR",
            "DBUS_SESSION_BUS_ADDRESS",
            "XAUTHORITY",
        ):
            if key not in env and os.environ.get(key):
                env[key] = os.environ[key]
    return env


def verify_process_alive(process_pid: int, *, settle_seconds: float = 0.3) -> bool:
    time.sleep(settle_seconds)
    return is_process_alive(process_pid)


def write_runtime_state_after_start(
    deployment: AgentDeployment,
    plan: dict[str, Any],
    *,
    process_pid: int,
    runtime_env: dict[str, str],
    host: str,
    requested_port: int | None,
    repo: Path,
) -> None:
    effective_port = plan.get("port")
    declared_health = deployment.health_uri or plan.get("health_uri")
    state = {
        "id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "pid": process_pid,
        "status": "running",
        "health_status": "unknown",
        "lifecycle_status": "running",
        "started_at": now_iso(),
        "command": plan["command_string"],
        "health_uri": plan["health_uri"],
        "log_uri": plan["log_uri"],
        "process_log_path": plan.get("process_log_path"),
        "process_log_uri": plan.get("process_log_uri"),
        "env": runtime_env,
        "requested_port": requested_port,
        "declared_health_uri": declared_health,
        "process": {
            "pid": process_pid,
            "command": plan["command_string"],
            "log_path": plan.get("process_log_path"),
            "log_uri": plan.get("process_log_uri"),
        },
        "network": {
            "host": host,
            "requested_port": requested_port,
            "effective_port": effective_port,
            "effective_health_uri": plan["health_uri"],
            "declared_health_uri": declared_health,
        },
    }
    save_runtime_state(deployment.id, state, repo)


def process_start_failure_payload(
    deployment_id: str,
    *,
    process_pid: int,
    plan: dict[str, Any],
    error: str | None = None,
) -> dict[str, Any]:
    detail = error
    if not detail:
        detail = (
            f"agent process exited immediately (pid={process_pid}); "
            f"port {plan.get('port')} may be unavailable"
        )
        log_path = plan.get("process_log_path")
        if log_path:
            path = Path(str(log_path))
            if path.exists():
                tail = path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
                if tail:
                    detail = f"{detail}; log: {tail[-1]}"
    return {
        "ok": False,
        "deployment_id": deployment_id,
        "error": detail,
        "port": plan.get("port"),
        "health_uri": plan.get("health_uri"),
        "port_rebound": plan.get("port_rebound"),
        "process_log_path": plan.get("process_log_path"),
        "process_log_uri": plan.get("process_log_uri"),
        "result_type": "lifecycle",
    }


def validate_run_dependencies(plan: dict[str, Any]) -> str | None:
    """Return an error message when required runtime dependencies are missing."""
    command = plan.get("command") or []
    if not isinstance(command, list):
        return None
    if "-m" not in command:
        return None
    try:
        module_index = command.index("-m") + 1
        module_name = str(command[module_index])
    except (ValueError, IndexError):
        return None
    if module_name != "uvicorn":
        return None
    python = str(command[0])
    import subprocess

    try:
        probe = subprocess.run(
            [python, "-c", "import uvicorn"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return f"cannot execute agent runtime ({python}): {exc}"
    if probe.returncode == 0:
        return None
    return (
        "uvicorn is not installed for the hypervisor venv "
        f"({python}); run: pip install 'uvicorn>=0.27' or pip install -e '.[server]'"
    )


def persist_rebound_port(
    deployment: AgentDeployment, plan: dict[str, Any], *, repo: Path
) -> dict[str, object] | None:
    rebound = plan.get("port_rebound")
    if not rebound:
        return None
    # Operator agents keep canonical contract ports in the registry; effective port lives in runtime state.
    if (deployment.metadata or {}).get("source") == "operator_agent":
        return None
    port = int(rebound.get("to") or plan.get("port") or 0)
    if port <= 0:
        return None
    from hypervisor.deployment_registry.registry_sync import sync_deployment_port

    return sync_deployment_port(deployment.id, port, root=repo)


def attach_started_process(plan: dict[str, Any], process_pid: int) -> dict[str, Any]:
    plan = dict(plan)
    plan["pid"] = process_pid
    plan["runtime_status"] = "running"
    return plan
