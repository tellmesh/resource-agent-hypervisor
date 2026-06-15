from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from uri2pact import extract_markpact_blocks

from hypervisor.agent_manifest.materialize import parse_manifest


def docker_block_from_manifest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    blocks = extract_markpact_blocks(text, "docker")
    if not blocks:
        raise ValueError(f"No markpact:docker block in {path}")
    payload = yaml.safe_load(blocks[0]["body"]) or {}
    service = payload.get("service")
    if not isinstance(service, dict):
        raise ValueError("markpact:docker block must contain service mapping")
    return payload


def compose_document_from_docker_block(docker_payload: dict[str, Any]) -> dict[str, Any]:
    service = docker_payload["service"]
    name = service.get("name") or service.get("container_name") or "agent"
    doc: dict[str, Any] = {
        "services": {
            name: {
                key: value
                for key, value in service.items()
                if key not in {"name"}
            }
        }
    }
    if "environment" not in doc["services"][name]:
        doc["services"][name]["environment"] = {"RESOURCE_RUNTIME_URL": "http://host.docker.internal:8000"}
    return doc


def materialize_compose_from_manifest(
    manifest_path: Path,
    *,
    repo: Path,
    output: Path | None = None,
) -> dict[str, Any]:
    path = manifest_path if manifest_path.is_absolute() else repo / manifest_path
    docker_payload = docker_block_from_manifest(path)
    compose_doc = compose_document_from_docker_block(docker_payload)
    compose_meta = docker_payload.get("compose") or {}
    if output is not None:
        target = output if output.is_absolute() else repo / output
    elif compose_meta.get("output"):
        target = repo / compose_meta["output"]
    else:
        agent_name = path.stem.replace(".markpact", "")
        target = repo / "output" / "deployments" / agent_name / "docker-compose.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(compose_doc, sort_keys=False), encoding="utf-8")
    return {
        "ok": True,
        "manifest_path": path.relative_to(repo).as_posix(),
        "compose_path": target.relative_to(repo).as_posix(),
        "service": docker_payload["service"].get("name"),
    }
