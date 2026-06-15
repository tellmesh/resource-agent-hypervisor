from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.ssh_helpers import generated_agent_dir
from hypervisor.paths import find_repo_root
from uri3.resolvers.ssh_resolver import parse_ssh_uri, ssh_transport_option


def build_ssh_deploy_plan(
    deployment,
    *,
    root: Path | None = None,
) -> dict[str, Any]:
    repo = root or find_repo_root()
    ssh_ref = parse_ssh_uri(deployment.target_uri)
    source = generated_agent_dir(deployment.agent_ref, repo)
    if not source.exists():
        raise FileNotFoundError(f"Generated agent source not found: {source}")
    remote_path = ssh_ref["path"]
    transport = ssh_transport_option(ssh_ref)
    rsync_cmd = [
        "rsync",
        "-avz",
        "--delete",
        "-e",
        transport,
        f"{source}/",
        f"{ssh_ref['target']}:{remote_path}/",
    ]
    post_deploy_checks = [
        f"test -d {shlex.quote(remote_path)}",
        f"test -f {shlex.quote(remote_path)}/main.py",
    ]
    return {
        "deployment_id": deployment.id,
        "agent_ref": deployment.agent_ref,
        "target_uri": deployment.target_uri,
        "ssh": ssh_ref,
        "local_source": str(source),
        "remote_path": remote_path,
        "steps": [
            {
                "action": "rsync",
                "description": "Sync generated agent package to remote host",
                "command": rsync_cmd,
                "command_string": " ".join(rsync_cmd),
            },
            {
                "action": "verify_remote_path",
                "description": "Verify remote agent directory exists",
                "remote_commands": post_deploy_checks,
            },
        ],
        "hint": "Use hypervisor deploy-agent --apply to run rsync (requires SSH auth).",
    }


def apply_ssh_deploy_plan(plan: dict[str, Any]) -> dict[str, Any]:
    import subprocess

    from uri3.resolvers.ssh_resolver import build_ssh_command, parse_ssh_uri

    results: list[dict[str, Any]] = []
    for step in plan["steps"]:
        if step["action"] == "rsync":
            completed = subprocess.run(step["command"], capture_output=True, text=True, check=False)
            results.append(
                {
                    "action": "rsync",
                    "returncode": completed.returncode,
                    "stdout": completed.stdout,
                    "stderr": completed.stderr,
                }
            )
            if completed.returncode != 0:
                return {"ok": False, "steps": results}
        elif step["action"] == "verify_remote_path":
            ref = parse_ssh_uri(plan["target_uri"])
            for remote_cmd in step["remote_commands"]:
                completed = subprocess.run(build_ssh_command(ref, remote_cmd), capture_output=True, text=True)
                results.append(
                    {
                        "action": "verify_remote_path",
                        "command": remote_cmd,
                        "returncode": completed.returncode,
                        "stdout": completed.stdout,
                        "stderr": completed.stderr,
                    }
                )
                if completed.returncode != 0:
                    return {"ok": False, "steps": results}
    return {"ok": True, "steps": results}
