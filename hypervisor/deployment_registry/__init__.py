from hypervisor.deployment_registry.loader import default_registry_path, load_deployment_registry
from hypervisor.deployment_registry.models import AgentDeployment, DeploymentRegistry
from hypervisor.deployment_registry.remote_runner import (
    apply_ssh_deploy_plan,
    apply_ssh_run_plan,
    build_ssh_deploy_plan,
    build_ssh_run_plan,
    verify_remote_deployment,
)
from hypervisor.deployment_registry.runner import (
    agent_logs_uri,
    agent_status,
    build_run_plan,
    inspect_agent,
    resolve_deployment,
    restart_agent,
    run_agent,
    stop_agent,
    supervise_agent,
)
from hypervisor.deployment_registry.status import (
    deployment_from_uri_tree,
    get_deployment_for_agent,
    list_deployments,
    registry_summary,
    resolve_status,
    sync_from_uri_tree,
)
from hypervisor.deployment_registry.writer import (
    remove_deployment,
    save_deployment_registry,
    upsert_deployment,
    write_deployment_registry,
)

__all__ = [
    "AgentDeployment",
    "DeploymentRegistry",
    "agent_logs_uri",
    "agent_status",
    "apply_ssh_deploy_plan",
    "apply_ssh_run_plan",
    "build_run_plan",
    "build_ssh_deploy_plan",
    "build_ssh_run_plan",
    "default_registry_path",
    "deployment_from_uri_tree",
    "get_deployment_for_agent",
    "inspect_agent",
    "list_deployments",
    "load_deployment_registry",
    "registry_summary",
    "remove_deployment",
    "resolve_deployment",
    "resolve_status",
    "restart_agent",
    "run_agent",
    "save_deployment_registry",
    "stop_agent",
    "supervise_agent",
    "sync_from_uri_tree",
    "upsert_deployment",
    "verify_remote_deployment",
    "write_deployment_registry",
]
