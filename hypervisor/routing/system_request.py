from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


@dataclass(frozen=True)
class SystemUriRequest:
    uri: str
    repo: Path
    approved: bool
    dry_run: bool
    payload: dict[str, Any] | None
    scheme: str
    parts: list[str]
    artifact_root: Path | None = None


def uri_path_parts(uri: str) -> list[str]:
    parsed = urlparse(uri)
    if parsed.netloc:
        combined = f"{parsed.netloc}/{parsed.path.lstrip('/')}"
    else:
        combined = parsed.path.lstrip("/")
    return [part for part in combined.split("/") if part]


def query_params(uri: str) -> dict[str, str]:
    from urllib.parse import parse_qs

    parsed = urlparse(uri)
    return {
        key: values[-1]
        for key, values in parse_qs(parsed.query, keep_blank_values=True).items()
        if values
    }


def bool_param(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).lower() in {"1", "true", "yes", "y", "on"}


def int_param(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)
