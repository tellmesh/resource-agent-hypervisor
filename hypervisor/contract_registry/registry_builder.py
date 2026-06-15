from __future__ import annotations

from pathlib import Path
from typing import Any
import hashlib
import json

from hypervisor.contract_registry.loader import load_contract_registry


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _contract_hash(root: Path) -> str:
    files: list[Path] = []
    for pattern in [
        "contracts/resources.yaml",
        "contracts/views.yaml",
        "contracts/registry.yaml",
        "contracts/compatibility/*.yaml",
        "contracts/agents/*.yaml",
        "contracts/proto/*.proto",
        "schemas/*.json",
    ]:
        files.extend(sorted(root.glob(pattern)))
    digest = hashlib.sha256()
    for path in files:
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b"|path|")
        digest.update(path.read_bytes())
        digest.update(b"|file|")
    return digest.hexdigest()


def build_registry_manifest(root: str | Path = ".") -> dict[str, Any]:
    root = Path(root)
    registry = load_contract_registry(root)
    raw_registry = registry.raw.get("registry", {})
    registry_meta = raw_registry.get("registry", raw_registry) if isinstance(raw_registry, dict) else {}
    return {
        "registry": registry_meta,
        "contract_hash": f"sha256:{_contract_hash(root)}",
        "resources": [r.__dict__ for r in registry.resources],
        "views": [v.__dict__ for v in registry.views],
        "capabilities": [c.__dict__ for c in registry.capabilities],
        "counts": {
            "resources": len(registry.resources),
            "views": len(registry.views),
            "capabilities": len(registry.capabilities),
        },
    }


def write_registry_manifest(root: str | Path = ".", output: str | Path | None = None) -> Path:
    root = Path(root)
    output_path = Path(output) if output else root / "output" / "contract_registry.resolved.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(build_registry_manifest(root), indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
