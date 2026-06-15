from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.supervisor import ensure_agent_healthy, inspect_agent
from hypervisor.events import emit_operation_event, emit_result_event
from hypervisor.paths import find_repo_root
from hypervisor.repair.classifier import classify_inspection
from hypervisor.repair.incident import build_incident_from_inspection, load_incident, write_incident
from hypervisor.repair.plan_builder import build_repair_plan_from_diagnosis
from hypervisor.repair.playbooks import apply_playbook
from hypervisor.repair.policy import is_playbook_allowed, playbook_requires_approval
from hypervisor.repair.proposal_builder import build_repair_proposal, link_proposal_to_incident
from hypervisor.repair.registry import find_matching_case
from hypervisor.repair.sandbox import test_repair_plan_in_sandbox


def _envelope(payload: dict[str, Any]) -> dict[str, Any]:
    from uri3.results.envelope import enrich_lifecycle_dict

    body = dict(payload)
    body.setdefault("result_type", "repair")
    return enrich_lifecycle_dict(body)


def _repo_root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else find_repo_root()


def _sync_registry_if_drifted(inspection: dict[str, Any], *, repo: Path) -> dict[str, Any] | None:
    if not inspection.get("ok"):
        return None
    effective = str(inspection.get("effective_health_uri") or "")
    declared = str(inspection.get("declared_health_uri") or "")
    if not effective or not declared or effective == declared:
        return None
    deployment_id = str(inspection.get("id") or "")
    if not deployment_id:
        return None
    from hypervisor.deployment_registry.registry_sync import sync_deployment_health_uri

    try:
        return sync_deployment_health_uri(deployment_id, effective, root=repo)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "error_type": type(exc).__name__}


def diagnose_agent(
    selector: str,
    *,
    root: str | Path | None = None,
    timeout: float = 2.0,
    log_limit: int = 20,
) -> dict[str, Any]:
    repo = _repo_root(root)
    inspection = inspect_agent(selector, root=repo, timeout=timeout, log_limit=log_limit)
    classification = classify_inspection(inspection, log_payload=inspection.get("log_errors"))
    known_case = find_matching_case(classification, inspection, repo_root=repo)
    diagnosis_body = {
        "ok": bool(inspection.get("ok")),
        "id": inspection.get("id"),
        "result_type": "diagnosis",
        "inspection": inspection,
        "classification": classification,
        "known_case": known_case,
        "readiness": inspection.get("readiness"),
        "agent_readiness": inspection.get("agent_readiness"),
    }
    if not inspection.get("ok"):
        diagnosis_body["repair_plan"] = build_repair_plan_from_diagnosis(diagnosis_body)
    result = _envelope(diagnosis_body)
    emit_operation_event(
        "REPAIR_DIAGNOSED",
        f"{selector} repair diagnosis completed",
        root=repo,
        level="INFO" if result.get("ok") else "WARNING",
        selector=str(result.get("id") or selector),
        operation="repair-diagnose",
        family=classification.get("family"),
        readiness=inspection.get("readiness"),
    )
    return result


def _repair_playbook_candidates(
    diagnosis: dict[str, Any],
    classification: dict[str, Any],
    *,
    playbook: str | None,
) -> list[str]:
    if playbook:
        return [playbook]
    known_case = diagnosis.get("known_case")
    if known_case:
        return list(known_case.get("repair_sequence") or [])[:4]
    plan_steps = ((diagnosis.get("repair_plan") or {}).get("spec") or {}).get("steps") or []
    return list(plan_steps or classification.get("safe_repairs") or [])[:4]


def _execute_repair_playbooks(
    candidates: list[str],
    *,
    selector: str,
    repo: Path,
    safe: bool,
    approved: bool,
    timeout: float,
    inspection: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    after = inspection
    for name in candidates:
        if safe and not is_playbook_allowed(name, max_level="level_1_safe_fix"):
            actions.append({"playbook": name, "status": "blocked", "reason": "requires approval"})
            continue
        if playbook_requires_approval(name) and not approved:
            actions.append({"playbook": name, "status": "blocked", "reason": "requires approval"})
            continue
        actions.append(apply_playbook(name, selector=selector, root=repo, approved=approved))
        time.sleep(0.5)
        after = inspect_agent(selector, root=repo, timeout=timeout)
        if after.get("ok"):
            break
    return actions, after


def _healthy_repair_apply_body(
    selector: str,
    diagnosis: dict[str, Any],
    inspection: dict[str, Any],
    *,
    repo: Path,
) -> dict[str, Any]:
    registry_sync = _sync_registry_if_drifted(inspection, repo=repo)
    body: dict[str, Any] = {
        "ok": True,
        "status": "healthy",
        "id": selector,
        "actions": [],
        "diagnosis": diagnosis,
    }
    if registry_sync is not None:
        body["registry_sync"] = registry_sync
    return body


def repair_apply(
    selector: str,
    *,
    root: str | Path | None = None,
    safe: bool = True,
    approved: bool = False,
    playbook: str | None = None,
    timeout: float = 2.0,
) -> dict[str, Any]:
    repo = _repo_root(root)
    diagnosis = diagnose_agent(selector, root=repo, timeout=timeout)
    inspection = diagnosis["inspection"]
    if inspection.get("ok") and not playbook:
        body = _healthy_repair_apply_body(selector, diagnosis, inspection, repo=repo)
        result = _envelope(body)
        emit_result_event(
            "repair-apply",
            str(result.get("id") or selector),
            result,
            root=repo,
            success_code="REPAIR_APPLY_SKIPPED_HEALTHY",
            failure_code="REPAIR_APPLY_FAILED",
            success_message=f"{selector} repair apply skipped; agent is healthy",
            failure_message=f"{selector} repair apply failed",
            extra_fields={"registry_sync": body.get("registry_sync")},
        )
        return result

    classification = diagnosis["classification"]
    candidates = _repair_playbook_candidates(diagnosis, classification, playbook=playbook)
    actions, after = _execute_repair_playbooks(
        candidates,
        selector=selector,
        repo=repo,
        safe=safe,
        approved=approved,
        timeout=timeout,
        inspection=inspection,
    )
    registry_sync = _sync_registry_if_drifted(after, repo=repo) if after.get("ok") else None
    body = {
        "ok": bool(after.get("ok")),
        "status": "repaired" if after.get("ok") else "degraded",
        "id": selector,
        "actions": actions,
        "diagnosis": diagnosis,
        "after": after,
    }
    if registry_sync is not None:
        body["registry_sync"] = registry_sync
    result = _envelope(body)
    emit_result_event(
        "repair-apply",
        str(result.get("id") or selector),
        result,
        root=repo,
        success_code="REPAIR_APPLY_COMPLETED",
        failure_code="REPAIR_APPLY_FAILED",
        success_message=f"{selector} repair apply completed",
        failure_message=f"{selector} repair apply failed",
        extra_fields={
            "action_count": len(actions),
            "registry_sync": registry_sync,
        },
    )
    return result


def supervise_with_repair(
    selector: str,
    *,
    root: str | Path | None = None,
    repair: str = "auto",
    learn: bool = True,
    timeout: float = 2.0,
    log_limit: int = 20,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Observe → diagnose → playbook → verify → incident → proposal (bounded)."""
    repo = _repo_root(root)

    healed = ensure_agent_healthy(
        selector,
        root=repo,
        repair=repair if repair != "learn" else "auto",
        timeout=timeout,
        log_limit=log_limit,
        max_attempts=max_attempts,
    )
    if healed.get("ok"):
        result = _envelope(
            {
                **healed,
                "result_type": "repair",
                "phase": "healthy",
            }
        )
        emit_result_event(
            "repair-heal",
            selector,
            result,
            root=repo,
            success_code="URI_HEALER_COMPLETED",
            failure_code="URI_HEALER_FAILED",
            success_message=f"{selector} uri-healer completed",
            failure_message=f"{selector} uri-healer failed",
            extra_fields={"phase": "healthy"},
        )
        return result

    after = healed.get("after") or inspect_agent(
        selector, root=repo, timeout=timeout, log_limit=log_limit
    )
    classification = classify_inspection(after, log_payload=after.get("log_errors"))
    incident = build_incident_from_inspection(
        after,
        classification=classification,
        source=f"hypervisor://agent/{selector}/supervise-with-repair",
    )
    incident.repair = {
        "attempted": healed.get("actions") or [],
        "next": {
            "operation": "repair.propose",
            "uri": f"repair://agent/{selector}/propose",
            "requires_approval": True,
        },
    }
    incident_path = write_incident(incident, repo_root=repo)

    proposal: dict[str, Any] | None = None
    escalation: dict[str, Any] | None = None
    if learn:
        proposal = build_repair_proposal(incident.to_dict(repo_root=repo), repo_root=repo)
        link_proposal_to_incident(incident_path, proposal)
        sandbox = test_repair_plan_in_sandbox(
            {
                "spec": {
                    "playbook": (classification.get("safe_repairs") or ["restart_agent"])[0],
                    "steps": classification.get("safe_repairs") or ["restart_agent"],
                }
            },
            selector=selector,
            root=repo,
        )
        if not sandbox.get("ok"):
            escalation = {
                "status": "human_review",
                "reason": "sandbox verification failed",
                "sandbox": sandbox,
            }

    result = _envelope(
        {
            "ok": False,
            "status": "incident_created",
            "id": selector,
            "phase": "learn",
            "incident_uri": incident.self_uri,
            "incident_path": str(incident_path),
            "classification": classification,
            "heal_attempt": healed,
            "proposal": proposal,
            "escalation": escalation,
        }
    )
    emit_result_event(
        "repair-heal",
        selector,
        result,
        root=repo,
        success_code="URI_HEALER_COMPLETED",
        failure_code="URI_HEALER_INCIDENT_CREATED",
        success_message=f"{selector} uri-healer completed",
        failure_message=f"{selector} uri-healer created incident",
        extra_fields={
            "phase": "learn",
            "incident_uri": incident.self_uri,
            "proposal_created": bool(proposal),
        },
    )
    return result


def learn_from_incident(
    incident_path: str | Path,
    *,
    root: str | Path | None = None,
    run_sandbox: bool = True,
) -> dict[str, Any]:
    repo = _repo_root(root)
    incident = load_incident(incident_path, repo_root=repo)
    metadata = incident.get("metadata") or {}
    agent_id = str(metadata.get("agent_id") or "")
    classification = incident.get("classification") or classify_inspection(
        {"incidents": incident.get("symptoms") or []}
    )
    proposal = build_repair_proposal(incident, repo_root=repo)
    link_proposal_to_incident(Path(incident_path), proposal)

    sandbox_result = None
    if run_sandbox and agent_id:
        sandbox_result = test_repair_plan_in_sandbox(
            {
                "spec": {
                    "playbook": (classification.get("safe_repairs") or ["restart_agent"])[0],
                    "steps": classification.get("safe_repairs") or ["restart_agent"],
                }
            },
            selector=agent_id,
            root=repo,
        )

    result = _envelope(
        {
            "ok": bool(sandbox_result.get("ok")) if sandbox_result else True,
            "status": "proposal_created",
            "incident_path": str(incident_path),
            "proposal": proposal,
            "sandbox": sandbox_result,
        }
    )
    emit_result_event(
        "repair-learn",
        agent_id or str(incident_path),
        result,
        root=repo,
        success_code="REPAIR_LEARN_COMPLETED",
        failure_code="REPAIR_LEARN_FAILED",
        success_message="repair learn completed",
        failure_message="repair learn failed",
        extra_fields={"incident_path": str(incident_path)},
    )
    return result
