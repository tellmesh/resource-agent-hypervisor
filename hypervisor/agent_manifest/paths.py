from __future__ import annotations

from pathlib import Path


def manifests_root(repo: Path) -> Path:
    return repo / "agents" / "manifests"


def manifest_path_for_agent(repo: Path, agent_name: str) -> Path:
    return manifests_root(repo) / f"{agent_name}.markpact.md"
