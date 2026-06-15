from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class EvolutionProposal:
    proposal_id: str
    type: str
    reason: str
    adds: dict[str, Any] = field(default_factory=dict)
    changes: dict[str, Any] = field(default_factory=dict)
    compatibility: dict[str, Any] = field(default_factory=dict)


def load_proposal(path: str | Path) -> EvolutionProposal:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path} must contain YAML mapping")
    return EvolutionProposal(
        proposal_id=raw["proposal_id"],
        type=raw.get("type", "change"),
        reason=raw.get("reason", ""),
        adds=raw.get("adds", {}) or {},
        changes=raw.get("changes", {}) or {},
        compatibility=raw.get("compatibility", {}) or {},
    )
