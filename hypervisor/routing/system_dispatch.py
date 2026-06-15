from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from hypervisor.paths import find_repo_root
from hypervisor.routing.system_handlers import (
    handle_agent_factory_uri,
    handle_contract_uri,
    handle_file_uri,
    handle_health_uri,
    handle_hypervisor_agent_uri,
    handle_log_uri,
    handle_repair_uri,
    handle_runtime_uri,
    handle_schema_uri,
)
from hypervisor.routing.system_request import SystemUriRequest, uri_path_parts

_SystemUriHandler = Callable[[SystemUriRequest], dict[str, Any]]

HYPERVISOR_SYSTEM_SCHEMES = frozenset(
    {
        "health",
        "runtime",
        "repair",
        "schema",
        "contract",
        "hypervisor",
        "log",
        "file",
        "agent-factory",
    }
)


def supports_hypervisor_system_uri(uri: str) -> bool:
    parsed = urlparse(uri.strip())
    return parsed.scheme in HYPERVISOR_SYSTEM_SCHEMES


def _is_runtime_request(request: SystemUriRequest) -> bool:
    return (
        request.scheme == "runtime"
        and len(request.parts) >= 3
        and request.parts[0] == "agent"
        and request.parts[2] == "state"
    )


def _is_health_request(request: SystemUriRequest) -> bool:
    return request.scheme == "health" and len(request.parts) >= 2 and request.parts[0] == "agent"


def _is_schema_request(request: SystemUriRequest) -> bool:
    return request.scheme == "schema" and len(request.parts) >= 2 and request.parts[0] == "agent"


def _is_repair_request(request: SystemUriRequest) -> bool:
    return request.scheme == "repair" and len(request.parts) >= 3 and request.parts[0] == "agent"


def _is_contract_request(request: SystemUriRequest) -> bool:
    return request.scheme == "contract"


def _is_agent_factory_request(request: SystemUriRequest) -> bool:
    return request.scheme == "agent-factory"


def _is_hypervisor_agent_request(request: SystemUriRequest) -> bool:
    if request.scheme != "hypervisor":
        return False
    from hypervisor.deployment_registry.selector import parse_hypervisor_uri

    try:
        selector, action = parse_hypervisor_uri(request.uri)
    except ValueError:
        return False
    return action == "run" and bool(selector) and selector != "unknown"


def _runtime_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_runtime_uri(request.parts, repo=request.repo)


def _health_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_health_uri(request.parts, repo=request.repo)


def _schema_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_schema_uri(request.parts, repo=request.repo)


def _repair_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_repair_uri(
        request.parts,
        repo=request.repo,
        approved=request.approved,
        dry_run=request.dry_run,
    )


def _agent_factory_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_agent_factory_uri(request)


def _hypervisor_agent_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_hypervisor_agent_uri(request)


def _log_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_log_uri(request.uri, repo=request.repo)


def _file_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_file_uri(request.uri)


def _contract_request(request: SystemUriRequest) -> dict[str, Any]:
    return handle_contract_uri(request.uri, request.repo)


_HYPERVISOR_SYSTEM_DISPATCH: tuple[
    tuple[Callable[[SystemUriRequest], bool], _SystemUriHandler],
    ...,
] = (
    (_is_runtime_request, _runtime_request),
    (_is_health_request, _health_request),
    (_is_schema_request, _schema_request),
    (_is_contract_request, _contract_request),
    (_is_repair_request, _repair_request),
    (_is_agent_factory_request, _agent_factory_request),
    (_is_hypervisor_agent_request, _hypervisor_agent_request),
    (lambda request: request.scheme == "log", _log_request),
    (lambda request: request.scheme == "file", _file_request),
)


def _select_hypervisor_system_handler(
    request: SystemUriRequest,
) -> _SystemUriHandler | None:
    for matches, handler in _HYPERVISOR_SYSTEM_DISPATCH:
        if matches(request):
            return handler
    return None


def call_hypervisor_system_uri(
    uri: str,
    *,
    root: Path | None = None,
    artifact_root: Path | None = None,
    approved: bool = False,
    dry_run: bool = False,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    repo = root or find_repo_root()
    parsed = urlparse(uri)
    request = SystemUriRequest(
        uri=uri,
        repo=repo,
        approved=approved,
        dry_run=dry_run,
        payload=payload,
        scheme=parsed.scheme,
        parts=uri_path_parts(uri),
        artifact_root=artifact_root,
    )
    handler = _select_hypervisor_system_handler(request)
    if handler is None:
        raise ValueError(f"unsupported hypervisor system URI: {uri}")
    return handler(request)
