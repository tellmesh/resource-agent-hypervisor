from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from uri3.resolvers.explain import explain_uri

_OPERATOR_SCHEMES = frozenset(
    {"browser", "dom", "screen", "input", "android", "pcwin", "robot", "device"}
)
_HYPERVISOR_SYSTEM_SCHEMES = frozenset(
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
        "view",
        "resource",
    }
)


def explain_semantic_route(uri: str, *, root: Path | None = None) -> dict[str, Any] | None:
    try:
        from uri3.routing import explain_semantic_uri

        return explain_semantic_uri(uri, root=root).to_dict()
    except Exception:
        return None


def explain_executable_uri(
    uri: str,
    *,
    root: Path | None = None,
    approved: bool = False,
    dry_run: bool = False,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Semantic explain (uri3) plus hypervisor executive resolution when applicable."""
    explain = explain_uri(uri, root=root)
    body: dict[str, Any] = {
        "ok": True,
        "result_type": "explain",
        "uri": uri,
        "dry_run": dry_run,
        "explain": explain,
        "semantic_route": explain_semantic_route(uri, root=root),
    }
    scheme = urlparse(uri).scheme
    if scheme in _OPERATOR_SCHEMES:
        from hypervisor.routing import resolve_hypervisor_route

        try:
            resolution = resolve_hypervisor_route(
                uri,
                payload=payload or {},
                root=root,
                approved=approved,
            )
        except Exception as exc:  # pragma: no cover - defensive explain enrichment
            body["hypervisor_resolution_error"] = str(exc)
        else:
            body["hypervisor_resolution"] = resolution.to_dict()
            body["canonical_uri"] = resolution.route.canonical_uri
    elif scheme in _HYPERVISOR_SYSTEM_SCHEMES:
        body["executable_layer"] = "hypervisor.system_dispatch"
    return body
