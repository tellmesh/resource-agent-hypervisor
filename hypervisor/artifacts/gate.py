from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from uri3.artifacts.validator import validate_artifact

from hypervisor.repair.validator import (
    validate_evolution_proposal_dict,
    validate_incident_dict,
    validate_repair_plan_dict,
    validate_runtime_state_dict,
    validate_ticket_dict,
)


def validate_config_dict(data: dict[str, Any], repo_root: Path) -> list[str]:
    return validate_artifact(data, repo_root, "schemas/config/config_base.schema.json")


def validate_runtime_environments_dict(data: dict[str, Any], repo_root: Path) -> list[str]:
    from uri2ops.server.runtime_profiles import (
        validate_runtime_registry_schema,
        validate_runtime_registry_semantics,
    )

    errors = validate_runtime_registry_schema(data, root=str(repo_root))
    errors.extend(validate_runtime_registry_semantics(data))
    return errors


@dataclass
class ArtifactCheckResult:
    path: str
    schema: str
    ok: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class ArtifactLifecycleResult:
    path: str
    category: str
    status: str
    missing: list[str] = field(default_factory=list)
    schema: str | None = None
    kind: str | None = None
    uri_self: str | None = None
    error: str | None = None


ARTIFACT_CHECKS: list[tuple[str, str, Any]] = [
    ("config/*.uri.yaml", "schemas/config/config_base.schema.json", validate_config_dict),
    (
        "config/runtime_environments.yaml",
        "schemas/runtime_environments.schema.json",
        validate_runtime_environments_dict,
    ),
    ("output/incidents/**/*.yaml", "schemas/incident.schema.json", validate_incident_dict),
    (
        "evolution/proposals/**/*.yaml",
        "schemas/evolution_proposal.schema.json",
        validate_evolution_proposal_dict,
    ),
    ("output/tickets/**/*.yaml", "schemas/ticket.schema.json", validate_ticket_dict),
    ("output/repair-plans/**/*.yaml", "schemas/repair_plan.schema.json", validate_repair_plan_dict),
    (
        "output/runtime/agents/**/state.json",
        "schemas/runtime_state.schema.json",
        validate_runtime_state_dict,
    ),
]


LIFECYCLE_ARTIFACT_SCANS: list[tuple[str, tuple[str, ...]]] = [
    ("config", ("config/*.uri.yaml",)),
    ("deployment_registry", ("deployments/**/*.yaml",)),
    ("contracts", ("contracts/**/*.yaml",)),
    ("domain_pack", ("domains/**/*.yaml",)),
    ("generated_marker", ("agents/generated/**/.generated.yaml",)),
    ("runtime_state", ("output/runtime/agents/**/state.json",)),
    ("workflow_artifact", ("output/artifacts/**/*.json", "output/artifacts/**/*.yaml")),
    (
        "workflow_output",
        (
            "output/**/*.uri.flow.yaml",
            "output/**/*.uri.graph.yaml",
            "output/**/*task_graph.yaml",
            "output/**/*task_plan.yaml",
            "output/*.json",
            "output/*.yaml",
        ),
    ),
    ("incident", ("output/incidents/**/*.yaml",)),
    ("ticket", ("output/tickets/**/*.yaml",)),
    ("repair_plan", ("output/repair-plans/**/*.yaml",)),
    ("evolution", ("evolution/proposals/**/*.yaml",)),
    (
        "example_workflow",
        (
            "examples/**/*.uri.flow.yaml",
            "examples/**/*.uri.graph.yaml",
            "examples/**/task_plan.yaml",
        ),
    ),
]


def _validate_path(path: Path, repo_root: Path, schema: str, validator) -> ArtifactCheckResult:
    import json

    import yaml

    rel = str(path.relative_to(repo_root))
    try:
        if path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
        else:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return ArtifactCheckResult(rel, schema, False, ["expected mapping root"])
        errors = validator(payload, repo_root)
        return ArtifactCheckResult(rel, schema, not errors, errors)
    except Exception as exc:  # noqa: BLE001
        return ArtifactCheckResult(rel, schema, False, [str(exc)])


def check_artifacts(repo_root: Path, *, patterns: list[str] | None = None) -> dict[str, Any]:
    checks = patterns or [item[0] for item in ARTIFACT_CHECKS]
    results: list[ArtifactCheckResult] = []
    for glob_pattern, schema, validator in ARTIFACT_CHECKS:
        if glob_pattern not in checks and patterns is not None:
            continue
        for path in sorted(repo_root.glob(glob_pattern)):
            if path.is_file():
                results.append(_validate_path(path, repo_root, schema, validator))
    failed = [item for item in results if not item.ok]
    return {
        "ok": not failed,
        "checked": len(results),
        "failed": len(failed),
        "results": [
            {
                "path": item.path,
                "schema": item.schema,
                "ok": item.ok,
                "errors": item.errors,
            }
            for item in results
        ],
    }


def _read_structured_mapping(path: Path) -> dict[str, Any]:
    import json

    import yaml

    text = path.read_text(encoding="utf-8")
    payload = json.loads(text) if path.suffix == ".json" else yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError("expected mapping root")
    return payload


def _artifact_lifecycle_result(
    path: Path, repo_root: Path, category: str
) -> ArtifactLifecycleResult:
    rel = str(path.relative_to(repo_root))
    try:
        payload = _read_structured_mapping(path)
    except Exception as exc:  # noqa: BLE001
        return ArtifactLifecycleResult(rel, category, "unreadable", error=str(exc))

    schema = payload.get("$schema")
    api_version = payload.get("apiVersion")
    kind = payload.get("kind")
    uri = payload.get("uri") or {}
    uri_self = uri.get("self") if isinstance(uri, dict) else None
    missing = [
        key
        for key, value in {
            "$schema": schema,
            "apiVersion": api_version,
            "kind": kind,
            "uri.self": uri_self,
        }.items()
        if not value
    ]
    if not missing:
        status = "canonical"
    elif schema and api_version and kind:
        status = "schema_backed_missing_uri"
    elif schema:
        status = "schema_declared_legacy"
    else:
        status = "loose"
    return ArtifactLifecycleResult(
        rel,
        category,
        status,
        missing,
        str(schema) if schema else None,
        str(kind) if kind else None,
        str(uri_self) if uri_self else None,
    )


def _collect_lifecycle_results(
    repo_root: Path,
) -> list[ArtifactLifecycleResult]:
    seen: set[Path] = set()
    results: list[ArtifactLifecycleResult] = []
    for category, patterns in LIFECYCLE_ARTIFACT_SCANS:
        for pattern in patterns:
            for path in sorted(repo_root.glob(pattern)):
                if not path.is_file() or path in seen:
                    continue
                seen.add(path)
                results.append(_artifact_lifecycle_result(path, repo_root, category))
    return results


def _lifecycle_summary(results: list[ArtifactLifecycleResult]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = {}
    for item in results:
        by_category = summary.setdefault(item.category, {})
        by_category[item.status] = by_category.get(item.status, 0) + 1
    return summary


def _lifecycle_samples(
    noncanonical: list[ArtifactLifecycleResult],
    *,
    sample_limit: int,
) -> list[dict[str, Any]]:
    return [
        {
            "path": item.path,
            "category": item.category,
            "status": item.status,
            "missing": item.missing,
            "schema": item.schema,
            "kind": item.kind,
            "uri_self": item.uri_self,
            "error": item.error,
        }
        for item in noncanonical[:sample_limit]
    ]


def check_lifecycle_coverage(
    repo_root: Path,
    *,
    strict: bool = False,
    sample_limit: int = 20,
) -> dict[str, Any]:
    """Report envelope coverage across the artifact lifecycle.

    This intentionally separates discovery from schema validation. `check_artifacts`
    validates known schema-backed locations, while this report shows where YAML/JSON
    lifecycle files still lack `$schema`, `apiVersion`, `kind`, or `uri.self`.
    """
    results = _collect_lifecycle_results(repo_root)
    summary = _lifecycle_summary(results)

    noncanonical_statuses = {
        "loose",
        "schema_declared_legacy",
        "schema_backed_missing_uri",
        "unreadable",
    }
    noncanonical = [item for item in results if item.status in noncanonical_statuses]
    loose = [item for item in results if item.status == "loose"]
    unreadable = [item for item in results if item.status == "unreadable"]
    failing = noncanonical if strict else unreadable
    return {
        "ok": not failing,
        "strict": strict,
        "checked": len(results),
        "canonical": sum(1 for item in results if item.status == "canonical"),
        "noncanonical": len(noncanonical),
        "loose": len(loose),
        "unreadable": len(unreadable),
        "summary": summary,
        "sample_limit": sample_limit,
        "samples": _lifecycle_samples(noncanonical, sample_limit=sample_limit),
    }


def check_schemas(repo_root: Path) -> dict[str, Any]:
    from jsonschema import Draft202012Validator

    schema_dir = repo_root / "schemas"
    results: list[dict[str, Any]] = []
    for path in sorted(schema_dir.rglob("*.schema.json")):
        rel = str(path.relative_to(repo_root))
        try:
            import json

            schema = json.loads(path.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema)
            results.append({"path": rel, "ok": True, "errors": []})
        except Exception as exc:  # noqa: BLE001
            results.append({"path": rel, "ok": False, "errors": [str(exc)]})
    failed = [item for item in results if not item["ok"]]
    return {"ok": not failed, "checked": len(results), "failed": len(failed), "results": results}
