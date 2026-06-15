from __future__ import annotations

from typing import Any

from hypervisor.deployment_registry.port_utils import is_port_free
from hypervisor.deployment_registry.process_discovery import (
    command_line,
    command_matches_plan,
    pids_listening_on_port,
)


def classify_port_listeners(
    port: int,
    *,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Classify TCP listeners on a port without terminating any process."""
    listeners: list[dict[str, Any]] = []
    for pid in sorted(pids_listening_on_port(port)):
        command = command_line(pid)
        owned = bool(plan and command_matches_plan(pid, plan))
        listeners.append(
            {
                "pid": pid,
                "command": command,
                "owned_by_agent": owned,
            }
        )
    foreign = [item for item in listeners if not item["owned_by_agent"]]
    free = is_port_free(port)
    return {
        "port": port,
        "free": free,
        "occupied": not free,
        "listeners": listeners,
        "foreign_listeners": foreign,
        "conflict": not free and bool(foreign),
    }


def port_conflict_detail(
    *,
    port: int,
    health: dict[str, Any],
    expected_agent: str | None,
    plan: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return enriched PORT_OCCUPIED incident data when a foreign listener holds the port."""
    from hypervisor.deployment_registry.port_utils import health_matches_agent

    probe = classify_port_listeners(port, plan=plan)
    if probe["free"]:
        return None
    if not probe["conflict"]:
        return None
    if health_matches_agent(health, expected_agent=expected_agent):
        return None

    foreign = health.get("foreign_service")
    detail = f"port {port} is in use by another service"
    if foreign:
        detail += f" ({foreign})"
    elif probe["foreign_listeners"]:
        first = probe["foreign_listeners"][0]
        detail += f" (pid {first['pid']}: {first['command'][:120]})"
    elif probe["listeners"]:
        first = probe["listeners"][0]
        detail += f" (pid {first['pid']}: {first['command'][:120]})"

    return {
        "code": "PORT_OCCUPIED",
        "detail": detail,
        "effective_port": port,
        "foreign_service": foreign,
        "port_probe": probe,
    }
