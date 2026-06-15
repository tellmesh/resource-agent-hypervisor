#!/usr/bin/env python3
"""Plan refactors from map.toon.yaml and duplication.toon.yaml."""

from __future__ import annotations

import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from architecture_audit.audit import build_audit  # noqa: E402
from architecture_audit.cli import main  # noqa: E402
from architecture_audit.parsers import parse_duplication, parse_map  # noqa: E402
from architecture_audit.render import render_markdown  # noqa: E402

__all__ = [
    "build_audit",
    "main",
    "parse_duplication",
    "parse_map",
    "render_markdown",
]


if __name__ == "__main__":
    raise SystemExit(main())
