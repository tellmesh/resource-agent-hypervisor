"""Unified Markpact manifests for agents (contract + deployment + runtime + docker)."""

from hypervisor.agent_manifest.compose import materialize_compose_from_manifest
from hypervisor.agent_manifest.materialize import materialize_agent_manifest
from hypervisor.agent_manifest.paths import manifest_path_for_agent
from hypervisor.agent_manifest.sync import sync_agent_manifest, sync_all_agent_manifests

__all__ = [
    "manifest_path_for_agent",
    "materialize_agent_manifest",
    "materialize_compose_from_manifest",
    "sync_agent_manifest",
    "sync_all_agent_manifests",
]
