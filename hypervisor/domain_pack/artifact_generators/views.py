from typing import Any


def generate_views(resources: dict[str, Any]) -> dict[str, Any]:
    views: dict[str, Any] = {"views": []}
    for resource in resources["resources"]:
        views["views"].append(
            {
                "name": resource["projection_ref"],
                "schema_ref": resource["schema_ref"],
                "renderer": resource["renderer_ref"],
                "mime_type": resource["mime_type"],
                "rebuildable": True,
            }
        )
    return views
