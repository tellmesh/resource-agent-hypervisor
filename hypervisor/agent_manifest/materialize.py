from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from uri2pact import extract_markpact_blocks

from hypervisor.agent_describe.collect import read_yaml


def parse_manifest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    blocks: dict[str, Any] = {}
    for block in extract_markpact_blocks(text, "agent"):
        blocks["agent"] = yaml.safe_load(block["body"]) or {}
    for block in extract_markpact_blocks(text, "deployment"):
        blocks["deployment"] = yaml.safe_load(block["body"]) or {}
    for block in extract_markpact_blocks(text, "runtime"):
        blocks["runtime"] = yaml.safe_load(block["body"]) or {}
    docker_blocks = extract_markpact_blocks(text, "docker")
    if docker_blocks:
        blocks["docker"] = yaml.safe_load(docker_blocks[0]["body"]) or {}
    return blocks


def materialize_agent_manifest(
    manifest_path: Path,
    *,
    repo: Path,
    write_contract: bool = False,
) -> dict[str, Any]:
    path = manifest_path if manifest_path.is_absolute() else repo / manifest_path
    if not path.is_file():
        raise FileNotFoundError(f"Manifest not found: {path}")
    blocks = parse_manifest(path)
    agent_block = blocks.get("agent") or {}
    agent_info = agent_block.get("agent") or {}
    contract_rel = agent_info.get("contract")
    result: dict[str, Any] = {
        "ok": True,
        "manifest_path": path.relative_to(repo).as_posix(),
        "agent_ref": agent_info.get("id"),
        "implementation": agent_info.get("implementation"),
        "contract_path": contract_rel,
        "blocks": sorted(blocks),
    }
    if write_contract and contract_rel and agent_block.get("capabilities"):
        contract_path = repo / contract_rel
        if not contract_path.is_file():
            contract_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "agent": {
                    "name": agent_info.get("name"),
                    "python_package": agent_info.get("python_package"),
                    "version": agent_info.get("version") or "0.1.0",
                    "description": agent_info.get("description") or "",
                    "runtime_url_env": "RESOURCE_RUNTIME_URL",
                    "runtime_url_default": "http://localhost:8000",
                },
                "capabilities": agent_block.get("capabilities") or [],
            }
            contract_path.write_text(
                yaml.safe_dump(payload, sort_keys=False),
                encoding="utf-8",
            )
            result["contract_written"] = contract_rel
    elif contract_rel:
        contract = read_yaml(repo / contract_rel)
        result["contract_exists"] = bool(contract)
    deployment_block = blocks.get("deployment") or {}
    if deployment_block.get("deployment"):
        result["deployment_id"] = deployment_block["deployment"].get("id")
    return result
