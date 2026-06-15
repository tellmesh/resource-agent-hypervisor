from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _hypervisor_repo_root(repo_root: Path):
    hypervisor = Path(os.environ.get("HYPERVISOR_REPO_ROOT", "/home/tom/github/wronai/hypervisor"))
    previous = os.environ.get("HYPERVISOR_REPO_ROOT")
    os.environ["HYPERVISOR_REPO_ROOT"] = str(hypervisor.resolve())
    yield
    if previous is None:
        os.environ.pop("HYPERVISOR_REPO_ROOT", None)
    else:
        os.environ["HYPERVISOR_REPO_ROOT"] = previous
