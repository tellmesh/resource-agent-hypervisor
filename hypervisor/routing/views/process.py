from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.selector import resolve_deployment
from hypervisor.deployment_registry.supervisor import inspect_agent
from hypervisor.paths import find_repo_root


def _human_title(agent_ref: str, agent_id: str) -> str:
    name = agent_ref.replace("agent://", "").replace("-", " ").title()
    return name or agent_id


def _related_uris(agent_id: str, inspection: dict[str, Any]) -> dict[str, str]:
    related = {
        "view": f"view://process/agent/{agent_id}/latest",
        "runtime": f"runtime://agent/{agent_id}/state",
        "health": f"health://agent/{agent_id}",
        "diagnose": f"repair://agent/{agent_id}/diagnose",
        "logs": str(inspection.get("log_uri") or f"log://hypervisor?grep={agent_id}"),
    }
    if inspection.get("effective_health_uri"):
        related["effective_health"] = str(inspection["effective_health_uri"])
    return related


def _process_actions(agent_id: str, related: dict[str, str]) -> list[dict[str, Any]]:
    return [
        {
            "label": "Diagnose",
            "uri": related["diagnose"],
            "requires_approval": False,
            "kind": "read",
        },
        {
            "label": "View runtime state",
            "uri": related["runtime"],
            "requires_approval": False,
            "kind": "read",
        },
        {
            "label": "Read error logs",
            "uri": related["logs"],
            "requires_approval": False,
            "kind": "read",
        },
        {
            "label": "Apply safe repair",
            "uri": f"repair://agent/{agent_id}/apply",
            "requires_approval": True,
            "kind": "repair",
        },
        {
            "label": "Create ticket from incident",
            "uri": f"ticket://bug/from-incident/{agent_id}",
            "requires_approval": True,
            "kind": "mutation",
        },
    ]


def _process_status_fields(
    inspection: dict[str, Any],
    readiness: dict[str, Any],
    summary: dict[str, Any],
) -> dict[str, str]:
    service_status = str(inspection.get("service_status") or "unknown")
    return {
        "service_status": service_status,
        "deployment_status": str(readiness.get("deployment_status") or service_status),
        "process_status": str(
            readiness.get("process_status") or summary.get("process") or "unknown"
        ),
        "health_status": str(readiness.get("health_status") or summary.get("health") or "unknown"),
        "recommended_action": str(readiness.get("recommended_action") or "observe"),
    }


def build_process_view_data(agent_id: str, *, root: Path | None = None) -> dict[str, Any]:
    repo = root or find_repo_root()
    deployment = resolve_deployment(agent_id, root=repo)
    inspection = inspect_agent(agent_id, root=repo)
    readiness = inspection.get("agent_readiness") or {}
    summary = inspection.get("readiness") or readiness.get("summary") or {}
    related = _related_uris(agent_id, inspection)
    status_fields = _process_status_fields(inspection, readiness, summary)
    return {
        "view_kind": "process",
        "agent_id": agent_id,
        "agent_ref": deployment.agent_ref,
        "title": _human_title(deployment.agent_ref, agent_id),
        **status_fields,
        "status": status_fields["service_status"],
        "effective_health_uri": inspection.get("effective_health_uri"),
        "effective_port": summary.get("effective_port") or readiness.get("effective_port"),
        "incidents": list(inspection.get("incidents") or []),
        "warnings": list(inspection.get("warnings") or []),
        "readiness": readiness,
        "related_uris": related,
        "actions": _process_actions(agent_id, related),
        "inspection": inspection,
    }
