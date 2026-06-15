from __future__ import annotations

import json

import typer

from hypervisor.deployment_registry.docker_runner import (
    apply_docker_deploy,
    build_docker_deploy_plan,
    verify_docker_deployment,
)
from hypervisor.deployment_registry.local_verify import verify_local_deployment
from hypervisor.deployment_registry.remote_runner import (
    apply_ssh_deploy_plan,
    build_ssh_deploy_plan,
    verify_remote_deployment,
)
from hypervisor.deployment_registry.runner import (
    agent_logs_uri,
    build_run_plan,
    resolve_deployment,
    run_agent,
)
from hypervisor.uri.client import Uri3Client


def echo_json(payload) -> None:
    typer.echo(
        json.dumps(
            payload if isinstance(payload, dict) else getattr(payload, "__dict__", str(payload)),
            indent=2,
            ensure_ascii=False,
        )
    )


def run_local_agent(
    selector: str,
    *,
    port: int | None,
    host: str,
    reload: bool,
    detach: bool,
    dry_run: bool,
    if_running: str | None = None,
    wait_healthy: bool = False,
    supervise_repair: str = "auto",
) -> None:
    from hypervisor import Hypervisor

    deployment = resolve_deployment(selector)
    plan = build_run_plan(deployment, port=port, host=host, reload=reload)
    echo_json(plan)
    if dry_run:
        from hypervisor.events import emit_operation_event

        emit_operation_event(
            "AGENT_RUN_PLANNED",
            f"{deployment.id} run-agent dry-run plan created",
            selector=deployment.id,
            operation="run-agent",
            target_uri=deployment.target_uri,
            port=plan.get("port"),
            module=plan.get("module"),
        )
        return
    if deployment.target_uri.startswith("docker://"):
        typer.echo("Use hypervisor deploy-agent for docker:// targets.", err=True)
        raise typer.Exit(1)
    hv = Hypervisor()
    hv.start()
    hv.register_agent(deployment.agent_ref)
    try:
        from uri3.logs.writer import append_log

        append_log(
            "hypervisor",
            "Starting agent via hypervisor run-agent",
            level="INFO",
            logger="hypervisor.cli",
            deployment_id=deployment.id,
            module=plan["module"],
            port=plan["port"],
            detach=detach,
        )
    except FileNotFoundError:
        pass
    result = run_agent(
        selector,
        port=port,
        host=host,
        reload=reload,
        detach=detach,
        if_running=if_running,
        wait_healthy=wait_healthy,
        supervise_repair=supervise_repair,
    )
    if detach:
        echo_json({"started": result})
        if wait_healthy and not result.get("service_healthy", True):
            raise typer.Exit(1)


def deploy_agent(selector: str, *, apply: bool) -> None:
    deployment = resolve_deployment(selector)
    if deployment.target_uri.startswith("ssh://"):
        plan = build_ssh_deploy_plan(deployment)
        echo_json(plan)
        if not apply:
            return
        result = apply_ssh_deploy_plan(plan)
        echo_json({"deploy_result": result})
        if not result.get("ok"):
            raise typer.Exit(1)
        return
    if deployment.target_uri.startswith("docker://"):
        plan = build_docker_deploy_plan(deployment)
        echo_json(plan)
        if not apply:
            return
        result = apply_docker_deploy(deployment)
        echo_json({"deploy_result": result})
        if not result.get("ok"):
            raise typer.Exit(1)
        return
    raise typer.BadParameter("deploy-agent requires ssh:// or docker:// deployment target")


def verify_agent(selector: str, *, check_health: bool) -> None:
    deployment = resolve_deployment(selector)
    target = deployment.target_uri
    if target.startswith("docker://"):
        payload = verify_docker_deployment(deployment, check_health=check_health)
    elif target.startswith("ssh://"):
        payload = verify_remote_deployment(deployment, check_health=check_health)
    elif target.startswith("local://"):
        payload = verify_local_deployment(deployment, check_health=check_health)
    else:
        raise typer.BadParameter(f"Unsupported deployment target: {target}")
    echo_json(payload)
    if not payload.get("verified"):
        raise typer.Exit(1)


def read_agent_logs(selector: str, *, limit: int) -> None:
    log_uri = agent_logs_uri(selector)
    if "limit=" not in log_uri:
        log_uri = f"{log_uri}&limit={limit}" if "?" in log_uri else f"{log_uri}?limit={limit}"
    echo_json(Uri3Client().logs(log_uri))


def call_docker(uri: str, *, dry_run: bool) -> None:
    client = Uri3Client()
    if dry_run:
        uri = f"{uri}&dry_run=1" if "?" in uri else f"{uri}?dry_run=1"
    payload = client.call(uri)
    echo_json(payload)
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise typer.Exit(1)
