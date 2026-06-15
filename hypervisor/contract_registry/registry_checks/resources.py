from __future__ import annotations

from hypervisor.contract_registry.models import ContractRegistry


def validate_resources(registry: ContractRegistry) -> list[str]:
    errors: list[str] = []
    resource_uris: set[str] = set()
    for resource in registry.resources:
        if resource.uri in resource_uris:
            errors.append(f"duplicate resource uri: {resource.uri}")
        resource_uris.add(resource.uri)
        if not resource.uri.startswith("resource://"):
            errors.append(f"resource uri must start with resource://: {resource.uri}")
        if "postgres" in resource.uri or "_view" in resource.uri.split("/")[2:]:
            errors.append(f"resource uri should be semantic, not storage-oriented: {resource.uri}")
        if not registry.view_by_name(resource.projection):
            errors.append(f"resource {resource.uri} references missing view/projection {resource.projection}")
    return errors


def validate_views(registry: ContractRegistry) -> list[str]:
    view_names = {view.name for view in registry.views}
    if len(view_names) != len(registry.views):
        return ["duplicate view names detected"]
    return []
