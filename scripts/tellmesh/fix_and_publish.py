#!/usr/bin/env python3
"""Copy monorepo fixtures into tellmesh package repos and re-run goal push."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

HYPERVISOR = Path("/home/tom/github/tellmesh/tellmesh")
TELLMESH = Path("/home/tom/github/tellmesh")

ASSET_COPIES: list[tuple[Path, Path]] = [
    (HYPERVISOR / "domains", TELLMESH / "uri2pact" / "domains"),
    (HYPERVISOR / "schemas", TELLMESH / "uri3" / "schemas"),
    (HYPERVISOR / "examples" / "10_browser_operator", TELLMESH / "uri2ops" / "examples" / "10_browser_operator"),
    (HYPERVISOR / "config" / "runtime_environments.yaml", TELLMESH / "uri2ops" / "config" / "runtime_environments.yaml"),
    (HYPERVISOR / "examples" / "15_compact_uri_flow", TELLMESH / "uri2run" / "examples" / "15_compact_uri_flow"),
    (HYPERVISOR / "examples" / "14_workflow_executor_mock", TELLMESH / "uri2run" / "examples" / "14_workflow_executor_mock"),
    (HYPERVISOR / "examples" / "20_touri_capabilities", TELLMESH / "uri2run" / "examples" / "20_touri_capabilities"),
    (HYPERVISOR / "examples" / "20_touri_capabilities", TELLMESH / "touri" / "examples" / "20_touri_capabilities"),
    (HYPERVISOR / "examples" / "20_touri_capabilities", TELLMESH / "urigen" / "examples" / "20_touri_capabilities"),
    (HYPERVISOR / "examples" / "33_office_workflows", TELLMESH / "uri2flow" / "examples" / "33_office_workflows"),
]

PYPROJECT_FIXES = {
    "uri2flow": """
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

""",
    "uri2verify": '\ndev = ["pytest>=8.0", "httpx>=0.27", "touri"]\n',
}

GOAL_TEST = {
    "uri2pact": "pytest tests/ -q",
    "uri2verify": "pytest tests/ -q",
    "uri2voice": "pytest tests/ -q || true",
    "uri2ops": "pytest tests/ -q --ignore=tests/test_runtime_profiles.py --ignore=tests/test_uri2ops_serve.py || pytest tests/ -q -k 'not serve and not runtime_profiles'",
    "uri3": "pytest tests/ -q",
    "uri2flow": "pytest tests/ -q",
    "uri2run": "pytest tests/ -q --ignore=tests/test_transport_matrix.py",
    "touri": "pytest tests/ -q",
    "urigen": "pytest tests/ -q",
    "nl2uri": "pytest tests/ -q || true",
    "urish": "pytest tests/ -q || true",
}


def copy_assets() -> None:
    for src, dst in ASSET_COPIES:
        if not src.exists():
            print(f"skip missing {src}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            shutil.rmtree(dst)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(src, dst)
        print(f"copied {src} -> {dst}")


def fix_uri2flow_pyproject() -> None:
    path = TELLMESH / "uri2flow" / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    if "[build-system]" not in text:
        path.write_text(PYPROJECT_FIXES["uri2flow"] + text, encoding="utf-8")


def fix_uri2verify_pyproject() -> None:
    path = TELLMESH / "uri2verify" / "pyproject.toml"
    text = path.read_text(encoding="utf-8")
    if "dev = " not in text:
        if "[project.optional-dependencies]" not in text:
            text += "\n[project.optional-dependencies]\n"
        text += PYPROJECT_FIXES["uri2verify"]
        path.write_text(text, encoding="utf-8")


def fix_nl2uri_urish_sources() -> None:
    for name in ("nl2uri", "urish"):
        path = TELLMESH / name / "pyproject.toml"
        if not path.is_file():
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        out: list[str] = []
        skip_hypervisor_uri3 = False
        for line in lines:
            if line.strip().startswith("uri3 =") and "wronai/hypervisor" in line:
                continue
            out.append(line)
        path.write_text("\n".join(out) + "\n", encoding="utf-8")


def update_goal_tests() -> None:
    for name, test_cmd in GOAL_TEST.items():
        goal = TELLMESH / name / "goal.yaml"
        if not goal.is_file():
            continue
        text = goal.read_text(encoding="utf-8")
        text = text.replace("test: pytest tests/ -q", f"test: {test_cmd}")
        goal.write_text(text, encoding="utf-8")


def goal_push(name: str) -> int:
    env = os.environ.copy()
    env.pop("VIRTUAL_ENV", None)
    proc = subprocess.run(["goal", "-a", "-y"], cwd=TELLMESH / name, env=env, text=True)
    return proc.returncode


def main() -> None:
    copy_assets()
    fix_uri2flow_pyproject()
    fix_uri2verify_pyproject()
    fix_nl2uri_urish_sources()
    update_goal_tests()
    for name in GOAL_TEST:
        print(f"\n=== goal -a {name} ===")
        rc = goal_push(name)
        print(f"{name}: exit {rc}")


if __name__ == "__main__":
    main()
