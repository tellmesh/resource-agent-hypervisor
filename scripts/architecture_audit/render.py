from __future__ import annotations

from architecture_audit.models import AuditResult


def render_markdown(result: AuditResult, *, top: int) -> str:
    lines: list[str] = []
    summary = result.summary
    map_summary = summary.get("map", {})
    dup_summary = summary.get("duplication", {})

    lines.append("# Architecture Responsibility Audit")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Modules parsed | {summary['modules_parsed']} |")
    lines.append(f"| Duplicate groups parsed | {summary['duplicate_groups_parsed']} |")
    lines.append(f"| Map generated date | {map_summary.get('generated_date', 'unknown')} |")
    lines.append(f"| Map critical functions | {map_summary.get('critical', 'unknown')} |")
    lines.append(f"| Duplication saved lines | {dup_summary.get('saved_lines', 'unknown')} |")
    lines.append(f"| Findings | {summary.get('findings', {})} |")
    lines.append("")
    lines.extend(_area_lines(result, top=top))
    lines.append("")
    lines.extend(_finding_lines(result, top=top))
    lines.append("")
    lines.extend(_backlog_lines(result))
    lines.append("")
    lines.extend(_gate_lines(result))
    lines.append("")
    return "\n".join(lines)


def _area_lines(result: AuditResult, *, top: int) -> list[str]:
    lines = [
        "## Responsibility Areas",
        "",
        "| Area | Files | Lines |",
        "|------|-------|-------|",
    ]
    for area in result.areas[:top]:
        lines.append(f"| {area['area']} | {area['files']} | {area['lines']} |")
    return lines


def _finding_lines(result: AuditResult, *, top: int) -> list[str]:
    lines = [
        "## Top Findings",
        "",
        "| Severity | Priority | Category | Finding | Paths |",
        "|----------|----------|----------|---------|-------|",
    ]
    for finding in result.findings[:top]:
        paths = "<br>".join(finding.paths[:3])
        if len(finding.paths) > 3:
            paths += f"<br>... +{len(finding.paths) - 3}"
        lines.append(
            f"| {finding.severity} | {finding.priority} | {finding.category} | "
            f"{finding.title}<br>{finding.recommendation} | {paths} |"
        )
    return lines


def _backlog_lines(result: AuditResult) -> list[str]:
    lines = ["## Refactor Backlog", ""]
    if not result.refactor_backlog:
        lines.append("- No refactor backlog generated from the current snapshots.")
        return lines
    for item in result.refactor_backlog:
        lines.append(
            f"- **{item['priority']}** {item['title']} "
            f"({item['finding_count']} finding(s)): {item['why']}"
        )
    return lines


def _gate_lines(result: AuditResult) -> list[str]:
    lines = ["## Suggested Gates", ""]
    for gate in result.gates:
        lines.append(f"- {gate}")
    return lines
