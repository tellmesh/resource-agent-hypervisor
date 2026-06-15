from __future__ import annotations

from pathlib import Path
from typing import Any

from uri3.config.uri_yaml import load_uri_yaml


def repo_config_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root) / "config"
    from uri3.config.repo_root import find_repo_root

    return find_repo_root() / "config"


def load_deployments_uri_config(root: Path | None = None) -> dict[str, Any]:
    path = repo_config_dir(root) / "deployments.uri.yaml"
    if not path.exists():
        return {"version": 1, "defaults": {}, "deployments": {}}
    return load_uri_yaml(path)


def load_runtime_uri_config(root: Path | None = None) -> dict[str, Any]:
    path = repo_config_dir(root) / "runtime.uri.yaml"
    if not path.exists():
        return {"version": 1, "defaults": {}, "agents": {}}
    return load_uri_yaml(path)
