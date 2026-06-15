from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from uri3.routing import UriRoute


@dataclass(frozen=True)
class RoutePolicyDecision:
    allowed: bool
    requires_approval: bool = False
    reasons: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True)
class HypervisorRouteResolution:
    route: UriRoute
    agent_uri: str | None = None
    deployment_id: str | None = None
    environment_uri: str | None = None
    contract_uri: str | None = None
    policy_uri: str | None = None
    side_effects: bool = False
    requires_approval: bool = False
    runtime: dict[str, Any] = field(default_factory=dict)
    context: dict[str, Any] = field(default_factory=dict)
    policy: RoutePolicyDecision = field(
        default_factory=lambda: RoutePolicyDecision(allowed=True)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "route": self.route.to_dict(),
            "agent_uri": self.agent_uri,
            "deployment_id": self.deployment_id,
            "environment_uri": self.environment_uri,
            "contract_uri": self.contract_uri,
            "policy_uri": self.policy_uri,
            "side_effects": self.side_effects,
            "requires_approval": self.requires_approval,
            "runtime": dict(self.runtime),
            "context": _public_context(self.context),
            "policy": self.policy.to_dict(),
        }


def _public_context(context: dict[str, Any]) -> dict[str, Any]:
    public = dict(context)
    session = public.get("session")
    if isinstance(session, dict):
        public["session"] = {
            "present": True,
            "keys": sorted(str(key) for key in session),
        }
    return public
