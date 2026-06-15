from typing import Any

from hypervisor.domain_pack.model import DomainModel


def generate_renderers(model: DomainModel) -> dict[str, Any]:
    renderers: dict[str, Any] = {
        "renderers": [{"id": "json", "view_kind": "json", "allowed_mime_types": ["application/json"]}]
    }
    if any(resource.get("renderer_ref") == "html" for resource in model.tree.get("resources", {}).values()):
        renderers["renderers"].append(
            {"id": "html", "view_kind": "html", "allowed_mime_types": ["text/html", "application/json"]}
        )
    return renderers
