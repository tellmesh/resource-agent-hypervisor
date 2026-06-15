from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMConfig:
    provider: str = "openrouter"
    model_uri: str = "llm://openrouter/qwen/qwen3-coder-next"
    api_key_uri: str = "env://OPENROUTER_API_KEY"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> LLMConfig:
        data = data or {}
        return cls(
            provider=str(data.get("provider", cls.provider)),
            model_uri=str(data.get("model_uri", cls.model_uri)),
            api_key_uri=str(data.get("api_key_uri", cls.api_key_uri)),
        )


@dataclass
class Uri3Config:
    enabled_schemes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> Uri3Config:
        data = data or {}
        schemes = data.get("enabled_schemes") or []
        return cls(enabled_schemes=[str(item) for item in schemes])


@dataclass
class RegistryConfig:
    path: str = "contracts/registry.yaml"
    output: str = "output/contract_registry.resolved.json"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> RegistryConfig:
        data = data or {}
        return cls(
            path=str(data.get("path", cls.path)),
            output=str(data.get("output", cls.output)),
        )


@dataclass
class DomainPackConfig:
    root: str = "domains/"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DomainPackConfig:
        data = data or {}
        return cls(root=str(data.get("root", cls.root)))


@dataclass
class AgentsConfig:
    generated_root: str = "agents/generated/"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AgentsConfig:
        data = data or {}
        return cls(generated_root=str(data.get("generated_root", cls.generated_root)))


@dataclass
class DeploymentConfig:
    registry: str = "deployments/agent_deployments.yaml"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> DeploymentConfig:
        data = data or {}
        return cls(registry=str(data.get("registry", cls.registry)))


@dataclass
class HypervisorSettings:
    log_level: str = "INFO"
    max_agents: int = 8
    default_profile: str = "normal"
    enable_event_sourcing: bool = True
    version: str = "0.0.0"

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> HypervisorSettings:
        data = data or {}
        max_agents = data.get("max_agents", cls.max_agents)
        return cls(
            log_level=str(data.get("log_level", cls.log_level)),
            max_agents=int(max_agents),
            default_profile=str(data.get("default_profile", cls.default_profile)),
            enable_event_sourcing=bool(data.get("enable_event_sourcing", cls.enable_event_sourcing)),
            version=str(data.get("version", cls.version)),
        )


@dataclass
class HypervisorConfig:
    platform: str = "auto"
    host_platform: str = "linux"
    locale: str | None = None
    dry_run: bool = False
    capture_dir: str = "/tmp/nlp2uri-captures"
    llm: LLMConfig = field(default_factory=LLMConfig)
    uri3: Uri3Config = field(default_factory=Uri3Config)
    registry: RegistryConfig = field(default_factory=RegistryConfig)
    domain_pack: DomainPackConfig = field(default_factory=DomainPackConfig)
    agents: AgentsConfig = field(default_factory=AgentsConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    hypervisor: HypervisorSettings = field(default_factory=HypervisorSettings)
    config_path: str = "<embedded-defaults>"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HypervisorConfig:
        return cls(
            platform=str(data.get("platform", cls.platform)),
            host_platform=str(data.get("host_platform", cls.host_platform)),
            locale=data.get("locale"),
            dry_run=bool(data.get("dry_run", cls.dry_run)),
            capture_dir=str(data.get("capture_dir", cls.capture_dir)),
            llm=LLMConfig.from_dict(data.get("llm")),
            uri3=Uri3Config.from_dict(data.get("uri3")),
            registry=RegistryConfig.from_dict(data.get("registry")),
            domain_pack=DomainPackConfig.from_dict(data.get("domain_pack")),
            agents=AgentsConfig.from_dict(data.get("agents")),
            deployment=DeploymentConfig.from_dict(data.get("deployment")),
            hypervisor=HypervisorSettings.from_dict(data.get("hypervisor")),
            config_path=str(data.get("_config_path", cls.config_path)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "host_platform": self.host_platform,
            "locale": self.locale,
            "dry_run": self.dry_run,
            "capture_dir": self.capture_dir,
            "llm": {
                "provider": self.llm.provider,
                "model_uri": self.llm.model_uri,
                "api_key_uri": self.llm.api_key_uri,
            },
            "uri3": {"enabled_schemes": list(self.uri3.enabled_schemes)},
            "registry": {"path": self.registry.path, "output": self.registry.output},
            "domain_pack": {"root": self.domain_pack.root},
            "agents": {"generated_root": self.agents.generated_root},
            "deployment": {"registry": self.deployment.registry},
            "hypervisor": {
                "log_level": self.hypervisor.log_level,
                "max_agents": self.hypervisor.max_agents,
                "default_profile": self.hypervisor.default_profile,
                "enable_event_sourcing": self.hypervisor.enable_event_sourcing,
                "version": self.hypervisor.version,
            },
            "_config_path": self.config_path,
        }
