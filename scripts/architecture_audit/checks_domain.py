from __future__ import annotations

from pathlib import Path

from architecture_audit.areas import (
    DOMAIN_VOCABULARY,
    GENERIC_CODE_AREAS,
    TEXT_SUFFIXES,
    domain_term_present,
)
from architecture_audit.models import Finding, ModuleEntry


def read_text_if_small(path: Path) -> str | None:
    if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
        return None
    try:
        if path.stat().st_size > 400_000:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def audit_domain_vocabulary(root: Path, modules: list[ModuleEntry]) -> list[Finding]:
    findings: list[Finding] = []
    for module in modules:
        if module.area not in GENERIC_CODE_AREAS:
            continue
        if _is_audit_tool_module(module.path):
            continue
        if module.path.endswith("__init__.py"):
            continue
        text = read_text_if_small(root / module.path)
        if not text:
            continue
        lowered = text.lower()
        hits = sorted(
            needle for needle in DOMAIN_VOCABULARY if domain_term_present(needle, lowered)
        )
        if not hits:
            continue
        findings.append(_domain_vocabulary_finding(module, hits))
    return findings


def _is_audit_tool_module(path: str) -> bool:
    return path == "scripts/architecture_responsibility_audit.py" or path.startswith(
        "scripts/architecture_audit/"
    )


def _domain_vocabulary_finding(module: ModuleEntry, hits: list[str]) -> Finding:
    high_signal_areas = {
        "operation_runtime",
        "runtime_uri_core",
        "system_control",
        "nl_planning",
        "command_surface",
    }
    severity = "warning" if module.area in high_signal_areas else "info"
    recommendation = (
        "Move vertical vocabulary and scenarios to domains/* or examples/*; "
        "keep this package as loader/router/runtime only."
    )
    if module.area == "operation_runtime":
        recommendation = (
            "Keep uri2ops generic; move office/bank/invoice workflow data to "
            "domains/* and call uri2ops through operation URIs."
        )
    return Finding(
        severity=severity,
        category="domain_vocabulary_in_generic_package",
        title=f"Domain vocabulary in {module.area}: {module.path}",
        detail=f"Generic package file contains domain terms: {', '.join(hits[:8])}.",
        recommendation=recommendation,
        paths=[module.path],
        evidence={"terms": hits, "area": module.area, "lines": module.lines},
        priority="P1" if severity == "warning" else "P2",
    )


def audit_stale_map_entries(root: Path, modules: list[ModuleEntry]) -> list[Finding]:
    findings: list[Finding] = []
    for module in modules:
        if module.lines <= 0 or (root / module.path).exists():
            continue
        if module.area in {"generated_output", "docs_project", "tests"}:
            continue
        findings.append(
            Finding(
                severity="warning",
                category="stale_map_entry",
                title=f"Map lists missing file: {module.path}",
                detail=(
                    "The file is present in project/map.toon.yaml but does not exist "
                    "in the current checkout."
                ),
                recommendation=(
                    "Regenerate project/map.toon.yaml before using this path as a "
                    "refactor target."
                ),
                paths=[module.path],
                evidence={"area": module.area, "lines": module.lines},
                priority="P0",
            )
        )
    return findings


def audit_domain_named_modules(root: Path, modules: list[ModuleEntry]) -> list[Finding]:
    findings: list[Finding] = []
    for module in modules:
        if not (root / module.path).exists():
            continue
        if module.area not in GENERIC_CODE_AREAS:
            continue
        path_text = module.path.lower().replace("/", " ")
        hits = sorted(
            needle for needle in DOMAIN_VOCABULARY if domain_term_present(needle, path_text)
        )
        if not hits:
            continue
        findings.append(
            Finding(
                severity="warning",
                category="domain_named_module_in_generic_package",
                title=f"Domain-named module in {module.area}: {module.path}",
                detail=(
                    "The module path itself contains domain vocabulary: "
                    f"{', '.join(hits[:8])}."
                ),
                recommendation=(
                    "Move the implementation or declarative data to domains/*; keep "
                    "the generic package entry point named after the generic loader."
                ),
                paths=[module.path],
                evidence={"terms": hits, "area": module.area, "lines": module.lines},
                priority="P1",
            )
        )
    return findings
