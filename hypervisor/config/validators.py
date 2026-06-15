from __future__ import annotations

from typing import Any

from hypervisor.config.config_checks import (
    validate_hypervisor,
    validate_llm,
    validate_path_sections,
    validate_uri3,
)
from hypervisor.config.defaults import NESTED_SECTIONS


def merge_config(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    for key, value in overlay.items():
        if key in NESTED_SECTIONS and isinstance(value, dict):
            section = base.setdefault(key, {})
            if isinstance(section, dict):
                section.update(value)
            else:
                base[key] = value
        else:
            base[key] = value
    return base


def validate_config(cfg: dict[str, Any]) -> list[str]:
    return [
        *validate_hypervisor(cfg),
        *validate_llm(cfg),
        *validate_uri3(cfg),
        *validate_path_sections(cfg),
    ]
