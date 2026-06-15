from __future__ import annotations

import sys
from pathlib import Path

from hypervisor.contract_registry.cli_commands import (
    run_build_command,
    run_check_command,
    run_cross_command,
    run_export_md_command,
    run_schema_command,
)

_COMMANDS = {
    "check": run_check_command,
    "schema": run_schema_command,
    "cross": run_cross_command,
    "build": run_build_command,
    "export-md": run_export_md_command,
}


def _parse_args(argv: list[str]) -> tuple[str, Path]:
    command = "check"
    root_arg = "."
    if argv and argv[0] in _COMMANDS:
        command = argv[0]
        root_arg = argv[1] if len(argv) > 1 else "."
    elif argv:
        root_arg = argv[0]
    return command, Path(root_arg)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    command, root = _parse_args(argv)
    return _COMMANDS[command](root)


if __name__ == "__main__":
    raise SystemExit(main())
