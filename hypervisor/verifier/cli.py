from __future__ import annotations

import json
import sys
from pathlib import Path

from hypervisor.contract_registry.loader import load_contract_registry
from hypervisor.contract_registry.validate import validate_registry
from hypervisor.verifier.capability_tests import build_capability_test_plan


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    root = Path(argv[0] if argv else ".")
    registry = load_contract_registry(root)
    errors = validate_registry(registry)
    if errors:
        print("Cannot build capability test plan; registry invalid:")
        for error in errors:
            print(f"- {error}")
        return 1
    plan = build_capability_test_plan(registry)
    print(json.dumps({"capability_tests": plan}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
