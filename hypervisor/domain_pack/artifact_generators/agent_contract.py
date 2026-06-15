from typing import Any

from hypervisor.domain_pack import templates
from hypervisor.domain_pack.model import DomainModel


def generate_agent_contract(model: DomainModel) -> dict[str, Any]:
    if model.domain_id == "weather_map":
        capabilities = [
            {
                "name": "read_weather_map",
                "type": "resource_read",
                "description": "Read generated weather map HTML view for a location and forecast horizon.",
                "uri": "resource://weather/maps/{place}/forecast/{days}",
                "output_schema": "app.weather.v1.WeatherMapHtmlView",
                "renderer": "html",
            },
            {
                "name": "generate_weather_map",
                "type": "command",
                "description": "Generate a weather map forecast HTML view for a location.",
                "command": "GenerateWeatherMap",
                "input_schema": "app.weather.v1.GenerateWeatherMapCommand",
                "emits": ["WeatherMapGenerationRequested", "WeatherMapGenerated"],
            },
        ]
    else:
        capabilities = [
            {
                "name": "run",
                "type": "command",
                "command": "RunTask",
                "input_schema": f"{templates.package_name(model.domain_id)}.RunTaskCommand",
                "emits": ["TaskRequested", "TaskCompleted"],
            }
        ]

    return {
        "agent": {
            "name": model.agent["id"],
            "python_package": model.agent["id"].replace("-", "_"),
            "version": "0.1.0",
            "description": model.domain.get("description", "Generated thin agent"),
            "runtime_url_env": "RESOURCE_RUNTIME_URL",
            "runtime_url_default": "http://localhost:8000",
        },
        "capabilities": capabilities,
    }
