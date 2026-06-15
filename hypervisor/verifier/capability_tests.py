from __future__ import annotations

from hypervisor.contract_registry.models import ContractRegistry
from uri2verify.capability_plan import build_capability_test_plan as _build_plan


def build_capability_test_plan(registry: ContractRegistry) -> list[dict]:
    return _build_plan(registry.capabilities)
