from __future__ import annotations

from pathlib import Path
from typing import Any

from uri3.artifacts.evolution_source import (
    EvolutionSource,
    attach_evolution_source,
    evolution_proposal_uri,
    normalize_evolution_source,
)
from uri3.artifacts.writer import write_yaml_artifact

EVOLUTION_PROPOSAL_SCHEMA = "schemas/evolution_proposal.schema.json"


def build_evolution_proposal(
    source: EvolutionSource,
    *,
    change_type: str,
    reason: str,
    repo_root: Path,
    spec_extra: dict[str, Any] | None = None,
    metadata_extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    proposal_id = f"proposal_from_{source.uri.rsplit('/', 1)[-1].replace(':', '_')}"
    proposals_dir = repo_root / "evolution" / "proposals"
    proposals_dir.mkdir(parents=True, exist_ok=True)
    proposal_path = proposals_dir / f"{proposal_id}.yaml"
    metadata = {
        "id": proposal_id,
        "created_by": "agent://evolution-planner",
        **(metadata_extra or {}),
    }
    payload: dict[str, Any] = {
        "$schema": EVOLUTION_PROPOSAL_SCHEMA,
        "apiVersion": "uri3.io/v1",
        "kind": "EvolutionProposal",
        "metadata": metadata,
        "uri": {
            "self": evolution_proposal_uri(source),
            "source": source.uri,
        },
        "spec": {
            "change_type": change_type,
            "reason": reason,
            **(spec_extra or {}),
        },
        "proposal_id": proposal_id,
        "type": change_type,
        "reason": reason,
    }
    payload = attach_evolution_source(payload, source)
    write_yaml_artifact(
        proposal_path,
        payload,
        repo_root=repo_root,
        schema_relative=EVOLUTION_PROPOSAL_SCHEMA,
        validate=True,
    )
    return {
        "ok": True,
        "proposal_id": proposal_id,
        "proposal_path": str(proposal_path),
        "proposal_uri": payload["uri"]["self"],
        "payload": payload,
    }


def build_repair_proposal_from_incident(
    incident: dict[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    metadata = incident.get("metadata") or {}
    incident_id = str(metadata.get("id") or "inc_unknown")
    classification = incident.get("classification") or {}
    families = classification.get("family") or ["HEALTH_TIMEOUT"]
    source_uri = str((incident.get("uri") or {}).get("self") or f"incident://unknown/{incident_id}")
    source = normalize_evolution_source(uri=source_uri, kind="Incident", schema="schemas/incident.schema.json")
    return build_evolution_proposal(
        source,
        change_type="add_repair_capability",
        reason=(
            f"Unresolved incident {source_uri} requires new repair capability "
            f"for {', '.join(families)}."
        ),
        repo_root=repo_root,
        spec_extra={
            "target": {"uri": f"repair-agent://{'-'.join(f.lower() for f in families[:2])}"},
            "creates": [
                {
                    "uri": "repair://agent/{agent_id}/diagnose-health",
                    "schema": "schemas/repair_plan.schema.json",
                }
            ],
        },
        metadata_extra={"source_incident": source_uri},
    )


def build_evolution_proposal_from_ticket(
    ticket: dict[str, Any],
    *,
    repo_root: Path,
) -> dict[str, Any]:
    metadata = ticket.get("metadata") or {}
    ticket_id = str(metadata.get("id") or "ticket_unknown")
    spec = ticket.get("spec") or {}
    ticket_type = str(spec.get("type") or "feature")
    source_uri = str((ticket.get("uri") or {}).get("self") or f"ticket://{ticket_type}/{ticket_id}")
    source = normalize_evolution_source(uri=source_uri, kind="Ticket", schema="schemas/ticket.schema.json")
    change_type = "add_capability" if ticket_type == "feature" else "add_repair_capability"
    if ticket_type == "architecture":
        change_type = "breaking_change"
    return build_evolution_proposal(
        source,
        change_type=change_type,
        reason=str(spec.get("description") or spec.get("title") or f"Ticket {ticket_id}"),
        repo_root=repo_root,
        spec_extra={
            "target": {"uri": source_uri, "kind": "Ticket"},
            "scope": ticket.get("scope"),
            "verification": ticket.get("verification"),
        },
        metadata_extra={"source_ticket": source_uri},
    )
