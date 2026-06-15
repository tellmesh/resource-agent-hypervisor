from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import yaml
from jsonschema import Draft202012Validator


@dataclass(frozen=True)
class SchemaValidationResult:
    path: str
    ok: bool
    errors: list[str]


def _read_yaml(path: Path) -> Any:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    return value if value is not None else {}


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_file(data_path: Path, schema_path: Path) -> SchemaValidationResult:
    data = _read_yaml(data_path)
    schema = _read_json(schema_path)
    validator = Draft202012Validator(schema)
    errors = [f"{'.'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in validator.iter_errors(data)]
    return SchemaValidationResult(str(data_path), not errors, errors)


def validate_contract_files(root: str | Path = ".") -> list[SchemaValidationResult]:
    root = Path(root)
    schemas = root / "schemas"
    results: list[SchemaValidationResult] = []
    pairs = [
        (root / "contracts" / "registry.yaml", schemas / "contract_registry.schema.json"),
        (root / "contracts" / "resources.yaml", schemas / "resources.schema.json"),
        (root / "contracts" / "views.yaml", schemas / "views.schema.json"),
    ]
    for data_path, schema_path in pairs:
        if data_path.exists() and schema_path.exists():
            results.append(validate_file(data_path, schema_path))
    agent_schema = schemas / "agent_contract.schema.json"
    for agent_path in sorted((root / "contracts" / "agents").glob("*.yaml")):
        results.append(validate_file(agent_path, agent_schema))
    proposal_schema = schemas / "evolution_proposal.schema.json"
    for proposal_path in sorted((root / "evolution" / "proposals").glob("*.yaml")):
        results.append(validate_file(proposal_path, proposal_schema))
    return results
