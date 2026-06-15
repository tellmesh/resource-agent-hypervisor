from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from architecture_audit.areas import SEVERITY_RANK
from architecture_audit.audit import build_audit
from architecture_audit.models import Finding
from architecture_audit.render import render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Plan refactors from map.toon.yaml and duplication.toon.yaml."
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Repository root. Defaults to cwd.",
    )
    parser.add_argument("--map", dest="map_path", type=Path, default=Path("project/map.toon.yaml"))
    parser.add_argument(
        "--dup",
        dest="dup_path",
        type=Path,
        default=Path("project/duplication.toon.yaml"),
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--out", type=Path, help="Write report to this file instead of stdout.")
    parser.add_argument(
        "--top",
        type=int,
        default=25,
        help="Number of areas/findings to show in markdown.",
    )
    parser.add_argument(
        "--fail-on",
        choices=("none", "info", "warning", "critical"),
        default="none",
    )
    return parser


def resolve_input(root: Path, path: Path) -> Path:
    return path if path.is_absolute() else root / path


def write_output(text: str, out: Path | None) -> None:
    if out is None:
        print(text)
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8")


def fail_code(findings: list[Finding], threshold: str) -> int:
    if threshold == "none":
        return 0
    minimum = SEVERITY_RANK[threshold]
    return 1 if any(SEVERITY_RANK[finding.severity] >= minimum for finding in findings) else 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    map_path = resolve_input(root, args.map_path)
    dup_path = resolve_input(root, args.dup_path)
    if not map_path.is_file():
        print(f"map file not found: {map_path}", file=sys.stderr)
        return 2
    if not dup_path.is_file():
        print(f"duplication file not found: {dup_path}", file=sys.stderr)
        return 2

    result = build_audit(root, map_path, dup_path)
    if args.format == "json":
        payload = {
            "summary": result.summary,
            "areas": result.areas,
            "findings": [asdict(finding) for finding in result.findings],
            "refactor_backlog": result.refactor_backlog,
            "gates": result.gates,
        }
        text = json.dumps(payload, indent=2, sort_keys=True)
    else:
        text = render_markdown(result, top=args.top)
    write_output(text, args.out)
    return fail_code(result.findings, args.fail_on)
