from __future__ import annotations

from typing import Any

import httpx


class ResourceRuntimeClient:
    """Small HTTP client used by generated thin agents.

    Expected runtime API:
    - GET  /resources/read?uri=resource://...
    - POST /commands with {"command": "...", "payload": {...}}
    """

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def read_resource(self, uri: str) -> dict[str, Any]:
        url = f"{self.base_url}/resources/read"
        try:
            response = httpx.get(url, params={"uri": uri}, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "error": "RESOURCE_RUNTIME_UNAVAILABLE",
                "message": str(exc),
                "uri": uri,
            }

    def dispatch_command(self, command: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url}/commands"
        body = {"command": command, "payload": payload}
        try:
            response = httpx.post(url, json=body, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as exc:
            return {
                "ok": False,
                "error": "RESOURCE_RUNTIME_UNAVAILABLE",
                "message": str(exc),
                "command": command,
            }
