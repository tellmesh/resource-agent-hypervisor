from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DomainModel:
    tree: dict[str, Any]
    domain_id: str
    domain: dict[str, Any]
    agent: dict[str, Any]
    out_dir: Path

    @classmethod
    def from_uri_tree(cls, tree: dict[str, Any], out_dir: Path) -> DomainModel:
        domain = tree["domain"]
        return cls(
            tree=tree,
            domain_id=domain["id"],
            domain=domain,
            agent=tree["agent"],
            out_dir=out_dir,
        )
