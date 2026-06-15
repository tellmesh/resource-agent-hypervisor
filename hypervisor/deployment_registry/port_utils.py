from __future__ import annotations

import socket
from typing import Any
from urllib.parse import urlparse


def is_port_free(port: int, *, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as handle:
        handle.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            handle.bind((host, port))
            return True
        except OSError:
            return False


def find_free_port(preferred: int, *, attempts: int = 30) -> int:
    if is_port_free(preferred):
        return preferred
    for offset in range(1, attempts + 1):
        candidate = preferred + offset
        if is_port_free(candidate):
            return candidate
    raise RuntimeError(f"no free port found near {preferred}")


def expected_agent_id(agent_ref: str | None) -> str | None:
    if not agent_ref:
        return None
    return agent_ref.removeprefix("agent://")


def port_from_http_uri(uri: str | None) -> int | None:
    if not uri:
        return None
    parsed = urlparse(uri)
    return parsed.port


def health_matches_agent(probe: dict[str, Any], *, expected_agent: str | None) -> bool:
    if not expected_agent:
        return bool(probe.get("ok"))
    payload = probe.get("payload")
    if not isinstance(payload, dict):
        return False
    agent = payload.get("agent")
    if agent is None:
        return False
    return str(agent) == expected_agent


def foreign_service_detail(probe: dict[str, Any]) -> str | None:
    payload = probe.get("payload")
    if not isinstance(payload, dict):
        return None
    if payload.get("service"):
        return str(payload["service"])
    agent = payload.get("agent")
    if agent:
        return str(agent)
    return None
