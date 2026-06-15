from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ErrorFamily:
    name: str
    symptoms: tuple[str, ...]
    safe_repairs: tuple[str, ...]


ERROR_FAMILIES: tuple[ErrorFamily, ...] = (
    ErrorFamily(
        "PORT_CONFLICT",
        (
            r"PORT_OCCUPIED",
            r"FOREIGN_SERVICE_ON_PORT",
            r"address already in use",
            r"port is already allocated",
            r"Port .* zaj[eę]ty",
            r"DYNAMIC_PORT_REBIND",
            r"COMMAND_HEALTH_MISMATCH",
            r"HEALTH_URI_DRIFT",
        ),
        ("rebind_port", "sync_health_uri", "restart_agent"),
    ),
    ErrorFamily(
        "HEALTH_TIMEOUT",
        (
            r"health check failed",
            r"connection refused",
            r"timeout",
            r"HEALTH_FAILED",
            r"PROCESS_RUNNING_BUT_UNHEALTHY",
            r"PROCESS_RUNNING_HEALTH_FAILED",
            r"health endpoint did not",
        ),
        ("check_process", "read_logs", "sync_health_uri", "restart_agent", "verify_effective_port"),
    ),
    ErrorFamily(
        "RUNTIME_STALE",
        (
            r"RUNTIME_STATE_STALE",
            r"PROCESS_NOT_ALIVE",
            r"runtime state points to a dead process",
            r"stale",
        ),
        ("clear_stale_runtime", "restart_agent"),
    ),
    ErrorFamily(
        "IMPORT_ERROR",
        (
            r"ModuleNotFoundError",
            r"ImportError",
        ),
        ("verify_generated_agent", "check_editable_install"),
    ),
    ErrorFamily(
        "CONTRACT_MISMATCH",
        (
            r"capability not found",
            r"schema validation failed",
            r"unknown resource uri",
        ),
        ("validate_contract_registry", "rebuild_registry_index"),
    ),
    ErrorFamily(
        "ENV_MISSING",
        (
            r"missing env",
            r"OPENROUTER_API_KEY",
            r"RESOURCE_RUNTIME_URL",
        ),
        ("resolve_env", "validate_runtime_config"),
    ),
)


def _incident_text(inspection: dict[str, Any]) -> list[str]:
    chunks: list[str] = []
    for item in inspection.get("incidents") or []:
        chunks.append(str(item.get("code") or ""))
        chunks.append(str(item.get("detail") or ""))
    return chunks


def _warning_text(inspection: dict[str, Any]) -> list[str]:
    chunks: list[str] = []
    for item in inspection.get("warnings") or []:
        chunks.append(str(item.get("code") or ""))
        chunks.append(str(item.get("detail") or ""))
    return chunks


def _log_text(log_payload: dict[str, Any] | None) -> list[str]:
    if not log_payload:
        return []
    chunks: list[str] = []
    for entry in log_payload.get("entries") or []:
        if isinstance(entry, dict):
            chunks.append(str(entry.get("message") or entry.get("raw") or ""))
        else:
            chunks.append(str(entry))
    return chunks


def _collect_text(inspection: dict[str, Any], log_payload: dict[str, Any] | None) -> str:
    health = inspection.get("health") or {}
    chunks = _incident_text(inspection)
    if not inspection.get("ok"):
        chunks.extend(_warning_text(inspection))
    chunks.append(str(health.get("error") or ""))
    chunks.extend(_log_text(log_payload))
    return "\n".join(chunks).lower()


def classify_inspection(
    inspection: dict[str, Any],
    *,
    log_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    haystack = _collect_text(inspection, log_payload)
    matched: list[str] = []
    repairs: list[str] = []
    for family in ERROR_FAMILIES:
        if any(re.search(pattern, haystack, re.IGNORECASE) for pattern in family.symptoms):
            matched.append(family.name)
            repairs.extend(family.safe_repairs)
    unique_repairs = list(dict.fromkeys(repairs))
    confidence = min(0.95, 0.45 + 0.12 * len(matched)) if matched else 0.0
    return {
        "family": matched,
        "confidence": round(confidence, 2),
        "safe_repairs": unique_repairs,
    }
