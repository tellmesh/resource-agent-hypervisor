from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from hypervisor.paths import find_repo_root
from hypervisor.repair.models import IncidentArtifact, Symptom
from hypervisor.repair.validator import validate_incident_dict


# Use shared now_iso to eliminate duplication (flagged in architecture audits).
from ..deployment_registry.runtime_state import now_iso as _now_iso


def _incident_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    return f"inc_{stamp}"


def incident_uri(agent_id: str, incident_id: str) -> str:
    return f"incident://agent/{agent_id}/{incident_id}"


def incident_storage_path(repo_root: Path, agent_id: str, incident_id: str) -> Path:
    day = datetime.now(UTC).strftime("%Y-%m-%d")
    return repo_root / "output" / "incidents" / day / agent_id / f"{incident_id}.yaml"


def _symptom_from_item(item: dict[str, Any], *, default_code: str, severity: str) -> Symptom:
    code = str(item.get("code") or default_code)
    message = str(item.get("detail") or item.get("code") or default_code.lower())
    return Symptom(code=code, message=message, severity=severity)


def _symptoms_from_inspection(inspection: dict[str, Any]) -> list[Symptom]:
    symptoms = [
        _symptom_from_item(item, default_code="UNKNOWN", severity="error")
        for item in inspection.get("incidents") or []
    ]
    symptoms.extend(
        _symptom_from_item(item, default_code="WARNING", severity="warning")
        for item in inspection.get("warnings") or []
    )
    if not symptoms:
        symptoms.append(
            Symptom(
                code="SERVICE_UNHEALTHY",
                message="Agent inspection reported degraded service status.",
                severity="error",
            )
        )
    return symptoms


def _incident_uri_block(agent_id: str, metadata_id: str, inspection: dict[str, Any]) -> dict[str, str]:
    agent_ref = inspection.get("agent_ref") or f"agent://{agent_id.split('.')[0]}"
    return {
        "self": incident_uri(agent_id, metadata_id),
        "subject": str(agent_ref),
        "deployment": f"hypervisor://local/{agent_id}",
        "runtime_state": f"runtime://agent/{agent_id}/state",
        "health": f"health://agent/{agent_id}",
        "logs": str(inspection.get("log_uri") or f"log://hypervisor?grep={agent_id}"),
    }


def _incident_status_block(
    inspection: dict[str, Any], readiness: dict[str, Any], health: dict[str, Any]
) -> dict[str, str]:
    ok = bool(inspection.get("ok"))
    return {
        "lifecycle_status": str(
            inspection.get("runtime_status") or readiness.get("process") or "unknown"
        ),
        "health_status": "ok" if health.get("ok") else "failed",
        "workflow_status": "completed" if ok else "failed",
        "execution_status": "completed",
        "service_result_status": "succeeded" if ok else "failed",
    }


def _incident_evidence(
    inspection: dict[str, Any],
    *,
    agent_id: str,
    readiness: dict[str, Any],
    process: dict[str, Any],
    health: dict[str, Any],
    logs: dict[str, Any],
) -> dict[str, Any]:
    runtime_state = inspection.get("runtime_state") or {}
    return {
        "runtime": {
            "pid": process.get("pid"),
            "running": process.get("running"),
            "effective_port": readiness.get("effective_port"),
            "declared_health_uri": readiness.get("declared_health_uri"),
            "effective_health_uri": readiness.get("effective_health_uri"),
            "runtime_state_path": str(
                find_repo_root() / "output" / "runtime" / "agents" / agent_id / "state.json"
            ),
            "command": runtime_state.get("command"),
            "stored_health_uri": runtime_state.get("health_uri"),
        },
        "health_check": {
            "uri": health.get("uri"),
            "ok": health.get("ok"),
            "status_code": health.get("status_code"),
            "error": health.get("error"),
        },
        "logs": {
            "uri": logs.get("uri") or inspection.get("log_uri"),
            "error_count": logs.get("error_count", 0),
            "entries": (logs.get("entries") or [])[:5],
        },
    }


def build_incident_from_inspection(
    inspection: dict[str, Any],
    *,
    classification: dict[str, Any] | None = None,
    created_by: str = "agent://repair-supervisor",
    source: str | None = None,
) -> IncidentArtifact:
    agent_id = str(inspection["id"])
    metadata_id = _incident_id()
    readiness = inspection.get("agent_readiness") or inspection.get("readiness") or {}
    process = inspection.get("process") or {}
    health = inspection.get("health") or {}
    logs = inspection.get("log_errors") or {}

    return IncidentArtifact(
        metadata_id=metadata_id,
        agent_id=agent_id,
        created_at=_now_iso(),
        created_by=created_by,
        source=source or f"hypervisor://agent/{agent_id}/supervise",
        uri=_incident_uri_block(agent_id, metadata_id, inspection),
        status=_incident_status_block(inspection, readiness, health),
        symptoms=_symptoms_from_inspection(inspection),
        evidence=_incident_evidence(
            inspection,
            agent_id=agent_id,
            readiness=readiness,
            process=process,
            health=health,
            logs=logs,
        ),
        classification=classification or {},
    )


def write_incident(
    incident: IncidentArtifact,
    *,
    repo_root: Path | None = None,
) -> Path:
    repo = repo_root or find_repo_root()
    payload = incident.to_dict(repo_root=repo)
    errors = validate_incident_dict(payload, repo)
    if errors:
        raise ValueError(f"incident validation failed: {errors[:3]}")
    path = incident_storage_path(repo, incident.agent_id, incident.metadata_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(payload, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path


def load_incident(path: str | Path, *, repo_root: Path | None = None) -> dict[str, Any]:
    repo = repo_root or find_repo_root()
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain YAML mapping")
    errors = validate_incident_dict(payload, repo)
    if errors:
        raise ValueError(f"invalid incident artifact: {errors[:3]}")
    return payload
