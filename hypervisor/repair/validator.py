from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from uri3.artifacts.validator import validate_artifact, validate_artifact_file

__all__ = [
    "read_yaml",
    "validate_artifact",
    "validate_artifact_file",
    "validate_incident_dict",
    "validate_repair_plan_dict",
    "validate_evolution_proposal_dict",
    "validate_runtime_state_dict",
    "validate_ticket_dict",
]


def validate_incident_dict(data: dict[str, Any], repo_root: Path) -> list[str]:
    from hypervisor.repair.models import INCIDENT_SCHEMA

    return validate_artifact(data, repo_root, INCIDENT_SCHEMA)


def validate_repair_plan_dict(data: dict[str, Any], repo_root: Path) -> list[str]:
    from hypervisor.repair.models import REPAIR_PLAN_SCHEMA

    return validate_artifact(data, repo_root, REPAIR_PLAN_SCHEMA)


def validate_evolution_proposal_dict(data: dict[str, Any], repo_root: Path) -> list[str]:
    return validate_artifact(data, repo_root, "schemas/evolution_proposal.schema.json")


def validate_runtime_state_dict(data: dict[str, Any], repo_root: Path) -> list[str]:
    from hypervisor.deployment_registry.runtime_state import RUNTIME_STATE_SCHEMA

    return validate_artifact(data, repo_root, RUNTIME_STATE_SCHEMA)


def validate_ticket_dict(data: dict[str, Any], repo_root: Path) -> list[str]:
    return validate_artifact(data, repo_root, "schemas/ticket.schema.json")


def read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return payload
