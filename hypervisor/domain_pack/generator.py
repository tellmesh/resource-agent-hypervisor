from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.contract_registry.merger import merge_main_contracts
from hypervisor.domain_pack.artifact_generators.agent_contract import generate_agent_contract
from hypervisor.domain_pack.artifact_generators.commands import generate_commands
from hypervisor.domain_pack.artifact_generators.handlers import generate_handlers
from hypervisor.domain_pack.artifact_generators.proto import generate_proto
from hypervisor.domain_pack.artifact_generators.renderers import generate_renderers
from hypervisor.domain_pack.artifact_generators.resources import generate_resources
from hypervisor.domain_pack.artifact_generators.views import generate_views
from hypervisor.domain_pack.model import DomainModel
from hypervisor.domain_pack.pack_writer import write_domain_pack
from hypervisor.domain_pack.parser import derive_domain_model, parse_uri_tree
from hypervisor.domain_pack.writer import repo_root

__all__ = [
    "DomainModel",
    "derive_domain_model",
    "generate_agent_contract",
    "generate_commands",
    "generate_domain_pack",
    "generate_domain_pack_from_tree",
    "generate_handlers",
    "generate_proto",
    "generate_renderers",
    "generate_resources",
    "generate_views",
    "parse_uri_tree",
    "write_domain_pack",
]


def generate_domain_pack_from_tree(
    tree: dict[str, Any],
    out_dir: Path,
    *,
    root: Path | None = None,
) -> dict[str, str]:
    project_root = root or repo_root()
    model = derive_domain_model(tree, out_dir)
    proto_text = generate_proto(model)
    resources = generate_resources(model)
    views = generate_views(resources)
    commands = generate_commands(model)
    renderers = generate_renderers(model)
    handler_name, handler_source = generate_handlers(model)
    agent_yaml = generate_agent_contract(model)

    files = write_domain_pack(
        model,
        proto_text=proto_text,
        resources=resources,
        views=views,
        commands=commands,
        renderers=renderers,
        handler_name=handler_name,
        handler_source=handler_source,
        agent_yaml=agent_yaml,
        root=project_root,
    )
    merge_main_contracts(model.domain_id, resources, views, proto_text, root=project_root)
    return files


def generate_domain_pack(
    uri_tree_path: str | Path,
    domain_dir: str | Path,
    *,
    root: Path | None = None,
) -> dict[str, str]:
    tree = parse_uri_tree(uri_tree_path)
    return generate_domain_pack_from_tree(tree, Path(domain_dir), root=root)
