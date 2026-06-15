"""Resolve hypervisor monorepo root from tellmesh package scripts."""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path


def hypervisor_root(start: Path | None = None) -> Path:
    env = os.environ.get("HYPERVISOR_REPO_ROOT")
    if env:
        return Path(env).expanduser().resolve()

    here = (start or Path(__file__)).resolve()
    if here.is_file():
        here = here.parent

    for path in (here, *here.parents):
        if (
            (path / "deployments" / "agent_deployments.yaml").is_file()
            and (path / "examples").is_dir()
            and (path / "pyproject.toml").is_file()
        ):
            return path

    for path in (here, *here.parents):
        if path.name == "tellmesh" and (path / "tellmesh" / "pyproject.toml").is_file():
            return (path / "tellmesh").resolve()

    for path in (here, *here.parents):
        if path.name == "tellmesh":
            candidate = path.parent / "wronai" / "hypervisor"
            if candidate.is_dir():
                return candidate.resolve()

    return Path("/home/tom/github/tellmesh/tellmesh").resolve()


_HYPERVISOR_PATHS = Path(__file__).resolve().parents[2] / "hypervisor" / "hypervisor" / "paths.py"


def www_dir() -> Path:
    """Return TellMesh www checkout (tellmesh/www or env override)."""
    spec = importlib.util.spec_from_file_location("hypervisor_paths", _HYPERVISOR_PATHS)
    if spec is None or spec.loader is None:
        raise SystemExit(f"missing hypervisor paths module: {_HYPERVISOR_PATHS}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    resolved = module.resolve_www_dir(hypervisor_root())
    if resolved is None or not (resolved / "index.html").is_file():
        tellmesh_www = Path(__file__).resolve().parents[2] / "www"
        raise SystemExit(
            "TellMesh www checkout not found. "
            f"Expected {tellmesh_www}/index.html or set HYPERVISOR_WWW_DIR."
        )
    return resolved
