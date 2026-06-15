from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from hypervisor.config.defaults import (
    DEFAULT_CONFIG_NAMES,
    apply_builtin_defaults,
    get_default_config,
    load_yaml_file,
)
from hypervisor.config.env import apply_env_overrides
from hypervisor.config.models import HypervisorConfig
from hypervisor.config.uri_config import apply_uri_yaml_configs
from hypervisor.config.validators import merge_config, validate_config
from hypervisor.paths import find_repo_root


def config_search_paths(
    *,
    explicit_path: str | Path | None = None,
    search_paths: list[Path] | None = None,
) -> list[Path]:
    candidates: list[Path] = []
    if explicit_path:
        candidates.append(Path(explicit_path).expanduser().resolve())
    if search_paths:
        candidates.extend(search_paths)

    for name in DEFAULT_CONFIG_NAMES:
        candidates.append(Path.cwd() / name)

    xdg = os.environ.get("XDG_CONFIG_HOME")
    config_home = Path(xdg) if xdg else Path.home() / ".config" / "hypervisor"
    for name in DEFAULT_CONFIG_NAMES:
        candidates.append(config_home / name)

    return candidates


def resolve_config_path(
    *,
    explicit_path: str | Path | None = None,
    search_paths: list[Path] | None = None,
) -> Path | None:
    for candidate in config_search_paths(
        explicit_path=explicit_path,
        search_paths=search_paths,
    ):
        if candidate.exists():
            return candidate
    return None


def load_config(
    path: str | Path | None = None,
    *,
    search_paths: list[Path] | None = None,
) -> dict[str, Any]:
    """
    Load configuration with precedence:
    1. Explicit path (if given)
    2. ./hypervisor.yaml or ./nlp2uri.yaml (cwd)
    3. XDG config dir
    4. Package embedded defaults
    """
    cfg = get_default_config()
    resolved = resolve_config_path(explicit_path=path, search_paths=search_paths)

    if resolved is not None:
        merge_config(cfg, load_yaml_file(resolved))
        cfg["_config_path"] = str(resolved)
    else:
        cfg["_config_path"] = "<embedded-defaults>"

    apply_builtin_defaults(cfg)
    try:
        apply_uri_yaml_configs(cfg, root=find_repo_root())
    except FileNotFoundError:
        pass
    apply_env_overrides(cfg)
    return cfg


def get_config() -> dict[str, Any]:
    """Return a freshly loaded configuration."""
    return load_config()


def load_hypervisor_config(
    path: str | Path | None = None,
    *,
    search_paths: list[Path] | None = None,
) -> HypervisorConfig:
    return HypervisorConfig.from_dict(load_config(path, search_paths=search_paths))
