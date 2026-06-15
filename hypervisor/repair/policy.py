from __future__ import annotations

from typing import Any

REPAIR_POLICY: dict[str, Any] = {
    "level_0_observe": {
        "allowed": ["read_logs", "read_runtime_state", "check_health", "check_ports", "diagnose"],
    },
    "level_1_safe_fix": {
        "allowed": [
            "sync_health_uri",
            "restart_agent",
            "clear_stale_runtime",
            "rebind_port",
            "verify_effective_port",
        ],
    },
    "level_2_mutating_fix": {
        "requires_approval": True,
        "allowed": [
            "kill_process",
            "modify_deployment_registry",
            "regenerate_agent",
            "modify_contracts",
        ],
    },
    "level_3_architecture_change": {
        "requires_human_review": True,
        "allowed": [
            "add_new_repair_agent",
            "change_operation_registry",
            "change_policy_gate",
            "change_uri_scheme",
            "register_repair_capability",
        ],
    },
}

PLAYBOOK_POLICY_LEVEL: dict[str, str] = {
    "diagnose": "level_0_observe",
    "read_logs": "level_0_observe",
    "check_process": "level_0_observe",
    "verify_effective_port": "level_0_observe",
    "sync_health_uri": "level_1_safe_fix",
    "restart_agent": "level_1_safe_fix",
    "clear_stale_runtime": "level_1_safe_fix",
    "rebind_port": "level_1_safe_fix",
    "regenerate_agent": "level_2_mutating_fix",
    "register_repair_capability": "level_3_architecture_change",
}


def policy_level_for_playbook(playbook: str) -> str:
    return PLAYBOOK_POLICY_LEVEL.get(playbook, "level_2_mutating_fix")


def playbook_requires_approval(playbook: str) -> bool:
    level = policy_level_for_playbook(playbook)
    policy = REPAIR_POLICY[level]
    return bool(policy.get("requires_approval") or policy.get("requires_human_review"))


def is_playbook_allowed(playbook: str, *, max_level: str = "level_1_safe_fix") -> bool:
    level = policy_level_for_playbook(playbook)
    order = (
        "level_0_observe",
        "level_1_safe_fix",
        "level_2_mutating_fix",
        "level_3_architecture_change",
    )
    return order.index(level) <= order.index(max_level)
