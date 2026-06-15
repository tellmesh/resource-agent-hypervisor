from typing import Any

from hypervisor.domain_pack.model import DomainModel


def generate_resources(model: DomainModel) -> dict[str, Any]:
    resources: dict[str, Any] = {"resources": []}
    for key, resource in model.tree.get("resources", {}).items():
        resources["resources"].append(
            {
                "id": f"{model.domain_id}.{key}.v1",
                "kind": "resource",
                "uri_template": resource["uri_template"],
                "stability": "experimental",
                "version": "v1",
                "schema_ref": resource["schema_ref"],
                "projection_ref": f"{model.domain_id}_{key}_view",
                "renderer_ref": resource.get("renderer_ref", "json"),
                "owner_agent": model.agent["id"],
                "read_method": "resources/read",
                "mime_type": resource.get("mime_type", "application/json"),
            }
        )
    return resources
