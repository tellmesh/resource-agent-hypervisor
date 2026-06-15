from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hypervisor.deployment_registry.env import default_log_uri, resolve_deployment_env
from hypervisor.deployment_registry.models import AgentDeployment
from hypervisor.deployment_registry.status import infer_port


def _local_endpoint(path: str, *, port: int) -> str:
    return f"http://localhost:{port}{path}"


def _local_health_uri(deployment: AgentDeployment, *, port: int, overridden: bool) -> str:
    candidates = (
        deployment.declared.health_uri if deployment.declared else None,
        deployment.health_uri,
    )
    for health_uri in candidates:
        if isinstance(health_uri, str) and health_uri.startswith("http") and not overridden:
            return health_uri
    return _local_endpoint("/health", port=port)


def _local_card_uri(deployment: AgentDeployment, *, port: int, overridden: bool) -> str:
    candidates = (
        deployment.declared.card_uri if deployment.declared else None,
        deployment.card_uri,
    )
    for card_uri in candidates:
        if isinstance(card_uri, str) and card_uri.startswith("http") and not overridden:
            return card_uri
    return _local_endpoint("/.well-known/agent-card.json", port=port)


def local_target_to_relative_path(target_uri: str) -> Path:
    parsed = urlparse(target_uri)
    if parsed.scheme != "local":
        raise ValueError(f"Only local:// targets can be started directly: {target_uri}")
    if parsed.netloc:
        return Path(f"{parsed.netloc}/{parsed.path.lstrip('/')}")
    return Path(parsed.path.lstrip("/"))


def repo_python_executable(repo: Path) -> str:
    """Prefer the repo virtualenv interpreter for local agent processes."""
    for name in ("python3", "python"):
        candidate = repo / ".venv" / "bin" / name
        if candidate.is_file():
            return str(candidate)
    return sys.executable


def local_target_to_module(target_uri: str) -> str:
    relative = local_target_to_relative_path(target_uri)
    parts = relative.parts
    if len(parts) >= 3 and parts[0] == "agents" and parts[1] in {
        "generated",
        "custom",
        "operators",
        "system",
    }:
        package = parts[2]
        return f"agents.{parts[1]}.{package}.main:app"
    if len(parts) >= 2 and parts[0] == "packages":
        package_dir = parts[1]
        module_name = package_dir.replace("-", "_")
        return f"{module_name}.main:app"
    raise ValueError(f"Unsupported local agent path: {target_uri}")


def build_local_run_plan(
    deployment: AgentDeployment,
    *,
    repo: Path,
    port: int | None = None,
    host: str = "0.0.0.0",
    reload: bool = False,
) -> dict[str, Any]:
    chosen_port = port or infer_port(deployment)
    port_overridden = port is not None
    module = local_target_to_module(deployment.target_uri)
    agent_path = repo / local_target_to_relative_path(deployment.target_uri)
    if not agent_path.exists():
        raise FileNotFoundError(f"Generated agent path not found: {agent_path}")
    command = [
        repo_python_executable(repo),
        "-m",
        "uvicorn",
        module,
        "--host",
        host,
        "--port",
        str(chosen_port),
    ]
    if reload:
        command.append("--reload")
    display_env = resolve_deployment_env(
        deployment.id, deployment.agent_ref, deployment.env, root=repo, resolve_secrets=False
    )
    runtime_state_path = repo / "output" / "runtime" / "agents" / deployment.id / "state.json"
    return {
        "deployment_id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "target_uri": deployment.target_uri,
        "module": module,
        "path": str(agent_path),
        "host": host,
        "port": chosen_port,
        "health_uri": _local_health_uri(deployment, port=chosen_port, overridden=port_overridden),
        "card_uri": _local_card_uri(deployment, port=chosen_port, overridden=port_overridden),
        "command": command,
        "command_string": " ".join(command),
        "env": display_env,
        "log_uri": default_log_uri(deployment.id, deployment.agent_ref, root=repo),
        "runtime_state_path": str(runtime_state_path),
    }
