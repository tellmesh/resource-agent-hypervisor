from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from hypervisor.deployment_registry.aliases import load_deployment_selector_aliases
from hypervisor.deployment_registry.loader import load_deployment_registry
from hypervisor.deployment_registry.models import AgentDeployment


def parse_hypervisor_uri(uri: str) -> tuple[str, str]:
    """Return ``(deployment_selector, action)`` for a hypervisor URI."""
    parsed = urlparse(uri)
    parts = [part for part in parsed.path.split("/") if part]
    action = parts[-1] if parts else "run"

    if parsed.netloc == "local":
        selector = parts[0] if parts else "unknown"
        if len(parts) > 1:
            action = parts[-1]
        return selector, action

    if parsed.netloc == "deployment":
        selector = parts[0] if parts else "unknown"
        return selector, action

    if parts and parts[0] == "deployment" and len(parts) >= 2:
        return parts[1], action

    selector = parts[0] if parts else (parsed.netloc or "unknown")
    return selector, action


def _prefer_local_deployment(matches: list[AgentDeployment]) -> AgentDeployment | None:
    local_matches = [
        item
        for item in matches
        if str(item.target_uri).startswith("local://") or item.id.endswith(".local")
    ]
    if not local_matches:
        return None
    exact = [item for item in local_matches if item.id.endswith(".local")]
    if len(exact) == 1:
        return exact[0]
    if len(local_matches) == 1:
        return local_matches[0]
    return None


def resolve_deployment(
    selector: str,
    *,
    root: str | Path = ".",
    prefer_local: bool = False,
) -> AgentDeployment:
    root_path = Path(root)
    registry = load_deployment_registry(root_path)
    aliases = load_deployment_selector_aliases(str(root_path.resolve()))
    normalized = aliases.get(selector, selector)
    deployment = registry.by_id(normalized)
    if deployment is None and normalized != selector:
        deployment = registry.by_id(selector)
    if deployment is None:
        agent_ref = normalized if normalized.startswith("agent://") else f"agent://{normalized}"
        matches = registry.by_agent_ref(agent_ref)
        if prefer_local and len(matches) > 1:
            deployment = _prefer_local_deployment(matches)
        if deployment is None:
            if len(matches) == 1:
                deployment = matches[0]
            elif len(matches) > 1:
                ids = ", ".join(item.id for item in matches)
                raise ValueError(f"Ambiguous agent selector {selector!r}; choose deployment id: {ids}")
    if deployment is None:
        raise ValueError(f"Deployment not found: {selector}")
    return deployment
