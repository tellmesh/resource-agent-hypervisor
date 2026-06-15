from __future__ import annotations

import copy
from pathlib import Path

from generator.validate import validate_agent
from meta_agent.models import RepairResult
from meta_agent.repair.loader import load_spec, write_spec
from meta_agent.repair.rules import repair_agent_block, repair_capabilities


def repair_agent_spec(path: Path, *, write: bool = False) -> RepairResult:
    """Repair common YAML contract mistakes without inventing domain logic."""
    errors_before = validate_agent(path)
    warnings: list[str] = []
    data = load_spec(path)
    repaired = copy.deepcopy(data)

    repair_agent_block(repaired, path.stem, warnings)
    repair_capabilities(repaired, warnings)

    if write:
        write_spec(path, repaired)
        errors_after = validate_agent(path)
    else:
        tmp = path.with_suffix(path.suffix + ".repair.tmp")
        try:
            write_spec(tmp, repaired)
            errors_after = validate_agent(tmp)
        finally:
            tmp.unlink(missing_ok=True)

    return RepairResult(
        changed=repaired != data,
        errors_before=errors_before,
        errors_after=errors_after,
        warnings=warnings,
        repaired_yaml=repaired,
    )
