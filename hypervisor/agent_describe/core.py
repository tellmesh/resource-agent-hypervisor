from __future__ import annotations

from pathlib import Path

from hypervisor.agent_describe.collect import (
    agent_kind,
    extract_markpact_blocks,
    find_contract_path,
    find_domain_pack,
    list_package_files,
    package_relative_path,
    read_yaml,
    rel,
    safe_run_plan,
)
from hypervisor.agent_describe.models import AgentDescribeReport
from hypervisor.agent_describe.render import RenderContext, render_markdown
from hypervisor.contract_registry.loader import load_contract_registry
from hypervisor.deployment_registry.loader import load_deployment_registry
from hypervisor.deployment_registry.selector import resolve_deployment
from hypervisor.paths import find_repo_root


def describe_agent(
    selector: str,
    *,
    root: str | Path | None = None,
) -> AgentDescribeReport:
    repo = find_repo_root() if root is None else Path(root)
    deployment = resolve_deployment(selector, root=repo, prefer_local=True)
    agent_name = deployment.agent_ref.removeprefix("agent://")
    contract_path = find_contract_path(repo, agent_name, deployment)
    contract = read_yaml(contract_path) if contract_path else {}
    is_operator = contract.get("kind") == "hypervisor.operator_agent"
    agent_meta = contract.get("metadata") if is_operator else (contract.get("agent") or {})
    if not agent_meta and not is_operator:
        agent_meta = contract.get("agent") or {}
    package_rel = package_relative_path(deployment, repo)
    package_dir = repo / package_rel if package_rel else None
    kind = agent_kind(deployment, is_operator=is_operator)
    generated_meta = read_yaml(package_dir / ".generated.yaml") if package_dir else {}
    domain_pack = find_domain_pack(repo, contract_path, deployment, contract)
    markpact_blocks = extract_markpact_blocks(package_dir / "README.md") if package_dir else []
    files = list_package_files(package_dir, agent_kind=kind) if package_dir and package_dir.is_dir() else []
    registry = load_contract_registry(repo)
    agent_caps = [cap for cap in registry.capabilities if cap.agent == agent_name]
    all_deployments = load_deployment_registry(repo).by_agent_ref(deployment.agent_ref)
    run_plan = safe_run_plan(deployment, repo)
    data = {
        "selector": selector,
        "deployment_id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "agent_name": agent_name,
        "contract_path": rel(repo, contract_path),
        "contract_format": "operator_yaml" if is_operator else "yaml",
        "markpact_in_readme": bool(markpact_blocks),
        "package_path": rel(repo, package_dir),
        "domain_pack": domain_pack,
        "files": files,
        "is_operator": is_operator,
        "agent_kind": kind,
        "deployments": [item.id for item in all_deployments],
    }
    markdown = render_markdown(
        RenderContext(
            repo=repo,
            selector=selector,
            deployment=deployment,
            agent_name=agent_name,
            agent_meta=agent_meta,
            contract_path=contract_path,
            contract=contract,
            is_operator=is_operator,
            generated_meta=generated_meta,
            domain_pack=domain_pack,
            markpact_blocks=markpact_blocks,
            files=files,
            agent_caps=agent_caps,
            all_deployments=all_deployments,
            run_plan=run_plan,
            registry=registry,
        )
    )
    return AgentDescribeReport(selector=selector, markdown=markdown, data=data)
