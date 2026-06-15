from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.agent_manifest.blocks import build_manifest_markdown, collect_manifest_context
from hypervisor.agent_manifest.paths import manifest_path_for_agent
from hypervisor.deployment_registry.loader import load_deployment_registry


def sync_agent_manifest(
    selector: str,
    *,
    root: str | Path,
) -> dict[str, Any]:
    repo = Path(root)
    ctx = collect_manifest_context(selector, repo=repo)
    agent_name = ctx["agent_name"]
    deployment = ctx["deployment"]
    markdown = build_manifest_markdown(
        repo=repo,
        selector=selector,
        deployment=deployment,
        agent_name=agent_name,
        contract_path=ctx["contract_path"],
        contract=ctx["contract"],
        is_operator=ctx["is_operator"],
    )
    path = manifest_path_for_agent(repo, agent_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown, encoding="utf-8")
    return {
        "ok": True,
        "agent_name": agent_name,
        "deployment_id": deployment.id,
        "manifest_path": path.relative_to(repo).as_posix(),
        "contract_path": ctx["contract_path"].relative_to(repo).as_posix()
        if ctx["contract_path"]
        else None,
    }


def sync_all_agent_manifests(*, root: str | Path) -> dict[str, Any]:
    repo = Path(root)
    registry = load_deployment_registry(repo)
    synced: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    seen_agents: set[str] = set()
    for deployment in registry.deployments:
        agent_name = deployment.agent_ref.removeprefix("agent://")
        if agent_name in seen_agents:
            continue
        seen_agents.add(agent_name)
        if not str(deployment.target_uri).startswith("local://"):
            skipped.append({"agent_name": agent_name, "reason": "non-local target"})
            continue
        try:
            synced.append(sync_agent_manifest(deployment.id, root=repo))
        except Exception as exc:
            skipped.append({"agent_name": agent_name, "reason": str(exc)})
    return {"ok": True, "synced": synced, "skipped": skipped, "count": len(synced)}
