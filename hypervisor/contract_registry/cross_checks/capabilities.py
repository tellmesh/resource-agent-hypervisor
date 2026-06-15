from __future__ import annotations

from hypervisor.contract_registry.cross_checks.proto_index import schema_exists
from hypervisor.contract_registry.models import ContractRegistry
from hypervisor.contract_registry.registry_checks.capabilities import _resolves_as_external_uri


def _validate_single_capability(
    capability,
    *,
    label: str,
    resource_uris: set[str],
    resource_schemas: set[str],
    renderer_names: set[str],
    proto_text: str,
    external_resource: bool,
) -> list[str]:
    """Pure validator for one capability; returns list of error strings."""
    errors: list[str] = []
    if capability.type == "resource_read":
        if not capability.uri:
            errors.append(f"capability {label} lacks uri")
        elif capability.uri not in resource_uris and not external_resource:
            errors.append(f"capability {label} references missing resource {capability.uri}")
        if (
            capability.output_schema
            and capability.output_schema not in resource_schemas
            and not external_resource
        ):
            errors.append(
                f"capability {label} output_schema does not match any resource "
                f"schema: {capability.output_schema}"
            )
    if capability.renderer and capability.renderer not in renderer_names:
        errors.append(f"capability {label} references unknown renderer {capability.renderer}")
    for schema_ref in [capability.input_schema, capability.output_schema]:
        if schema_ref and proto_text and not schema_exists(proto_text, schema_ref):
            errors.append(f"capability {label} references missing proto schema {schema_ref}")
    return errors

def validate_capability_cross_refs(
    registry: ContractRegistry,
    *,
    resource_uris: set[str],
    resource_schemas: set[str],
    renderer_names: set[str],
    proto_text: str,
) -> list[str]:
    errors: list[str] = []
    for capability in registry.capabilities:
        label = f"{capability.agent}.{capability.name}"
        external_resource = bool(
            capability.uri
            and capability.uri not in resource_uris
            and _resolves_as_external_uri(capability.uri)
        )
        errors.extend(
            _validate_single_capability(
                capability,
                label=label,
                resource_uris=resource_uris,
                resource_schemas=resource_schemas,
                renderer_names=renderer_names,
                proto_text=proto_text,
                external_resource=external_resource,
            )
        )
    return errors
