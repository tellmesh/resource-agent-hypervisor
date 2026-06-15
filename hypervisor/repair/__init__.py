"""Evolutionary self-healing: incidents, playbooks, repair supervisor."""

from hypervisor.repair.healer import run_uri_healer
from hypervisor.repair.supervisor import (
    diagnose_agent,
    learn_from_incident,
    repair_apply,
    supervise_with_repair,
)

__all__ = [
    "diagnose_agent",
    "learn_from_incident",
    "repair_apply",
    "run_uri_healer",
    "supervise_with_repair",
]
