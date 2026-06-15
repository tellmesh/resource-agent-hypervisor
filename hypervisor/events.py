from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.paths import find_repo_root


def _repo_root(root: str | Path | None) -> Path:
    return Path(root) if root is not None else find_repo_root()


def emit_operation_event(
    code: str,
    message: str,
    *,
    root: str | Path | None = None,
    level: str = "INFO",
    selector: str | None = None,
    operation: str | None = None,
    subject_uri: str | None = None,
    **fields: Any,
) -> Path | None:
    """Append a dashboard-visible LogEvent for lifecycle and repair operations.

    Event emission is deliberately best-effort. A failed event write must not
    block lifecycle or repair commands.
    """
    try:
        from uri3.logs.writer import append_log

        subject = subject_uri
        if subject is None and selector:
            subject = f"health://agent/{selector}"
        payload_fields = {
            "event_code": code,
            **({"selector": selector} if selector else {}),
            **({"operation": operation} if operation else {}),
            **fields,
        }
        return append_log(
            "hypervisor-events",
            message,
            level=level,
            logger="hypervisor.events",
            root=_repo_root(root),
            subject_uri=subject,
            **payload_fields,
        )
    except Exception:
        return None


def emit_result_event(
    operation: str,
    selector: str,
    result: dict[str, Any],
    *,
    root: str | Path | None = None,
    success_code: str,
    failure_code: str,
    success_message: str,
    failure_message: str,
    extra_fields: dict[str, Any] | None = None,
) -> Path | None:
    ok = result.get("ok") is not False
    code = success_code if ok else failure_code
    level = "INFO" if ok else "ERROR"
    message = success_message if ok else failure_message
    fields = {
        "status": result.get("status"),
        "workflow_status": result.get("workflow_status"),
        "execution_status": result.get("execution_status"),
        "service_result_status": result.get("service_result_status"),
        "result_type": result.get("result_type"),
        **(extra_fields or {}),
    }
    return emit_operation_event(
        code,
        message,
        root=root,
        level=level,
        selector=selector,
        operation=operation,
        **fields,
    )
