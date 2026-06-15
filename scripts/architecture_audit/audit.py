from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

from architecture_audit.checks_domain import (
    audit_domain_named_modules,
    audit_domain_vocabulary,
    audit_stale_map_entries,
)
from architecture_audit.checks_structure import (
    audit_duplication,
    audit_large_modules,
    audit_map_alerts,
    sort_findings,
)
from architecture_audit.models import AuditResult, Finding, ModuleEntry
from architecture_audit.parsers import parse_duplication, parse_map


def area_summary(modules: list[ModuleEntry]) -> list[dict[str, object]]:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for module in modules:
        counts[module.area]["files"] += 1
        counts[module.area]["lines"] += module.lines
    return [
        {"area": area, "files": values["files"], "lines": values["lines"]}
        for area, values in sorted(counts.items(), key=lambda item: (-item[1]["lines"], item[0]))
    ]


def build_backlog(findings: list[Finding]) -> list[dict[str, object]]:
    categories = Counter(finding.category for finding in findings)
    backlog: list[dict[str, object]] = []
    if any(finding.severity == "critical" for finding in findings):
        backlog.append(_backlog_item("P0", "Split critical complexity and fan-out hotspots", (
            "Critical map alerts are the most likely source of regressions during feature work."
        ), sum(1 for finding in findings if finding.severity == "critical")))
    if categories["domain_vocabulary_in_generic_package"]:
        backlog.append(_backlog_item("P1", "Move vertical vocabulary out of generic packages", (
            "Domain data in runtime/router packages makes agents and domains harder to separate."
        ), categories["domain_vocabulary_in_generic_package"]))
    if categories["stale_map_entry"]:
        backlog.append(_backlog_item("P0", "Regenerate stale project snapshots", (
            "The map lists files that are no longer in the checkout, so it can point "
            "refactors at already-removed modules."
        ), categories["stale_map_entry"]))
    if categories["domain_named_module_in_generic_package"]:
        backlog.append(_backlog_item("P1", "Remove domain-named modules from generic packages", (
            "A file such as urish/office_*.py makes the package boundary look "
            "domain-specific even when the real data is already externalized."
        ), categories["domain_named_module_in_generic_package"]))
    if categories["cross_area_duplication"] or categories["runtime_operator_boundary_duplication"]:
        count = (
            categories["cross_area_duplication"]
            + categories["runtime_operator_boundary_duplication"]
        )
        backlog.append(
            _backlog_item(
                "P1",
                "Resolve duplication crossing responsibility boundaries",
                (
                    "Cross-boundary copies drift silently and usually need a shared contract "
                    "or one owning package."
                ),
                count,
            )
        )
    if categories["large_command_surface"] or categories["large_module"]:
        count = categories["large_command_surface"] + categories["large_module"]
        backlog.append(_backlog_item("P2", "Thin large command, dashboard and runtime modules", (
            "Large entry points hide policy and behavior that should be covered independently."
        ), count))
    if categories["generated_snapshot_duplication"]:
        backlog.append(
            _backlog_item(
                "P2",
                "Keep generated snapshots out of source refactors",
                (
                    "Generated copies should be regenerated from source templates "
                    "instead of edited by hand."
                ),
                categories["generated_snapshot_duplication"],
            )
        )
    return backlog


def _backlog_item(priority: str, title: str, why: str, finding_count: int) -> dict[str, object]:
    return {
        "priority": priority,
        "title": title,
        "why": why,
        "finding_count": finding_count,
    }


def build_audit(root: Path, map_path: Path, dup_path: Path) -> AuditResult:
    map_header, modules, alerts, map_hotspots = parse_map(map_path)
    dup_summary, dup_hotspots, dup_groups = parse_duplication(dup_path)

    findings = sort_findings(
        [
            *audit_map_alerts(alerts, map_hotspots),
            *audit_large_modules(modules),
            *audit_duplication(dup_groups, dup_hotspots, root=root),
            *audit_domain_vocabulary(root, modules),
            *audit_stale_map_entries(root, modules),
            *audit_domain_named_modules(root, modules),
        ]
    )
    severity_counts = Counter(finding.severity for finding in findings)
    summary = {
        "map": map_header,
        "duplication": dup_summary,
        "modules_parsed": len(modules),
        "duplicate_groups_parsed": len(dup_groups),
        "findings": dict(sorted(severity_counts.items())),
    }
    return AuditResult(
        summary=summary,
        areas=area_summary(modules),
        findings=findings,
        refactor_backlog=build_backlog(findings),
        gates=_suggested_gates(),
    )


def _suggested_gates() -> list[str]:
    return [
        (
            "Keep this script in report mode for planning: "
            "python scripts/architecture_responsibility_audit.py --top 30"
        ),
        (
            "Use --fail-on warning only after noisy legacy findings are converted "
            "into explicit TODO exceptions."
        ),
        "Run make architecture-gate for hard import/envelope checks before merging refactors.",
        (
            "When a finding moves code across layers, add a focused regression test "
            "under tests/architecture or tests/hypervisor."
        ),
    ]
