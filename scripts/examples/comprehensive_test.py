#!/usr/bin/env python3
"""Comprehensive examples test runner with machine capability report.

Runs all example commands (mock/dry-run by default), then optional real-mode
variants when host requirements are met. Writes JSON + Markdown reports under
output/examples/.

Usage:
  python3 scripts/examples/comprehensive_test.py
  python3 scripts/examples/comprehensive_test.py --real-only
  python3 scripts/examples/comprehensive_test.py --tier mock,dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
import textwrap
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))
from repo_root import hypervisor_root  # noqa: E402

ROOT = hypervisor_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.conftest import cli_argv, workspace_env  # noqa: E402
from tests.examples.capabilities import (  # noqa: E402
    MachineCapabilities,
    probe_machine,
    write_capabilities_report,
)
from tests.examples.command_catalog import (  # noqa: E402
    ALL_COMMANDS,
    DEFAULT_COMMANDS,
    REAL_COMMANDS,
    CommandSpec,
)
from tests.examples.conftest import playwright_python, run_shell  # noqa: E402

EXIT_SKIP = 77


@dataclass
class CommandResult:
    id: str
    example_id: str
    label: str
    tier: str
    category: str
    status: str  # pass | fail | skip
    requires: list[str]
    missing: list[str]
    exit_code: int | None = None
    detail: str = ""
    duration_s: float | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""


@dataclass
class ComprehensiveReport:
    generated_at: str
    host: str
    capabilities: dict
    results: list[CommandResult] = field(default_factory=list)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skip")


def _resolve_argv(spec: CommandSpec, repo_root: Path, env: dict[str, str]) -> list[str]:
    argv = list(spec.argv)
    if "__PROMPT__" in argv:
        prompt_path = repo_root / "examples/07_invoices_agent/create_invoices_agent_prompt.txt"
        prompt = prompt_path.read_text(encoding="utf-8").strip()
        argv = [prompt if a == "__PROMPT__" else a for a in argv]
    if argv and argv[0] in {"python", "python3"}:
        return [env.get("PYTHON", sys.executable), *argv[1:]]
    if argv and argv[0] in {"uri3", "uri", "hypervisor", "touri", "uri2ops", "uri2flow", "nl2uri"}:
        return cli_argv(argv[0], *argv[1:], env=env, repo_root=repo_root)
    return argv


def _missing_requirements(caps: MachineCapabilities, requires: tuple[str, ...]) -> list[str]:
    return [req for req in requires if not caps.available(req)]


def _tail(text: str, limit: int = 2000) -> str:
    return text[-limit:] if text else ""


def _run_command(
    spec: CommandSpec,
    repo_root: Path,
    env: dict[str, str],
    caps: MachineCapabilities,
    *,
    force: bool = False,
) -> CommandResult:
    missing = _missing_requirements(caps, spec.requires)
    if missing and not force:
        return CommandResult(
            id=spec.id,
            example_id=spec.example_id,
            label=spec.label,
            tier=spec.tier,
            category=spec.category,
            status="skip",
            requires=list(spec.requires),
            missing=missing,
            detail="requirements not met on this host",
        )

    argv = _resolve_argv(spec, repo_root, env)
    started = time.monotonic()

    if spec.id == "ex03-ssh":
        up = run_shell(repo_root, ["make", "docker-testenv-up"], env=env, timeout_s=240)
        if up.returncode != 0:
            return CommandResult(
                id=spec.id,
                example_id=spec.example_id,
                label=spec.label,
                tier=spec.tier,
                category=spec.category,
                status="fail",
                requires=list(spec.requires),
                missing=missing,
                exit_code=up.returncode,
                detail=_tail(up.stderr),
                duration_s=time.monotonic() - started,
                stdout_tail=_tail(up.stdout),
                stderr_tail=_tail(up.stderr),
            )
        env = {**env, "HYPERVISOR_SSH_PASSWORD": env.get("HYPERVISOR_SSH_PASSWORD", "deploy")}
        try:
            result = run_shell(repo_root, argv, env=env, timeout_s=spec.timeout_s)
        finally:
            run_shell(repo_root, ["make", "docker-testenv-down"], env=env, timeout_s=120)
    elif spec.id == "ex16www-monitor-url-down":
        result = run_shell(repo_root, argv, env=env, timeout_s=spec.timeout_s)
        # monitor_url exits non-zero on PAGE_DOWN — that is expected success
        ok = result.returncode != 0 and "PAGE_DOWN" in (result.stdout + result.stderr)
        return CommandResult(
            id=spec.id,
            example_id=spec.example_id,
            label=spec.label,
            tier=spec.tier,
            category=spec.category,
            status="pass" if ok else "fail",
            requires=list(spec.requires),
            missing=missing,
            exit_code=result.returncode,
            detail=_tail(result.stdout + result.stderr),
            duration_s=time.monotonic() - started,
            stdout_tail=_tail(result.stdout),
            stderr_tail=_tail(result.stderr),
        )
    else:
        result = run_shell(repo_root, argv, env=env, timeout_s=spec.timeout_s)

    ok = result.returncode == 0
    detail = ""
    if not ok:
        detail = (result.stdout + "\n" + result.stderr)[-3000:]
    return CommandResult(
        id=spec.id,
        example_id=spec.example_id,
        label=spec.label,
        tier=spec.tier,
        category=spec.category,
        status="pass" if ok else "fail",
        requires=list(spec.requires),
        missing=missing,
        exit_code=result.returncode,
        detail=detail,
        duration_s=time.monotonic() - started,
        stdout_tail=_tail(result.stdout),
        stderr_tail=_tail(result.stderr),
    )


def run_suite(
    repo_root: Path,
    *,
    tiers: set[str] | None = None,
    real_only: bool = False,
    include_real: bool = True,
) -> ComprehensiveReport:
    import platform

    caps = probe_machine(repo_root)
    python = playwright_python(repo_root) or sys.executable
    env = {**workspace_env(repo_root), "PYTHON": python}

    if real_only:
        commands = REAL_COMMANDS
    elif include_real:
        commands = ALL_COMMANDS
    else:
        commands = DEFAULT_COMMANDS

    if tiers:
        commands = tuple(c for c in commands if c.tier in tiers)

    report = ComprehensiveReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        host=platform.node(),
        capabilities=caps.to_dict(),
    )

    for spec in commands:
        print(f"\n{'=' * 60}\n▶ {spec.id}: {spec.label} [{spec.tier}]", flush=True)
        cr = _run_command(spec, repo_root, env, caps)
        report.results.append(cr)
        icon = {"pass": "✓", "fail": "✗", "skip": "⊘"}[cr.status]
        print(f"{icon} {cr.status.upper()}", end="")
        if cr.missing:
            print(f" (missing: {', '.join(cr.missing)})", end="")
        print(flush=True)
        if cr.status == "fail" and cr.detail:
            print(textwrap.indent(cr.detail[-500:], "  "), flush=True)

    return report


def write_reports(repo_root: Path, report: ComprehensiveReport) -> tuple[Path, Path]:
    out_dir = repo_root / "output" / "examples"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "comprehensive_report.json"
    md_path = out_dir / "comprehensive_report.md"

    payload = {
        "generated_at": report.generated_at,
        "host": report.host,
        "summary": {
            "pass": report.passed,
            "fail": report.failed,
            "skip": report.skipped,
            "total": len(report.results),
        },
        "capabilities": report.capabilities,
        "results": [asdict(r) for r in report.results],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    caps = report.capabilities
    lines = [
        "# Examples comprehensive test report",
        "",
        f"- **Generated:** {report.generated_at}",
        f"- **Host:** {report.host}",
        f"- **Summary:** PASS={report.passed} FAIL={report.failed} SKIP={report.skipped}",
        "",
        "## Machine capabilities (real mode)",
        "",
        "| Requirement | Available | Detail |",
        "|-------------|-----------|--------|",
    ]
    for probe in caps["probes"]:
        ok = "yes" if probe["available"] else "no"
        lines.append(f"| `{probe['id']}` | {ok} | {probe.get('detail') or probe['label']} |")

    lines.extend(["", "## Results by category", ""])
    by_cat: dict[str, list[CommandResult]] = {}
    for r in report.results:
        by_cat.setdefault(r.category, []).append(r)

    for cat in sorted(by_cat):
        lines.append(f"### {cat}")
        lines.append("")
        lines.append("| Status | Example | Command | Notes |")
        lines.append("|--------|---------|---------|-------|")
        for r in by_cat[cat]:
            if r.status == "skip":
                note = ", ".join(r.missing)
            elif r.status == "fail":
                note = r.detail[:120] if r.detail else ""
            else:
                elapsed = f"{r.duration_s:.1f}s" if r.duration_s is not None else "n/a"
                note = f"exit={r.exit_code}, {elapsed}"
            lines.append(
                f"| {r.status} | {r.example_id} | {r.label} | {note} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Real-mode automations on this host",
            "",
            _automation_summary(report),
            "",
            "## Commands",
            "",
            "```bash",
            "python3 scripts/examples/comprehensive_test.py              # mock + real attempts",
            "python3 scripts/examples/comprehensive_test.py --mock-only",
            "python3 scripts/examples/comprehensive_test.py --real-only",
            "pytest tests/examples/test_comprehensive.py -q",
            "make examples-comprehensive",
            "```",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    write_capabilities_report(repo_root, probe_machine(repo_root), out_dir / "capabilities.json")
    return json_path, md_path


def _automation_summary(report: ComprehensiveReport) -> str:
    """Summarize which automations work locally vs need remote/mock."""
    real_by_cat: dict[str, list[str]] = {}
    skip_by_cat: dict[str, list[str]] = {}
    for r in report.results:
        if r.tier != "real":
            continue
        bucket = real_by_cat if r.status == "pass" else skip_by_cat
        bucket.setdefault(r.category, []).append(r.label)

    parts = []
    if real_by_cat:
        parts.append("**Works in real mode on this machine:**")
        for cat, labels in sorted(real_by_cat.items()):
            parts.append(f"- *{cat}:* " + "; ".join(labels))
    if skip_by_cat:
        parts.append("")
        parts.append("**Needs remote hardware, credentials, or mock:**")
        for cat, labels in sorted(skip_by_cat.items()):
            parts.append(f"- *{cat}:* " + "; ".join(labels))
    return "\n".join(parts) if parts else "_No real-tier commands were run._"


def main() -> int:
    parser = argparse.ArgumentParser(description="Comprehensive examples test runner")
    parser.add_argument(
        "--mock-only",
        action="store_true",
        help="Run only default mock/dry-run/validate commands (no real variants)",
    )
    parser.add_argument(
        "--real-only",
        action="store_true",
        help="Run only real-mode command variants",
    )
    parser.add_argument(
        "--tier",
        default="",
        help="Comma-separated tiers: mock,dry-run,real,validate",
    )
    parser.add_argument(
        "--fail-on-skip",
        action="store_true",
        help="Treat skipped real commands as failures (strict lab mode)",
    )
    args = parser.parse_args()

    tiers = {t.strip() for t in args.tier.split(",") if t.strip()} or None
    report = run_suite(
        ROOT,
        tiers=tiers,
        real_only=args.real_only,
        include_real=not args.mock_only,
    )
    json_path, md_path = write_reports(ROOT, report)

    print("\n" + "=" * 60)
    print(f"SUMMARY: PASS={report.passed} FAIL={report.failed} SKIP={report.skipped}")
    print(f"JSON: {json_path}")
    print(f"Markdown: {md_path}")

    if report.failed > 0:
        return 1
    if args.fail_on_skip and report.skipped > 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
