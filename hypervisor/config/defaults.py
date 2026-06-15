from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor._version import __version__

DEFAULT_CONFIG_NAMES = ("hypervisor.yaml", "nlp2uri.yaml")
LEGACY_CONFIG_NAME = "nlp2uri.yaml"
PACKAGE_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
NESTED_SECTIONS = (
    "hypervisor",
    "llm",
    "uri3",
    "registry",
    "domain_pack",
    "agents",
    "deployment",
)


def load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def embedded_defaults_raw() -> dict[str, Any]:
    default_path = PACKAGE_DATA_DIR / LEGACY_CONFIG_NAME
    return load_yaml_file(default_path)


def apply_builtin_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    cfg.setdefault("hypervisor", {})
    cfg["hypervisor"].setdefault("version", __version__)
    cfg.setdefault("llm", {})
    cfg["llm"].setdefault("provider", "openrouter")
    cfg["llm"].setdefault("model_uri", "llm://openrouter/qwen/qwen3-coder-next")
    cfg["llm"].setdefault("api_key_uri", "env://OPENROUTER_API_KEY")
    cfg.setdefault("uri3", {})
    cfg["uri3"].setdefault(
        "enabled_schemes",
        ["env", "llm", "log", "python", "http", "https", "a2a", "mcp", "pypi", "artifact"],
    )
    cfg.setdefault("registry", {})
    cfg["registry"].setdefault("path", "contracts/registry.yaml")
    cfg["registry"].setdefault("output", "output/contract_registry.resolved.json")
    cfg.setdefault("domain_pack", {})
    cfg["domain_pack"].setdefault("root", "domains/")
    cfg.setdefault("agents", {})
    cfg["agents"].setdefault("generated_root", "agents/generated/")
    cfg.setdefault("deployment", {})
    cfg["deployment"].setdefault("registry", "deployments/agent_deployments.yaml")
    return cfg


def get_default_config() -> dict[str, Any]:
    """Return embedded defaults with required sections."""
    return apply_builtin_defaults(dict(embedded_defaults_raw()))
