from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from hypervisor.domain_pack.model import DomainModel


def parse_uri_tree(uri_tree_path: str | Path) -> dict[str, Any]:
    path = Path(uri_tree_path)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def derive_domain_model(tree: dict[str, Any], out_dir: Path) -> DomainModel:
    return DomainModel.from_uri_tree(tree, Path(out_dir))
