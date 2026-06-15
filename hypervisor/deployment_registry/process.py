from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any


def _safe_log_stem(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)
    return safe or "agent"


def process_log_path(plan: dict[str, Any], *, root: Path) -> Path:
    deployment_id = str(plan.get("deployment_id") or plan.get("id") or "agent")
    path = root / "output" / "logs" / "agents" / f"{_safe_log_stem(deployment_id)}.process.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def process_log_uri(path: Path, *, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path
    return f"log://file/{relative.as_posix()}"


def start_process(
    plan: dict[str, Any],
    *,
    root: Path,
    detach: bool,
    runtime_env: dict[str, str] | None = None,
) -> subprocess.Popen[Any] | None:
    env = os.environ.copy()
    env.update(runtime_env or plan.get("env") or {})
    cwd = str(root)
    command = plan["command"]
    if detach:
        log_path = process_log_path(plan, root=root)
        plan["process_log_path"] = str(log_path)
        plan["process_log_uri"] = process_log_uri(log_path, root=root)
        log_handle = log_path.open("ab", buffering=0)
        try:
            return subprocess.Popen(
                command,
                cwd=cwd,
                env=env,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        finally:
            log_handle.close()
    subprocess.run(command, check=True, cwd=cwd, env=env)
    return None
