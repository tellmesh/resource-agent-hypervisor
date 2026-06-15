from __future__ import annotations

from typing import Any

from uri3.config.uri_yaml import resolve_uri_values


def merge_runtime_defaults(
    merged: dict[str, Any],
    *,
    agent_runtime: dict[str, Any],
    runtime_defaults: dict[str, Any],
) -> None:
    if agent_runtime.get("resource_runtime_url"):
        merged.setdefault("RESOURCE_RUNTIME_URL", agent_runtime["resource_runtime_url"])
    elif runtime_defaults.get("resource_runtime_url"):
        merged.setdefault("RESOURCE_RUNTIME_URL", runtime_defaults["resource_runtime_url"])


def materialize_env_values(merged: dict[str, Any], *, resolve_secrets: bool) -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in merged.items():
        if value is None:
            continue
        if isinstance(value, str) and value.startswith(("env://", "secret://")):
            resolved = resolve_uri_values(value, resolve_secrets=resolve_secrets)
            if resolved is not None:
                env[str(key)] = str(resolved)
            continue
        env[str(key)] = str(value)
    return env
