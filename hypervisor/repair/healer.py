from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.repair.supervisor import supervise_with_repair


def run_uri_healer(
    selector: str,
    *,
    root: str | Path | None = None,
    repair: str = "auto",
    learn: bool = True,
    timeout: float = 2.0,
    log_limit: int = 20,
    max_attempts: int = 3,
) -> dict[str, Any]:
    """Bounded uri-healer loop: observe → repair → incident → evolution proposal.

    Wraps ``supervise_with_repair``. Regenerate-agent and registry rollback remain
    manual/policy-gated follow-ups on the returned proposal.
    """
    payload = supervise_with_repair(
        selector,
        root=root,
        repair=repair,
        learn=learn,
        timeout=timeout,
        log_limit=log_limit,
        max_attempts=max_attempts,
    )
    payload["healer"] = True
    payload["result_type"] = "healer"
    return payload
