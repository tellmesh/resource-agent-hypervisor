from __future__ import annotations

import os
from typing import Any


def _parse_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def apply_legacy_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    for key in ("platform", "host_platform", "locale", "capture_dir"):
        env_key = f"NLP2URI_{key.upper()}"
        if env_key in os.environ:
            cfg[key] = os.environ[env_key]

    if "NLP2URI_DRY_RUN" in os.environ:
        cfg["dry_run"] = _parse_bool(os.environ["NLP2URI_DRY_RUN"])

    for key in ("log_level", "max_agents", "default_profile"):
        env_key = f"HYPERVISOR_{key.upper()}"
        if env_key in os.environ:
            cfg.setdefault("hypervisor", {})[key] = os.environ[env_key]

    return cfg


def apply_structured_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    if provider := os.environ.get("HYPERVISOR_LLM_PROVIDER"):
        cfg.setdefault("llm", {})["provider"] = provider
    if model_uri := os.environ.get("HYPERVISOR_LLM_MODEL_URI", os.environ.get("LLM_MODEL")):
        cfg.setdefault("llm", {})["model_uri"] = model_uri
    if api_key_uri := os.environ.get("HYPERVISOR_LLM_API_KEY_URI"):
        cfg.setdefault("llm", {})["api_key_uri"] = api_key_uri

    if registry_path := os.environ.get("HYPERVISOR_REGISTRY_PATH"):
        cfg.setdefault("registry", {})["path"] = registry_path
    if registry_output := os.environ.get("HYPERVISOR_REGISTRY_OUTPUT"):
        cfg.setdefault("registry", {})["output"] = registry_output

    if domain_root := os.environ.get("HYPERVISOR_DOMAIN_PACK_ROOT"):
        cfg.setdefault("domain_pack", {})["root"] = domain_root
    if generated_root := os.environ.get("HYPERVISOR_AGENTS_GENERATED_ROOT"):
        cfg.setdefault("agents", {})["generated_root"] = generated_root
    if deployment_registry := os.environ.get("HYPERVISOR_DEPLOYMENT_REGISTRY"):
        cfg.setdefault("deployment", {})["registry"] = deployment_registry

    return cfg


def apply_env_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    apply_legacy_env_overrides(cfg)
    apply_structured_env_overrides(cfg)
    return cfg
