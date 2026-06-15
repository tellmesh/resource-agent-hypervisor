#!/usr/bin/env python3
"""Sync hypervisor package tests into tellmesh repos.

Destructive cleanup and pushes require explicit flags.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

HYPERVISOR = Path("/home/tom/github/tellmesh/tellmesh")
TELLMESH = Path("/home/tom/github/tellmesh")

PACKAGES = [
    "uri2flow",
    "uri2ops",
    "uri2pact",
    "uri2run",
    "uri2verify",
    "uri3",
    "urigen",
    "urish",
    "nl2uri",
    "touri",
]

EXTRA_TESTS: dict[str, list[str]] = {
    "uri2ops": [
        "tests/test_uri2ops_android.py",
        "tests/test_uri2ops_browser.py",
        "tests/test_uri2ops_pcwin.py",
        "tests/test_uri2ops_serve.py",
        "tests/test_uri2ops_v01.py",
        "tests/test_operation_registry.py",
        "tests/test_physical_ops.py",
    ],
    "uri3": ["tests/integration/test_uri3_uri2ops_delegation.py"],
    "nl2uri": [
        "tests/test_nl2a_v04.py",
        "tests/integration/test_nl2a_e2e.py",
    ],
    "uri2flow": ["tests/integration/test_flow_to_workflow_execution.py"],
}

CONFTEST = """\
from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
"""


def sync_tests(name: str) -> None:
    src = HYPERVISOR / "tests" / name
    dst = TELLMESH / name / "tests"
    if not src.is_dir():
        print(f"skip missing {src}")
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in {"__pycache__", "conftest.py"}:
            continue
        target = dst / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(item, target)
    for rel in EXTRA_TESTS.get(name, []):
        path = HYPERVISOR / rel
        if not path.is_file():
            continue
        if rel.startswith("tests/integration/"):
            target_dir = dst / "integration"
            target_dir.mkdir(parents=True, exist_ok=True)
            if not (target_dir / "__init__.py").exists():
                (target_dir / "__init__.py").write_text("", encoding="utf-8")
            shutil.copy2(path, target_dir / path.name)
        else:
            shutil.copy2(path, dst / path.name)
    if not (dst / "__init__.py").exists():
        (dst / "__init__.py").write_text("", encoding="utf-8")
    (dst / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    print(f"synced {name} -> {dst}")


def remove_hypervisor_tests(name: str) -> None:
    src = HYPERVISOR / "tests" / name
    if src.is_dir():
        shutil.rmtree(src)
        print(f"removed {src}")
    for rel in EXTRA_TESTS.get(name, []):
        path = HYPERVISOR / rel
        if path.is_file():
            path.unlink()
            print(f"removed {path}")


def push_tellmesh(name: str) -> None:
    repo = TELLMESH / name
    subprocess.run(["git", "add", "-A"], cwd=repo, check=False)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if not status.stdout.strip():
        return
    subprocess.run(
        ["git", "commit", "-m", f"test({name}): sync tests from hypervisor monorepo"],
        cwd=repo,
        check=False,
    )
    subprocess.run(["git", "push", "origin", "main"], cwd=repo, check=False)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--remove-hypervisor",
        action="store_true",
        help="delete migrated package tests from the hypervisor checkout",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="commit and push synced tests in tellmesh repos",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    for name in PACKAGES:
        sync_tests(name)
    if args.remove_hypervisor:
        for name in PACKAGES:
            remove_hypervisor_tests(name)
        integration = HYPERVISOR / "tests" / "integration"
        if integration.is_dir() and not any(integration.iterdir()):
            integration.rmdir()
    if args.push:
        for name in PACKAGES:
            push_tellmesh(name)


if __name__ == "__main__":
    main()
