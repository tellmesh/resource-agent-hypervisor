from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor.contract_registry.loader import load_contract_registry


def _load_policy(root: Path) -> dict[str, Any]:
    path = root / "contracts" / "compatibility" / "policy.yaml"
    if not path.exists():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def classify_registry_change(old_root: str | Path, new_root: str | Path) -> dict[str, Any]:
    old_root = Path(old_root)
    new_root = Path(new_root)
    old = load_contract_registry(old_root)
    new = load_contract_registry(new_root)

    old_uris = {r.uri for r in old.resources}
    new_uris = {r.uri for r in new.resources}
    old_caps = {(c.agent, c.name) for c in old.capabilities}
    new_caps = {(c.agent, c.name) for c in new.capabilities}

    removed_resources = sorted(old_uris - new_uris)
    added_resources = sorted(new_uris - old_uris)
    removed_capabilities = sorted([f"{a}.{n}" for a, n in old_caps - new_caps])
    added_capabilities = sorted([f"{a}.{n}" for a, n in new_caps - old_caps])

    breaking = bool(removed_resources or removed_capabilities)
    return {
        "breaking_change": breaking,
        "added_resources": added_resources,
        "removed_resources": removed_resources,
        "added_capabilities": added_capabilities,
        "removed_capabilities": removed_capabilities,
        "policy": _load_policy(new_root).get("compatibility", {}),
    }
