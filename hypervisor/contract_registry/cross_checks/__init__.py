from hypervisor.contract_registry.cross_checks.capabilities import validate_capability_cross_refs
from hypervisor.contract_registry.cross_checks.proto_index import load_proto_text
from hypervisor.contract_registry.cross_checks.resources import validate_resource_cross_refs

__all__ = [
    "load_proto_text",
    "validate_capability_cross_refs",
    "validate_resource_cross_refs",
]
