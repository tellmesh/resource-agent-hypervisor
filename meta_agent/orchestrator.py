from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from meta_agent.models import PipelineResult
from meta_agent.planner import infer_intent, intent_to_agent_spec, package_name
from meta_agent.repair import repair_agent_spec
from uri3.config.repo_root import find_repo_root

ROOT = find_repo_root(Path(__file__))
CONTRACTS_AGENTS = ROOT / "contracts" / "agents"


def save_proposal_from_prompt(prompt: str, output_path: Path | None = None) -> Path:
    intent = infer_intent(prompt)
    spec = intent_to_agent_spec(intent)
    output_path = output_path or (CONTRACTS_AGENTS / f"{package_name(intent.agent_name)}.yaml")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(yaml.safe_dump(spec, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return output_path


def validate_repair_generate(spec_path: Path, *, auto_repair: bool = True) -> PipelineResult:
    from generator.agent_generator import generate_agent
    from generator.validate import validate_agent
    from generator.verify import verify_generated_agent

    validation_errors = validate_agent(spec_path)
    repair_warnings: list[str] = []

    if validation_errors and auto_repair:
        repair = repair_agent_spec(spec_path, write=True)
        repair_warnings = repair.warnings
        validation_errors = repair.errors_after

    if validation_errors:
        return PipelineResult(status="failed", spec_path=str(spec_path), validation_errors=validation_errors, repair_warnings=repair_warnings)

    try:
        generated_path = generate_agent(spec_path)
    except Exception as exc:  # noqa: BLE001
        return PipelineResult(status="failed", spec_path=str(spec_path), validation_errors=[str(exc)], repair_warnings=repair_warnings)

    verify_errors = verify_generated_agent(generated_path) if generated_path.exists() else ["generated path missing"]
    if verify_errors:
        return PipelineResult(
            status="failed",
            spec_path=str(spec_path),
            generated_path=str(generated_path),
            repair_warnings=repair_warnings,
            verify_errors=verify_errors,
        )

    return PipelineResult(status="generated", spec_path=str(spec_path), generated_path=str(generated_path), repair_warnings=repair_warnings)


def pipeline_from_prompt(prompt: str, *, output_path: Path | None = None, auto_repair: bool = True) -> PipelineResult:
    spec_path = save_proposal_from_prompt(prompt, output_path)
    return validate_repair_generate(spec_path, auto_repair=auto_repair)


def asdict_result(result: PipelineResult) -> dict[str, Any]:
    return {
        "status": result.status,
        "spec_path": result.spec_path,
        "generated_path": result.generated_path,
        "validation_errors": result.validation_errors,
        "repair_warnings": result.repair_warnings,
        "verify_errors": result.verify_errors,
    }
