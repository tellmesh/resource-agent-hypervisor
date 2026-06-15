from __future__ import annotations

from typing import Any
from urllib.parse import urlsplit

from hypervisor.deployment_registry.port_conflict import port_conflict_detail


BLOCKING_INCIDENT_CODES = frozenset(
    {
        "HEALTH_FAILED",
        "PROCESS_RUNNING_BUT_UNHEALTHY",
        "RUNTIME_STATE_STALE",
        "PROCESS_NOT_ALIVE",
        "COMMAND_HEALTH_MISMATCH",
        "CARD_FAILED",
        "PORT_OCCUPIED",
        "FOREIGN_SERVICE_ON_PORT",
    }
)


def _port_from_http_uri(uri: str | None) -> int | None:
    if not uri:
        return None
    parsed = urlsplit(uri)
    return parsed.port


def _port_conflict_incident(
    *,
    effective_port: int | None,
    health: dict[str, Any],
    expected_agent: str | None,
    run_plan: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not effective_port:
        return None
    return port_conflict_detail(
        port=effective_port,
        health=health,
        expected_agent=expected_agent,
        plan=run_plan,
    )


def _foreign_service_incident(
    *, health: dict[str, Any], effective_port: int | None
) -> dict[str, Any] | None:
    if not health.get("foreign_service"):
        return None
    return {
        "code": "FOREIGN_SERVICE_ON_PORT",
        "detail": f"health probe matched foreign service: {health.get('foreign_service')}",
        "uri": health.get("uri"),
        "effective_port": effective_port,
    }


def _runtime_incidents(*, runtime: str, process_alive: bool) -> list[dict[str, Any]]:
    incidents: list[dict[str, Any]] = []
    if runtime == "stale":
        incidents.append(
            {"code": "RUNTIME_STATE_STALE", "detail": "runtime state points to a dead process"}
        )
    if runtime == "running" and not process_alive:
        incidents.append(
            {
                "code": "PROCESS_NOT_ALIVE",
                "detail": "runtime status is running but pid is not alive",
            }
        )
    return incidents


def _health_incidents(
    *,
    process_alive: bool,
    health: dict[str, Any],
    effective_port: int | None,
) -> list[dict[str, Any]]:
    if process_alive and not health.get("ok"):
        return [
            {
                "code": "PROCESS_RUNNING_BUT_UNHEALTHY",
                "detail": "process is alive but HTTP health probe failed",
                "uri": health.get("uri"),
                "effective_port": effective_port,
            }
        ]
    if health.get("ok"):
        return []
    return [
        {
            "code": "HEALTH_FAILED",
            "detail": health.get("error") or f"health returned {health.get('status_code')}",
            "uri": health.get("uri"),
        }
    ]


def classify_incidents(
    *,
    runtime: str,
    process_alive: bool,
    deployment_health_uri: str | None,
    stored_health_uri: str,
    effective_health_uri: str,
    command_port: int | None,
    health: dict[str, Any],
    card: dict[str, Any],
    logs: dict[str, Any],
    expected_agent: str | None = None,
    run_plan: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    stored_port = _port_from_http_uri(stored_health_uri)
    effective_port = _port_from_http_uri(effective_health_uri)
    incidents: list[dict[str, Any]] = []

    for builder in (
        lambda: _port_conflict_incident(
            effective_port=effective_port,
            health=health,
            expected_agent=expected_agent,
            run_plan=run_plan,
        ),
        lambda: _foreign_service_incident(health=health, effective_port=effective_port),
    ):
        item = builder()
        if item:
            incidents.append(item)

    incidents.extend(_runtime_incidents(runtime=runtime, process_alive=process_alive))

    if command_port is not None and stored_port is not None and command_port != stored_port:
        incidents.append(
            {
                "code": "COMMAND_HEALTH_MISMATCH",
                "detail": "uvicorn command port differs from stored health_uri",
                "command_port": command_port,
                "stored_health_uri": stored_health_uri,
                "severity": "error",
            }
        )
    if deployment_health_uri and effective_health_uri and deployment_health_uri != effective_health_uri:
        incidents.append(
            {
                "code": "HEALTH_URI_DRIFT",
                "detail": "effective health URI differs from deployment registry health URI",
                "declared": deployment_health_uri,
                "effective": effective_health_uri,
                "severity": "warning",
            }
        )

    incidents.extend(
        _health_incidents(
            process_alive=process_alive,
            health=health,
            effective_port=effective_port,
        )
    )

    if card.get("uri") and not card.get("ok"):
        incidents.append(
            {
                "code": "CARD_FAILED",
                "detail": card.get("error") or f"card returned {card.get('status_code')}",
                "uri": card.get("uri"),
            }
        )
    if logs.get("error_count", 0) > 0:
        incidents.append(
            {
                "code": "RECENT_LOG_ERRORS",
                "detail": f"{logs['error_count']} recent error log entries matched",
                "uri": logs.get("uri"),
            }
        )
    return incidents


def blocking_incidents(incidents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [item for item in incidents if item.get("code") in BLOCKING_INCIDENT_CODES]
