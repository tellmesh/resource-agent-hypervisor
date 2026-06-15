#!/usr/bin/env python3
"""Split hypervisor workspace packages into tellmesh/* repos and publish with goal."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import textwrap
from pathlib import Path

HYPERVISOR = Path("/home/tom/github/tellmesh/tellmesh")
TELLMESH = Path("/home/tom/github/tellmesh")

PACKAGES = [
    "uri2pact",
    "uri2verify",
    "uri2voice",
    "uri2ops",
    "uri3",
    "uri2flow",
    "uri2run",
    "touri",
    "urigen",
    "nl2uri",
    "urish",
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

TELLMESH_DEPS = {
    "uri2flow": ["uri2pact"],
    "uri2run": ["uri2flow", "uri2ops", "uri3"],
    "touri": ["uri2pact", "uri2run", "uri2verify"],
    "urigen": ["touri", "uri2flow", "uri3"],
    "nl2uri": ["uri3"],
    "urish": ["uri2run", "uri2flow", "uri2ops", "uri3", "nl2uri", "urigen"],
}

HYPERVISOR_GIT_DEPS: dict[str, list[tuple[str, str]]] = {
    "nl2uri": [
        ("resource-agent-hypervisor", "../resource-agent-hypervisor"),
        ("resource-agent-factory", "../resource-agent-factory"),
    ],
    "urish": [
        ("resource-agent-hypervisor", "../resource-agent-hypervisor"),
        ("hypervisor-dashboard-agent", "../hypervisor-dashboard"),
    ],
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

from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]
"""


def run(cmd: list[str], *, cwd: Path, env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True)


def goal_yaml(name: str) -> str:
    return textwrap.dedent(
        f"""\
        version: '1.0'
        project:
          name: {name}
          type: [python]
          description: '{name} — TellMesh URI package'
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


def copy_package(name: str) -> Path:
    src = HYPERVISOR / "packages" / name
    dst = TELLMESH / name
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(
        src,
        dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.egg-info", ".pytest_cache", ".mypy_cache"),
    )
    tests_src = HYPERVISOR / "tests" / name
    tests_dst = dst / "tests"
    if tests_src.is_dir():
        shutil.copytree(
            tests_src,
            tests_dst,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    else:
        tests_dst.mkdir(parents=True, exist_ok=True)
        (tests_dst / "__init__.py").write_text("", encoding="utf-8")

    for rel in EXTRA_TESTS.get(name, []):
        path = HYPERVISOR / rel
        if not path.is_file():
            continue
        if rel.startswith("tests/integration/"):
            target_dir = tests_dst / "integration"
            target_dir.mkdir(parents=True, exist_ok=True)
            if not (target_dir / "__init__.py").exists():
                (target_dir / "__init__.py").write_text("", encoding="utf-8")
            shutil.copy2(path, target_dir / path.name)
        else:
            shutil.copy2(path, tests_dst / path.name)

    if name == "touri":
        voice_src = HYPERVISOR / "examples" / "21_touri_voice" / "touri_examples_voice"
        voice_dst = dst / "examples" / "21_touri_voice" / "touri_examples_voice"
        voice_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(
            voice_src,
            voice_dst,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
        pyproject = dst / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        text = text.replace(
            '"touri_examples_voice" = "../../examples/21_touri_voice/touri_examples_voice"',
            '"touri_examples_voice" = "examples/21_touri_voice/touri_examples_voice"',
        )
        pyproject.write_text(text, encoding="utf-8")

    (dst / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    if not (tests_dst / "conftest.py").exists():
        (tests_dst / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    (dst / "goal.yaml").write_text(goal_yaml(name), encoding="utf-8")

    readme = dst / "README.md"
    if not readme.is_file():
        readme.write_text(
            f"# {name}\n\nTellMesh URI package extracted from [tellmesh/tellmesh](https://github.com/tellmesh/tellmesh).\n",
            encoding="utf-8",
        )
    return dst


def append_uv_sources(pyproject_path: Path, name: str) -> None:
    lines = pyproject_path.read_text(encoding="utf-8").splitlines()
    if "[tool.uv.sources]" in lines:
        return
    block = ["", "[tool.uv.sources]"]
    for dep in TELLMESH_DEPS.get(name, []):
        block.append(f'{dep} = {{ git = "https://github.com/tellmesh/{dep}.git" }}')
    for dep_name, rel in HYPERVISOR_GIT_DEPS.get(name, []):
        block.append(f'{dep_name} = {{ path = "{rel}", editable = true }}')
    if len(block) > 2:
        pyproject_path.write_text("\n".join(lines + block) + "\n", encoding="utf-8")


def ensure_repo(name: str, dst: Path) -> None:
    append_uv_sources(dst / "pyproject.toml", name)
    if not (dst / ".git").exists():
        run(["git", "init", "-b", "main"], cwd=dst).check_returncode()
    run(["git", "add", "-A"], cwd=dst).check_returncode()
    status = run(["git", "status", "--porcelain"], cwd=dst)
    if status.stdout.strip():
        run(
            ["git", "commit", "-m", f"chore({name}): initial tellmesh split from hypervisor"],
            cwd=dst,
        ).check_returncode()

    remote = run(["git", "remote", "get-url", "origin"], cwd=dst)
    if remote.returncode != 0:
        create = run(
            [
                "gh",
                "repo",
                "create",
                f"tellmesh/{name}",
                "--public",
                "--source",
                str(dst),
                "--remote",
                "origin",
                "--push",
            ],
            cwd=dst,
        )
        if create.returncode != 0 and "already exists" not in (create.stderr or ""):
            run(["git", "remote", "add", "origin", f"git@github.com:tellmesh/{name}.git"], cwd=dst)
            run(["git", "push", "-u", "origin", "main"], cwd=dst)
    else:
        run(["git", "push", "-u", "origin", "main"], cwd=dst)


def publish_with_goal(name: str, dst: Path) -> dict[str, str | int]:
    env = os.environ.copy()
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    result = run(["goal", "-a", "-y"], cwd=dst, env=env)
    out = {
        "package": name,
        "returncode": result.returncode,
        "stdout": (result.stdout or "")[-4000:],
        "stderr": (result.stderr or "")[-4000:],
    }
    return out


def main() -> None:
    TELLMESH.mkdir(parents=True, exist_ok=True)
    report: list[dict[str, str | int]] = []
    for name in PACKAGES:
        print(f"\n===== {name} =====", flush=True)
        dst = copy_package(name)
        ensure_repo(name, dst)
        report.append(publish_with_goal(name, dst))
    report_path = TELLMESH / "split_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
