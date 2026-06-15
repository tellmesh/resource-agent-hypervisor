from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from urish.policy import PolicyOptions, evaluate_policy as urish_evaluate_policy

from hypervisor.routing.models import RoutePolicyDecision

_OPERATOR_SCHEMES = frozenset(
    {"browser", "dom", "screen", "input", "android", "pcwin", "robot", "device"}
)


@dataclass(frozen=True)
class PolicyRequest:
    approved: bool = False
    dry_run: bool = False
    readonly: bool = False
    policy: str = "dev"
    strict_approve: bool = False


@dataclass(frozen=True)
class PolicyEvaluation:
    allowed: bool
    requires_approval: bool
    reasons: tuple[str, ...]
    force_dry_run: bool

    @property
    def reason(self) -> str | None:
        return self.reasons[0] if self.reasons else None

    def to_route_decision(self) -> RoutePolicyDecision:
        return RoutePolicyDecision(
            allowed=self.allowed,
            requires_approval=self.requires_approval,
            reasons=self.reasons,
        )


def policy_options(request: PolicyRequest) -> PolicyOptions:
    """Build urish PolicyOptions; strict_approve mirrors dashboard explicit-approval gate."""
    return PolicyOptions.from_flags(
        dry_run=request.dry_run,
        approve=request.approved,
        readonly=request.readonly,
        policy=request.policy,
        no_approve=request.strict_approve and not request.approved and not request.dry_run,
    )


def _semantic_requires_approval(uri: str, *, root: str | Path | None) -> bool:
    scheme = urlparse(uri).scheme
    if scheme not in _OPERATOR_SCHEMES:
        return False
    try:
        from uri3.routing import explain_semantic_uri

        semantic = explain_semantic_uri(uri, root=root)
        return bool(semantic.requires_approval)
    except Exception:
        return False


def evaluate_route_policy(
    uri: str,
    *,
    request: PolicyRequest | None = None,
    approved: bool = False,
    dry_run: bool = False,
    readonly: bool = False,
    policy: str = "dev",
    strict_approve: bool = False,
    root: str | Path | None = None,
    context_policy: str | None = None,
) -> PolicyEvaluation:
    """Unified policy gate for dashboard, CLI, and hypervisor executive routing."""
    req = request or PolicyRequest(
        approved=approved,
        dry_run=dry_run,
        readonly=readonly,
        policy=policy,
        strict_approve=strict_approve,
    )
    options = policy_options(req)
    allowed, reason, force_dry_run = urish_evaluate_policy(
        uri,
        options=options,
        context_policy=context_policy,
    )

    reasons: list[str] = []
    if reason:
        reasons.append(reason)

    requires_approval = (
        not req.approved
        and not req.dry_run
        and (not allowed or _semantic_requires_approval(uri, root=root))
    )
    if _semantic_requires_approval(uri, root=root) and not req.approved and not req.dry_run:
        if "route requires approval" not in reasons:
            reasons.append("route requires approval")
        if req.strict_approve or urlparse(uri).scheme in _OPERATOR_SCHEMES:
            allowed = False

    if force_dry_run:
        allowed = True

    return PolicyEvaluation(
        allowed=allowed,
        requires_approval=requires_approval,
        reasons=tuple(reasons),
        force_dry_run=force_dry_run,
    )


def evaluate_route_policy_decision(
    uri: str,
    *,
    approved: bool = False,
    dry_run: bool = False,
    root: str | Path | None = None,
    context_policy: str | None = None,
) -> RoutePolicyDecision:
    """Hypervisor resolver entry point (non-strict, matches CLI dev auto-approve)."""
    return evaluate_route_policy(
        uri,
        approved=approved,
        dry_run=dry_run,
        root=root,
        context_policy=context_policy,
    ).to_route_decision()
