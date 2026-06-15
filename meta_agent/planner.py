from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any

from meta_agent.models import AgentCreationIntent


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9ąćęłńóśźż_-]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    # python package must be ascii-ish; keep external name readable, normalize package elsewhere
    return value or "generated-agent"


def package_name(agent_name: str) -> str:
    value = agent_name.replace("-", "_").lower()
    value = re.sub(r"[^a-z0-9_]+", "_", value)
    value = re.sub(r"_+", "_", value).strip("_")
    if not value:
        return "generated_agent"
    if value[0].isdigit():
        value = "agent_" + value
    return value


def singularize(word: str) -> str:
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith("s") and len(word) > 3:
        return word[:-1]
    return word


def infer_intent(prompt: str) -> AgentCreationIntent:
    """Rule-based planner used as safe default before any LLM integration.

    This intentionally produces a conservative contract proposal, not arbitrary code.
    """

    text = prompt.strip()
    lowered = text.lower()

    # Try to catch phrases like "agent do zamówień" / "orders agent" / "obsługi faktur".
    domain = "resource"
    patterns = [
        r"agent(?:a)?\s+do\s+obsługi\s+([\wąćęłńóśźż -]+)",
        r"agent(?:a)?\s+do\s+([\wąćęłńóśźż -]+)",
        r"obsługi\s+([\wąćęłńóśźż -]+)",
        r"for\s+([a-z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            candidate = match.group(1).strip().split(",")[0].split(".")[0]
            candidate = candidate.replace("zamówień", "orders").replace("zamowien", "orders")
            candidate = candidate.replace("faktur", "invoices").replace("dokumentów", "documents")
            candidate = candidate.replace("użytkowników", "users").replace("uzytkownikow", "users")
            domain = slugify(candidate).split("-")[0]
            break

    # Fallback keyword detection.
    keywords = {
        "order": "orders",
        "orders": "orders",
        "zamów": "orders",
        "zamow": "orders",
        "invoice": "invoices",
        "faktur": "invoices",
        "document": "documents",
        "dokument": "documents",
        "user": "users",
        "użytk": "users",
        "uzytk": "users",
    }
    for key, value in keywords.items():
        if key in lowered:
            domain = value
            break

    domain = slugify(domain).replace("-", "_")
    singular = singularize(domain)
    agent_name = f"{domain.replace('_', '-')}-agent"

    resources = [
        f"resource://{domain}/{{{singular}_id}}",
        f"resource://{domain}/{{{singular}_id}}/events",
    ]
    commands = []
    if any(k in lowered for k in ["create", "utw", "dod", "zapis", "command", "komend"]):
        commands.append(f"Create{singular.title().replace('_', '')}")
    if any(k in lowered for k in ["update", "aktual", "zmień", "zmien", "edit"]):
        commands.append(f"Update{singular.title().replace('_', '')}")

    return AgentCreationIntent(
        domain=domain,
        agent_name=agent_name,
        package=package_name(agent_name),
        description=f"Generated thin agent for {domain} resources.",
        resources=resources,
        commands=commands,
    )


def intent_to_agent_spec(intent: AgentCreationIntent) -> dict[str, Any]:
    singular = singularize(intent.domain)
    domain_title = singular.title().replace("_", "")
    capabilities: list[dict[str, Any]] = []

    if not intent.resources:
        intent.resources = [f"resource://{intent.domain}/{{{singular}_id}}"]

    for uri in intent.resources:
        suffix = uri.rstrip("/").split("/")[-1]
        if suffix == "events" or suffix == "activity" or suffix == "history":
            cap_name = f"read_{singular}_{suffix}"
            renderer = "timeline"
            schema = f"app.{intent.domain}.v1.{domain_title}{suffix.title()}View"
        else:
            cap_name = f"read_{singular}"
            renderer = "detail"
            schema = f"app.{intent.domain}.v1.{domain_title}View"
        capabilities.append(
            {
                "name": cap_name,
                "type": "resource_read",
                "description": f"Read {uri} from the shared Resource Runtime.",
                "uri": uri,
                "output_schema": schema,
                "renderer": renderer,
            }
        )

    for command in intent.commands:
        snake = re.sub(r"(?<!^)(?=[A-Z])", "_", command).lower()
        capabilities.append(
            {
                "name": snake,
                "type": "command",
                "description": f"Execute {command} through the shared Resource Runtime.",
                "command": command,
                "input_schema": f"app.{intent.domain}.v1.{command}Command",
                "emits": [f"{command}Requested"],
            }
        )

    return {
        "agent": {
            "name": intent.agent_name,
            "python_package": intent.package or package_name(intent.agent_name),
            "version": "0.1.0",
            "description": intent.description,
            "runtime_url_env": "RESOURCE_RUNTIME_URL",
            "runtime_url_default": "http://localhost:8000",
        },
        "capabilities": capabilities,
    }
