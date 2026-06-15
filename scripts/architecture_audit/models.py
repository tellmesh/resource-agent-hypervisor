from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModuleEntry:
    path: str
    lines: int
    area: str


@dataclass(frozen=True)
class DupFragment:
    path: str
    start: int
    end: int
    symbol: str
    area: str


@dataclass(frozen=True)
class DupGroup:
    digest: str
    flagged: bool
    kind: str
    name: str
    lines: int
    fragments_count: int
    saved_lines: int
    similarity: float | None
    fragments: tuple[DupFragment, ...]


@dataclass
class Finding:
    severity: str
    category: str
    title: str
    detail: str
    recommendation: str
    paths: list[str] = field(default_factory=list)
    evidence: dict[str, object] = field(default_factory=dict)
    priority: str = "P2"


@dataclass
class AuditResult:
    summary: dict[str, object]
    areas: list[dict[str, object]]
    findings: list[Finding]
    refactor_backlog: list[dict[str, object]]
    gates: list[str]
