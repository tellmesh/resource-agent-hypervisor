from __future__ import annotations

from pathlib import Path

from hypervisor.paths import repo_root


def write_file(path: Path, content: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return str(path)
