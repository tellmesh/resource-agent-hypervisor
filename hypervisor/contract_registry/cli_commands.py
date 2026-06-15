from __future__ import annotations

import json
from pathlib import Path

from hypervisor.contract_registry.cross_validator import validate_root
from hypervisor.contract_registry.loader import load_contract_registry
from hypervisor.contract_registry.registry_builder import write_registry_manifest
from hypervisor.contract_registry.registry_exporter import export_markdown
from hypervisor.contract_registry.schema_validator import validate_contract_files
from hypervisor.contract_registry.validate import validate_registry


def run_schema_command(root: Path) -> int:
    results = validate_contract_files(root)
    failed = [result for result in results if not result.ok]
    for result in results:
        print(json.dumps({"path": result.path, "ok": result.ok, "errors": result.errors}, indent=2))
    return 1 if failed else 0


def run_cross_command(root: Path) -> int:
    errors = validate_root(root)
    if errors:
        print("Cross-reference validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Cross-reference validation OK")
    return 0


def run_build_command(root: Path) -> int:
    path = write_registry_manifest(root)
    print(f"Wrote {path}")
    return 0


def run_export_md_command(root: Path) -> int:
    path = export_markdown(root)
    print(f"Wrote {path}")
    return 0


def run_check_command(root: Path) -> int:
    schema_results = validate_contract_files(root)
    schema_errors = [f"{result.path}: {error}" for result in schema_results for error in result.errors]
    registry = load_contract_registry(root)
    logical_errors = validate_registry(registry)
    cross_errors = validate_root(root)
    errors = schema_errors + logical_errors + cross_errors
    if errors:
        print("Contract registry validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    path = write_registry_manifest(root)
    summary = {
        "resources": len(registry.resources),
        "views": len(registry.views),
        "capabilities": len(registry.capabilities),
        "resolved_registry": str(path),
    }
    print(json.dumps(summary, indent=2))
    return 0
