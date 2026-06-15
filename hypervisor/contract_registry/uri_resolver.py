from __future__ import annotations

import re
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import yaml

from hypervisor.contract_registry.cross_validator import validate_cross_references
from hypervisor.contract_registry.loader import load_contract_registry
from hypervisor.contract_registry.registry_builder import build_registry_manifest
from hypervisor.contract_registry.schema_validator import validate_contract_files
from hypervisor.contract_registry.validate import validate_registry
from hypervisor.deployment_registry.loader import load_deployment_registry


GENERATED_AGENT_FILES = (
    "__init__.py",
    "main.py",
    "routes.py",
    "agent_card.py",
    "Dockerfile",
    "README.md",
    "tests/test_contract.py",
    ".generated.yaml",
)


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_kinds(value: str | None) -> set[str] | None:
    if not value:
        return None
    kinds = {item.strip() for item in value.split(",") if item.strip()}
    return kinds or None


def _schema_refs_from_contract(contract: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for cap in contract.get("capabilities") or []:
        if not isinstance(cap, dict):
            continue
        for key in ("output_schema", "input_schema"):
            schema = cap.get(key)
            if isinstance(schema, str) and schema.strip():
                refs.add(schema.strip())
    return refs


def _find_proto_files(root: Path, schema_refs: set[str]) -> list[Path]:
    protos_dir = root / "contracts" / "proto"
    if not protos_dir.is_dir() or not schema_refs:
        return []
    packages = {".".join(ref.split(".")[:-1]) for ref in schema_refs if "." in ref}
    found: list[Path] = []
    for path in sorted(protos_dir.glob("*.proto")):
        text = path.read_text(encoding="utf-8")
        if any(f"package {package};" in text for package in packages):
            found.append(path)
    return found


def _artifact_entry(*, kind: str, path: Path, root: Path, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    rel = str(path.relative_to(root))
    payload: dict[str, Any] = {
        "kind": kind,
        "path": rel,
        "uri": f"file://{path.resolve().as_posix()}",
    }
    if path.is_file():
        from generator.hashutil import file_sha256

        payload["hash"] = file_sha256(path)
    if extra:
        payload.update(extra)
    return payload


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _slug_to_snake(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")


def _contract_uri(path: Path) -> str:
    return f"contract://agents/{path.stem}"


def _agent_contract_uri(agent_name: str) -> str:
    return f"contract://agent/{agent_name}"


def resolve_contract_path(name: str, root: Path) -> Path | None:
    """Resolve logical agent or deployment name to contracts/agents/*.yaml."""
    normalized = name.strip().strip("/")
    if not normalized:
        return None

    agents_dir = root / "contracts" / "agents"
    if not agents_dir.is_dir():
        return None

    registry = load_deployment_registry(root)

    deployment = registry.by_id(normalized)
    if deployment is not None:
        contract = deployment.metadata.get("contract")
        if contract:
            path = root / str(contract)
            if path.is_file():
                return path
        if deployment.target_uri.startswith("local://agents/generated/"):
            package = deployment.target_uri.rsplit("/", 1)[-1]
            candidate = agents_dir / f"{package}.yaml"
            if candidate.is_file():
                return candidate

    agent_ref = normalized if normalized.startswith("agent://") else f"agent://{normalized}"
    for item in registry.deployments:
        if item.agent_ref == agent_ref:
            contract = item.metadata.get("contract")
            if contract:
                path = root / str(contract)
                if path.is_file():
                    return path
            if item.target_uri.startswith("local://agents/generated/"):
                package = item.target_uri.rsplit("/", 1)[-1]
                candidate = agents_dir / f"{package}.yaml"
                if candidate.is_file():
                    return candidate

    direct_candidates = [
        agents_dir / f"{normalized}.yaml",
        agents_dir / f"{_slug_to_snake(normalized)}.yaml",
    ]
    for candidate in direct_candidates:
        if candidate.is_file():
            return candidate

    for path in sorted(agents_dir.glob("*.yaml")):
        agent = _read_yaml(path).get("agent") or {}
        agent_name = str(agent.get("name") or "")
        package = str(agent.get("python_package") or path.stem)
        if normalized in {agent_name, package, path.stem, _slug_to_snake(agent_name)}:
            return path
    return None


def _format_schema_results(results: list[Any]) -> list[dict[str, Any]]:
    formatted: list[dict[str, Any]] = []
    for item in results:
        formatted.append(
            {
                "path": item.path,
                "ok": item.ok,
                "errors": item.errors,
            }
        )
    return formatted


def _validation_payload(
    *,
    uri: str,
    ok: bool,
    errors: list[str],
    checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": ok,
        "result_type": "contract_validation",
        "workflow_status": "completed",
        "service_result_status": "succeeded" if ok else "failed",
        "uri": uri,
        "valid": ok,
        "errors": errors,
        "checks": checks,
    }


def fetch_agent_contract(name: str, root: Path, *, uri: str | None = None) -> dict[str, Any]:
    path = resolve_contract_path(name, root)
    contract_uri = uri or _agent_contract_uri(name)
    if path is None:
        return {
            "ok": False,
            "result_type": "agent_contract",
            "workflow_status": "completed_with_service_error",
            "service_result_status": "failed",
            "uri": contract_uri,
            "agent_name": name,
            "error": f"Contract not found for agent: {name}",
        }

    contract = _read_yaml(path)
    agent = contract.get("agent") or {}
    agent_name = str(agent.get("name") or name)
    file_uri = f"file://{path.resolve().as_posix()}"
    related_uris: dict[str, str] = {
        "validate": f"{contract_uri.rstrip('/')}/validate",
        "generate": f"{contract_uri.rstrip('/')}/generate",
        "artifacts": f"{contract_uri.rstrip('/')}/artifacts",
        "file": file_uri,
    }
    registry = load_deployment_registry(root)
    for deployment in registry.deployments:
        if deployment.agent_ref == f"agent://{agent_name}":
            related_uris["schema"] = f"schema://agent/{deployment.id}"
            break
    return {
        "ok": True,
        "result_type": "agent_contract",
        "workflow_status": "completed",
        "service_result_status": "succeeded",
        "uri": contract_uri,
        "self": contract_uri,
        "agent_name": agent_name,
        "contract_path": str(path.relative_to(root)),
        "file_uri": file_uri,
        "contract": contract,
        "capabilities": contract.get("capabilities") or [],
        "related_uris": related_uris,
    }


def validate_agent_contract(name: str, root: Path, *, uri: str | None = None) -> dict[str, Any]:
    contract_uri = uri or f"{_agent_contract_uri(name)}/validate"
    path = resolve_contract_path(name, root)
    if path is None:
        return _validation_payload(
            uri=contract_uri,
            ok=False,
            errors=[f"Contract not found for agent: {name}"],
            checks={},
        )

    schema_path = root / "schemas" / "agent_contract.schema.json"
    schema_results = []
    if schema_path.is_file():
        from hypervisor.contract_registry.schema_validator import validate_file

        schema_results = [validate_file(path, schema_path)]

    registry = load_contract_registry(root)
    agent = _read_yaml(path).get("agent") or {}
    agent_name = str(agent.get("name") or name)
    registry_errors = [
        error
        for error in validate_registry(registry)
        if agent_name in error or path.stem in error
    ]
    cross_errors = [
        error
        for error in validate_cross_references(registry)
        if agent_name in error or path.stem in error
    ]

    schema_errors = [error for result in schema_results for error in result.errors]
    all_errors = [*schema_errors, *registry_errors, *cross_errors]
    return _validation_payload(
        uri=contract_uri,
        ok=not all_errors,
        errors=all_errors,
        checks={
            "schema": _format_schema_results(schema_results),
            "registry": registry_errors,
            "cross_ref": cross_errors,
        },
    )


def validate_contract_registry_uri(
    root: Path,
    *,
    uri: str = "contract://registry/validate",
    level: str = "all",
) -> dict[str, Any]:
    schema_results = validate_contract_files(root) if level in {"all", "schema"} else []
    registry = load_contract_registry(root)
    registry_errors = validate_registry(registry) if level in {"all", "registry"} else []
    cross_errors = validate_cross_references(registry) if level in {"all", "cross"} else []

    schema_errors = [error for result in schema_results for error in result.errors]
    all_errors = [*schema_errors, *registry_errors, *cross_errors]
    return _validation_payload(
        uri=uri,
        ok=not all_errors,
        errors=all_errors,
        checks={
            "schema": _format_schema_results(schema_results),
            "registry": registry_errors,
            "cross_ref": cross_errors,
        },
    )


def fetch_registry_manifest(root: Path, *, uri: str = "contract://registry") -> dict[str, Any]:
    manifest = build_registry_manifest(root)
    return {
        "ok": True,
        "result_type": "contract_registry",
        "workflow_status": "completed",
        "service_result_status": "succeeded",
        "uri": uri,
        "manifest": manifest,
        "related_uris": {
            "validate": "contract://registry/validate",
        },
    }


def generate_agent_contract(
    name: str,
    root: Path,
    *,
    uri: str | None = None,
    dry_run: bool = False,
    overwrite: bool = True,
) -> dict[str, Any]:
    contract_uri = uri or f"{_agent_contract_uri(name)}/generate"
    path = resolve_contract_path(name, root)
    if path is None:
        return {
            "ok": False,
            "result_type": "contract_generate",
            "workflow_status": "completed_with_service_error",
            "service_result_status": "failed",
            "uri": contract_uri,
            "agent_name": name,
            "dry_run": dry_run,
            "error": f"Contract not found for agent: {name}",
        }

    from generator.agent_generator import generate_agent
    from generator.hashutil import file_sha256
    from generator.model import load_agent_spec
    from generator.validate import validate_agent
    from generator.verify import verify_generated_agent

    validation_errors = validate_agent(path)
    if validation_errors:
        return {
            "ok": False,
            "result_type": "contract_generate",
            "workflow_status": "completed_with_service_error",
            "service_result_status": "failed",
            "uri": contract_uri,
            "agent_name": name,
            "dry_run": dry_run,
            "errors": validation_errors,
        }

    spec = load_agent_spec(path)
    contract_hash = file_sha256(path)
    output_root = root / "agents" / "generated"
    output_dir = output_root / spec.output_dir_name
    planned_files = [str((output_dir / rel).relative_to(root)) for rel in GENERATED_AGENT_FILES]

    if dry_run:
        return {
            "ok": True,
            "result_type": "contract_generate",
            "workflow_status": "completed",
            "service_result_status": "succeeded",
            "uri": contract_uri,
            "agent_name": spec.name,
            "dry_run": True,
            "contract_path": str(path.relative_to(root)),
            "contract_hash": contract_hash,
            "output_dir": str(output_dir.relative_to(root)),
            "planned_files": planned_files,
            "generator": "resource-agent-factory",
        }

    if output_dir.exists() and not overwrite:
        return {
            "ok": False,
            "result_type": "contract_generate",
            "workflow_status": "completed_with_service_error",
            "service_result_status": "failed",
            "uri": contract_uri,
            "agent_name": spec.name,
            "dry_run": False,
            "error": f"Generated agent already exists: {output_dir.relative_to(root)} (use overwrite=1)",
            "contract_hash": contract_hash,
            "output_dir": str(output_dir.relative_to(root)),
        }

    written = generate_agent(path, output_root=output_root)
    verify_errors = verify_generated_agent(written)
    files = sorted(str(item.relative_to(root)) for item in written.rglob("*") if item.is_file())
    ok = not verify_errors
    return {
        "ok": ok,
        "result_type": "contract_generate",
        "workflow_status": "completed" if ok else "completed_with_service_error",
        "service_result_status": "succeeded" if ok else "failed",
        "uri": contract_uri,
        "agent_name": spec.name,
        "dry_run": False,
        "contract_path": str(path.relative_to(root)),
        "contract_hash": contract_hash,
        "output_dir": str(written.relative_to(root)),
        "files": files,
        "errors": verify_errors,
        "generator": "resource-agent-factory",
    }


def fetch_agent_artifacts(
    name: str,
    root: Path,
    *,
    uri: str | None = None,
    kinds: set[str] | None = None,
) -> dict[str, Any]:
    contract_uri = uri or f"{_agent_contract_uri(name)}/artifacts"
    path = resolve_contract_path(name, root)
    if path is None:
        return {
            "ok": False,
            "result_type": "contract_artifacts",
            "workflow_status": "completed_with_service_error",
            "service_result_status": "failed",
            "uri": contract_uri,
            "agent_name": name,
            "error": f"Contract not found for agent: {name}",
        }

    contract = _read_yaml(path)
    agent = contract.get("agent") or {}
    agent_name = str(agent.get("name") or name)
    package = str(agent.get("python_package") or path.stem)
    artifacts: list[dict[str, Any]] = []

    def include(kind: str) -> bool:
        return kinds is None or kind in kinds

    if include("contract"):
        artifacts.append(_artifact_entry(kind="contract", path=path, root=root))

    if include("agent"):
        output_dir = root / "agents" / "generated" / package
        if output_dir.is_dir():
            for rel in GENERATED_AGENT_FILES:
                file_path = output_dir / rel
                if file_path.is_file():
                    artifacts.append(_artifact_entry(kind="agent", path=file_path, root=root))

    if include("deployment"):
        registry = load_deployment_registry(root)
        for deployment in registry.deployments:
            if deployment.agent_ref != f"agent://{agent_name}":
                continue
            artifacts.append(
                {
                    "kind": "deployment",
                    "id": deployment.id,
                    "target_uri": deployment.target_uri,
                    "health_uri": deployment.health_uri,
                    "path": "deployments/agent_deployments.yaml",
                }
            )

    if include("capability"):
        for cap in contract.get("capabilities") or []:
            if not isinstance(cap, dict):
                continue
            artifacts.append(
                {
                    "kind": "capability",
                    "name": cap.get("name"),
                    "type": cap.get("type"),
                    "uri": cap.get("uri"),
                    "command": cap.get("command"),
                    "input_schema": cap.get("input_schema"),
                    "output_schema": cap.get("output_schema"),
                }
            )

    if include("proto"):
        schema_refs = _schema_refs_from_contract(contract)
        for proto_path in _find_proto_files(root, schema_refs):
            artifacts.append(_artifact_entry(kind="proto", path=proto_path, root=root, extra={"schemas": sorted(schema_refs)}))

    from generator.hashutil import file_sha256

    return {
        "ok": True,
        "result_type": "contract_artifacts",
        "workflow_status": "completed",
        "service_result_status": "succeeded",
        "uri": contract_uri,
        "agent_name": agent_name,
        "contract_path": str(path.relative_to(root)),
        "contract_hash": file_sha256(path),
        "kinds": sorted(kinds) if kinds else None,
        "artifacts": artifacts,
        "related_uris": {
            "contract": _agent_contract_uri(agent_name),
            "generate": f"{_agent_contract_uri(agent_name)}/generate",
            "validate": f"{_agent_contract_uri(agent_name)}/validate",
        },
    }


def handle_contract_uri(uri: str, root: Path) -> dict[str, Any]:
    parsed = urlparse(uri)
    parts = [part for part in parsed.path.strip("/").split("/") if part]
    if parsed.netloc:
        parts = [parsed.netloc, *parts]
    params = {
        key: values[-1]
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
        if values
    }
    level = str(params.get("level") or "all")
    dry_run = _parse_bool(params.get("dry_run"))
    overwrite = _parse_bool(params.get("overwrite"), default=True)
    kinds = _parse_kinds(params.get("kinds"))

    if not parts:
        raise ValueError("contract:// requires a target path")

    if parts[0] == "registry":
        if len(parts) >= 2 and parts[1] == "validate":
            return validate_contract_registry_uri(root, uri=uri, level=level)
        return fetch_registry_manifest(root, uri=uri)

    if parts[0] == "agents" and len(parts) == 2:
        slug = parts[1]
        return fetch_agent_contract(slug, root, uri=uri)

    if parts[0] == "agent":
        if len(parts) < 2:
            raise ValueError("contract://agent/{name} requires an agent name")
        name = parts[1]
        if len(parts) >= 3 and parts[2] == "validate":
            return validate_agent_contract(name, root, uri=uri)
        if len(parts) >= 3 and parts[2] == "generate":
            return generate_agent_contract(
                name,
                root,
                uri=uri,
                dry_run=dry_run,
                overwrite=overwrite,
            )
        if len(parts) >= 3 and parts[2] == "artifacts":
            return fetch_agent_artifacts(name, root, uri=uri, kinds=kinds)
        return fetch_agent_contract(name, root, uri=uri)

    raise ValueError(f"unsupported contract URI: {uri}")
