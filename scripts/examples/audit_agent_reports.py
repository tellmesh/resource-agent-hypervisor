#!/usr/bin/env python3
"""Audit examples/* against deployments, contracts and describe-agent reports."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))
from repo_root import hypervisor_root  # noqa: E402

ROOT = hypervisor_root()
_root = str(ROOT)
if _root in sys.path:
    sys.path.remove(_root)
sys.path.insert(0, _root)

from hypervisor.agent_describe import describe_agent  # noqa: E402
from hypervisor.contract_registry.cross_validator import validate_root  # noqa: E402
from hypervisor.contract_registry.schema_validator import validate_contract_files  # noqa: E402
from hypervisor.deployment_registry.loader import load_deployment_registry  # noqa: E402
from hypervisor.deployment_registry.status import infer_port  # noqa: E402
from tests.examples.catalog import ALL_EXAMPLES  # noqa: E402


@dataclass(frozen=True)
class ExampleAuditSpec:
    example_id: str
    name: str
    deployment_id: str | None = None
    contract_path: str | None = None
    notes: str = ""
    example_dir: str | None = None


EXAMPLE_AUDIT: tuple[ExampleAuditSpec, ...] = (
    ExampleAuditSpec("01", "quickstart_local"),
    ExampleAuditSpec("02", "uri3_scan_http", "weather-map-agent.local"),
    ExampleAuditSpec("03", "ssh_remote_agent", "weather-map-agent.ssh-dev"),
    ExampleAuditSpec("04", "nl2a_weather_map", "weather-map-agent.local"),
    ExampleAuditSpec("05", "meta_repair"),
    ExampleAuditSpec(
        "06",
        "orders_agent",
        contract_path="examples/06_orders_agent/create_orders_agent.yaml",
        notes="Example-only contract; not in deployment registry",
    ),
    ExampleAuditSpec(
        "07",
        "invoices_agent",
        "invoices-agent.local",
        "contracts/agents/invoices_agent.yaml",
    ),
    ExampleAuditSpec("08", "evolution"),
    ExampleAuditSpec("09", "run_agent_hypervisor", "weather-map-agent.local"),
    ExampleAuditSpec("10", "browser_operator", "browser-operator.local", "agents/operators/browser_operator.yaml"),
    ExampleAuditSpec("11", "playwright_browser", "browser-operator.local"),
    ExampleAuditSpec("12", "android_operator", "desktop-operator.local"),
    ExampleAuditSpec("13op", "pcwin_operator", "desktop-operator.local"),
    ExampleAuditSpec("13nl", "nl2uri_multi_uri_graph", "weather-map-agent.local"),
    ExampleAuditSpec("14wf", "workflow_executor_mock"),
    ExampleAuditSpec("14srv", "uri2ops_serve", "browser-operator.local"),
    ExampleAuditSpec("15cf", "compact_uri_flow", "weather-map-agent.local"),
    ExampleAuditSpec("15pw", "playwright_via_uri3_mock", "browser-operator.local", example_dir="examples/15_playwright_browser"),
    ExampleAuditSpec("16", "llm_graph_planner"),
    ExampleAuditSpec("16www", "www_landing_monitor"),
    ExampleAuditSpec("17", "flow_vs_graph", "weather-map-agent.local"),
    ExampleAuditSpec("18", "llm_flow_planner"),
    ExampleAuditSpec("20", "touri_capabilities"),
    ExampleAuditSpec("21", "touri_voice"),
    ExampleAuditSpec("22", "markpact_weather", "weather-map-agent.local"),
    ExampleAuditSpec("22dash", "dashboard_agent_capabilities", "hypervisor-dashboard.local", example_dir="examples/22_dashboard_agent"),
    ExampleAuditSpec("23", "nl_to_agent_tutorial", "weather-map-agent.local"),
    ExampleAuditSpec("30", "golden_path", "weather-map-agent.local"),
    ExampleAuditSpec("31", "office_day", "invoices-agent.local"),
    ExampleAuditSpec("32", "ecommerce_integrations", "invoices-agent.local"),
    ExampleAuditSpec("33", "office_workflows", "invoices-agent.local"),
    ExampleAuditSpec("34", "cron_uri", "invoices-agent.local"),
    ExampleAuditSpec("35", "website_screenshot_schedule"),
    ExampleAuditSpec("36", "physical_ops", "device-robot-operator.local", "agents/operators/device_robot_operator.yaml"),
    ExampleAuditSpec(
        "37",
        "agent_screenshot_analysis",
        "screenshot-analysis-agent.local",
        "contracts/agents/screenshot_analysis_agent.yaml",
    ),
    ExampleAuditSpec(
        "38",
        "autonomous_agents",
        "remote-deploy-agent.local",
        "contracts/agents/remote_deploy_agent.yaml",
    ),
)


@dataclass
class Finding:
    severity: str  # ok | warn | error
    example_id: str
    message: str


@dataclass
class AuditReport:
    generated_at: str
    findings: list[Finding] = field(default_factory=list)
    deployment_reports: dict[str, str] = field(default_factory=dict)

    @property
    def errors(self) -> int:
        return sum(1 for item in self.findings if item.severity == "error")

    @property
    def warnings(self) -> int:
        return sum(1 for item in self.findings if item.severity == "warn")


def _validate_example(spec: ExampleAuditSpec, repo: Path, registry: object) -> list[Finding]:
    findings: list[Finding] = []
    example_dir = (
        repo / spec.example_dir
        if spec.example_dir
        else next(
            (repo / "examples" / path.name for path in repo.glob(f"examples/*_{spec.name}")),
            None,
        )
    )
    if example_dir is None or not example_dir.is_dir():
        findings.append(Finding("error", spec.example_id, f"Missing example directory for {spec.name}"))
        return findings

    if spec.contract_path and not (repo / spec.contract_path).is_file():
        findings.append(
            Finding("error", spec.example_id, f"Contract not found: {spec.contract_path}")
        )

    if spec.deployment_id:
        deployment = registry.by_id(spec.deployment_id)  # type: ignore[attr-defined]
        if deployment is None:
            findings.append(
                Finding("error", spec.example_id, f"Deployment not found: {spec.deployment_id}")
            )
            return findings

        metadata_contract = (deployment.metadata or {}).get("contract")
        if spec.contract_path and metadata_contract and metadata_contract != spec.contract_path:
            findings.append(
                Finding(
                    "warn",
                    spec.example_id,
                    f"metadata.contract={metadata_contract} != expected {spec.contract_path}",
                )
            )

        if not deployment.health_uri and spec.deployment_id.endswith(".local"):
            findings.append(
                Finding("warn", spec.example_id, f"Deployment {spec.deployment_id} missing health_uri")
            )

        try:
            report = describe_agent(spec.deployment_id, root=repo)
        except Exception as exc:  # noqa: BLE001
            findings.append(
                Finding("error", spec.example_id, f"describe-agent failed: {exc}")
            )
            return findings

        if not report.data.get("contract_path"):
            findings.append(
                Finding("error", spec.example_id, f"No contract resolved for {spec.deployment_id}")
            )
        elif spec.contract_path and report.data["contract_path"] != spec.contract_path:
            findings.append(
                Finding(
                    "warn",
                    spec.example_id,
                    f"describe contract={report.data['contract_path']} != expected {spec.contract_path}",
                )
            )
        else:
            findings.append(
                Finding("ok", spec.example_id, f"describe-agent OK for {spec.deployment_id}")
            )
        if (
            spec.deployment_id
            and "weather-map" not in spec.deployment_id
            and "place=Gdansk" in report.markdown
        ):
            findings.append(
                Finding(
                    "warn",
                    spec.example_id,
                    "describe report contains weather-specific skill examples",
                )
            )
        if spec.deployment_id == "hypervisor-dashboard.local" and "System agent package" not in report.markdown:
            findings.append(
                Finding(
                    "warn",
                    spec.example_id,
                    "dashboard describe report missing system-agent labeling",
                )
            )
    elif spec.notes:
        findings.append(Finding("ok", spec.example_id, spec.notes))
    else:
        findings.append(Finding("ok", spec.example_id, f"Example dir OK: {example_dir.name}"))

    return findings


def _validate_contracts(repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    schema_results = validate_contract_files(repo)
    for result in schema_results:
        if result.ok:
            continue
        for error in result.errors:
            findings.append(
                Finding("error", "contracts", f"{result.path}: {error}")
            )
    cross_errors = validate_root(repo)
    for error in cross_errors:
        findings.append(Finding("error", "contracts", error))
    if not findings:
        findings.append(Finding("ok", "contracts", "Contract schema + cross-reference validation OK"))
    return findings


def _validate_deployments(repo: Path, registry: object) -> list[Finding]:
    findings: list[Finding] = []
    ports: dict[int, list[str]] = {}
    for deployment in registry.deployments:  # type: ignore[attr-defined]
        if str(deployment.target_uri).startswith("local://agents/generated/"):
            rel = deployment.target_uri.removeprefix("local://")
            package_dir = repo / rel
            if package_dir.exists():
                root_owned = [
                    p
                    for p in package_dir.rglob("*")
                    if p.is_file()
                    and os.stat(p).st_uid != os.getuid()
                    and "__pycache__" not in p.parts
                    and p.suffix in {".py", ".yaml", ".yml", ".md", ""}
                ]
                if root_owned:
                    findings.append(
                        Finding(
                            "warn",
                            deployment.id,
                            f"Generated package has root-owned files ({len(root_owned)}); run: sudo chown -R $USER:$USER {rel}",
                        )
                    )
        port = infer_port(deployment)
        ports.setdefault(port, []).append(deployment.id)

        metadata_contract = (deployment.metadata or {}).get("contract")
        if metadata_contract and not (repo / metadata_contract).is_file():
            findings.append(
                Finding("error", deployment.id, f"metadata.contract missing: {metadata_contract}")
            )

        try:
            report = describe_agent(deployment.id, root=repo)
        except Exception as exc:  # noqa: BLE001
            findings.append(Finding("error", deployment.id, f"describe-agent failed: {exc}"))
            continue
        if not report.data.get("contract_path"):
            findings.append(Finding("error", deployment.id, "describe-agent resolved no contract"))
        elif metadata_contract and report.data["contract_path"] != metadata_contract:
            findings.append(
                Finding(
                    "warn",
                    deployment.id,
                    f"describe contract={report.data['contract_path']} != metadata {metadata_contract}",
                )
            )
        elif str(deployment.target_uri).startswith("local://agents/custom/") and (
            "Custom agent package" not in report.markdown
        ):
            findings.append(
                Finding(
                    "warn",
                    deployment.id,
                    "custom agent describe missing Custom agent package label",
                )
            )
        elif str(deployment.target_uri).startswith("local://agents/custom/") and (
            "resource proxy" in report.markdown or "generated artifact" in report.markdown
        ):
            findings.append(
                Finding(
                    "warn",
                    deployment.id,
                    "custom agent describe uses generated-agent file labels",
                )
            )
        else:
            findings.append(Finding("ok", deployment.id, "deployment describe-agent OK"))

    for port, deployment_ids in sorted(ports.items()):
        local_ids = [item for item in deployment_ids if item.endswith(".local")]
        if len(local_ids) > 1:
            findings.append(
                Finding(
                    "warn",
                    "deployments",
                    f"Port {port} shared by local deployments: {', '.join(local_ids)}",
                )
            )
    return findings


def _write_deployment_reports(repo: Path, out_dir: Path) -> dict[str, str]:
    written: dict[str, str] = {}
    registry = load_deployment_registry(repo)
    for deployment in registry.deployments:
        report = describe_agent(deployment.id, root=repo)
        path = out_dir / f"{deployment.id}.md"
        report.write(path)
        written[deployment.id] = str(path.relative_to(repo))
    return written


def _render_markdown(report: AuditReport) -> str:
    lines = [
        "# Examples audit report",
        "",
        f"Generated: {report.generated_at}",
        "",
        f"- Errors: **{report.errors}**",
        f"- Warnings: **{report.warnings}**",
        "",
        "## Findings",
        "",
        "| Severity | Example | Message |",
        "|----------|---------|---------|",
    ]
    for item in report.findings:
        lines.append(f"| {item.severity} | `{item.example_id}` | {item.message} |")

    contract_findings = [item for item in report.findings if item.example_id == "contracts"]
    deployment_findings = [
        item
        for item in report.findings
        if item.example_id not in {spec.example_id for spec in EXAMPLE_AUDIT} | {"contracts", "deployments"}
    ]
    if contract_findings:
        lines.extend(["", "## Contract validation", ""])
        for item in contract_findings:
            lines.append(f"- **{item.severity}** — {item.message}")
    if deployment_findings:
        lines.extend(["", "## Deployment registry", ""])
        for item in deployment_findings:
            lines.append(f"- **{item.severity}** `{item.example_id}` — {item.message}")

    lines.extend(["", "## Deployment describe reports", ""])
    for deployment_id, rel_path in sorted(report.deployment_reports.items()):
        lines.append(f"- `{deployment_id}` → `{rel_path}`")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "-o",
        "--output-dir",
        default="output/reports/examples-audit",
        help="Directory for describe-agent markdown reports",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON summary to stdout",
    )
    args = parser.parse_args()

    repo = ROOT
    out_dir = repo / args.output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    registry = load_deployment_registry(repo)
    audit = AuditReport(generated_at=datetime.now(timezone.utc).isoformat())

    catalog_ids = {spec.id for spec in ALL_EXAMPLES}
    for spec in EXAMPLE_AUDIT:
        if spec.example_id not in catalog_ids:
            audit.findings.append(
                Finding("warn", spec.example_id, "Example id missing from tests/examples/catalog.py")
            )
        audit.findings.extend(_validate_example(spec, repo, registry))

    audit.findings.extend(_validate_contracts(repo))
    audit.findings.extend(_validate_deployments(repo, registry))

    audit.deployment_reports = _write_deployment_reports(repo, out_dir)

    summary_path = out_dir / "index.md"
    summary_path.write_text(_render_markdown(audit), encoding="utf-8")
    json_path = out_dir / "summary.json"
    json_path.write_text(
        json.dumps(
            {
                "generated_at": audit.generated_at,
                "errors": audit.errors,
                "warnings": audit.warnings,
                "findings": [asdict(item) for item in audit.findings],
                "deployment_reports": audit.deployment_reports,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Wrote {summary_path}")
    print(f"Wrote {json_path}")
    print(f"errors={audit.errors} warnings={audit.warnings}")

    if args.json:
        print(json.dumps({"errors": audit.errors, "warnings": audit.warnings}, indent=2))

    return 1 if audit.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
