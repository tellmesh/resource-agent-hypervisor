from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from hypervisor.deployment_registry.local_targets import (
    build_local_run_plan,
    local_target_to_relative_path,
)


def deployment_health_label(deployment_item: Any) -> str:
    declared = deployment_item.declared
    for candidate in (
        deployment_item.health_uri,
        declared.health_uri if declared else None,
    ):
        if isinstance(candidate, str) and candidate:
            return candidate
    if str(deployment_item.target_uri).startswith("local://"):
        from hypervisor.deployment_registry.status import infer_port

        port = infer_port(deployment_item)
        return f"http://localhost:{port}/health"
    return "—"


def safe_run_plan(deployment: Any, repo: Path) -> dict[str, Any] | None:
    if not str(deployment.target_uri).startswith("local://"):
        return None
    try:
        return build_local_run_plan(deployment, repo=repo)
    except (FileNotFoundError, ValueError):
        return None


def find_contract_path(repo: Path, agent_name: str, deployment: Any) -> Path | None:
    metadata = deployment.metadata or {}
    contract_rel = metadata.get("contract")
    if contract_rel:
        path = repo / contract_rel
        if path.is_file():
            return path.resolve()
    slug = agent_name.replace("-", "_")
    candidate = repo / "contracts" / "agents" / f"{slug}.yaml"
    if candidate.is_file():
        return candidate.resolve()
    domain_id = (deployment.metadata or {}).get("domain_id")
    if domain_id:
        fragment = repo / "domains" / domain_id.replace("-", "_") / "registry.fragment.yaml"
        if fragment.is_file():
            raw = read_yaml(fragment)
            rel = raw.get("agent_contract")
            if rel:
                path = repo / rel
                if path.is_file():
                    return path.resolve()
    for path in sorted((repo / "contracts" / "agents").glob("*.yaml")):
        raw = read_yaml(path)
        if (raw.get("agent") or {}).get("name") == agent_name:
            return path.resolve()
    operator_candidate = repo / "agents" / "operators" / slug / f"{slug}.yaml"
    if operator_candidate.is_file():
        return operator_candidate.resolve()
    return None


def find_domain_pack(
    repo: Path,
    contract_path: Path | None,
    deployment: Any | None = None,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    metadata = (deployment.metadata or {}) if deployment is not None else {}
    domain_rel = metadata.get("domain_pack")
    if not domain_rel and contract:
        contracts_block = contract.get("contracts") or {}
        domain_rel = contracts_block.get("domain_pack")
    if domain_rel:
        domain_path = repo / domain_rel
        if domain_path.is_file():
            return _domain_pack_from_dir(repo, domain_path.parent, domain_path)
    if contract_path is None:
        return None
    contract_rel = rel(repo, contract_path)
    for fragment_path in sorted((repo / "domains").glob("*/registry.fragment.yaml")):
        raw = read_yaml(fragment_path)
        if raw.get("agent_contract") == contract_rel:
            return _domain_pack_from_dir(repo, fragment_path.parent)
    return None


def _domain_pack_from_dir(
    repo: Path,
    domain_dir: Path,
    domain_yaml: Path | None = None,
) -> dict[str, Any]:
    domain_path = domain_yaml or domain_dir / "domain.yaml"
    return {
        "id": domain_dir.name,
        "path": rel(repo, domain_dir),
        "domain_yaml": rel(repo, domain_path) if domain_path.is_file() else None,
        "registry_fragment": rel(repo, domain_dir / "registry.fragment.yaml"),
        "uri_tree": rel(repo, domain_dir / "uri_tree.yaml"),
        "commands": rel(repo, domain_dir / "commands.yaml"),
        "resources": rel(repo, domain_dir / "resources.yaml"),
        "views": rel(repo, domain_dir / "views.yaml"),
        "operator_registry": rel(repo, domain_dir / "operator_registry.yaml"),
        "scenario_registry": rel(repo, domain_dir / "scenario_registry.yaml"),
    }


def package_relative_path(deployment: Any, repo: Path) -> Path | None:
    if not str(deployment.target_uri).startswith("local://"):
        return None
    try:
        return local_target_to_relative_path(deployment.target_uri)
    except ValueError:
        return None


def list_package_files(package_dir: Path, *, agent_kind: str) -> list[dict[str, str]]:
    skip = {"__pycache__", ".pytest_cache", ".mypy_cache", ".egg-info"}
    items: list[dict[str, str]] = []
    for path in sorted(package_dir.rglob("*")):
        if not path.is_file():
            continue
        if any(part in skip or part.endswith(".egg-info") for part in path.parts):
            continue
        rel_path = path.relative_to(package_dir).as_posix()
        items.append({"path": rel_path, "role": file_role(rel_path, agent_kind=agent_kind)})
    return items


def agent_kind(deployment: Any, *, is_operator: bool) -> str:
    if is_operator:
        return "operator"
    if str(deployment.target_uri).startswith("local://agents/custom/"):
        return "custom"
    metadata = deployment.metadata or {}
    if metadata.get("source") == "system_agent" or str(deployment.target_uri).startswith(
        "local://agents/system/"
    ):
        return "system"
    return "generated"


def capability_backing_note(*, agent_kind: str) -> str:
    if agent_kind == "system":
        return "served natively by the system agent"
    if agent_kind == "custom":
        return "served by the hand-written custom agent"
    if agent_kind == "operator":
        return "executed by uri2ops adapters"
    return "via Resource Runtime"


def skill_invoke_example(cap: dict[str, Any], *, deployment: Any) -> str:
    name = cap.get("name", "skill")
    uri = str(cap.get("uri") or "")
    if cap.get("type") == "command":
        command = cap.get("command") or "Command"
        return f"POST /skills/{name} with {command} payload"
    if "{place}" in uri and "{days}" in uri:
        return f"GET /skills/{name}?place=Gdansk&days=7"
    if "{agent_id}" in uri:
        return f"GET /skills/{name}?agent_id={deployment.id}"
    if "{invoice_id}" in uri:
        return f"GET /skills/{name}?invoice_id=demo-1"
    if "{user_id}" in uri:
        return f"GET /skills/{name}?user_id=demo"
    if "{workflow_id}" in uri:
        return f"GET /skills/{name}?workflow_id=demo-workflow"
    if "{incident_id}" in uri:
        return f"GET /skills/{name}?incident_id=demo-incident"
    return f"GET /skills/{name}?uri={uri or '...'}"


def file_role(rel_path: str, *, agent_kind: str) -> str:
    if agent_kind == "custom":
        custom_roles = {
            "main.py": "FastAPI entrypoint (uvicorn target)",
            "routes.py": "HTTP routes: health, card, skills",
            "agent_card.py": "Agent Card payload (hand-maintained from contract)",
            "analysis.py": "Business logic and agent-to-agent orchestration",
            "__init__.py": "Package marker",
        }
        if rel_path in custom_roles:
            return custom_roles[rel_path]
        if rel_path.endswith(".py"):
            return "Hand-written Python module"
        return "Hand-written package file"

    roles = {
        "main.py": "FastAPI entrypoint (uvicorn target)",
        "routes.py": "HTTP routes: health, card, skills, resource proxy",
        "agent_card.py": "Agent Card payload (generated from contract)",
        "README.md": "Human docs + Markpact provenance blocks",
        ".generated.yaml": "Generator metadata (source contract, hash)",
        "Dockerfile": "Container image for deployment",
        "tests/test_contract.py": "Contract conformance tests",
    }
    return roles.get(rel_path, "generated artifact")


def extract_markpact_blocks(readme_path: Path) -> list[dict[str, str]]:
    if not readme_path.is_file():
        return []
    text = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(r"```markpact(?::([^\n]+))?\n(.*?)```", re.S)
    return [
        {"label": (match.group(1) or "block").strip(), "body": match.group(2).strip()}
        for match in pattern.finditer(text)
    ]


def read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def rel(repo: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return path.relative_to(repo).as_posix()
    except ValueError:
        return str(path)
