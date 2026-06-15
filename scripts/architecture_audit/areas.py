from __future__ import annotations

import re

AREA_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("generated_output", ("output/ecosystems/", "output/contract_registry", "output/runtime/")),
    (
        "generated_agents",
        ("agents/generated/", "packages/resource-agent-factory/agents/generated/"),
    ),
    ("domain_artifacts", ("domains/", "agents/scenarios/")),
    ("operator_contracts", ("agents/operators/",)),
    ("command_surface", ("scripts/", "Makefile", "project.sh")),
    ("dashboard_app", ("agents/system/", "www/", "scripts/www/")),
    ("system_control", ("packages/resource-agent-hypervisor/", "hypervisor/")),
    ("runtime_uri_core", ("packages/uri3/", "uri3/")),
    ("runtime_transports", ("packages/uri2run/",)),
    ("workflow_runtime", ("packages/uri2flow/",)),
    ("operation_runtime", ("packages/uri2ops/",)),
    ("capability_runtime", ("packages/touri/",)),
    ("verification_runtime", ("packages/uri2verify/",)),
    ("scenario_contracts", ("packages/uri2pact/",)),
    ("voice_runtime", ("packages/uri2voice/",)),
    (
        "generation_factory",
        ("packages/resource-agent-factory/", "packages/urigen/", "generator/", "nl2a/"),
    ),
    ("nl_planning", ("packages/nl2uri/", "packages/urish/", "nl2uri/")),
    ("contracts_config", ("contracts/", "config/", "deployments/", "schemas/", "evolution/")),
    ("examples", ("examples/", "scripts/examples/")),
    ("tests", ("tests/", "testql-scenarios/")),
    (
        "docs_project",
        (
            "docs/",
            "project/",
            "README",
            "CHANGELOG",
            "TODO",
            "planfile.yaml",
            "goal.yaml",
            "tree.txt",
        ),
    ),
    ("test_infra", ("testenv/", "integration/")),
    (
        "build_config",
        (
            "Dockerfile",
            "docker-compose.yml",
            "pyproject.toml",
            "setup.py",
            "requirements.txt",
            "manifest.yaml",
            "prefact.yaml",
            "nlp2uri.yaml",
        ),
    ),
    ("legacy_runtime", ("runtime_client/", "meta_agent/", "uri2ops/")),
    ("knowledge_base", ("knowledge/",)),
)

COMMAND_HINTS = ("/cli.py", "/cli_commands.py", "/commands/", "/main.py")

GENERIC_CODE_AREAS = {
    "system_control",
    "command_surface",
    "runtime_uri_core",
    "runtime_transports",
    "workflow_runtime",
    "operation_runtime",
    "capability_runtime",
    "verification_runtime",
    "scenario_contracts",
    "voice_runtime",
    "generation_factory",
    "nl_planning",
}

DOMAIN_VOCABULARY = {
    "allegro",
    "bank",
    "baselinker",
    "biuro",
    "erp",
    "faktur",
    "invoice",
    "invoices",
    "marta",
    "office",
    "portal",
    "skapiec",
    "subiekt",
    "supplier",
    "weather_map",
    "weather-map",
    "woocommerce",
    "zus",
}

TEXT_SUFFIXES = {
    ".py",
    ".js",
    ".ts",
    ".yaml",
    ".yml",
    ".toml",
    ".md",
    ".txt",
    ".sh",
    ".j2",
    ".json",
}

SEVERITY_RANK = {"critical": 3, "warning": 2, "info": 1}


def normalize_path(path: str) -> str:
    return path.strip().replace("\\", "/").lstrip("./")


def area_for_path(path: str) -> str:
    normalized = normalize_path(path)
    early_areas = {
        "generated_output",
        "generated_agents",
        "domain_artifacts",
        "operator_contracts",
        "dashboard_app",
        "contracts_config",
        "examples",
        "tests",
        "docs_project",
        "build_config",
    }
    for area, prefixes in AREA_PATTERNS:
        if area not in early_areas:
            continue
        for prefix in prefixes:
            if normalized == prefix or normalized.startswith(prefix):
                return area
    if any(hint in normalized for hint in COMMAND_HINTS) and normalized.startswith(
        ("packages/", "hypervisor/", "nl2uri/", "uri3/")
    ):
        return "command_surface"
    for area, prefixes in AREA_PATTERNS:
        for prefix in prefixes:
            if normalized == prefix or normalized.startswith(prefix):
                return area
    return "unknown"


def domain_term_present(term: str, text: str) -> bool:
    if term in {"faktur", "weather_map", "weather-map"}:
        return term in text
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None
