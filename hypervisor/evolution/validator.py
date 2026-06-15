from __future__ import annotations

from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from hypervisor.repair.validator import validate_evolution_proposal_dict


def validate_proposal_dict(payload: dict[str, Any], repo_root: Path) -> list[str]:
    if payload.get("kind") == "EvolutionProposal":
        return validate_evolution_proposal_dict(payload, repo_root)
    errors: list[str] = []
    if not payload.get("proposal_id") and not (payload.get("metadata") or {}).get("id"):
        errors.append("proposal_id or metadata.id is required")
    change_type = payload.get("type") or (payload.get("spec") or {}).get("change_type")
    if change_type not in {
        "new_agent",
        "add_capability",
        "add_resource",
        "change",
        "modify_agent",
        "add_repair_capability",
        "breaking_change",
    }:
        errors.append(f"unsupported proposal type: {change_type}")
    reason = payload.get("reason") or (payload.get("spec") or {}).get("reason")
    if not reason:
        errors.append("reason is required")
    compatibility = payload.get("compatibility") or {}
    if compatibility.get("breaking_change") and not compatibility.get("requires_approval"):
        errors.append("breaking changes must set compatibility.requires_approval=true")
    return errors


def validate_proposal(proposal) -> list[str]:
    from hypervisor.paths import find_repo_root

    if hasattr(proposal, "to_dict"):
        payload = proposal.to_dict()
    elif is_dataclass(proposal):
        payload = asdict(proposal)
    else:
        payload = dict(proposal)
    return validate_proposal_dict(payload, find_repo_root())
