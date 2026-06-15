from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from uri3.config.uri_yaml import load_uri_yaml


def _repo_config_dir(root: Path | None = None) -> Path:
    if root is not None:
        return Path(root) / "config"
    from hypervisor.paths import find_repo_root

    return find_repo_root() / "config"


def apply_uri_yaml_configs(cfg: dict[str, Any], *, root: Path | None = None) -> None:
    config_dir = _repo_config_dir(root)
    llm_path = config_dir / "llm.uri.yaml"
    if not llm_path.exists():
        return

    data = load_uri_yaml(llm_path)
    profiles = data.get("profiles") or {}
    profile_name = os.environ.get("DEFAULT_LLM_PROFILE") or (data.get("defaults") or {}).get("profile", "default")
    profile = profiles.get(profile_name) or profiles.get("default") or {}

    llm_cfg = cfg.setdefault("llm", {})
    if profile.get("model"):
        llm_cfg["model"] = profile["model"]
        llm_cfg["model_uri"] = profile["model"]
    if profile.get("api_key"):
        llm_cfg["api_key"] = profile["api_key"]
        llm_cfg["api_key_uri"] = profile["api_key"]
    if profile.get("provider"):
        llm_cfg["provider"] = profile["provider"]
    llm_cfg["profile"] = profile_name
    llm_cfg["uri_profiles"] = profiles
    llm_cfg["uri_config"] = str(llm_path)
