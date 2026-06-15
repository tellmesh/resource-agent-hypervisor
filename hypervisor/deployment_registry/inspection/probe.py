from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

from hypervisor.deployment_registry.port_utils import foreign_service_detail


def _probe_payload_ok(
    payload: Any,
    *,
    response_ok: bool,
    expected_agent: str | None,
    expected_service: str | None = None,
) -> bool:
    if not response_ok:
        return False
    if not isinstance(payload, dict):
        return True
    if payload.get("ok") is False:
        return False
    if not expected_agent:
        if expected_service and payload.get("service") is not None:
            return str(payload["service"]) == expected_service
        return True
    agent_name = payload.get("agent")
    if agent_name is not None and str(agent_name) != expected_agent:
        return False
    if agent_name is None and response_ok and payload.get("service"):
        return bool(expected_service and str(payload["service"]) == expected_service)
    return True


def _host_probe_uri(uri: str) -> str:
    bridge_host = os.environ.get("HYPERVISOR_PROBE_HOST", "").strip()
    if not bridge_host:
        return uri
    try:
        parsed = urlsplit(uri)
    except ValueError:
        return uri
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return uri
    netloc = bridge_host
    if parsed.port:
        netloc = f"{bridge_host}:{parsed.port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _probe_response(
    uri: str,
    response: httpx.Response,
    *,
    expected_agent: str | None,
    expected_service: str | None = None,
    probe_uri: str | None = None,
) -> dict[str, Any]:
    content_type = response.headers.get("content-type", "")
    payload = response.json() if "json" in content_type else None
    json_ok = payload.get("ok") if isinstance(payload, dict) else None
    agent_name = payload.get("agent") if isinstance(payload, dict) else None
    service_name = payload.get("service") if isinstance(payload, dict) else None
    ok = _probe_payload_ok(
        payload,
        response_ok=response.is_success,
        expected_agent=expected_agent,
        expected_service=expected_service,
    )
    foreign = None
    if not ok and isinstance(payload, dict):
        foreign = foreign_service_detail({"payload": payload})
    result = {
        "uri": uri,
        "ok": ok,
        "status_code": response.status_code,
        "json_ok": json_ok,
        "agent": agent_name,
        "service": service_name,
        "payload": payload if isinstance(payload, dict) else None,
        "foreign_service": foreign,
    }
    if probe_uri and probe_uri != uri:
        result["probe_uri"] = probe_uri
    return result


def probe_http(
    uri: str | None,
    *,
    timeout: float,
    expected_agent: str | None = None,
    expected_service: str | None = None,
) -> dict[str, Any]:
    if not uri or not uri.startswith(("http://", "https://")):
        return {"uri": uri, "ok": False, "skipped": True, "reason": "missing http uri"}
    probe_uri = _host_probe_uri(uri)
    try:
        response = httpx.get(probe_uri, timeout=timeout)
        return _probe_response(
            uri,
            response,
            expected_agent=expected_agent,
            expected_service=expected_service,
            probe_uri=probe_uri,
        )
    except Exception as exc:
        result = {"uri": uri, "ok": False, "error": str(exc)}
        if probe_uri != uri:
            result["probe_uri"] = probe_uri
        return result


def log_uri_with_filters(log_uri: str, *, limit: int, level: str = "ERROR") -> str:
    parsed = urlsplit(log_uri)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    query.setdefault("level", level)
    query["limit"] = str(limit)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment)
    )


def read_error_logs(log_uri: str, *, root: Path, limit: int) -> dict[str, Any]:
    filtered = log_uri_with_filters(log_uri, limit=limit)
    try:
        from uri3.logs.reader import read_logs_result, summarize_logs

        summary = summarize_logs(filtered, root=root)
        entries = read_logs_result(filtered, root=root)
        if isinstance(entries, dict):
            log_entries = entries.get("entries") or []
            hint = entries.get("hint")
        else:
            log_entries = entries
            hint = ""
        return {
            "uri": filtered,
            "summary": summary,
            "entries": log_entries[-limit:],
            "hint": hint,
            "error_count": len(log_entries),
        }
    except Exception as exc:
        return {"uri": filtered, "summary": {}, "entries": [], "error": str(exc), "error_count": 0}
