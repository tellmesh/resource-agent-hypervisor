from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

DEPLOYMENT_STATUSES = frozenset({"generated", "deployed", "running", "stopped", "failed", "unknown"})
LIFECYCLE_STATUSES = frozenset({"planned", "generated", "deployed", "running", "stopped", "failed", "degraded"})
HEALTH_STATUSES = frozenset({"unknown", "ok", "failed", "degraded"})


@dataclass(frozen=True)
class DeploymentDeclared:
    target_uri: str
    preferred_port: int | None = None
    health_uri: str | None = None
    card_uri: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"target_uri": self.target_uri}
        if self.preferred_port is not None:
            payload["preferred_port"] = self.preferred_port
        if self.health_uri:
            payload["health_uri"] = self.health_uri
        if self.card_uri:
            payload["card_uri"] = self.card_uri
        return payload


@dataclass(frozen=True)
class DeploymentRuntimeView:
    effective_port: int | None = None
    effective_health_uri: str | None = None
    pid: int | None = None
    lifecycle_status: str = "unknown"
    health_status: str = "unknown"
    deployment_status: str = "unknown"
    service_result_status: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "effective_port": self.effective_port,
            "effective_health_uri": self.effective_health_uri,
            "pid": self.pid,
            "lifecycle_status": self.lifecycle_status,
            "health_status": self.health_status,
            "deployment_status": self.deployment_status,
            "service_result_status": self.service_result_status,
        }


def _port_from_uri(uri: str | None) -> int | None:
    if not uri:
        return None
    parsed = urlparse(uri)
    return parsed.port


@dataclass(frozen=True)
class AgentDeployment:
    id: str
    agent_ref: str
    target_uri: str
    card_uri: str | None = None
    health_uri: str | None = None
    status: str = "generated"
    env: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    declared: DeploymentDeclared | None = None
    runtime: DeploymentRuntimeView | None = None

    @property
    def declared_health_uri(self) -> str | None:
        if self.declared and self.declared.health_uri:
            return self.declared.health_uri
        return self.health_uri

    @property
    def effective_health_uri(self) -> str | None:
        if self.runtime and self.runtime.effective_health_uri:
            return self.runtime.effective_health_uri
        return None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "agent_ref": self.agent_ref,
            "target_uri": self.target_uri,
            "status": self.status,
        }
        declared = self.declared or DeploymentDeclared(
            target_uri=self.target_uri,
            preferred_port=_port_from_uri(self.health_uri),
            health_uri=self.health_uri,
            card_uri=self.card_uri,
        )
        payload["declared"] = declared.to_dict()
        if self.runtime:
            payload["runtime"] = self.runtime.to_dict()
        if self.card_uri:
            payload["card_uri"] = self.card_uri
        if self.health_uri:
            payload["health_uri"] = self.health_uri
        if self.env:
            payload["env"] = self.env
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload


@dataclass
class DeploymentRegistry:
    root: Path
    path: Path
    deployments: list[AgentDeployment]
    raw: dict[str, Any]

    def by_id(self, deployment_id: str) -> AgentDeployment | None:
        return next((item for item in self.deployments if item.id == deployment_id), None)

    def by_agent_ref(self, agent_ref: str) -> list[AgentDeployment]:
        return [item for item in self.deployments if item.agent_ref == agent_ref]
