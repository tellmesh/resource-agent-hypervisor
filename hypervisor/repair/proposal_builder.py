from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor.evolution.proposal_from_source import build_repair_proposal_from_incident


def build_repair_proposal(
    incident: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    from hypervisor.paths import find_repo_root

    repo = repo_root or find_repo_root()
    return build_repair_proposal_from_incident(incident, repo_root=repo)


def link_proposal_to_incident(incident_path: Path, proposal: dict[str, Any]) -> None:
    payload = yaml.safe_load(incident_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{incident_path} must contain YAML mapping")
    payload["evolution"] = {
        "proposal_uri": proposal.get("proposal_uri"),
        "proposal_path": proposal.get("proposal_path"),
        "allowed": False,
        "requires_approval": True,
    }
    incident_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
