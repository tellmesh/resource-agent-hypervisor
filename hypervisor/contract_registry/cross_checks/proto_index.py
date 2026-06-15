from __future__ import annotations

import re
from pathlib import Path


def load_proto_text(root: Path) -> str:
    parts: list[str] = []
    for path in sorted((root / "contracts" / "proto").glob("*.proto")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def schema_exists(proto_text: str, schema_ref: str) -> bool:
    name = schema_ref.split(".")[-1]
    return re.search(rf"\bmessage\s+{re.escape(name)}\b", proto_text) is not None
