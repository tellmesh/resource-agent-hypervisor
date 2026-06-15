from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from hypervisor.deployment_registry.loader import load_deployment_registry
from hypervisor.deployment_registry.runtime_state import load_runtime_state
from hypervisor.deployment_registry.supervisor import inspect_agent
from hypervisor.repair.supervisor import diagnose_agent, repair_apply, supervise_with_repair

from hypervisor.routing.system_request import (
    SystemUriRequest,
    bool_param,
    int_param,
    query_params,
)


def handle_runtime_uri(parts: list[str], *, repo: Path) -> dict[str, Any]:
    agent_id = parts[1]
    state = load_runtime_state(agent_id, repo) or {}
    return {
        "ok": True,
        "result_type": "runtime_state",
        "workflow_status": "completed",
        "service_result_status": "succeeded",
        "agent_id": agent_id,
        "state": state,
    }


def handle_health_uri(parts: list[str], *, repo: Path) -> dict[str, Any]:
    agent_id = parts[1]
    inspection = inspect_agent(agent_id, root=repo)
    return {
        "result_type": "health",
        "agent_id": agent_id,
        "ok": inspection.get("health", {}).get("ok"),
        "health": inspection.get("health"),
        "service_status": inspection.get("service_status"),
    }


def _contract_path_for_agent(agent_id: str, *, repo: Path) -> Path | None:
    registry = load_deployment_registry(root=repo)
    deployment = registry.by_id(agent_id)
    if deployment is None:
        return None
    contract = deployment.metadata.get("contract")
    if contract:
        return repo / str(contract)
    if deployment.target_uri.startswith("local://agents/generated/"):
        package = deployment.target_uri.rsplit("/", 1)[-1]
        return repo / "contracts" / "agents" / f"{package}.yaml"
    return None


def _schema_refs_from_capabilities(capabilities: list[dict[str, Any]]) -> dict[str, list[str]]:
    input_refs: list[str] = []
    output_refs: list[str] = []
    for capability in capabilities:
        input_schema = capability.get("input_schema")
        output_schema = capability.get("output_schema")
        if input_schema:
            input_refs.append(str(input_schema))
        if output_schema:
            output_refs.append(str(output_schema))
    return {
        "input": sorted(set(input_refs)),
        "output": sorted(set(output_refs)),
    }


def _read_contract(path: Path | None) -> tuple[str | None, dict[str, Any] | None]:
    if path is None:
        return None, None
    contract_uri = f"file://{path.resolve().as_posix()}"
    if not path.is_file():
        return contract_uri, None
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return contract_uri, data if isinstance(data, dict) else None


def _contract_uri_for_schema(agent_id: str, file_uri: str | None, *, repo: Path) -> str | None:
    from hypervisor.contract_registry.uri_resolver import resolve_contract_path

    path = resolve_contract_path(agent_id, repo)
    if path is not None:
        agent = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        agent_name = str((agent.get("agent") or {}).get("name") or agent_id)
        return f"contract://agent/{agent_name}"
    if file_uri and file_uri.startswith("file://"):
        stem = Path(file_uri.removeprefix("file://")).stem
        return f"contract://agents/{stem}"
    return None


def handle_schema_uri(parts: list[str], *, repo: Path) -> dict[str, Any]:
    if len(parts) < 2 or parts[0] != "agent":
        raise ValueError("schema:// supports schema://agent/{deployment_id}")
    agent_id = parts[1]
    registry = load_deployment_registry(root=repo)
    deployment = registry.by_id(agent_id)
    if deployment is None:
        return {
            "ok": False,
            "result_type": "agent_schema",
            "workflow_status": "completed_with_service_error",
            "service_result_status": "failed",
            "agent_id": agent_id,
            "error": f"Deployment not found: {agent_id}",
        }

    inspection = inspect_agent(agent_id, root=repo)
    card_probe = inspection.get("card") or {}
    card_payload = card_probe.get("payload") if isinstance(card_probe, dict) else None
    card_payload = card_payload if isinstance(card_payload, dict) else None
    contract_uri, contract = _read_contract(_contract_path_for_agent(agent_id, repo=repo))
    contract_capabilities = (contract or {}).get("capabilities") or []
    runtime_capabilities = (card_payload or {}).get("capabilities") or []
    capabilities = runtime_capabilities or contract_capabilities
    capabilities = [item for item in capabilities if isinstance(item, dict)]

    effective_health_uri = inspection.get("effective_health_uri") or deployment.health_uri
    card_uri = card_probe.get("uri") if isinstance(card_probe, dict) else None
    card_uri = card_uri or deployment.card_uri
    return {
        "ok": bool(card_payload or contract),
        "result_type": "agent_schema",
        "workflow_status": "completed",
        "service_result_status": "succeeded" if card_payload or contract else "failed",
        "agent_id": agent_id,
        "agent_ref": deployment.agent_ref,
        "deployment_id": deployment.id,
        "target_uri": deployment.target_uri,
        "health_uri": effective_health_uri,
        "card_uri": card_uri,
        "contract_uri": contract_uri,
        "card": card_payload,
        "contract": contract,
        "capabilities": capabilities,
        "schemas": _schema_refs_from_capabilities(capabilities),
        "related_uris": {
            "health": f"health://agent/{agent_id}",
            "view": f"view://process/agent/{agent_id}/latest",
            "runtime": f"runtime://agent/{agent_id}/state",
            "schema": f"schema://agent/{agent_id}",
            "contract": _contract_uri_for_schema(agent_id, contract_uri, repo=repo),
            "card": card_uri,
        },
    }


def handle_repair_uri(
    parts: list[str],
    *,
    repo: Path,
    approved: bool,
    dry_run: bool,
) -> dict[str, Any]:
    agent_id = parts[1]
    action = parts[2]
    if action == "diagnose":
        return diagnose_agent(agent_id, root=repo)
    if action == "apply":
        if dry_run:
            diagnosis = diagnose_agent(agent_id, root=repo)
            return {
                "ok": True,
                "result_type": "repair",
                "uri": f"repair://agent/{agent_id}/apply",
                "dry_run": True,
                "workflow_status": "planned",
                "service_result_status": "preview",
                "diagnosis": diagnosis,
                "repair_plan": diagnosis.get("repair_plan"),
            }
        return repair_apply(agent_id, root=repo, approved=approved, safe=True)
    if action == "auto":
        if dry_run:
            diagnosis = diagnose_agent(agent_id, root=repo)
            return {
                "ok": True,
                "result_type": "repair",
                "uri": f"repair://agent/{agent_id}/auto",
                "dry_run": True,
                "workflow_status": "planned",
                "service_result_status": "preview",
                "agent_id": agent_id,
                "diagnosis": diagnosis,
                "repair_plan": diagnosis.get("repair_plan"),
                "planned_action": "supervise_with_repair",
            }
        return supervise_with_repair(
            agent_id,
            root=repo,
            repair="auto",
            learn=False,
        )
    raise ValueError(f"unsupported repair action: {action}")


def handle_agent_factory_uri(request: SystemUriRequest) -> dict[str, Any]:
    if len(request.parts) < 2 or request.parts[0] != "generate":
        raise ValueError(f"unsupported agent factory URI: {request.uri}")
    from urish.backends.agent_factory import generate_agent_from_prompt

    params = query_params(request.uri)
    payload = request.payload or {}
    agent_id = request.parts[1]
    prompt = str(payload.get("prompt") or params.get("prompt") or f"create agent {agent_id}")
    overwrite = bool_param(payload.get("overwrite", params.get("overwrite")), default=False)
    port = int_param(payload.get("port", params.get("port")))
    result = generate_agent_from_prompt(
        prompt,
        name=agent_id,
        port=port,
        dry_run=request.dry_run,
        approve=request.approved,
        overwrite=overwrite,
        root=request.repo,
    )
    result.setdefault("uri", request.uri)
    return result


def handle_hypervisor_agent_uri(request: SystemUriRequest) -> dict[str, Any]:
    from hypervisor.deployment_registry.runner import run_agent
    from hypervisor.deployment_registry.selector import parse_hypervisor_uri, resolve_deployment

    selector, action = parse_hypervisor_uri(request.uri)
    if action != "run":
        raise ValueError(f"unsupported hypervisor agent action: {action}")
    try:
        deployment = resolve_deployment(selector, root=request.repo, prefer_local=True)
    except ValueError as exc:
        if request.dry_run:
            return {
                "ok": True,
                "result_type": "lifecycle_plan",
                "workflow_status": "planned",
                "service_result_status": "preview",
                "uri": request.uri,
                "deployment_id": selector,
                "pending_dependency": "deployment registry entry",
                "note": str(exc),
            }
        raise ValueError(f"unsupported hypervisor URI: {request.uri} ({exc})") from exc
    deployment_id = deployment.id
    if request.dry_run:
        try:
            return run_agent(deployment_id, root=request.repo, dry_run=True, detach=True)
        except Exception as exc:
            return {
                "ok": True,
                "result_type": "lifecycle_plan",
                "workflow_status": "planned",
                "service_result_status": "preview",
                "uri": request.uri,
                "deployment_id": deployment_id,
                "pending_dependency": "deployment registry entry",
                "note": str(exc),
            }
    return run_agent(
        deployment_id,
        root=request.repo,
        detach=True,
        wait_healthy=True,
        if_running="reuse",
    )


def handle_log_uri(uri: str, *, repo: Path) -> dict[str, Any]:
    from uri3.logs.reader import read_logs_result

    entries = read_logs_result(uri, root=repo)
    return {
        "ok": True,
        "result_type": "logs",
        "workflow_status": "completed",
        "service_result_status": "succeeded",
        "uri": uri,
        "entries": entries,
    }


def handle_file_uri(uri: str) -> dict[str, Any]:
    from uri3.resolvers.resolve_core import resolve

    resolved = resolve(uri)
    return {
        "ok": True,
        "result_type": "file",
        "workflow_status": "completed",
        "service_result_status": "succeeded",
        "uri": uri,
        "data": resolved.target,
    }


def handle_contract_uri(uri: str, repo: Path) -> dict[str, Any]:
    from hypervisor.contract_registry.uri_resolver import handle_contract_uri

    return handle_contract_uri(uri, repo)
