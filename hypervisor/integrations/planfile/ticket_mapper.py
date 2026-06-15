from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor.evolution.proposal_from_source import build_evolution_proposal_from_ticket
from hypervisor.repair.validator import validate_ticket_dict
from uri3.artifacts.writer import write_yaml_artifact

TICKET_SCHEMA = "schemas/ticket.schema.json"


def _ticket_uri(ticket_type: str, ticket_id: str) -> str:
    return f"ticket://{ticket_type}/{ticket_id}"


def planfile_task_to_ticket(task: dict[str, Any], *, sprint_id: str | int, strategy_uri: str) -> dict[str, Any]:
    ticket_id = str(task.get("id") or "PL-unknown")
    ticket_type = str(task.get("type") or "feature")
    return {
        "$schema": TICKET_SCHEMA,
        "apiVersion": "uri3.io/v1",
        "kind": "Ticket",
        "metadata": {
            "id": ticket_id,
            "created_at": task.get("created_at") or "",
            "created_by": "planfile://strategy/import",
            "source": strategy_uri,
        },
        "uri": {
            "self": _ticket_uri(ticket_type, ticket_id),
            "source_strategy": strategy_uri,
            "proposal": f"evolution://proposal/from-ticket/{ticket_id}",
        },
        "spec": {
            "type": ticket_type,
            "title": str(task.get("title") or ticket_id),
            "description": str(task.get("description") or ""),
            "priority": str(task.get("priority") or "normal"),
            "sprint": sprint_id,
        },
        "scope": {"affected_uris": list(task.get("affected_uris") or [])},
        "acceptance_criteria": list(task.get("acceptance_criteria") or []),
        "verification": {"required": list(task.get("verification") or [])},
    }


def load_planfile_strategy(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain YAML mapping")
    return payload


def import_tickets_from_planfile(
    strategy_path: Path,
    *,
    repo_root: Path,
    sprint_id: str | int | None = None,
) -> dict[str, Any]:
    strategy = load_planfile_strategy(strategy_path)
    strategy_uri = f"planfile://strategy/{strategy.get('name') or strategy_path.stem}"
    tickets_dir = repo_root / "output" / "tickets"
    tickets_dir.mkdir(parents=True, exist_ok=True)
    imported: list[dict[str, Any]] = []
    for sprint in strategy.get("sprints") or []:
        if sprint_id is not None and str(sprint.get("id")) != str(sprint_id):
            continue
        sid = sprint.get("id") or "0"
        for task in sprint.get("tasks") or []:
            if not isinstance(task, dict):
                continue
            ticket = planfile_task_to_ticket(task, sprint_id=sid, strategy_uri=strategy_uri)
            out = tickets_dir / f"{ticket['metadata']['id']}.yaml"
            write_yaml_artifact(
                out,
                ticket,
                repo_root=repo_root,
                schema_relative=TICKET_SCHEMA,
                validate=True,
            )
            imported.append({"path": str(out), "uri": ticket["uri"]["self"]})
    return {"ok": True, "imported": imported, "count": len(imported)}


def propose_from_ticket_path(ticket_path: Path, *, repo_root: Path) -> dict[str, Any]:
    ticket = yaml.safe_load(ticket_path.read_text(encoding="utf-8"))
    if not isinstance(ticket, dict):
        raise ValueError(f"{ticket_path} must contain YAML mapping")
    errors = validate_ticket_dict(ticket, repo_root)
    if errors:
        raise ValueError(f"ticket validation failed: {'; '.join(errors)}")
    return build_evolution_proposal_from_ticket(ticket, repo_root=repo_root)
