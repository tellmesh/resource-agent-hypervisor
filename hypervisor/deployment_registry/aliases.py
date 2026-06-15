from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


@lru_cache(maxsize=8)
def load_deployment_selector_aliases(root: str) -> dict[str, str]:
    """Load selector aliases from domain registry fragments (e.g. weather-agent → deployment id)."""
    root_path = Path(root)
    aliases: dict[str, str] = {}
    for fragment_path in sorted((root_path / "domains").glob("*/registry.fragment.yaml")):
        raw = _read_yaml(fragment_path)
        block = raw.get("deployment_selector_aliases") or {}
        if isinstance(block, dict):
            for alias, target in block.items():
                aliases[str(alias)] = str(target)
            continue
        if isinstance(block, list):
            target = raw.get("default_deployment_id")
            if target:
                for alias in block:
                    aliases[str(alias)] = str(target)
    return aliases
