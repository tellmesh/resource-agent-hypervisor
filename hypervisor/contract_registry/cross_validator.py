from __future__ import annotations

from pathlib import Path

from hypervisor.contract_registry.cross_checks.capabilities import validate_capability_cross_refs
from hypervisor.contract_registry.cross_checks.proto_index import load_proto_text
from hypervisor.contract_registry.cross_checks.resources import validate_resource_cross_refs
from hypervisor.contract_registry.loader import load_contract_registry
from hypervisor.contract_registry.models import ContractRegistry


def validate_cross_references(registry: ContractRegistry) -> list[str]:
    view_names = {view.name for view in registry.views}
    renderer_names = {view.viewKind for view in registry.views} | {
        "chart",
        "detail",
        "table",
        "text",
        "timeline",
    }
    resource_uris = {resource.uri for resource in registry.resources}
    resource_schemas = {resource.schema for resource in registry.resources}
    proto_text = load_proto_text(registry.root)
    return [
        *validate_resource_cross_refs(
            registry,
            view_names=view_names,
            renderer_names=renderer_names,
            proto_text=proto_text,
        ),
        *validate_capability_cross_refs(
            registry,
            resource_uris=resource_uris,
            resource_schemas=resource_schemas,
            renderer_names=renderer_names,
            proto_text=proto_text,
        ),
    ]


def validate_root(root: str | Path = ".") -> list[str]:
    return validate_cross_references(load_contract_registry(root))
