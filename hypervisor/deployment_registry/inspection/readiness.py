from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from hypervisor.deployment_registry.inspection.incidents import BLOCKING_INCIDENT_CODES


def readiness_summary(
    *,
    process_alive: bool,
    health: dict[str, Any],
    card: dict[str, Any],
    logs: dict[str, Any],
    effective_health_uri: str,
    declared_health_uri: str | None,
) -> dict[str, Any]:
    effective_port = None
    if effective_health_uri:
        parsed = urlsplit(effective_health_uri)
        effective_port = parsed.port
    return {
        "process": "running" if process_alive else "stopped",
        "health": "ok" if health.get("ok") else "failed",
        "card": "ok" if card.get("ok") else ("skipped" if not card.get("uri") else "failed"),
        "log_errors": logs.get("error_count", 0),
        "effective_port": effective_port,
        "declared_health_uri": declared_health_uri,
        "effective_health_uri": effective_health_uri,
    }


def recommended_action_from_incidents(incident_codes: set[str]) -> str:
    if not incident_codes:
        return "none"
    if incident_codes & {"PORT_OCCUPIED", "FOREIGN_SERVICE_ON_PORT"}:
        return "rebind_port"
    if incident_codes & {"RUNTIME_STATE_STALE", "PROCESS_NOT_ALIVE"}:
        return "restart"
    if incident_codes & {"HEALTH_FAILED", "PROCESS_RUNNING_BUT_UNHEALTHY", "CARD_FAILED"}:
        return "repair"
    if incident_codes & {"COMMAND_HEALTH_MISMATCH", "HEALTH_URI_DRIFT"}:
        return "observe"
    return "escalate"


def build_agent_readiness_report(
    *,
    deployment_id: str,
    service_status: str,
    runtime: str,
    process_alive: bool,
    health: dict[str, Any],
    card: dict[str, Any],
    logs: dict[str, Any],
    incidents: list[dict[str, Any]],
    effective_health_uri: str,
    declared_health_uri: str | None,
) -> dict[str, Any]:
    blocking_codes = {
        str(item.get("code")) for item in incidents if item.get("code") in BLOCKING_INCIDENT_CODES
    }
    all_codes = {str(item.get("code")) for item in incidents if item.get("code")}
    warning_codes = all_codes - blocking_codes
    summary = readiness_summary(
        process_alive=process_alive,
        health=health,
        card=card,
        logs=logs,
        effective_health_uri=effective_health_uri,
        declared_health_uri=declared_health_uri,
    )
    process_status = "running" if process_alive else ("stale" if runtime == "stale" else "stopped")
    return {
        "$schema": "schemas/agent_readiness.schema.json",
        "apiVersion": "uri3.io/v1",
        "kind": "AgentReadinessReport",
        "uri": {"self": f"readiness://agent/{deployment_id}"},
        "ok": service_status == "healthy",
        "process_status": process_status,
        "health_status": "ok" if health.get("ok") else "failed",
        "contract_status": "unknown",
        "capabilities_status": "unknown",
        "logs_status": "errors_found" if logs.get("error_count", 0) else "ok",
        "deployment_status": service_status,
        "recommended_action": recommended_action_from_incidents(blocking_codes),
        "effective_port": summary.get("effective_port"),
        "effective_health_uri": effective_health_uri,
        "incident_codes": sorted(blocking_codes),
        "warning_codes": sorted(warning_codes),
        "summary": summary,
    }
