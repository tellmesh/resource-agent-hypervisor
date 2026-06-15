from __future__ import annotations

from pathlib import Path

import yaml

from generator.validate import validate_agent
from generator.verify import verify_generated
from meta_agent.orchestrator import ROOT, asdict_result, pipeline_from_prompt, save_proposal_from_prompt, validate_repair_generate
from meta_agent.repair import repair_agent_spec


def cmd_plan(prompt: str, out: str | None) -> int:
    path = save_proposal_from_prompt(prompt, Path(out) if out else None)
    print(path)
    print(path.read_text(encoding="utf-8"))
    return 0


def cmd_validate(spec: str) -> int:
    errors = validate_agent(Path(spec))
    if errors:
        print("FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK")
    return 0


def cmd_repair(spec: str, *, write: bool) -> int:
    result = repair_agent_spec(Path(spec), write=write)
    print(
        yaml.safe_dump(
            {
                "changed": result.changed,
                "errors_before": result.errors_before,
                "errors_after": result.errors_after,
                "warnings": result.warnings,
                "repaired_yaml": result.repaired_yaml,
            },
            sort_keys=False,
            allow_unicode=True,
        )
    )
    return 0 if not result.errors_after else 1


def cmd_generate(spec: str, *, auto_repair: bool) -> int:
    result = validate_repair_generate(Path(spec), auto_repair=auto_repair)
    print(yaml.safe_dump(asdict_result(result), sort_keys=False, allow_unicode=True))
    return 0 if result.status == "generated" else 1


def cmd_pipeline(prompt: str, out: str | None, *, auto_repair: bool) -> int:
    result = pipeline_from_prompt(prompt, output_path=Path(out) if out else None, auto_repair=auto_repair)
    print(yaml.safe_dump(asdict_result(result), sort_keys=False, allow_unicode=True))
    return 0 if result.status == "generated" else 1


def cmd_verify() -> int:
    errors = verify_generated(ROOT / "agents" / "generated")
    if errors:
        print("FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("OK")
    return 0
