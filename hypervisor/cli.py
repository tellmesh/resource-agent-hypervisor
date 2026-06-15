import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import typer

from hypervisor import Hypervisor, get_config, load_config
from hypervisor.cli_commands import (
    call_docker,
    deploy_agent,
    echo_json,
    read_agent_logs,
    run_local_agent,
    verify_agent,
)
from hypervisor.deployment_registry.runner import (
    agent_status,
    inspect_agent,
    restart_agent,
    stop_agent,
    supervise_agent,
    supervise_watch,
)
from hypervisor.deployment_registry.status import registry_summary
from hypervisor.uri.client import Uri3Client

app = typer.Typer(help="Hypervisor CLI — deployment registry, agent lifecycle, uri3 adapter")
repair_app = typer.Typer(help="Evolutionary self-healing: diagnose, apply, learn from incidents")
app.add_typer(repair_app, name="repair")
artifacts_app = typer.Typer(help="Validate schema-backed runtime artifacts")
app.add_typer(artifacts_app, name="artifacts")
evolution_app = typer.Typer(help="Evolution proposals from incidents, tickets, and tests")
app.add_typer(evolution_app, name="evolution")
ticket_app = typer.Typer(help="Ticket artifacts and planfile import")
app.add_typer(ticket_app, name="ticket")


def _load_json_payload(payload: str, payload_file: str = "") -> dict[str, Any] | None:
    if payload_file:
        return json.loads(Path(payload_file).read_text(encoding="utf-8"))
    if not payload:
        return None
    loaded = json.loads(payload)
    if not isinstance(loaded, dict):
        raise typer.BadParameter("payload must decode to a JSON object")
    return loaded


@app.command()
def call(
    uri: str,
    payload: str = typer.Option("", "--payload", help="JSON object payload"),
    payload_file: str = typer.Option("", "--payload-file", help="Read JSON payload from file"),
    approve: bool = typer.Option(False, "--approve", help="Approve side-effecting operator calls"),
    environment: str = typer.Option(
        "",
        "--environment",
        help="Operator environment: mock/local/docker/remote",
    ),
):
    """Execute a callable URI through uri3 or hypervisor operator routing."""
    body = _load_json_payload(payload, payload_file)
    echo_json(
        Uri3Client().call(
            uri,
            body,
            approved=approve,
            environment=environment or None,
        )
    )


@app.command()
def explain(
    uri: str,
    payload: str = typer.Option("", "--payload", help="JSON object payload"),
    payload_file: str = typer.Option("", "--payload-file", help="Read JSON payload from file"),
):
    """Explain semantic URI routing and hypervisor runtime resolution."""
    body = _load_json_payload(payload, payload_file)
    echo_json(Uri3Client().explain(uri, payload=body))


@app.command()
def scan(uri: str):
    payload = [
        item.__dict__ if hasattr(item, "__dict__") else item for item in Uri3Client().scan(uri)
    ]
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command()
def resolve(uri: str):
    echo_json(Uri3Client().resolve(uri))


@app.command()
def status():
    """Show hypervisor runtime status."""
    echo_json(Hypervisor().status())


@app.command(name="config")
def config_cmd(path: bool = typer.Option(False, "--path", help="Print config path only")):
    """Show or inspect configuration."""
    if path:
        cfg = load_config()
        typer.echo(cfg.get("_config_path", "<embedded-defaults>"))
    else:
        echo_json(get_config())


@app.command("deployments")
def deployments_list():
    """List entries from deployment registry."""
    typer.echo(json.dumps(registry_summary(), indent=2, ensure_ascii=False))


@app.command("run-agent")
def run_agent_cmd(
    selector: str = typer.Argument(
        ..., help="Deployment id or agent ref, e.g. <agent-id>"
    ),
    port: int | None = typer.Option(None, "--port", help="Override HTTP port"),
    host: str = typer.Option("0.0.0.0", "--host"),
    reload: bool = typer.Option(False, "--reload"),
    detach: bool = typer.Option(
        False, "--detach", help="Start in background and write runtime state"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print uvicorn command without starting"),
    if_running: str = typer.Option(
        "auto",
        "--if-running",
        help="Existing process policy: auto, reuse, restart, fail",
    ),
    wait_healthy: bool = typer.Option(
        False,
        "--wait-healthy",
        help="After detach start, run bounded supervise/repair until HTTP health OK",
    ),
    approve: bool = typer.Option(
        False,
        "--approve",
        help="Compatibility no-op; direct hypervisor run-agent is not policy-gated.",
    ),
    supervise_repair: str = typer.Option(
        "auto",
        "--supervise-repair",
        help="Repair loop for --wait-healthy: auto, restart, reuse, sync_health",
    ),
):
    """Start a local agent or print an SSH remote start plan with --dry-run."""
    _ = approve
    run_local_agent(
        selector,
        port=port,
        host=host,
        reload=reload,
        detach=detach,
        dry_run=dry_run,
        if_running=None if if_running == "auto" else if_running,
        wait_healthy=wait_healthy,
        supervise_repair=supervise_repair,
    )


@app.command("stop-agent")
def stop_agent_cmd(selector: str = typer.Argument(..., help="Deployment id or agent ref")):
    """Stop a detached local agent using runtime state."""
    echo_json(stop_agent(selector))


@app.command("restart-agent")
def restart_agent_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    port: int | None = typer.Option(None, "--port"),
    host: str = typer.Option("0.0.0.0", "--host"),
    reload: bool = typer.Option(False, "--reload"),
    detach: bool = typer.Option(
        True, "--detach/--foreground", help="Restart in background by default"
    ),
):
    """Restart a local agent (stop then start)."""
    echo_json(restart_agent(selector, port=port, host=host, reload=reload, detach=detach))


@app.command("agent-status")
def agent_status_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    no_health: bool = typer.Option(False, "--no-health", help="Skip HTTP health probe"),
):
    """Show deployment status and optional health check."""
    echo_json(agent_status(selector, check_health=not no_health))


@app.command("inspect-agent")
def inspect_agent_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    timeout: float = typer.Option(2.0, "--timeout", help="HTTP probe timeout"),
    log_limit: int = typer.Option(20, "--log-limit", help="Recent ERROR log entries to include"),
):
    """Inspect process, health, card and recent error logs."""
    echo_json(inspect_agent(selector, timeout=timeout, log_limit=log_limit))


@app.command("describe-agent")
def describe_agent_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write markdown report to this file",
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit metadata JSON instead of markdown"),
):
    """Describe agent contract, files, domain pack links, and invocation paths (markdown)."""
    from hypervisor.agent_describe import describe_agent

    report = describe_agent(selector)
    if output is not None:
        written = report.write(output)
        payload = {"ok": True, "written": str(written), **report.data}
        if json_out:
            echo_json(payload)
        else:
            typer.echo(f"Wrote agent report: {written}")
    elif json_out:
        echo_json({"ok": True, "markdown": report.markdown, **report.data})
    else:
        typer.echo(report.markdown)


@app.command("sync-agent-manifest")
def sync_agent_manifest_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
):
    """Write agents/manifests/<agent>.markpact.md from contract + deployment + runtime."""
    from hypervisor.agent_manifest import sync_agent_manifest
    from hypervisor.paths import find_repo_root

    echo_json(sync_agent_manifest(selector, root=find_repo_root()))


@app.command("sync-agent-manifests")
def sync_agent_manifests_cmd():
    """Sync Markpact manifests for all local:// agents into agents/manifests/."""
    from hypervisor.agent_manifest import sync_all_agent_manifests
    from hypervisor.paths import find_repo_root

    echo_json(sync_all_agent_manifests(root=find_repo_root()))


@app.command("materialize-agent")
def materialize_agent_cmd(
    manifest: Path = typer.Argument(..., help="Path to *.markpact.md"),
    write_contract: bool = typer.Option(
        False,
        "--write-contract",
        help="Create contracts/agents/*.yaml from markpact:agent when missing",
    ),
):
    """Parse a Markpact manifest and validate (optionally materialize contract YAML)."""
    from hypervisor.agent_manifest import materialize_agent_manifest
    from hypervisor.paths import find_repo_root

    repo = find_repo_root()
    path = manifest if manifest.is_absolute() else repo / manifest
    echo_json(materialize_agent_manifest(path, repo=repo, write_contract=write_contract))


@app.command("materialize-agent-compose")
def materialize_agent_compose_cmd(
    manifest: Path = typer.Argument(..., help="Path to *.markpact.md"),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Override docker-compose.yaml output path",
    ),
):
    """Write docker-compose.yaml from markpact:docker block in an agent manifest."""
    from hypervisor.agent_manifest import materialize_compose_from_manifest
    from hypervisor.paths import find_repo_root

    repo = find_repo_root()
    path = manifest if manifest.is_absolute() else repo / manifest
    echo_json(materialize_compose_from_manifest(path, repo=repo, output=output))


@app.command("supervise")
def supervise_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    repair: str = typer.Option(
        "none",
        "--repair",
        help="Repair strategy: none, auto, restart, reuse, sync_health",
    ),
    watch: bool = typer.Option(
        False,
        "--watch",
        help="Keep supervising in a loop and emit deduped JSONL events.",
    ),
    interval: float = typer.Option(10.0, "--interval", help="Seconds between watch ticks"),
    count: int | None = typer.Option(
        None,
        "--count",
        help="Stop watch mode after N ticks. Omit for daemon-style loop.",
    ),
    repair_backoff_ticks: int = typer.Option(
        3,
        "--repair-backoff-ticks",
        help="Minimum watch ticks before retrying repair for the same failure.",
    ),
    max_attempts: int = typer.Option(3, "--max-attempts", help="Bounded repair attempts"),
    timeout: float = typer.Option(2.0, "--timeout", help="HTTP probe timeout"),
    log_limit: int = typer.Option(20, "--log-limit", help="Recent ERROR log entries to include"),
    learn: bool = typer.Option(
        False,
        "--learn",
        help="On unresolved failure create schema-valid incident + evolution proposal",
    ),
):
    """Run bounded health supervision or continuous watch mode."""
    if watch:
        def print_tick(tick: dict[str, Any]) -> None:
            typer.echo(json.dumps(tick, ensure_ascii=False))

        payload = supervise_watch(
            selector,
            repair=repair,
            interval=interval,
            count=count,
            timeout=timeout,
            log_limit=log_limit,
            max_attempts=max_attempts,
            learn=learn,
            repair_backoff_ticks=repair_backoff_ticks,
            on_tick=print_tick,
        )
        echo_json(
            {
                key: value
                for key, value in payload.items()
                if key != "ticks"
            }
        )
        if not payload.get("ok"):
            raise typer.Exit(1)
        return

    if learn:
        from hypervisor.repair.supervisor import supervise_with_repair

        payload = supervise_with_repair(
            selector,
            repair=repair if repair != "none" else "auto",
            learn=True,
            timeout=timeout,
            log_limit=log_limit,
            max_attempts=max_attempts,
        )
    else:
        payload = supervise_agent(
            selector,
            repair=repair,
            timeout=timeout,
            log_limit=log_limit,
            max_attempts=max_attempts,
        )
    echo_json(payload)
    if not payload.get("ok"):
        raise typer.Exit(1)


@repair_app.command("diagnose")
def repair_diagnose_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    timeout: float = typer.Option(2.0, "--timeout"),
    log_limit: int = typer.Option(20, "--log-limit"),
):
    """Classify agent failure from runtime, health and logs."""
    from hypervisor.repair.supervisor import diagnose_agent

    echo_json(diagnose_agent(selector, timeout=timeout, log_limit=log_limit))


@repair_app.command("apply")
def repair_apply_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    safe: bool = typer.Option(True, "--safe/--unsafe", help="Only level-1 playbooks"),
    approve: bool = typer.Option(False, "--approve", help="Allow mutating playbooks"),
    playbook: str | None = typer.Option(None, "--playbook", help="Force a specific playbook"),
):
    """Apply known repair playbooks after diagnosis."""
    from hypervisor.repair.supervisor import repair_apply

    payload = repair_apply(
        selector,
        safe=safe,
        approved=approve,
        playbook=playbook,
    )
    echo_json(payload)
    if not payload.get("ok"):
        raise typer.Exit(1)


@repair_app.command("heal")
def repair_heal_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    repair: str = typer.Option("auto", "--repair", help="Repair strategy before learn"),
    learn: bool = typer.Option(True, "--learn/--no-learn", help="Create incident + proposal"),
    max_attempts: int = typer.Option(3, "--max-attempts"),
    timeout: float = typer.Option(2.0, "--timeout"),
    log_limit: int = typer.Option(20, "--log-limit"),
):
    """Uri-healer entry: bounded repair loop, then incident and evolution proposal."""
    from hypervisor.repair.healer import run_uri_healer

    payload = run_uri_healer(
        selector,
        repair=repair,
        learn=learn,
        timeout=timeout,
        log_limit=log_limit,
        max_attempts=max_attempts,
    )
    echo_json(payload)
    if not payload.get("ok"):
        raise typer.Exit(1)


@repair_app.command("learn")
def repair_learn_cmd(
    incident_path: str = typer.Argument(..., help="Path to incident.yaml"),
    sandbox: bool = typer.Option(True, "--sandbox/--no-sandbox"),
):
    """Build evolution proposal from incident and optionally sandbox-test repairs."""
    from hypervisor.repair.supervisor import learn_from_incident

    payload = learn_from_incident(incident_path, run_sandbox=sandbox)
    echo_json(payload)
    if not payload.get("ok"):
        raise typer.Exit(1)


@artifacts_app.command("check")
def artifacts_check_cmd(
    path: str = typer.Option("", "--path", help="Optional glob root under repo"),
):
    """Validate schema-backed artifacts under output/ and evolution/."""
    from hypervisor.artifacts.gate import check_artifacts
    from hypervisor.paths import find_repo_root

    repo = find_repo_root()
    payload = check_artifacts(repo)
    echo_json(payload)
    if not payload.get("ok"):
        raise typer.Exit(1)


@artifacts_app.command("schemas")
def artifacts_schemas_cmd():
    """Validate JSON Schema documents under schemas/."""
    from hypervisor.artifacts.gate import check_schemas
    from hypervisor.paths import find_repo_root

    payload = check_schemas(find_repo_root())
    echo_json(payload)
    if not payload.get("ok"):
        raise typer.Exit(1)


@artifacts_app.command("lifecycle")
def artifacts_lifecycle_cmd(
    strict: bool = typer.Option(
        False,
        "--strict/--report-only",
        help="Fail when lifecycle YAML/JSON files lack artifact envelope keys",
    ),
    sample_limit: int = typer.Option(20, "--sample-limit", help="Number of noncanonical samples"),
):
    """Report artifact-envelope coverage across configs, contracts, runtime and outputs."""
    from hypervisor.artifacts.gate import check_lifecycle_coverage
    from hypervisor.paths import find_repo_root

    payload = check_lifecycle_coverage(
        find_repo_root(),
        strict=strict,
        sample_limit=sample_limit,
    )
    echo_json(payload)
    if strict and not payload.get("ok"):
        raise typer.Exit(1)


@ticket_app.command("import")
def ticket_import_cmd(
    strategy: str = typer.Argument(..., help="Path to planfile/strategy YAML"),
    sprint: str = typer.Option("", "--sprint", help="Import only this sprint id"),
):
    """Import planfile tasks as schema-valid ticket:// artifacts."""
    from hypervisor.integrations.planfile import import_tickets_from_planfile
    from hypervisor.paths import find_repo_root

    repo = find_repo_root()
    payload = import_tickets_from_planfile(
        repo / strategy if not strategy.startswith("/") else Path(strategy),
        repo_root=repo,
        sprint_id=sprint or None,
    )
    echo_json(payload)


@evolution_app.command("propose-from-ticket")
def evolution_propose_from_ticket_cmd(
    ticket_path: str = typer.Argument(
        ..., help="Path to ticket YAML or ticket id under output/tickets"
    ),
):
    """Generate evolution://proposal/from-ticket/* from a Ticket artifact."""
    from hypervisor.integrations.planfile import propose_from_ticket_path
    from hypervisor.paths import find_repo_root

    repo = find_repo_root()
    path = Path(ticket_path)
    if not path.exists():
        path = repo / "output" / "tickets" / f"{ticket_path}.yaml"
    payload = propose_from_ticket_path(path, repo_root=repo)
    echo_json(payload)


@evolution_app.command("propose-from-incident")
def evolution_propose_from_incident_cmd(
    incident_path: str = typer.Argument(..., help="Path to incident.yaml"),
):
    """Generate evolution://proposal/from-incident/* from an Incident artifact."""
    from hypervisor.evolution.proposal_from_source import build_repair_proposal_from_incident
    from hypervisor.paths import find_repo_root
    from hypervisor.repair.validator import read_yaml

    repo = find_repo_root()
    incident = read_yaml(Path(incident_path))
    payload = build_repair_proposal_from_incident(incident, repo_root=repo)
    echo_json(payload)


@app.command("logs")
def logs_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    limit: int = typer.Option(50, "--limit"),
):
    """Read agent-related logs via log:// URI."""
    read_agent_logs(selector, limit=limit)


@app.command("deploy-agent")
def deploy_agent_cmd(
    selector: str = typer.Argument(..., help="Deployment id (ssh:// or docker:// target)"),
    apply: bool = typer.Option(False, "--apply", help="Apply deploy (rsync or docker compose up)"),
):
    """Print or apply a deploy plan for SSH or Docker targets."""
    deploy_agent(selector, apply=apply)


@app.command("verify-agent")
def verify_agent_cmd(
    selector: str = typer.Argument(..., help="Deployment id or agent ref"),
    no_health: bool = typer.Option(False, "--no-health", help="Skip HTTP health scan"),
):
    """Verify SSH/Docker deployment and optional HTTP health."""
    verify_agent(selector, check_health=not no_health)


@app.command("docker")
def docker_cmd(
    uri: str = typer.Argument(
        ..., help="docker:// URI with action query, e.g. docker://stack/ssh-testenv?action=up"
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Return command plan only"),
):
    """Control Docker stacks/containers through uri3."""
    call_docker(uri, dry_run=dry_run)


@app.command("replay-failure")
def replay_failure_cmd(
    source: str = typer.Argument(..., help="Workflow id or path to JSONL event log"),
    create_test: str = typer.Option(
        "", "--create-test", help="Write pytest regression file to this path"
    ),
    json_out: bool = typer.Option(False, "--json", help="Output JSON summary"),
):
    """Summarize failed workflow logs or generate a regression pytest file."""
    from uri2verify.replay import create_regression_test, replay_workflow_events

    if create_test:
        payload = create_regression_test(source, out=create_test)
    else:
        payload = replay_workflow_events(source)
        if json_out:
            payload = {key: value for key, value in payload.items() if key != "timeline"}
    echo_json(payload)


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point that accepts optional argv (for tests and scripts)."""
    args = list(argv) if argv is not None else None
    try:
        app(args=args)
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
