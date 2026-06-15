from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

API_VERSION = "uri3.io/v1"
INCIDENT_SCHEMA = "schemas/incident.schema.json"
REPAIR_PLAN_SCHEMA = "schemas/repair_plan.schema.json"
RUNTIME_STATE_SCHEMA = "schemas/runtime_state.schema.json"


@dataclass
class Symptom:
    code: str
    message: str
    severity: str = "error"

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message, "severity": self.severity}


@dataclass
class IncidentArtifact:
    metadata_id: str
    agent_id: str
    created_at: str
    created_by: str
    source: str
    uri: dict[str, str]
    status: dict[str, str]
    symptoms: list[Symptom]
    evidence: dict[str, Any] = field(default_factory=dict)
    classification: dict[str, Any] = field(default_factory=dict)
    repair: dict[str, Any] = field(default_factory=dict)
    evolution: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self, *, repo_root: Path) -> dict[str, Any]:
        return {
            "$schema": INCIDENT_SCHEMA,
            "apiVersion": API_VERSION,
            "kind": "Incident",
            "metadata": {
                "id": self.metadata_id,
                "created_at": self.created_at,
                "created_by": self.created_by,
                "source": self.source,
                "agent_id": self.agent_id,
            },
            "uri": self.uri,
            "status": self.status,
            "symptoms": [item.to_dict() for item in self.symptoms],
            "evidence": self.evidence,
            "classification": self.classification,
            "repair": self.repair,
            "evolution": self.evolution,
            "result": self.result,
        }

    @property
    def self_uri(self) -> str:
        return self.uri["self"]
