from __future__ import annotations

from pathlib import Path
from typing import Any

from uri3.results import ServiceResult, service_result

from hypervisor.routing.resolver import resolve_hypervisor_route


def call_uri(
    input_uri: str,
    payload: dict[str, Any] | None = None,
    *,
    root: str | Path | None = None,
    environment: str | None = None,
    approved: bool = False,
) -> ServiceResult:
    """Resolve a URI through hypervisor routing and execute the selected runtime backend."""
    call_payload = payload if payload is not None else {}
    resolution = resolve_hypervisor_route(
        input_uri,
        payload=call_payload,
        root=root,
        environment=environment,
        approved=approved,
    )
    if not resolution.policy.allowed:
        return service_result(
            ok=False,
            result_type="policy_decision",
            uri=input_uri,
            data={
                "canonical_uri": resolution.route.canonical_uri,
                "policy": resolution.policy.to_dict(),
                "resolution": resolution.to_dict(),
            },
            errors=[
                {
                    "code": "ROUTE_REQUIRES_APPROVAL",
                    "source": resolution.policy_uri or input_uri,
                    "detail": "; ".join(resolution.policy.reasons),
                    "recoverable": True,
                }
            ],
        )

    try:
        from uri2run import run_backend
    except Exception as exc:
        return service_result(
            ok=False,
            result_type="runtime_dispatch",
            uri=input_uri,
            errors=[
                {
                    "code": "RUNTIME_UNAVAILABLE",
                    "source": "hypervisor.routing",
                    "detail": str(exc),
                    "recoverable": True,
                }
            ],
            meta={"resolution": resolution.to_dict()},
        )

    result = run_backend(resolution.runtime, call_payload, resolution.context)
    result.uri = result.uri or input_uri
    result.meta.setdefault("canonical_uri", resolution.route.canonical_uri)
    result.meta.setdefault("agent_uri", resolution.agent_uri)
    result.meta.setdefault("deployment_id", resolution.deployment_id)
    result.meta.setdefault("environment_uri", resolution.environment_uri)
    result.meta.setdefault("hypervisor_resolution", resolution.to_dict())
    return result.finalize()
