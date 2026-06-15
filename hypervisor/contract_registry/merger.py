from __future__ import annotations

from pathlib import Path
from typing import Any

from hypervisor.contract_registry.merge_helpers import (
    merge_proto_contract,
    merge_resources_contract,
    merge_views_contract,
)
from hypervisor.domain_pack.writer import repo_root


def merge_main_contracts(
    domain_id: str,
    resources: dict[str, Any],
    views: dict[str, Any],
    proto_text: str,
    *,
    root: Path | None = None,
) -> None:
    """Register generated domain artifacts in global contracts."""
    contracts = (root or repo_root()) / "contracts"
    merge_proto_contract(contracts, domain_id, proto_text)
    merge_resources_contract(contracts, resources)
    merge_views_contract(contracts, views)
