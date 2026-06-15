from __future__ import annotations

import os
from pathlib import Path


def _is_hypervisor_root(path: Path) -> bool:
    return (
        (path / "pyproject.toml").is_file()
        and (path / "examples").is_dir()
        and (path / "deployments" / "agent_deployments.yaml").is_file()
    )


def _walk_hypervisor_root(start: Path) -> Path | None:
    current = start.resolve()
    if current.is_file():
        current = current.parent
    for path in (current, *current.parents):
        if _is_hypervisor_root(path):
            return path
    return None


def find_repo_root(start: Path | None = None, *, strict: bool = True) -> Path:
    """Locate the hypervisor monorepo root (not an external uri3 checkout)."""
    env_root = os.environ.get("HYPERVISOR_REPO_ROOT")
    if env_root:
        return Path(env_root).resolve()

    if start is None:
        found = _walk_hypervisor_root(Path.cwd())
        if found is not None:
            return found
        start = Path(__file__)

    found = _walk_hypervisor_root(start)
    if found is not None:
        return found

    if strict:
        raise FileNotFoundError(
            "Hypervisor repository root not found (expected examples/ and deployments/agent_deployments.yaml)"
        )
    return Path.cwd()


def repo_root() -> Path:
    return find_repo_root()


def _looks_like_www(path: Path) -> bool:
    return path.is_dir() and (path / "index.html").is_file()


def resolve_www_dir(start: Path | None = None) -> Path | None:
    """Return TellMesh product www/ (tellmesh/www checkout, local copy, or env override)."""
    env = os.environ.get("HYPERVISOR_WWW_DIR")
    if env:
        candidate = Path(env).expanduser().resolve()
        if _looks_like_www(candidate):
            return candidate

    repo = find_repo_root(start, strict=False)
    sibling = repo.parent.parent / "tellmesh" / "www"
    if _looks_like_www(sibling):
        return sibling

    local = repo / "www"
    if _looks_like_www(local):
        return local

    return None


__all__ = ["find_repo_root", "repo_root", "resolve_www_dir"]
