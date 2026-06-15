from __future__ import annotations

from hypervisor.contract_registry.cross_checks.proto_index import schema_exists
from hypervisor.contract_registry.models import ContractRegistry


def validate_resource_cross_refs(
    registry: ContractRegistry,
    *,
    view_names: set[str],
    renderer_names: set[str],
    proto_text: str,
) -> list[str]:
    errors: list[str] = []
    for resource in registry.resources:
        if resource.projection not in view_names:
            errors.append(f"resource {resource.uri} references missing projection/view {resource.projection}")
        if resource.renderer not in renderer_names:
            errors.append(f"resource {resource.uri} references unknown renderer {resource.renderer}")
        if proto_text and not schema_exists(proto_text, resource.schema):
            errors.append(f"resource {resource.uri} references missing proto schema {resource.schema}")
    return errors
