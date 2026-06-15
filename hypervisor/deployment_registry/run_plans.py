from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hypervisor.deployment_registry.local_targets import build_local_run_plan
from hypervisor.deployment_registry.models import AgentDeployment
from hypervisor.paths import find_repo_root


def build_run_plan(
    deployment: AgentDeployment,
    *,
    root: str | Path | None = None,
    port: int | None = None,
    host: str = "0.0.0.0",
    reload: bool = False,
) -> dict[str, Any]:
    repo = Path(root) if root is not None else find_repo_root()
    scheme = urlparse(deployment.target_uri).scheme

    if scheme == "local":
        return build_local_run_plan(deployment, repo=repo, port=port, host=host, reload=reload)
    if scheme == "ssh":
        from hypervisor.deployment_registry.remote_runner import build_ssh_run_plan

        return build_ssh_run_plan(deployment, root=repo, port=port, host=host)
    if scheme == "docker":
        from hypervisor.deployment_registry.docker_runner import build_docker_control_plan

        return build_docker_control_plan(deployment, "up", root=repo)
    raise ValueError(f"Unsupported deployment target scheme: {scheme}")
