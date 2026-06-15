from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from uri3.routing import explain_semantic_uri

from hypervisor.paths import find_repo_root
from hypervisor.routing.models import HypervisorRouteResolution
from hypervisor.routing.policy import evaluate_route_policy_decision
from hypervisor.routing.registry_bridge import load_runtime_registry, resolve_operator_by_scheme


def resolve_hypervisor_route(
    input_uri: str,
    *,
    payload: dict[str, Any] | None = None,
    root: str | Path | None = None,
    environment: str | None = None,
    approved: bool = False,
) -> HypervisorRouteResolution:
    repo = Path(root) if root is not None else find_repo_root()
    semantic = explain_semantic_uri(input_uri, root=repo)
    registry = load_runtime_registry(repo)
    operator_id, operator = resolve_operator_by_scheme(
        _canonical_operator_scheme(semantic.route),
        root=repo,
    )
    selected_environment, selected_adapter = _select_environment_and_adapter(
        explicit=environment,
        payload=payload or {},
        operator=operator,
        registry=registry,
    )
    policy = evaluate_route_policy_decision(
        input_uri,
        approved=approved,
        root=repo,
    )
    route = semantic.route
    runtime = {
        "type": "uri2ops",
        "uri": route.input_uri,
        "canonical_uri": route.canonical_uri,
        "scheme": _canonical_operator_scheme(route),
        "operation": route.action or "call",
        "environment": selected_environment,
        "deployment_id": operator_id,
    }
    if selected_adapter:
        runtime["adapter"] = selected_adapter
    agent_uri = str(operator.get("agent_ref") or "") if operator else None
    if agent_uri:
        runtime["agent_uri"] = agent_uri
    operator_url = _operator_base_url(operator)
    if operator_url:
        runtime["operator_url"] = operator_url

    context = {
        "root": str(repo),
        "uri": route.input_uri,
        "canonical_uri": route.canonical_uri,
        "scheme": runtime["scheme"],
        "operation": runtime["operation"],
        "environment": selected_environment,
        "deployment_id": operator_id,
        "agent_uri": agent_uri,
        "adapter": selected_adapter,
    }
    session = _payload_session(payload or {})
    if session is not None:
        context["session"] = session
    return HypervisorRouteResolution(
        route=route,
        agent_uri=agent_uri,
        deployment_id=operator_id,
        environment_uri=f"environment://{selected_environment}" if selected_environment else None,
        contract_uri=semantic.contract_uri,
        policy_uri=semantic.policy_uri,
        side_effects=semantic.side_effects,
        requires_approval=semantic.requires_approval,
        runtime=runtime,
        context={key: value for key, value in context.items() if value is not None},
        policy=policy,
    )


def _select_environment_and_adapter(
    *,
    explicit: str | None,
    payload: dict[str, Any],
    operator: dict[str, Any],
    registry: dict[str, Any],
) -> tuple[str, str | None]:
    raw = explicit or payload.get("environment") or operator.get("default_execution_environment")
    adapter = str(payload.get("adapter") or "") or None
    if not raw:
        raw = (registry.get("defaults") or {}).get("execution_environment") or "local"
    raw_value = str(raw)
    if raw_value in {"auto", "playwright"}:
        adapter = adapter or raw_value
        raw_value = "local"
    environment = _normalize_environment(raw_value, registry)
    if environment == "mock":
        adapter = "mock"
    return environment, adapter


def _payload_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    session = payload.get("session")
    return session if isinstance(session, dict) else None


def _normalize_environment(value: str, registry: dict[str, Any]) -> str:
    environments = registry.get("environments") or {}
    if value in environments:
        return value
    for name, spec in environments.items():
        if not isinstance(spec, dict):
            continue
        aliases = {str(item) for item in spec.get("aliases") or []}
        if value in aliases:
            return str(name)
    return value


def _canonical_operator_scheme(route) -> str:
    if route.domain.startswith("operators/"):
        return route.domain.rsplit("/", 1)[-1]
    return str(route.scheme or "")


def _operator_base_url(operator: dict[str, Any]) -> str | None:
    endpoints = operator.get("endpoints") or {}
    mcp_call = endpoints.get("mcp_call")
    if mcp_call:
        return str(mcp_call).rsplit("/mcp/tools/call", 1)[0]
    health = endpoints.get("health")
    if health:
        parsed = urlparse(str(health))
        if parsed.scheme and parsed.netloc:
            return f"{parsed.scheme}://{parsed.netloc}"
    port = operator.get("port")
    if port:
        return f"http://127.0.0.1:{port}"
    return None
