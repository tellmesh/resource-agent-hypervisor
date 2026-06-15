from __future__ import annotations

from pathlib import Path

from hypervisor.deployment_registry.models import AgentDeployment


def generated_agent_dir(agent_ref: str, root: Path) -> Path:
    package = agent_ref.removeprefix("agent://").replace("-", "_")
    return root / "agents" / "generated" / package


def remote_module_for(deployment: AgentDeployment) -> str:
    return str(deployment.metadata.get("remote_module") or "main:app")
