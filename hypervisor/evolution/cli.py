from __future__ import annotations

import sys
from pathlib import Path

from hypervisor.evolution.models import load_proposal
from hypervisor.evolution.validator import validate_proposal


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not argv:
        print("Usage: python -m hypervisor.evolution.cli examples/08_evolution/proposals/*.yaml")
        return 1
    errors: list[str] = []
    for item in argv:
        for path in sorted(Path().glob(item)) or [Path(item)]:
            proposal = load_proposal(path)
            errs = validate_proposal(proposal)
            if errs:
                errors.extend([f"{path}: {err}" for err in errs])
            else:
                print(f"Valid proposal: {proposal.proposal_id}")
    if errors:
        print("Evolution proposal validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
