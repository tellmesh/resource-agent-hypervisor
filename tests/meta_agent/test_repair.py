"""Repair rule tests."""

from __future__ import annotations

from pathlib import Path

import yaml

from generator.validate import validate_agent
from meta_agent.repair.pipeline import repair_agent_spec
from meta_agent.repair.rules import (
    repair_agent_block,
    repair_capabilities,
    repair_command_capability,
    repair_resource_read_capability,
)


def test_repair_agent_block_fills_metadata():
    data: dict = {"agent": {}}
    warnings: list[str] = []
    repair_agent_block(data, "orders_agent", warnings)
    assert data["agent"]["name"] == "orders-agent"
    assert data["agent"]["python_package"]
    assert data["agent"]["version"] == "0.1.0"
    assert warnings


def test_repair_resource_read_fills_renderer_and_schema():
    cap = {"name": "read_events", "type": "resource_read", "uri": "resource://orders/{id}/events"}
    warnings: list[str] = []
    repair_resource_read_capability(cap, warnings)
    assert cap["renderer"] == "timeline"
    assert cap["output_schema"]


def test_repair_command_fills_fields():
    cap = {"name": "create_order", "type": "command"}
    warnings: list[str] = []
    repair_command_capability(cap, warnings)
    assert cap["command"] == "CreateOrder"
    assert cap["input_schema"]


def test_repair_capabilities_deduplicates_names():
    data = {
        "capabilities": [
            {"name": "read_thing", "type": "resource_read", "uri": "resource://things/{id}"},
            {"name": "read_thing", "type": "resource_read", "uri": "resource://things/{id}/events"},
        ]
    }
    repair_capabilities(data, warnings := [])
    names = [cap["name"] for cap in data["capabilities"]]
    assert len(names) == len(set(names))


def test_repair_agent_spec_integration(tmp_path: Path):
    broken = tmp_path / "broken_agent.yaml"
    broken.write_text(
        """
agent:
  name: broken-agent
capabilities:
  - name: read_thing
    type: resource_read
    uri: resource://things/{thing_id}
  - name: read_thing
    type: resource_read
    uri: resource://things/{thing_id}/events
  - name: create_thing
    type: command
""".strip(),
        encoding="utf-8",
    )
    result = repair_agent_spec(broken, write=True)
    assert result.changed
    assert result.errors_after == []
    repaired = yaml.safe_load(broken.read_text(encoding="utf-8"))
    assert validate_agent(broken) == []
