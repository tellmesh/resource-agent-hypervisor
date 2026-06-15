"""Domain pack generator tests."""

from __future__ import annotations

import warnings
from pathlib import Path

from hypervisor.domain_pack.generator import (
    derive_domain_model,
    generate_domain_pack,
    generate_domain_pack_from_tree,
    generate_proto,
    generate_resources,
    generate_views,
    parse_uri_tree,
)


def _weather_tree() -> dict:
    return {
        "domain": {"id": "weather_map", "description": "Weather map domain"},
        "agent": {"id": "weather-map-agent"},
        "resources": {
            "html_map": {
                "uri_template": "resource://weather/maps/{place}/forecast/{days}",
                "schema_ref": "app.weather.v1.WeatherMapHtmlView",
                "renderer_ref": "html",
                "mime_type": "text/html",
            }
        },
        "commands": {
            "generate": {
                "name": "GenerateWeatherMap",
                "uri": "command://weather/generate-map",
                "handler_uri": "python://domains.weather_map.handlers.generate_weather_map:handler",
                "input_schema_ref": "app.weather.v1.GenerateWeatherMapCommand",
                "emits": ["WeatherMapGenerationRequested", "WeatherMapGenerated"],
            }
        },
    }


def test_derive_domain_model():
    model = derive_domain_model(_weather_tree(), Path("domains/weather_map"))
    assert model.domain_id == "weather_map"
    assert model.agent["id"] == "weather-map-agent"


def test_generate_proto_weather():
    model = derive_domain_model(_weather_tree(), Path("domains/weather_map"))
    proto = generate_proto(model)
    assert "GenerateWeatherMapCommand" in proto


def test_generate_resources_and_views():
    model = derive_domain_model(_weather_tree(), Path("domains/weather_map"))
    resources = generate_resources(model)
    views = generate_views(resources)
    assert resources["resources"][0]["renderer_ref"] == "html"
    assert views["views"][0]["renderer"] == "html"


def test_generate_domain_pack_from_tree(tmp_path):
    files = generate_domain_pack_from_tree(_weather_tree(), tmp_path / "weather_map")
    assert Path(files["uri_tree"]).exists()
    assert Path(files["registry_fragment"]).exists()


def test_generate_domain_pack_from_uri_tree_file(tmp_path):
    tree_path = tmp_path / "uri_tree.yaml"
    tree_path.write_text("domain:\n  id: weather_map\nagent:\n  id: weather-map-agent\nresources: {}\ncommands: {}\n", encoding="utf-8")
    files = generate_domain_pack(tree_path, tmp_path / "weather_map")
    assert Path(files["domain"]).exists()
    assert parse_uri_tree(tree_path)["domain"]["id"] == "weather_map"


def test_deprecated_meta_agent_reexport():
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        from meta_agent.domain_planner.domain_pack_generator import generate_domain_pack_from_tree as legacy

        assert legacy is generate_domain_pack_from_tree
    assert any(issubclass(w.category, DeprecationWarning) for w in caught)
