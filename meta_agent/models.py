from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

import yaml

ProposalStatus = Literal["draft", "valid", "repaired", "generated", "failed"]


@dataclass
class AgentCreationIntent:
    """Normalized request to create an agent."""

    domain: str
    agent_name: str
    description: str
    resources: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    package: str | None = None


@dataclass
class RepairResult:
    changed: bool
    errors_before: list[str]
    errors_after: list[str]
    warnings: list[str]
    repaired_yaml: dict[str, Any]


@dataclass
class PipelineResult:
    status: ProposalStatus
    spec_path: str
    generated_path: str | None = None
    validation_errors: list[str] = field(default_factory=list)
    repair_warnings: list[str] = field(default_factory=list)
    verify_errors: list[str] = field(default_factory=list)


def dump_yaml(data: dict[str, Any]) -> str:
    return yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
