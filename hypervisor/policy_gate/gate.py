from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    requires_approval: bool
    reasons: list[str]


def evaluate_change(change_report: dict[str, Any], approved: bool = False) -> GateDecision:
    reasons: list[str] = []
    breaking = bool(change_report.get("breaking_change"))
    if breaking:
        reasons.append("breaking_change detected")
    if change_report.get("removed_resources"):
        reasons.append("resource removal requires approval")
    if change_report.get("removed_capabilities"):
        reasons.append("capability removal requires approval")

    requires_approval = bool(reasons)
    allowed = not requires_approval or approved
    return GateDecision(allowed=allowed, requires_approval=requires_approval, reasons=reasons)
