from __future__ import annotations

from pathlib import Path
from glob import glob
from typing import Any

import yaml

from hypervisor.contract_registry.models import (
    CapabilityContract,
    ContractRegistry,
    ResourceContract,
    ViewContract,
)


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def load_contract_registry(root: str | Path = ".") -> ContractRegistry:
    root = Path(root)
    registry_raw = _read_yaml(root / "contracts" / "registry.yaml")
    resources_raw = _read_yaml(root / "contracts" / "resources.yaml").get("resources", [])
    views_raw = _read_yaml(root / "contracts" / "views.yaml").get("views", [])

    resources = [
        ResourceContract(
            uri=item["uri"],
            projection=item["projection"],
            schema=item["schema"],
            renderer=item["renderer"],
            owner_agent=item.get("owner_agent", ""),
            stability=item.get("stability", "experimental"),
            version=str(item.get("version", "v1")),
        )
        for item in resources_raw
    ]

    views = [
        ViewContract(
            name=item["name"],
            viewKind=item["viewKind"],
            mimeType=item.get("mimeType", "application/json"),
            columns=item.get("columns", []) or [],
            rendererHint=item.get("rendererHint", ""),
        )
        for item in views_raw
    ]

    capabilities: list[CapabilityContract] = []
    for agent_path in sorted(glob(str(root / "contracts" / "agents" / "*.yaml"))):
        raw = _read_yaml(Path(agent_path))
        agent = raw.get("agent") or {}
        agent_name = agent.get("name", Path(agent_path).stem)
        for cap in raw.get("capabilities") or []:
            capabilities.append(
                CapabilityContract(
                    name=cap["name"],
                    agent=agent_name,
                    type=cap["type"],
                    uri=cap.get("uri"),
                    command=cap.get("command"),
                    input_schema=cap.get("input_schema"),
                    output_schema=cap.get("output_schema"),
                    renderer=cap.get("renderer"),
                    emits=cap.get("emits", []) or [],
                )
            )

    return ContractRegistry(
        root=root,
        resources=resources,
        views=views,
        capabilities=capabilities,
        raw={"registry": registry_raw, "resources": resources_raw, "views": views_raw},
    )
