from __future__ import annotations

from typing import Any


def validate_hypervisor(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    hypervisor = cfg.get("hypervisor") or {}
    max_agents = hypervisor.get("max_agents")
    if max_agents is not None:
        try:
            if int(max_agents) < 1:
                errors.append("hypervisor.max_agents must be >= 1")
        except (TypeError, ValueError):
            errors.append("hypervisor.max_agents must be an integer")

    profile = hypervisor.get("default_profile")
    if profile is not None and profile not in {"normal", "fast", "full"}:
        errors.append("hypervisor.default_profile must be one of: normal, fast, full")
    return errors


def validate_llm(cfg: dict[str, Any]) -> list[str]:
    llm = cfg.get("llm") or {}
    if llm.get("model_uri") and not str(llm["model_uri"]).startswith("llm://"):
        return ["llm.model_uri must use llm:// scheme"]
    return []


def validate_uri3(cfg: dict[str, Any]) -> list[str]:
    uri3 = cfg.get("uri3") or {}
    schemes = uri3.get("enabled_schemes")
    if schemes is not None and not isinstance(schemes, list):
        return ["uri3.enabled_schemes must be a list"]
    return []


def validate_path_sections(cfg: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for section, key in (
        ("registry", "path"),
        ("registry", "output"),
        ("domain_pack", "root"),
        ("agents", "generated_root"),
        ("deployment", "registry"),
    ):
        value = (cfg.get(section) or {}).get(key)
        if value is not None and not str(value).strip():
            errors.append(f"{section}.{key} must not be empty")
    return errors
