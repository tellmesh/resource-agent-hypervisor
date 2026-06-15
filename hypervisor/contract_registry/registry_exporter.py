from __future__ import annotations

from pathlib import Path

from hypervisor.contract_registry.registry_builder import build_registry_manifest, write_registry_manifest


def export_json(root: str | Path = ".", output: str | Path | None = None) -> Path:
    return write_registry_manifest(root, output)


def export_markdown(root: str | Path = ".", output: str | Path | None = None) -> Path:
    root = Path(root)
    manifest = build_registry_manifest(root)
    output_path = Path(output) if output else root / "output" / "contract_registry.md"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Contract Registry Export", "", f"Contract hash: `{manifest['contract_hash']}`", ""]
    lines.append("## Resources")
    for item in manifest["resources"]:
        lines.append(
            f"- `{item['uri']}` -> `{item['projection']}` / `{item['schema']}` / renderer `{item['renderer']}`"
        )
    lines.append("")
    lines.append("## Capabilities")
    for item in manifest["capabilities"]:
        target = item.get("uri") or item.get("command") or "n/a"
        lines.append(f"- `{item['agent']}.{item['name']}` ({item['type']}) -> `{target}`")
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
