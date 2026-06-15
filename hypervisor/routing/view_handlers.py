from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from hypervisor.routing.system_request import uri_path_parts
from hypervisor.routing.views.process import build_process_view_data

ViewRenderer = Callable[[str, dict[str, Any]], str | None]

_view_renderer: ViewRenderer | None = None


@dataclass
class ViewEnvelope:
    view_uri: str
    content_type: str
    title: str
    data: dict[str, Any]
    html: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "result_type": "view",
            "view_uri": self.view_uri,
            "content_type": self.content_type,
            "title": self.title,
            "data": self.data,
        }
        if self.html is not None:
            payload["html"] = self.html
        return payload


def register_view_renderer(renderer: ViewRenderer | None) -> None:
    global _view_renderer
    _view_renderer = renderer


def supports_view_uri(uri: str) -> bool:
    parsed = urlparse(uri.strip())
    if parsed.scheme == "view":
        return True
    if parsed.scheme == "resource":
        parts = uri_path_parts(uri)
        return bool(parts) and parts[0] == "dashboard"
    return False


def normalize_view_uri(uri: str) -> str | None:
    parsed = urlparse(uri)
    parts = uri_path_parts(uri)
    if parsed.scheme == "view":
        return uri
    if parsed.scheme == "resource" and parts and parts[0] == "dashboard":
        tail = parts[1:]
        if tail[:2] == ["repair", "agent"] and len(tail) >= 4 and tail[3] == "diagnosis":
            return f"repair://agent/{tail[2]}/diagnose"
        return "view://" + "/".join(tail)
    return None


def resolve_view_envelope(
    view_uri: str,
    *,
    root: Path | None = None,
    renderer: ViewRenderer | None = None,
) -> ViewEnvelope:
    parsed = urlparse(view_uri)
    if parsed.scheme != "view":
        raise ValueError(f"unsupported view URI scheme: {view_uri}")
    parts = uri_path_parts(view_uri)
    if len(parts) >= 4 and parts[0] == "process" and parts[1] == "agent" and parts[3] == "latest":
        agent_id = parts[2]
        data = build_process_view_data(agent_id, root=root)
        envelope = ViewEnvelope(
            view_uri=view_uri,
            content_type="text/html",
            title=str(data["title"]),
            data=data,
        )
    elif len(parts) >= 3 and parts[0] == "incident" and parts[2] == "explain":
        incident_id = parts[1]
        envelope = ViewEnvelope(
            view_uri=view_uri,
            content_type="application/json",
            title=f"Incident {incident_id}",
            data={"incident_id": incident_id, "status": "planned", "view_kind": "incident"},
        )
    else:
        raise ValueError(f"unsupported view URI: {view_uri}")

    render_fn = renderer or _view_renderer
    if render_fn and envelope.content_type == "text/html" and envelope.html is None:
        envelope = ViewEnvelope(
            view_uri=envelope.view_uri,
            content_type=envelope.content_type,
            title=envelope.title,
            data=envelope.data,
            html=render_fn(view_uri, envelope.data),
        )
    return envelope


def handle_view_uri(
    uri: str,
    *,
    repo: Path,
    approved: bool = False,
    dry_run: bool = False,
    payload: dict[str, Any] | None = None,
    system_uri_handler: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    normalized = normalize_view_uri(uri)
    if normalized and normalized.startswith("repair://"):
        dispatch = system_uri_handler
        if dispatch is None:
            from hypervisor.routing.system_dispatch import call_hypervisor_system_uri

            dispatch = call_hypervisor_system_uri
        return dispatch(
            normalized,
            root=repo,
            approved=approved,
            dry_run=dry_run,
            payload=payload,
        )
    if normalized:
        view = resolve_view_envelope(normalized, root=repo).to_dict()
        return {
            "ok": True,
            "workflow_status": "completed",
            "service_result_status": "succeeded",
            **view,
        }
    raise ValueError(f"unsupported dashboard resource URI: {uri}")
