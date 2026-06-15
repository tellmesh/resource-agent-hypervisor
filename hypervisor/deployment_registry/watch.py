from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from hypervisor.deployment_registry.supervisor import supervise_agent
from hypervisor.paths import find_repo_root

WATCH_LOG_RELATIVE = "output/logs/hypervisor-watch.jsonl"
WATCH_EVENT_SCHEMA = "schemas/log_event.schema.json"


def _repo_root(root: str | Path) -> Path:
    return Path(root) if str(root) != "." else find_repo_root()


# Use shared now_iso to eliminate duplication (flagged in architecture audits).
from .runtime_state import now_iso as _now_iso


def _safe_selector(selector: str) -> str:
    return "".join(char if char.isalnum() or char in "._-" else "_" for char in selector)


def watch_state_path(selector: str, root: str | Path = ".") -> Path:
    repo = _repo_root(root)
    return repo / "output" / "runtime" / "watch" / f"{_safe_selector(selector)}.json"


def load_watch_state(selector: str, root: str | Path = ".") -> dict[str, Any]:
    path = watch_state_path(selector, root)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def save_watch_state(selector: str, state: dict[str, Any], root: str | Path = ".") -> Path:
    path = watch_state_path(selector, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def _inspection_from_result(result: dict[str, Any]) -> dict[str, Any]:
    for key in ("after", "before", "inspection"):
        value = result.get(key)
        if isinstance(value, dict):
            return value
    diagnosis = result.get("diagnosis")
    if isinstance(diagnosis, dict) and isinstance(diagnosis.get("inspection"), dict):
        return diagnosis["inspection"]
    return result


def _incident_codes(inspection: dict[str, Any]) -> list[str]:
    codes: list[str] = []
    for item in inspection.get("incidents") or []:
        if isinstance(item, dict) and item.get("code"):
            codes.append(str(item["code"]))
    return sorted(set(codes))


def _service_status(result: dict[str, Any]) -> str:
    inspection = _inspection_from_result(result)
    if result.get("ok") is True:
        return "healthy"
    status = (
        inspection.get("service_status")
        or inspection.get("status")
        or result.get("status")
        or "degraded"
    )
    return str(status)


def _health_signature(result: dict[str, Any]) -> str:
    if result.get("ok") is True:
        return "healthy"
    inspection = _inspection_from_result(result)
    codes = ",".join(_incident_codes(inspection)) or str(result.get("reason") or "unknown")
    return f"{_service_status(result)}:{codes}"


def _actions_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    actions = result.get("actions")
    if isinstance(actions, list) and actions:
        return [item for item in actions if isinstance(item, dict)]
    heal_attempt = result.get("heal_attempt")
    if isinstance(heal_attempt, dict) and isinstance(heal_attempt.get("actions"), list):
        return [item for item in heal_attempt["actions"] if isinstance(item, dict)]
    if isinstance(actions, list):
        return []
    return []


def _write_watch_log(
    root: Path,
    *,
    selector: str,
    code: str,
    message: str,
    level: str = "INFO",
    fields: dict[str, Any] | None = None,
) -> Path:
    path = root / WATCH_LOG_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "$schema": WATCH_EVENT_SCHEMA,
        "apiVersion": "uri3.io/v1",
        "kind": "LogEvent",
        "timestamp": _now_iso(),
        "level": level.upper(),
        "logger": "hypervisor.watch",
        "message": message,
        "uri": {
            "self": f"log://file/{WATCH_LOG_RELATIVE}",
            "subject": f"health://agent/{selector}",
        },
        "event": {
            "code": code,
            "message": message,
        },
    }
    if fields:
        entry["fields"] = fields
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def _repair_allowed(
    state: dict[str, Any],
    *,
    tick: int,
    repair: str,
    repair_backoff_ticks: int,
) -> bool:
    if repair == "none":
        return False
    last_repair_tick = int(state.get("last_repair_tick") or 0)
    if last_repair_tick <= 0:
        return True
    return tick - last_repair_tick >= max(1, repair_backoff_ticks)


def _run_supervision(
    selector: str,
    *,
    root: Path,
    repair: str,
    learn: bool,
    timeout: float,
    log_limit: int,
    max_attempts: int,
) -> dict[str, Any]:
    if learn and repair != "none":
        from hypervisor.repair.supervisor import supervise_with_repair

        return supervise_with_repair(
            selector,
            root=root,
            repair=repair,
            learn=True,
            timeout=timeout,
            log_limit=log_limit,
            max_attempts=max_attempts,
        )
    return supervise_agent(
        selector,
        root=root,
        repair=repair,
        timeout=timeout,
        log_limit=log_limit,
        max_attempts=max_attempts,
        settle_seconds=0,
    )


def _learn_allowed_for_state(state: dict[str, Any], *, learn: bool) -> bool:
    if not learn:
        return False
    if state.get("last_ok") is not False:
        return True
    last_signature = state.get("last_signature")
    if not last_signature:
        return True
    return state.get("last_incident_signature") != last_signature


def _emit_tick_events(
    repo: Path,
    *,
    selector: str,
    tick: int,
    state: dict[str, Any],
    result: dict[str, Any],
    effective_repair: str,
) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    signature = _health_signature(result)
    previous_signature = str(state.get("last_signature") or "")
    service_status = _service_status(result)
    level = "INFO" if result.get("ok") else "WARNING"

    if signature != previous_signature:
        event = {
            "code": "AGENT_HEALTH_CHANGED",
            "message": f"{selector} health changed to {service_status}",
            "level": level,
            "fields": {
                "tick": tick,
                "selector": selector,
                "previous_signature": previous_signature or None,
                "signature": signature,
                "ok": bool(result.get("ok")),
                "service_status": service_status,
                "incident_codes": _incident_codes(_inspection_from_result(result)),
            },
        }
        _write_watch_log(repo, selector=selector, **event)
        events.append(event)

    actions = _actions_from_result(result)
    if actions:
        started = {
            "code": "REPAIR_STARTED",
            "message": f"{selector} repair started ({effective_repair})",
            "level": "INFO",
            "fields": {
                "tick": tick,
                "selector": selector,
                "repair": effective_repair,
                "action_count": len(actions),
            },
        }
        _write_watch_log(repo, selector=selector, **started)
        events.append(started)
        finished_code = "REPAIR_COMPLETED" if result.get("ok") else "REPAIR_FAILED"
        finished = {
            "code": finished_code,
            "message": f"{selector} repair {'completed' if result.get('ok') else 'failed'}",
            "level": "INFO" if result.get("ok") else "ERROR",
            "fields": {
                "tick": tick,
                "selector": selector,
                "repair": effective_repair,
                "action_count": len(actions),
                "ok": bool(result.get("ok")),
            },
        }
        _write_watch_log(repo, selector=selector, **finished)
        events.append(finished)

    incident_uri = result.get("incident_uri")
    if incident_uri and incident_uri != state.get("last_incident_uri"):
        event = {
            "code": "INCIDENT_CREATED",
            "message": f"{selector} incident created",
            "level": "ERROR",
            "fields": {
                "tick": tick,
                "selector": selector,
                "incident_uri": incident_uri,
                "incident_path": result.get("incident_path"),
            },
        }
        _write_watch_log(repo, selector=selector, **event)
        events.append(event)

    return events


def _next_state(
    state: dict[str, Any],
    *,
    selector: str,
    tick: int,
    result: dict[str, Any],
    effective_repair: str,
) -> dict[str, Any]:
    actions = _actions_from_result(result)
    body = dict(state)
    body.update(
        {
            "selector": selector,
            "updated_at": _now_iso(),
            "ticks": tick,
            "last_ok": bool(result.get("ok")),
            "last_status": _service_status(result),
            "last_signature": _health_signature(result),
        }
    )
    if effective_repair != "none" and (actions or result.get("incident_uri") or not result.get("ok")):
        body["last_repair_tick"] = tick
    if result.get("incident_uri"):
        body["last_incident_uri"] = result.get("incident_uri")
        body["last_incident_tick"] = tick
        body["last_incident_signature"] = _health_signature(result)
    return body


def supervise_watch(
    selector: str,
    *,
    root: str | Path = ".",
    repair: str = "none",
    interval: float = 10.0,
    count: int | None = None,
    timeout: float = 2.0,
    log_limit: int = 20,
    max_attempts: int = 3,
    learn: bool = False,
    repair_backoff_ticks: int = 3,
    sleep: Callable[[float], None] = time.sleep,
    on_tick: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Run continuous health supervision with deduped JSONL events.

    `count` is primarily for tests and smoke runs. When omitted, the loop runs
    until interrupted by the caller.
    """
    if repair not in {"none", "restart", "reuse", "sync_health", "auto"}:
        raise ValueError("repair must be one of: none, restart, reuse, sync_health, auto")
    if interval < 0:
        raise ValueError("interval must be >= 0")
    if count is not None and count < 1:
        raise ValueError("count must be >= 1")

    repo = _repo_root(root)
    state = load_watch_state(selector, repo)
    ticks: list[dict[str, Any]] = []
    tick = int(state.get("ticks") or 0)

    try:
        while count is None or len(ticks) < count:
            tick += 1
            effective_repair = (
                repair
                if _repair_allowed(
                    state,
                    tick=tick,
                    repair=repair,
                    repair_backoff_ticks=repair_backoff_ticks,
                )
                else "none"
            )
            result = _run_supervision(
                selector,
                root=repo,
                repair=effective_repair,
                learn=_learn_allowed_for_state(state, learn=learn),
                timeout=timeout,
                log_limit=log_limit,
                max_attempts=max_attempts,
            )
            events = _emit_tick_events(
                repo,
                selector=selector,
                tick=tick,
                state=state,
                result=result,
                effective_repair=effective_repair,
            )
            state = _next_state(
                state,
                selector=selector,
                tick=tick,
                result=result,
                effective_repair=effective_repair,
            )
            save_watch_state(selector, state, repo)
            tick_payload = {
                "tick": tick,
                "ok": bool(result.get("ok")),
                "status": _service_status(result),
                "repair": effective_repair,
                "events": events,
                "result": result,
            }
            ticks.append(tick_payload)
            if on_tick:
                on_tick(tick_payload)
            if count is None or len(ticks) < count:
                sleep(interval)
    except KeyboardInterrupt:
        state["interrupted_at"] = _now_iso()
        save_watch_state(selector, state, repo)

    return {
        "ok": bool(ticks[-1]["ok"]) if ticks else True,
        "result_type": "watch",
        "selector": selector,
        "watch": True,
        "repair": repair,
        "learn": learn,
        "ticks": ticks,
        "tick_count": len(ticks),
        "state_path": str(watch_state_path(selector, repo)),
        "log_path": str(repo / WATCH_LOG_RELATIVE),
    }
