#!/usr/bin/env python3
"""Move remaining hypervisor Python packages into tellmesh/* repos."""

from __future__ import annotations

import shutil
import subprocess
import textwrap
from pathlib import Path

HYPERVISOR = Path("/home/tom/github/tellmesh/tellmesh")
TELLMESH = Path("/home/tom/github/tellmesh")

CORE_PACKAGES: dict[str, Path] = {
    "resource-agent-hypervisor": TELLMESH / "resource-agent-hypervisor",
    "resource-agent-factory": TELLMESH / "resource-agent-factory",
    "hypervisor-dashboard": TELLMESH / "hypervisor-dashboard",
}

PACKAGE_TESTS: dict[str, list[Path]] = {
    "resource-agent-hypervisor": [
        HYPERVISOR / "tests" / "meta_agent",
        HYPERVISOR / "tests" / "domain_pack",
        HYPERVISOR / "tests" / "test_hypervisor.py",
        HYPERVISOR / "tests" / "test_evolution_proposal.py",
    ],
    "resource-agent-factory": [
        HYPERVISOR / "tests" / "generator",
        HYPERVISOR / "tests" / "resource_agent_factory",
        HYPERVISOR / "tests" / "domain_pack" / "test_generator.py",
    ],
    "hypervisor-dashboard": [
        HYPERVISOR / "tests" / "hypervisor" / "test_dashboard_agent.py",
        HYPERVISOR / "tests" / "hypervisor" / "test_dashboard_routing_api.py",
        HYPERVISOR / "tests" / "hypervisor" / "test_dashboard_policy.py",
    ],
}

TELLMESH_UV_SOURCES: dict[str, dict[str, str]] = {
    "resource-agent-hypervisor": {
        "uri3": "../uri3",
        "uri2pact": "../uri2pact",
        "uri2run": "../uri2run",
        "uri2verify": "../uri2verify",
        "urish": "../urish",
        "nl2uri": "../nl2uri",
        "uri2ops": "../uri2ops",
    },
    "resource-agent-factory": {},
    "hypervisor-dashboard": {
        "resource-agent-hypervisor": "../resource-agent-hypervisor",
        "urish": "../urish",
        "uri3": "../uri3",
        "uri2voice": "../uri2voice",
    },
}

GITIGNORE = """\
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
.venv/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.coverage
htmlcov/
.DS_Store
"""

CONFTEST = """\
from __future__ import annotations

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def package_root() -> Path:
    return Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(
        os.environ.get("HYPERVISOR_REPO_ROOT", "/home/tom/github/tellmesh/tellmesh")
    ).resolve()


@pytest.fixture(scope="session", autouse=True)
def _hypervisor_repo_root_env(repo_root: Path):
    previous = os.environ.get("HYPERVISOR_REPO_ROOT")
    os.environ["HYPERVISOR_REPO_ROOT"] = str(repo_root)
    yield
    if previous is None:
        os.environ.pop("HYPERVISOR_REPO_ROOT", None)
    else:
        os.environ["HYPERVISOR_REPO_ROOT"] = previous
"""


def goal_yaml(name: str) -> str:
    return textwrap.dedent(
        f"""\
        version: '1.0'
        project:
          name: {name}
          type: [python]
          description: '{name} — TellMesh core package'
        versioning:
          strategy: semver
          files: [pyproject.toml:version]
        git:
          commit:
            strategy: conventional
            scope: {name}
          tag:
            enabled: true
            prefix: v
        strategies:
          python:
            test: pytest tests/ -q
            build: python -m build
            publish: twine upload dist/{name}-{{version}}*
            publish_enabled: true
        registries:
          pypi:
            url: https://pypi.org/simple/
            token_env: PYPI_TOKEN
        """
    )


def _ignore_copy(_dir: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name in {"__pycache__", ".pytest_cache", ".mypy_cache", ".venv", ".egg-info"}
        or name.endswith(".egg-info")
    }


def copy_tree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=_ignore_copy)


def append_uv_sources(dst: Path, name: str) -> None:
    sources = TELLMESH_UV_SOURCES.get(name, {})
    if not sources:
        return
    pyproject = dst / "pyproject.toml"
    text = pyproject.read_text(encoding="utf-8")
    if "[tool.uv.sources]" in text:
        return
    lines = ["", "[tool.uv.sources]"]
    for dep, rel in sources.items():
        lines.append(f'{dep} = {{ path = "{rel}", editable = true }}')
    pyproject.write_text(text.rstrip() + "\n" + "\n".join(lines) + "\n", encoding="utf-8")


def sync_tests(name: str, dst: Path) -> None:
    tests_dst = dst / "tests"
    tests_dst.mkdir(parents=True, exist_ok=True)
    for src in PACKAGE_TESTS.get(name, []):
        if not src.exists():
            continue
        target = tests_dst / src.name
        if src.is_dir():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(src, target, ignore=_ignore_copy)
        else:
            shutil.copy2(src, target)
    if not (tests_dst / "__init__.py").exists():
        (tests_dst / "__init__.py").write_text("", encoding="utf-8")
    (tests_dst / "conftest.py").write_text(CONFTEST, encoding="utf-8")


def ensure_repo(name: str, dst: Path) -> None:
    (dst / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    if not (dst / "goal.yaml").is_file():
        (dst / "goal.yaml").write_text(goal_yaml(name), encoding="utf-8")
    readme = dst / "README.md"
    if not readme.is_file():
        readme.write_text(
            f"# {name}\n\nTellMesh core package extracted from [tellmesh/tellmesh](https://github.com/tellmesh/tellmesh).\n",
            encoding="utf-8",
        )
    append_uv_sources(dst, name)
    if not (dst / ".git").exists():
        subprocess.run(["git", "init", "-b", "main"], cwd=dst, check=False)
    subprocess.run(["git", "add", "-A"], cwd=dst, check=False)
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=dst,
        capture_output=True,
        text=True,
        check=False,
    )
    if status.stdout.strip():
        subprocess.run(
            ["git", "commit", "-m", f"chore({name}): split core package from hypervisor"],
            cwd=dst,
            check=False,
        )


def migrate_package(name: str, src: Path) -> Path:
    dst = TELLMESH / name
    print(f"migrate {name}: {src} -> {dst}")
    copy_tree(src, dst)
    sync_tests(name, dst)
    ensure_repo(name, dst)
    return dst


def main() -> None:
    TELLMESH.mkdir(parents=True, exist_ok=True)
    for name, src in CORE_PACKAGES.items():
        if not src.is_dir():
            raise SystemExit(f"missing source: {src}")
        migrate_package(name, src)
    print("done — update hypervisor pyproject.toml and remove local copies")


if __name__ == "__main__":
    main()
