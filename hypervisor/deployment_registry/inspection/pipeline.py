from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.health_uri import (
    command_port_from_runtime,
    resolve_effective_health_uri,
)
from hypervisor.deployment_registry.inspection.incidents import (
    BLOCKING_INCIDENT_CODES,
    blocking_incidents,
    classify_incidents,
)
from hypervisor.deployment_registry.inspection.probe import probe_http, read_error_logs
from hypervisor.deployment_registry.inspection.readiness import build_agent_readiness_report
from hypervisor.deployment_registry.lifecycle import agent_logs_uri
from hypervisor.deployment_registry.models import AgentDeployment
from hypervisor.deployment_registry.port_utils import expected_agent_id
from hypervisor.deployment_registry.run_plans import build_run_plan
from hypervisor.deployment_registry.runtime_state import (
    is_process_alive,
    load_runtime_state,
    runtime_status,
)


# Use shared to reduce duplication (helps large file + CC metrics across the package).
from hypervisor.deployment_registry.runtime_state import (
    state_command as _state_command,
    state_pid as _state_pid,
    state_health_uri as _state_health_uri,
)


def _runtime_command_port(state: dict[str, Any], plan: dict[str, Any]) -> int | None:
    runtime_command = _state_command(state)
    if runtime_command:
        return command_port_from_runtime({"command": runtime_command}, plan)
    return None


@dataclass
class InspectionContext:
    deployment: AgentDeployment
    state: dict[str, Any]
    run_plan: dict[str, Any]
    pid: int | None
    process_alive: bool
    runtime: str
    stored_health_uri: str
    effective_health_uri: str
    effective_card_uri: str | None
    log_uri: str
    process_log_uri: str | None
    expected_agent: str | None
    expected_service: str | None


def _derive_effective_card_uri(effective_health_uri: str | None, state: dict[str, Any], run_plan: dict[str, Any], deployment: AgentDeployment) -> str | None:
    from urllib.parse import urlsplit

    card = state.get("card_uri") or run_plan.get("card_uri") or deployment.card_uri
    if effective_health_uri:
        try:
            port = urlsplit(effective_health_uri).port
            if port:
                card = f"http://localhost:{port}/.well-known/agent-card.json"
        except Exception:
            pass
    return str(card) if card else None


def gather_inspection_context(deployment: AgentDeployment, *, repo: Path) -> InspectionContext:
    state = load_runtime_state(deployment.id, repo) or {}
    try:
        run_plan = build_run_plan(deployment, root=repo)
    except (FileNotFoundError, ValueError):
        run_plan = {}
    pid = _state_pid(state)
    process_alive = is_process_alive(pid if isinstance(pid, int) else None)
    runtime = runtime_status(deployment.id, repo)
    stored_health_uri = str(
        _state_health_uri(state) or run_plan.get("health_uri") or deployment.health_uri or ""
    )
    effective_health_uri = resolve_effective_health_uri(state, run_plan)
    effective_card_uri = _derive_effective_card_uri(effective_health_uri, state, run_plan, deployment)
    log_uri = str(state.get("log_uri") or agent_logs_uri(deployment.id, root=repo))
    process_log_uri = state.get("process_log_uri")
    return InspectionContext(
        deployment=deployment,
        state=state,
        run_plan=run_plan,
        pid=pid if isinstance(pid, int) else None,
        process_alive=process_alive,
        runtime=runtime,
        stored_health_uri=stored_health_uri,
        effective_health_uri=effective_health_uri,
        effective_card_uri=effective_card_uri,
        log_uri=log_uri,
        process_log_uri=str(process_log_uri) if process_log_uri else None,
        expected_agent=expected_agent_id(deployment.agent_ref),
        expected_service=str(deployment.metadata.get("expected_service") or "") or None,
    )


def _merge_log_results(
    primary: dict[str, Any], secondary: dict[str, Any], *, limit: int
) -> dict[str, Any]:
    entries = list(primary.get("entries") or []) + list(secondary.get("entries") or [])
    merged = dict(primary)
    merged["sources"] = [
        {
            "uri": primary.get("uri"),
            "summary": primary.get("summary"),
            "error_count": primary.get("error_count", 0),
            "hint": primary.get("hint"),
        },
        {
            "uri": secondary.get("uri"),
            "summary": secondary.get("summary"),
            "error_count": secondary.get("error_count", 0),
            "hint": secondary.get("hint"),
        },
    ]
    merged["entries"] = entries[-limit:]
    merged["error_count"] = int(primary.get("error_count", 0)) + int(
        secondary.get("error_count", 0)
    )
    return merged


def probe_agent_endpoints(
    context: InspectionContext,
    *,
    repo: Path,
    timeout: float,
    log_limit: int,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    health = probe_http(
        context.effective_health_uri or None,
        timeout=timeout,
        expected_agent=context.expected_agent,
        expected_service=context.expected_service,
    )
    card = probe_http(
        context.effective_card_uri,
        timeout=timeout,
        expected_agent=context.expected_agent,
        expected_service=context.expected_service,
    )
    logs = read_error_logs(context.log_uri, root=repo, limit=log_limit)
    if context.process_log_uri:
        process_logs = read_error_logs(context.process_log_uri, root=repo, limit=log_limit)
        logs = _merge_log_results(logs, process_logs, limit=log_limit)
    return health, card, logs


def build_inspection_report(
    context: InspectionContext,
    *,
    health: dict[str, Any],
    card: dict[str, Any],
    logs: dict[str, Any],
) -> dict[str, Any]:
    incidents = classify_incidents(
        runtime=context.runtime,
        process_alive=context.process_alive,
        deployment_health_uri=context.deployment.health_uri,
        stored_health_uri=context.stored_health_uri,
        effective_health_uri=context.effective_health_uri,
        command_port=_runtime_command_port(context.state, context.run_plan),
        health=health,
        card=card,
        logs=logs,
        expected_agent=context.expected_agent,
        run_plan=context.run_plan,
    )
    blocking = blocking_incidents(incidents)
    service_status = (
        "healthy" if health.get("ok") and context.process_alive and not blocking else "degraded"
    )
    if context.runtime in {"stopped", "stale"} and not context.process_alive:
        service_status = "stopped"
    elif not health.get("ok") and context.process_alive:
        service_status = "unhealthy"

    readiness = build_agent_readiness_report(
        deployment_id=context.deployment.id,
        service_status=service_status,
        runtime=context.runtime,
        process_alive=context.process_alive,
        health=health,
        card=card,
        logs=logs,
        incidents=incidents,
        effective_health_uri=context.effective_health_uri,
        declared_health_uri=context.deployment.health_uri,
    )

    payload = {
        "ok": service_status == "healthy",
        "id": context.deployment.id,
        "agent_ref": context.deployment.agent_ref,
        "target_uri": context.deployment.target_uri,
        "service_status": service_status,
        "runtime_status": context.runtime,
        "process": {"pid": context.pid, "running": context.process_alive},
        "readiness": readiness["summary"],
        "agent_readiness": readiness,
        "health": health,
        "card": card,
        "log_uri": context.log_uri,
        "process_log_uri": context.process_log_uri,
        "log_errors": logs,
        "declared_health_uri": context.deployment.health_uri,
        "stored_health_uri": context.stored_health_uri or None,
        "effective_health_uri": context.effective_health_uri,
        "incidents": blocking,
        "warnings": [item for item in incidents if item.get("code") not in BLOCKING_INCIDENT_CODES],
        "runtime_state": context.state or None,
    }
    if context.run_plan:
        payload["run_plan"] = {
            "port": context.run_plan.get("port"),
            "health_uri": context.run_plan.get("health_uri"),
            "card_uri": context.run_plan.get("card_uri"),
            "command": context.run_plan.get("command_string"),
        }
    return payload
