from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path

from architecture_audit.areas import SEVERITY_RANK
from architecture_audit.models import DupFragment, DupGroup, Finding, ModuleEntry


def is_generated_area(area: str) -> bool:
    return area in {"generated_agents", "generated_output"}


def unique_ordered(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            result.append(value)
            seen.add(value)
    return result


def sort_findings(findings: Iterable[Finding]) -> list[Finding]:
    return sorted(
        findings,
        key=lambda item: (-SEVERITY_RANK[item.severity], item.priority, item.category, item.title),
    )


def audit_map_alerts(alerts: list[str], hotspots: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for entry in alerts:
        severity = (
            "critical"
            if re.search(r"CC\s+\S+=([3-9]\d|\d{3,})", entry)
            else "warning"
        )
        findings.append(
            Finding(
                severity=severity,
                category="map_alert",
                title=f"Map alert: {entry}",
                detail="The project map reports a complexity or fan-out alert.",
                recommendation=(
                    "Split orchestration from policy/data handling and add a focused "
                    "regression test before changing this function."
                ),
                evidence={"source": "project/map.toon.yaml", "alert": entry},
                priority="P0" if severity == "critical" else "P1",
            )
        )
    for entry in hotspots:
        findings.append(
            Finding(
                severity="warning",
                category="map_hotspot",
                title=f"Hotspot: {entry}",
                detail="The project map reports high fan-out for this function.",
                recommendation=(
                    "Keep the function as a thin coordinator and move branch-specific "
                    "behavior into registries or backend modules."
                ),
                evidence={"source": "project/map.toon.yaml", "hotspot": entry},
                priority="P1",
            )
        )
    return findings


def audit_large_modules(modules: list[ModuleEntry]) -> list[Finding]:
    findings: list[Finding] = []
    ignored_areas = {
        "docs_project",
        "examples",
        "tests",
        "generated_agents",
        "generated_output",
    }
    for module in modules:
        if module.lines <= 0 or module.area in ignored_areas:
            continue
        threshold = 300
        if module.area == "dashboard_app":
            threshold = 450
        elif module.area == "contracts_config" or module.area == "command_surface":
            threshold = 250
        if module.lines < threshold:
            continue
        severity = "warning" if module.lines < threshold * 2 else "critical"
        category = "large_command_surface" if module.area == "command_surface" else "large_module"
        findings.append(
            Finding(
                severity=severity,
                category=category,
                title=f"Large {module.area} file: {module.path}",
                detail=f"{module.path} has {module.lines} lines in the current system map.",
                recommendation=(
                    "Extract stable policy, rendering, registry, or backend units "
                    "before adding more behavior here."
                ),
                paths=[module.path],
                evidence={"lines": module.lines, "area": module.area},
                priority="P1" if module.area in {"command_surface", "dashboard_app"} else "P2",
            )
        )
    return findings


def _hotspot_finding(hotspot: dict[str, object]) -> Finding:
    return Finding(
        severity="info",
        category="duplication_hotspot",
        title=f"Duplication hotspot: {hotspot['path']}",
        detail=(
            f"{hotspot['path']} has {hotspot['duplicated_lines']} duplicated lines "
            f"across {hotspot['groups']} group(s)."
        ),
        recommendation=(
            "Check whether the duplicated fragments encode one reusable "
            "contract/helper or expected generated boilerplate."
        ),
        paths=[str(hotspot["path"])],
        evidence=hotspot,
        priority="P2",
    )


def _should_skip_hotspot(hotspot: dict[str, object]) -> bool:
    return hotspot.get("area") in {"generated_agents", "generated_output"}


def audit_duplication(
    groups: list[DupGroup],
    hotspots: list[dict[str, object]],
    *,
    root: Path | None = None,
) -> list[Finding]:
    findings: list[Finding] = []
    for hotspot in hotspots:
        if _should_skip_hotspot(hotspot):
            continue
        findings.append(_hotspot_finding(hotspot))

    for group in groups:
        live_group = _live_duplication_group(group, root)
        if not live_group.fragments:
            continue
        findings.extend(_duplication_group_findings(live_group))
    return findings


def _ignored_source_areas() -> set[str]:
    return {"tests", "docs_project", "examples"}


def _source_areas(areas: list[str]) -> list[str]:
    ignored = _ignored_source_areas()
    return [a for a in areas if a not in ignored]


def _is_generated_source_mix(areas: list[str]) -> bool:
    ignored = _ignored_source_areas()
    has_gen = any(is_generated_area(a) for a in areas)
    has_real = any(not is_generated_area(a) and a not in ignored for a in areas)
    return has_gen and has_real


def _is_cross_area(source_areas: list[str]) -> bool:
    return len(set(source_areas)) > 1


def _is_runtime_operator_boundary(source_areas: list[str]) -> bool:
    areas_set = set(source_areas)
    if {"runtime_uri_core", "operation_runtime"} <= areas_set:
        return True
    return {"runtime_uri_core", "operator_contracts"} <= areas_set


def _classify_duplication(group: DupGroup, areas: list[str]) -> tuple[str, str, str, str]:
    """Return (category, severity, priority, recommendation). Pure; low CC."""
    source = _source_areas(areas)
    if _is_generated_source_mix(areas):
        return (
            "generated_snapshot_duplication",
            "info",
            "P2",
            "Treat generated/output copies as derived artifacts; refactor the "
            "source template/package, then regenerate.",
        )
    if _is_runtime_operator_boundary(source):
        return (
            "runtime_operator_boundary_duplication",
            "warning",
            "P1",
            "Keep browser/desktop operation implementation in agents/operators/* "
            "and let uri3 reference it through an adapter contract.",
        )
    if _is_cross_area(source):
        return (
            "cross_area_duplication",
            "warning",
            "P1",
            "Move the shared behavior to the owning lower layer or keep only an "
            "explicit adapter at the boundary.",
        )
    if group.flagged or group.saved_lines >= 20:
        return (
            "same_area_duplication",
            "warning",
            "P2",
            "Extract a small local helper only when it reduces behavior drift; "
            "generated boilerplate can stay generated.",
        )
    return (
        "same_area_duplication",
        "info",
        "P2",
        "Extract a small local helper only when it reduces behavior drift; "
        "generated boilerplate can stay generated.",
    )


def _live_duplication_group(group: DupGroup, root: Path | None) -> DupGroup:
    if root is None:
        return group
    fragments = tuple(
        fragment for fragment in group.fragments if not _fragment_symbol_is_stale(root, fragment)
    )
    if len(fragments) == len(group.fragments):
        return group
    return replace(group, fragments=fragments, fragments_count=len(fragments))


def _fragment_symbol_is_stale(root: Path, fragment: DupFragment) -> bool:
    path = root / fragment.path
    if not path.exists() or path.suffix != ".py" or not fragment.symbol:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False
    escaped = re.escape(fragment.symbol)
    definition_re = re.compile(rf"^\s*(?:async\s+def|def|class)\s+{escaped}\b", re.MULTILINE)
    return definition_re.search(text) is None


def _duplication_group_findings(group: DupGroup) -> list[Finding]:
    areas = unique_ordered(fragment.area for fragment in group.fragments)
    paths = unique_ordered(fragment.path for fragment in group.fragments)

    if len(paths) == 1 and group.saved_lines < 20 and not group.flagged:
        return []

    category, severity, priority, recommendation = _classify_duplication(group, areas)
    return [
        Finding(
            severity=severity,
            category=category,
            title=f"Duplicate {group.name} spans {', '.join(areas)}",
            detail=(
                f"{group.kind} duplicate saves {group.saved_lines} lines "
                f"across {group.fragments_count} fragments."
            ),
            recommendation=recommendation,
            paths=paths,
            evidence={
                "digest": group.digest,
                "lines": group.lines,
                "saved_lines": group.saved_lines,
                "fragments": group.fragments_count,
                "flagged": group.flagged,
            },
            priority=priority,
        )
    ]
