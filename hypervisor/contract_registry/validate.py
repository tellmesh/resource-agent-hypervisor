from __future__ import annotations

from hypervisor.contract_registry.models import ContractRegistry
from hypervisor.contract_registry.registry_checks.capabilities import validate_capabilities
from hypervisor.contract_registry.registry_checks.resources import validate_resources, validate_views


def validate_registry(registry: ContractRegistry) -> list[str]:
    return [
        *validate_resources(registry),
        *validate_views(registry),
        *validate_capabilities(registry),
    ]
