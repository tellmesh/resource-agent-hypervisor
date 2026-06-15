from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse


def port_from_http_uri(uri: str | None) -> int | None:
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


def port_from_command(command: str | None) -> int | None:
    if not command:
        return None
    match = re.search(r"--port(?:=|\s+)(\d+)", command)
    return int(match.group(1)) if match else None


def health_uri_for_port(port: int) -> str:
    return f"http://localhost:{port}/health"


def _runtime_command(state: dict[str, Any], plan: dict[str, Any]) -> str:
    process = state.get("process") or {}
    if isinstance(process, dict) and process.get("command"):
        return str(process["command"])
    return str(state.get("command") or plan.get("command_string") or "")


def _network_effective_port(state: dict[str, Any]) -> int | None:
    network = state.get("network") or {}
    if isinstance(network, dict) and network.get("effective_port") is not None:
        return int(network["effective_port"])
    return None


def resolve_effective_health_uri(state: dict[str, Any], plan: dict[str, Any]) -> str:
    network = state.get("network") or {}
    if isinstance(network, dict) and network.get("effective_health_uri"):
        return str(network["effective_health_uri"])
    command_port = port_from_command(_runtime_command(state, plan))
    if command_port is not None:
        return health_uri_for_port(command_port)
    network_port = _network_effective_port(state)
    if network_port is not None:
        return health_uri_for_port(network_port)
    return str(state.get("health_uri") or plan.get("health_uri") or "")


def command_port_from_runtime(state: dict[str, Any], plan: dict[str, Any]) -> int | None:
    command_port = port_from_command(_runtime_command(state, plan))
    if command_port is not None:
        return command_port
    network_port = _network_effective_port(state)
    if network_port is not None:
        return network_port
    return port_from_http_uri(str(state.get("health_uri") or plan.get("health_uri") or ""))
