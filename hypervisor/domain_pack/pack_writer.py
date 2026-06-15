from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor.domain_pack.model import DomainModel
from hypervisor.domain_pack.writer import repo_root, write_file


def write_domain_pack(
    model: DomainModel,
    *,
    proto_text: str,
    resources: dict[str, Any],
    views: dict[str, Any],
    commands: dict[str, Any],
    renderers: dict[str, Any],
    handler_name: str,
    handler_source: str,
    agent_yaml: dict[str, Any],
    root: Path | None = None,
) -> dict[str, str]:
    project_root = root or repo_root()
    out_dir = model.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, str] = {}

    files["uri_tree"] = write_file(
        out_dir / "uri_tree.yaml",
        yaml.safe_dump(model.tree, sort_keys=False, allow_unicode=True),
    )
    files["domain"] = write_file(
        out_dir / "domain.yaml",
        yaml.safe_dump(
            {"domain": model.domain, "dependencies": model.tree.get("dependencies", [])},
            sort_keys=False,
            allow_unicode=True,
        ),
    )
    files["proto"] = write_file(out_dir / "proto" / f"{model.domain_id}.proto", proto_text)
    files["resources"] = write_file(
        out_dir / "resources.yaml",
        yaml.safe_dump(resources, sort_keys=False, allow_unicode=True),
    )
    files["views"] = write_file(
        out_dir / "views.yaml",
        yaml.safe_dump(views, sort_keys=False, allow_unicode=True),
    )
    files["commands"] = write_file(
        out_dir / "commands.yaml",
        yaml.safe_dump(commands, sort_keys=False, allow_unicode=True),
    )
    files["renderers"] = write_file(
        out_dir / "renderers.yaml",
        yaml.safe_dump(renderers, sort_keys=False, allow_unicode=True),
    )

    handler_dir = project_root / "domains" / model.domain_id / "handlers"
    files["handler"] = write_file(handler_dir / handler_name, handler_source)
    write_file(project_root / "domains" / model.domain_id / "__init__.py", "")
    write_file(handler_dir / "__init__.py", "")

    agent_path = project_root / "contracts" / "agents" / f"{model.agent['id'].replace('-', '_')}.yaml"
    files["agent_contract"] = write_file(
        agent_path,
        yaml.safe_dump(agent_yaml, sort_keys=False, allow_unicode=True),
    )

    registry_ref = {
        "domain_pack": str(out_dir.relative_to(project_root)) if out_dir.is_relative_to(project_root) else str(out_dir),
        "agent_contract": str(agent_path.relative_to(project_root)),
    }
    preserved_keys = (
        "default_deployment_id",
        "deployment_selector_aliases",
        "flow_aliases",
        "default_health_uri",
        "default_card_uri",
    )
    existing_fragment = out_dir / "registry.fragment.yaml"
    if existing_fragment.is_file():
        preserved = yaml.safe_load(existing_fragment.read_text(encoding="utf-8")) or {}
        if isinstance(preserved, dict):
            for key in preserved_keys:
                if key in preserved:
                    registry_ref[key] = preserved[key]
    files["registry_fragment"] = write_file(
        out_dir / "registry.fragment.yaml",
        yaml.safe_dump(registry_ref, sort_keys=False, allow_unicode=True),
    )
    return files
