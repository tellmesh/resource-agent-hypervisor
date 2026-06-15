#!/usr/bin/env python3
"""Verify tellmesh/www canonical checkout (hypervisor/www is deploy glue only)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR.parent))
from repo_root import hypervisor_root  # noqa: E402

HYPERVISOR_ROOT = hypervisor_root()
DEFAULT_TARGET = HYPERVISOR_ROOT.parent.parent / "tellmesh" / "www"

REQUIRED_FILES = (
    "index.html",
    "chat.html",
    "przyklady.html",
    "docs/examples.html",
    "generated/examples-manifest.js",
)


def check_www_checkout(target: Path) -> list[str]:
    errors: list[str] = []
    if not target.is_dir():
        return [f"directory missing: {target}"]
    for rel in REQUIRED_FILES:
        if not (target / rel).is_file():
            errors.append(f"missing {rel}")
    glue = HYPERVISOR_ROOT / "www"
    for name in ("Dockerfile", "docker-compose.yml"):
        if not (glue / name).is_file():
            errors.append(f"missing hypervisor/www/{name}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=DEFAULT_TARGET,
        help=f"tellmesh/www checkout (default: {DEFAULT_TARGET})",
    )
    args = parser.parse_args()
    target = args.target.resolve()
    errors = check_www_checkout(target)
    if errors:
        for err in errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 1
    print(f"OK tellmesh/www checkout ({target})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
