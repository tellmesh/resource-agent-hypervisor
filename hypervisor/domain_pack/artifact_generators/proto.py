from hypervisor.domain_pack import templates
from hypervisor.domain_pack.model import DomainModel


def generate_proto(model: DomainModel) -> str:
    if model.domain_id == "weather_map":
        return templates.weather_proto()
    return templates.generic_proto(model.domain_id)
