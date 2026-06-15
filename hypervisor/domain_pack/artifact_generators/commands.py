from typing import Any

from hypervisor.domain_pack.model import DomainModel


def generate_commands(model: DomainModel) -> dict[str, Any]:
    commands: dict[str, Any] = {"commands": []}
    for _, command in model.tree.get("commands", {}).items():
        commands["commands"].append(
            {
                "name": command["name"],
                "uri": command["uri"],
                "handler_uri": command.get("handler_uri"),
                "input_schema_ref": command.get("input_schema_ref"),
                "emits": command.get("emits", []),
            }
        )
    return commands
