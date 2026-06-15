from __future__ import annotations

import shlex
import sys
from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.env import resolve_deployment_env
from hypervisor.deployment_registry.ssh_helpers import remote_module_for
from hypervisor.deployment_registry.status import infer_port
from hypervisor.paths import find_repo_root
from uri3.resolvers.ssh_resolver import parse_ssh_uri


def build_ssh_run_plan(
    deployment,
    *,
    root: Path | None = None,
    port: int | None = None,
    host: str = "0.0.0.0",
) -> dict[str, Any]:
    repo = root or find_repo_root()
    ssh_ref = parse_ssh_uri(deployment.target_uri)
    chosen_port = port or infer_port(deployment)
    remote_path = ssh_ref["path"]
    module = remote_module_for(deployment)
    display_env = resolve_deployment_env(
        deployment.id, deployment.agent_ref, deployment.env, root=repo, resolve_secrets=False
    )
    env_prefix = " ".join(f"{key}={shlex.quote(value)}" for key, value in display_env.items())
    remote_command = (
        f"cd {shlex.quote(remote_path)} && "
        f"{env_prefix + ' ' if env_prefix else ''}"
        f"{shlex.quote(sys.executable)} -m uvicorn {module} "
        f"--host {shlex.quote(host)} --port {chosen_port}"
    )
    from uri3.resolvers.ssh_resolver import build_ssh_command

    command = build_ssh_command(ssh_ref, remote_command)
    health_uri = deployment.health_uri or f"http://{ssh_ref['host']}:{chosen_port}/health"
    return {
        "deployment_id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "target_uri": deployment.target_uri,
        "transport": "ssh",
        "ssh": ssh_ref,
        "remote_path": remote_path,
        "module": module,
        "host": host,
        "port": chosen_port,
        "health_uri": health_uri,
        "card_uri": deployment.card_uri or f"http://{ssh_ref['host']}:{chosen_port}/.well-known/agent-card.json",
        "remote_command": remote_command,
        "command": command,
        "command_string": " ".join(command),
        "env": display_env,
        "hint": "Use hypervisor run-agent with --detach to start the agent on the remote host.",
    }


def apply_ssh_run_plan(
    plan: dict[str, Any],
    *,
    wait_healthy: bool = False,
    timeout_s: float = 30.0,
) -> dict[str, Any]:
    import subprocess
    import time
    import urllib.error
    import urllib.request

    from uri3.resolvers.ssh_resolver import build_ssh_command, parse_ssh_uri

    ssh_ref = parse_ssh_uri(plan["target_uri"])
    remote_path = plan["remote_path"]
    log_path = f"{remote_path}/agent.process.log"
    remote_start = (
        f"cd {shlex.quote(remote_path)} && "
        f"nohup {plan['remote_command']} >> {shlex.quote(log_path)} 2>&1 & echo $!"
    )
    completed = subprocess.run(
        build_ssh_command(ssh_ref, remote_start),
        capture_output=True,
        text=True,
        check=False,
    )
    payload: dict[str, Any] = {
        "ok": completed.returncode == 0,
        "transport": "ssh",
        "deployment_id": plan["deployment_id"],
        "remote_path": remote_path,
        "remote_command": plan["remote_command"],
        "log_path": log_path,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
        "health_uri": plan["health_uri"],
    }
    if completed.returncode != 0:
        payload["error"] = completed.stderr.strip() or "remote start failed"
        return payload
    pid_text = completed.stdout.strip().splitlines()[-1] if completed.stdout.strip() else ""
    if pid_text.isdigit():
        payload["remote_pid"] = int(pid_text)
    if wait_healthy:
        deadline = time.time() + timeout_s
        health_uri = str(plan["health_uri"])
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(health_uri, timeout=2) as response:
                    if response.status == 200:
                        payload["service_healthy"] = True
                        break
            except (urllib.error.URLError, TimeoutError):
                time.sleep(0.5)
        else:
            payload["service_healthy"] = False
            payload["warning"] = f"remote process started but health check timed out: {health_uri}"
    return payload
