from hypervisor.domain_pack import templates
from hypervisor.domain_pack.model import DomainModel


def generate_handlers(model: DomainModel) -> tuple[str, str]:
    handler_name = "generate_weather_map.py" if model.domain_id == "weather_map" else "run.py"
    handler_source = (
        templates.weather_handler() if model.domain_id == "weather_map" else templates.generic_handler()
    )
    return handler_name, handler_source
