from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AgentDescribeReport:
    selector: str
    markdown: str
    data: dict[str, Any] = field(default_factory=dict)

    def write(self, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.markdown, encoding="utf-8")
        return path
