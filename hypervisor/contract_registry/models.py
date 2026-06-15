from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ResourceContract:
    uri: str
    projection: str
    schema: str
    renderer: str
    owner_agent: str
    stability: str = "experimental"
    version: str = "v1"


@dataclass(frozen=True)
class ViewContract:
    name: str
    viewKind: str
    mimeType: str
    columns: list[str] = field(default_factory=list)
    rendererHint: str = ""


@dataclass(frozen=True)
class CapabilityContract:
    name: str
    agent: str
    type: str
    uri: str | None = None
    command: str | None = None
    input_schema: str | None = None
    output_schema: str | None = None
    renderer: str | None = None
    emits: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ContractRegistry:
    root: Path
    resources: list[ResourceContract]
    views: list[ViewContract]
    capabilities: list[CapabilityContract]
    raw: dict[str, Any]

    def resource_by_uri(self, uri: str) -> ResourceContract | None:
        return next((item for item in self.resources if item.uri == uri), None)

    def view_by_name(self, name: str) -> ViewContract | None:
        return next((item for item in self.views if item.name == name), None)

    def capability_by_name(self, agent: str, name: str) -> CapabilityContract | None:
        return next((item for item in self.capabilities if item.agent == agent and item.name == name), None)
