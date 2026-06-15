from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.repair.playbooks import apply_playbook


def simulate_playbook(
    playbook: str,
    *,
    selector: str,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Dry-run repair: report intent without mutating production (level 0)."""
    return {
        "ok": True,
        "mode": "simulate",
        "playbook": playbook,
        "selector": selector,
        "would_apply": playbook
        in {
            "sync_health_uri",
            "restart_agent",
            "clear_stale_runtime",
            "rebind_port",
        },
        "message": f"simulated playbook {playbook} for {selector}",
    }


def test_repair_plan_in_sandbox(
    plan: dict[str, Any],
    *,
    selector: str,
    root: str | Path | None = None,
) -> dict[str, Any]:
    """Run safe playbooks only; mutating steps stay simulated."""
    spec = plan.get("spec") or {}
    steps = spec.get("steps") or [spec.get("playbook")]
    results: list[dict[str, Any]] = []
    for step in steps:
        name = str(step)
        if name in {"regenerate_agent", "register_repair_capability"}:
            results.append(simulate_playbook(name, selector=selector, root=root))
        else:
            results.append(apply_playbook(name, selector=selector, root=root, approved=False))
    ok = all(item.get("ok") is not False for item in results)
    return {"ok": ok, "mode": "sandbox", "results": results}
