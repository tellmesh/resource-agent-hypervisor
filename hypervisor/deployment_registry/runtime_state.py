from __future__ import annotations

import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hypervisor.paths import find_repo_root

RUNTIME_STATE_SCHEMA = "schemas/runtime_state.schema.json"


def runtime_root(root: Path | None = None) -> Path:
    repo = Path(root) if root is not None else find_repo_root()
    return repo / "output" / "runtime" / "agents"


def state_path(deployment_id: str, root: Path | None = None) -> Path:
    return runtime_root(root) / deployment_id / "state.json"


def _port_from_http_uri(uri: str | None) -> int | None:
    if not uri:
        return None
    parsed = urlparse(uri)
    if parsed.port is not None:
        return parsed.port
    if parsed.scheme == "http":
        return 80
    if parsed.scheme == "https":
        return 443
    return None


def _port_from_command(command: str | None) -> int | None:
    if not command:
        return None
    match = re.search(r"--port(?:=|\s+)(\d+)", command)
    return int(match.group(1)) if match else None


def _process_status(raw: dict[str, Any]) -> str:
    status = raw.get("status")
    if isinstance(status, dict):
        return str(status.get("process_status") or "unknown")
    return str(status or "unknown")


def _health_uri(raw: dict[str, Any]) -> str:
    network = raw.get("network") or {}
    if isinstance(network, dict) and network.get("effective_health_uri"):
        return str(network["effective_health_uri"])
    return str(raw.get("health_uri") or "")


def _pid(raw: dict[str, Any]) -> int | None:
    process = raw.get("process") or {}
    if isinstance(process, dict) and process.get("pid") is not None:
        return process.get("pid")
    return raw.get("pid")


def _command(raw: dict[str, Any]) -> str:
    process = raw.get("process") or {}
    if isinstance(process, dict) and process.get("command"):
        return str(process["command"])
    return str(raw.get("command") or "")


# Public aliases for shared use across deployment_registry (lifecycle, pipeline, etc.)
# to reduce duplication and help large-module metrics.
state_pid = _pid
state_command = _command


def state_health_uri(raw: dict[str, Any]) -> str:
    """Public version of the health uri extractor from raw/legacy state."""
    network = raw.get("network") or {}
    if isinstance(network, dict) and network.get("effective_health_uri"):
        return str(network["effective_health_uri"])
    return str(raw.get("health_uri") or "")




def _process_log_path(raw: dict[str, Any]) -> str | None:
    process = raw.get("process") or {}
    if isinstance(process, dict) and process.get("log_path"):
        return str(process["log_path"])
    value = raw.get("process_log_path")
    return str(value) if value else None


def _process_log_uri(raw: dict[str, Any]) -> str | None:
    process = raw.get("process") or {}
    if isinstance(process, dict) and process.get("log_uri"):
        return str(process["log_uri"])
    value = raw.get("process_log_uri")
    return str(value) if value else None


def _build_uri_block(raw: dict[str, Any], dep_id: str) -> dict[str, Any]:
    block: dict[str, Any] = {
        "self": f"runtime://agent/{dep_id}/state",
        "deployment": f"hypervisor://local/{dep_id}",
    }
    if raw.get("agent_ref"):
        block["agent"] = raw.get("agent_ref")
    return block


def _build_process_block(raw: dict[str, Any], command: str) -> dict[str, Any]:
    process_log_path = _process_log_path(raw)
    process_log_uri = _process_log_uri(raw)
    block: dict[str, Any] = {
        "pid": _pid(raw),
        "command": command,
    }
    if process_log_path:
        block["log_path"] = process_log_path
    if process_log_uri:
        block["log_uri"] = process_log_uri
    return block


def _build_status_block(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "process_status": str(raw.get("status") or "unknown"),
        "health_status": str(raw.get("health_status") or "unknown"),
        "lifecycle_status": str(raw.get("lifecycle_status") or raw.get("status") or "unknown"),
        "deployment_status": str(raw.get("deployment_status") or "unknown"),
        "service_result_status": str(raw.get("service_result_status") or "unknown"),
    }


def _build_network_block(command: str, health_uri: str, raw: dict[str, Any]) -> dict[str, Any]:
    effective_port = _port_from_command(command) or _port_from_http_uri(health_uri)
    return {
        "requested_port": raw.get("requested_port"),
        "effective_port": effective_port,
        "effective_health_uri": health_uri,
        "declared_health_uri": raw.get("declared_health_uri"),
    }


def _legacy_runtime_state(raw: dict[str, Any], *, deployment_id: str | None) -> dict[str, Any]:
    command = _command(raw)
    health_uri = str(raw.get("health_uri") or "")
    dep_id = str(deployment_id or raw.get("id") or "")
    process_log_path = _process_log_path(raw)
    process_log_uri = _process_log_uri(raw)

    uri_block = _build_uri_block(raw, dep_id)
    process_block = _build_process_block(raw, command)
    status_block = _build_status_block(raw)
    network_block = _build_network_block(command, health_uri, raw)

    return {
        "$schema": RUNTIME_STATE_SCHEMA,
        "apiVersion": "uri3.io/v1",
        "kind": "RuntimeState",
        "id": dep_id,
        "agent_ref": raw.get("agent_ref"),
        "uri": uri_block,
        "status": status_block,
        "process": process_block,
        "network": network_block,
        "started_at": raw.get("started_at"),
        "stopped_at": raw.get("stopped_at"),
        "command": command,
        "health_uri": health_uri,
        "log_uri": raw.get("log_uri"),
        "process_log_path": process_log_path,
        "process_log_uri": process_log_uri,
        "env": raw.get("env") or {},
    }


def _apply_flat_accessors(body: dict[str, Any]) -> dict[str, Any]:
    body["pid"] = _pid(body)
    body["process_status"] = _process_status(body)
    body["status"] = (
        body.get("status")
        if isinstance(body.get("status"), dict)
        else {
            "process_status": str(body.get("status") or "unknown"),
        }
    )
    body["command"] = _command(body)
    body["health_uri"] = _health_uri(body)
    body["process_log_path"] = _process_log_path(body)
    body["process_log_uri"] = _process_log_uri(body)
    return body


def normalize_runtime_state(
    raw: dict[str, Any], *, deployment_id: str | None = None
) -> dict[str, Any]:
    """Upgrade legacy flat runtime state to schema artifact while keeping flat accessors."""
    if raw.get("kind") == "RuntimeState" and isinstance(raw.get("status"), dict):
        body = dict(raw)
    else:
        body = _legacy_runtime_state(raw, deployment_id=deployment_id)
    return _apply_flat_accessors(body)


def load_runtime_state(deployment_id: str, root: Path | None = None) -> dict[str, Any] | None:
    path = state_path(deployment_id, root)
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return None
    return normalize_runtime_state(data, deployment_id=deployment_id)


def save_runtime_state(deployment_id: str, state: dict[str, Any], root: Path | None = None) -> Path:
    repo = Path(root) if root is not None else find_repo_root()
    normalized = normalize_runtime_state(
        {**state, "id": deployment_id}, deployment_id=deployment_id
    )
    artifact = dict(normalized)
    artifact.pop("process_status", None)
    for key in (
        "started_at",
        "stopped_at",
        "log_uri",
        "process_log_path",
        "process_log_uri",
        "agent_ref",
        "command",
        "health_uri",
    ):
        if artifact.get(key) is None:
            artifact.pop(key, None)
    uri = dict(artifact.get("uri") or {})
    if uri.get("agent") is None:
        uri.pop("agent", None)
    network = dict(artifact.get("network") or {})
    for key in list(network):
        if network[key] is None:
            network.pop(key)
    if network:
        artifact["network"] = network
    elif "network" in artifact:
        artifact.pop("network")
    if uri:
        artifact["uri"] = uri
    from uri3.artifacts.writer import write_json_artifact

    return write_json_artifact(
        state_path(deployment_id, repo),
        artifact,
        repo_root=repo,
        schema_relative=RUNTIME_STATE_SCHEMA,
        validate=True,
    )


def clear_runtime_state(deployment_id: str, root: Path | None = None) -> None:
    path = state_path(deployment_id, root)
    if path.exists():
        path.unlink()


def is_process_alive(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def runtime_status(deployment_id: str, root: Path | None = None) -> str:
    state = load_runtime_state(deployment_id, root)
    if not state:
        return "stopped"
    pid = _pid(state)
    process_status = _process_status(state)
    if process_status == "running" and is_process_alive(pid):
        return "running"
    if process_status == "running":
        return "stale"
    return process_status or "stopped"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
