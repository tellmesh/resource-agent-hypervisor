"""
Core Hypervisor runtime.

The Hypervisor is the central orchestrator responsible for:
- Managing fleets of agents (koru, proxeen backends, etc.)
- Coordinating NLP-to-URI / NLP-to-action pipelines
- Providing virtualized desktop sessions and resource control
- Event bus, lifecycle, and policy enforcement
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .config import get_config, load_config


@dataclass
class Hypervisor:
    """
    Main Hypervisor controller.

    Example:
        from hypervisor import Hypervisor
        hv = Hypervisor()
        print(hv)
        hv.start()
    """

    config: dict[str, Any] = field(default_factory=get_config)
    agents: list[str] = field(default_factory=list)
    running: bool = False

    def __post_init__(self) -> None:
        hv_cfg = self.config.get("hypervisor", {})
        self.max_agents: int = int(hv_cfg.get("max_agents", 8))
        self.profile: str = str(hv_cfg.get("default_profile", "normal"))
        self._config_path = self.config.get("_config_path", "<in-memory>")

    @classmethod
    def from_config(cls, path: str | None = None) -> Hypervisor:
        """Create Hypervisor with config loaded from explicit path or search."""
        cfg = load_config(path)
        return cls(config=cfg)

    def start(self) -> None:
        """Start the hypervisor control loop (stub)."""
        if self.running:
            return
        self.running = True
        # TODO: initialize event bus, load plugins, start agent supervisors, etc.

    def stop(self) -> None:
        """Stop the hypervisor and release resources (stub)."""
        if not self.running:
            return
        self.running = False

    def register_agent(self, name: str) -> None:
        """Register a new agent / driver under management."""
        if name in self.agents:
            return
        if len(self.agents) >= self.max_agents:
            raise RuntimeError(f"max_agents limit reached ({self.max_agents})")
        self.agents.append(name)

    def status(self) -> dict[str, Any]:
        """Return a snapshot of hypervisor state."""
        return {
            "version": self.config.get("hypervisor", {}).get("version"),
            "running": self.running,
            "profile": self.profile,
            "registered_agents": list(self.agents),
            "max_agents": self.max_agents,
            "config_path": self._config_path,
            "platform": self.config.get("platform"),
        }

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"Hypervisor(running={self.running}, profile={self.profile!r}, "
            f"agents={len(self.agents)}/{self.max_agents}, config={self._config_path!r})"
        )
