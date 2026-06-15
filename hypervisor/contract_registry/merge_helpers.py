from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor.domain_pack.writer import write_file


def merge_proto_contract(contracts_dir: Path, domain_id: str, proto_text: str) -> None:
    proto_name = "weather.proto" if domain_id == "weather_map" else f"{domain_id}.proto"
    write_file(contracts_dir / "proto" / proto_name, proto_text)


def merge_resources_contract(contracts_dir: Path, resources: dict[str, Any]) -> None:
    resources_path = contracts_dir / "resources.yaml"
    existing = (
        yaml.safe_load(resources_path.read_text(encoding="utf-8"))
        if resources_path.exists()
        else {"resources": []}
    )
    existing_uris = {resource.get("uri") for resource in existing.get("resources", [])}
    for resource in resources.get("resources", []):
        item = {
            "uri": resource["uri_template"],
            "projection": resource["projection_ref"],
            "schema": resource["schema_ref"],
            "renderer": resource["renderer_ref"],
            "owner_agent": resource.get("owner_agent"),
            "stability": resource.get("stability", "experimental"),
            "version": resource.get("version", "v1"),
        }
        if item["uri"] not in existing_uris:
            existing.setdefault("resources", []).append(item)
            existing_uris.add(item["uri"])
    write_file(resources_path, yaml.safe_dump(existing, sort_keys=False, allow_unicode=True))


def merge_views_contract(contracts_dir: Path, views: dict[str, Any]) -> None:
    views_path = contracts_dir / "views.yaml"
    existing_views = (
        yaml.safe_load(views_path.read_text(encoding="utf-8"))
        if views_path.exists()
        else {"views": []}
    )
    existing_names = {view.get("name") for view in existing_views.get("views", [])}
    for view in views.get("views", []):
        item = {
            "name": view["name"],
            "viewKind": view.get("renderer", "json"),
            "mimeType": view.get("mime_type", "application/json"),
            "columns": ["place", "days", "html_url"]
            if view.get("renderer") == "html"
            else ["place", "days", "model"],
            "rendererHint": view.get("renderer", "json"),
        }
        if item["name"] not in existing_names:
            existing_views.setdefault("views", []).append(item)
            existing_names.add(item["name"])
    write_file(views_path, yaml.safe_dump(existing_views, sort_keys=False, allow_unicode=True))
