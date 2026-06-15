from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor.agent_describe.collect import (
    agent_kind,
    find_contract_path,
    package_relative_path,
    read_yaml,
    rel,
    safe_run_plan,
)
from hypervisor.deployment_registry.local_targets import local_target_to_module
from hypervisor.deployment_registry.selector import resolve_deployment


def build_agent_block(
    *,
    repo: Path,
    agent_name: str,
    deployment: Any,
    contract_path: Path | None,
    contract: dict[str, Any],
    is_operator: bool,
) -> str:
    kind = agent_kind(deployment, is_operator=is_operator)
    payload: dict[str, Any] = {
        "version": 1,
        "agent": {
            "id": deployment.agent_ref,
            "name": agent_name,
            "implementation": kind,
            "contract": rel(repo, contract_path),
            "package": rel(repo, repo / package_relative_path(deployment, repo))
            if package_relative_path(deployment, repo)
            else None,
            "module": local_target_to_module(deployment.target_uri)
            if str(deployment.target_uri).startswith("local://")
            else None,
        },
    }
    if is_operator:
        payload["operator"] = {
            "kind": contract.get("kind"),
            "runtime_package": (contract.get("metadata") or {}).get("runtime_package"),
        }
    else:
        agent_meta = contract.get("agent") or {}
        payload["agent"].update(
            {
                "version": agent_meta.get("version"),
                "python_package": agent_meta.get("python_package"),
                "description": agent_meta.get("description"),
            }
        )
        payload["capabilities"] = contract.get("capabilities") or []
    return yaml.safe_dump(payload, sort_keys=False).strip()


def build_deployment_block(*, repo: Path, deployment: Any, agent_name: str) -> str:
    metadata = deployment.metadata or {}
    declared = deployment.declared
    payload = {
        "deployment": {
            "id": deployment.id,
            "agent_ref": deployment.agent_ref,
            "target_uri": deployment.target_uri,
            "status": deployment.status,
            "health_uri": deployment.health_uri
            or (declared.health_uri if declared else None),
            "card_uri": deployment.card_uri or (declared.card_uri if declared else None),
            "view_uri": f"view://process/agent/{deployment.id}/latest",
        },
        "metadata": metadata,
        "runtime": {
            "run": f"hypervisor run-agent {deployment.id} --detach --wait-healthy",
            "inspect": f"hypervisor inspect-agent {deployment.id}",
            "describe": f"hypervisor describe-agent {deployment.id}",
        },
        "supervise": {
            "once": f"hypervisor supervise {deployment.id} --repair auto",
            "watch": f"hypervisor supervise {deployment.id} --watch --repair auto --interval 15",
        },
        "logs": {
            "hypervisor": f"log://hypervisor?grep={deployment.id}",
            "process": f"log://file/output/logs/agents/{deployment.id}.process.log",
        },
        "manifest": {
            "self": f"markpact://agents/manifests/{agent_name}.markpact.md",
        },
    }
    if deployment.env:
        payload["env"] = deployment.env
    return yaml.safe_dump(payload, sort_keys=False).strip()


def build_runtime_block(*, repo: Path, deployment: Any) -> str:
    run_plan = safe_run_plan(deployment, repo)
    if not run_plan:
        return yaml.safe_dump({"runtime": {"target_uri": deployment.target_uri}}, sort_keys=False).strip()
    payload = {
        "runtime": {
            "module": run_plan.get("module"),
            "path": run_plan.get("path"),
            "port": run_plan.get("port"),
            "health_uri": run_plan.get("health_uri"),
            "card_uri": run_plan.get("card_uri"),
            "command": run_plan.get("command_string"),
        }
    }
    return yaml.safe_dump(payload, sort_keys=False).strip()


def build_docker_block(*, repo: Path, agent_name: str, deployment: Any) -> str | None:
    from hypervisor.deployment_registry.status import infer_port

    docker_config = read_yaml(repo / "config" / "docker.uri.yaml")
    agents = (docker_config.get("spec") or {}).get("agents") or {}
    profile = dict(agents.get(agent_name) or {})
    if not profile:
        package_rel = package_relative_path(deployment, repo)
        if not package_rel:
            return None
        dockerfile = repo / package_rel / "Dockerfile"
        if not dockerfile.is_file():
            return None
        profile = {"dockerfile": rel(repo, dockerfile)}

    port = infer_port(deployment)
    service = {
        "service": {
            "name": agent_name,
            "build": {
                "context": ".",
                "dockerfile": profile.get("dockerfile"),
            },
            "container_name": profile.get("container_name") or agent_name,
            "ports": [f"{port}:{port}"],
            "healthcheck": {
                "test": ["CMD", "curl", "-f", f"http://localhost:{port}/health"],
            },
            "environment": {
                "RESOURCE_RUNTIME_URL": "http://host.docker.internal:8000",
            },
        }
    }
    output_compose = profile.get("output_compose")
    if output_compose:
        service["compose"] = {"output": output_compose}
    else:
        service["compose"] = {"output": f"output/deployments/{agent_name}/docker-compose.yaml"}
    return yaml.safe_dump(service, sort_keys=False).strip()


def build_manifest_markdown(
    *,
    repo: Path,
    selector: str,
    deployment: Any,
    agent_name: str,
    contract_path: Path | None,
    contract: dict[str, Any],
    is_operator: bool,
) -> str:
    description = ""
    if is_operator:
        description = (contract.get("metadata") or {}).get("description") or ""
    else:
        description = (contract.get("agent") or {}).get("description") or ""

    lines = [
        f"# {agent_name}",
        "",
        description or f"Markpact manifest for `{deployment.agent_ref}`.",
        "",
        "Canonical portable definition: contract, deployment, runtime and optional Docker service.",
        "",
        f"Sync: `hypervisor sync-agent-manifest {selector}`",
        "",
        f"```markpact:agent {agent_name}",
        build_agent_block(
            repo=repo,
            agent_name=agent_name,
            deployment=deployment,
            contract_path=contract_path,
            contract=contract,
            is_operator=is_operator,
        ),
        "```",
        "",
        f"```markpact:deployment {deployment.id}",
        build_deployment_block(repo=repo, deployment=deployment, agent_name=agent_name),
        "```",
        "",
        f"```markpact:runtime {deployment.id}",
        build_runtime_block(repo=repo, deployment=deployment),
        "```",
    ]
    docker_block = build_docker_block(repo=repo, agent_name=agent_name, deployment=deployment)
    if docker_block:
        lines.extend(
            [
                "",
                f"```markpact:docker {agent_name}",
                docker_block,
                "```",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def collect_manifest_context(selector: str, *, repo: Path) -> dict[str, Any]:
    deployment = resolve_deployment(selector, root=repo, prefer_local=True)
    agent_name = deployment.agent_ref.removeprefix("agent://")
    contract_path = find_contract_path(repo, agent_name, deployment)
    contract = read_yaml(contract_path) if contract_path else {}
    is_operator = contract.get("kind") == "hypervisor.operator_agent"
    return {
        "selector": selector,
        "deployment": deployment,
        "agent_name": agent_name,
        "contract_path": contract_path,
        "contract": contract,
        "is_operator": is_operator,
    }
