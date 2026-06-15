#!/usr/bin/env python3
"""Run example 15pw against the current weather agent endpoint.

The documentation example is intentionally compact and often starts with
localhost:8101. In real mode the hypervisor may rebind the agent to another
free port, so this runner reads the effective health URI from the deployment
inspection before opening it in Playwright.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen

from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR.parent) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR.parent))
from repo_root import hypervisor_root  # noqa: E402

ROOT = hypervisor_root()
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.conftest import cli_argv, workspace_env  # noqa: E402

DEFAULT_AGENT = "weather-map-agent.local"


def _run(
    argv: list[str],
    *,
    env: dict[str, str],
    timeout_s: int = 180,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        argv,
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=timeout_s,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            "command failed: "
            + " ".join(argv)
            + f"\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def _json_cmd(argv: list[str], *, env: dict[str, str], timeout_s: int = 180) -> dict[str, Any]:
    result = _run(argv, env=env, timeout_s=timeout_s, check=True)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        message = f"command did not return JSON: {' '.join(argv)}\n{result.stdout}"
        raise RuntimeError(message) from exc


def _health_ok(url: str) -> bool:
    try:
        with urlopen(url, timeout=3) as response:  # noqa: S310 - local/dev health probe
            return 200 <= response.status < 300
    except (OSError, URLError):
        return False


def _extract_health_uri(payload: dict[str, Any]) -> str | None:
    candidates = [
        payload.get("readiness", {}).get("effective_health_uri"),
        payload.get("agent_readiness", {}).get("effective_health_uri"),
        payload.get("health", {}).get("uri"),
        payload.get("plan", {}).get("health_uri"),
        payload.get("data", {}).get("health_uri"),
    ]
    for candidate in candidates:
        if isinstance(candidate, str) and candidate.startswith("http"):
            return candidate
    return None


def _discover_local_agent_health(*, agent_marker: str = "weather-map") -> str | None:
    for port in range(8101, 8131):
        url = f"http://localhost:{port}/health"
        try:
            with urlopen(url, timeout=3) as response:  # noqa: S310 - local/dev health probe
                if not (200 <= response.status < 300):
                    continue
                body = response.read().decode("utf-8", errors="replace")
        except (OSError, URLError):
            continue
        if agent_marker in body:
            return url
    return None


def _inspect_agent(agent_id: str, *, env: dict[str, str]) -> dict[str, Any] | None:
    result = _run(
        cli_argv("hypervisor", "inspect-agent", agent_id, env=env, repo_root=ROOT),
        env=env,
        timeout_s=90,
    )
    if result.returncode != 0:
        return None
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _is_agent_healthy(inspected: dict[str, Any] | None, health_uri: str | None) -> bool:
    return bool(
        inspected
        and inspected.get("ok") is True
        and health_uri
        and _health_ok(health_uri)
    )

def _try_repair_or_start(agent_id: str, *, env: dict[str, str]) -> None:
    repair = _run(
        cli_argv("hypervisor", "repair", "apply", agent_id, "--approve", env=env, repo_root=ROOT),
        env=env,
        timeout_s=240,
    )
    if repair.returncode != 0:
        _run(
            cli_argv(
                "hypervisor",
                "run-agent",
                agent_id,
                "--detach",
                "--wait-healthy",
                env=env,
                repo_root=ROOT,
            ),
            env=env,
            timeout_s=240,
        )

def _ensure_weather_agent(agent_id: str, *, env: dict[str, str]) -> tuple[dict[str, Any], str]:
    inspected = _inspect_agent(agent_id, env=env)
    health_uri = _extract_health_uri(inspected or {}) if inspected else None
    if _is_agent_healthy(inspected, health_uri):
        return inspected, health_uri

    _try_repair_or_start(agent_id, env=env)

    inspected = _inspect_agent(agent_id, env=env)
    health_uri = _extract_health_uri(inspected or {}) if inspected else None
    if health_uri and _health_ok(health_uri):
        return inspected or {}, health_uri

    discovered = _discover_local_agent_health()
    if discovered:
        return inspected or {"ok": True, "discovered": True}, discovered

    raise RuntimeError(
        f"{agent_id} is not healthy after repair/run attempt; "
        f"health_uri={health_uri!r}"
    )


def _flow_text(flow_id: str, health_uri: str, *, include_screenshot: bool) -> str:
    lines = [
        "flow:",
        f"  id: {flow_id}",
        "  description: Open current weather agent health endpoint in a real browser.",
        "",
        "do:",
        "  - id: open_health",
        "    uri: browser://chrome/page/open",
        "    with:",
        f"      url: {health_uri}",
        "",
        "  - id: read_dom",
        "    uri: dom://chrome/active/body",
        "    operation: read",
        "    after: open_health",
    ]
    if include_screenshot:
        lines.extend(
            [
                "",
                "  - id: screenshot",
                "    uri: screen://browser/active/screenshot",
                "    operation: capture",
                "    after: read_dom",
            ]
        )
    return "\n".join(lines) + "\n"


def _task_text(task_id: str, health_uri: str) -> str:
    return "\n".join(
        [
            "task:",
            f"  id: {task_id}",
            "  description: Open current weather agent health endpoint with uri2ops.",
            "",
            "steps:",
            "  - id: open_health",
            "    uri: browser://chrome/page/open",
            "    operation: open",
            "    kind: command",
            "    payload:",
            f"      url: {health_uri}",
            "",
            "  - id: read_dom",
            "    uri: browser://chrome/page/active",
            "    operation: extract_dom",
            "    kind: query",
            "    depends_on:",
            "      - open_health",
            "",
            "  - id: verify_ok",
            "    uri: assertion://contains",
            "    operation: check",
            "    kind: query",
            "    payload:",
            "      actual_from: read_dom.text",
            "      expected: weather-map-agent",
            "    depends_on:",
            "      - read_dom",
            "",
        ]
    )


def _artifact_to_path(uri: str) -> Path | None:
    prefix = "artifact://workflow/"
    if not uri.startswith(prefix):
        return None
    parts = uri[len(prefix) :].split("/")
    if len(parts) < 4:
        return None
    workflow_id, run_id, step_id, *rest = parts
    return (
        ROOT
        / "output"
        / "artifacts"
        / "workflows"
        / workflow_id
        / run_id
        / step_id
        / Path(*rest)
    )


def _validate_workflow_result(payload: dict[str, Any], health_uri: str) -> dict[str, Any]:
    workflow_result = payload.get("workflow_result") or payload.get("simulation", {}).get(
        "workflow_result", {}
    )
    steps = payload.get("steps") or payload.get("simulation", {}).get("steps", [])
    if workflow_result.get("ok") is not True:
        raise RuntimeError(f"workflow failed: {json.dumps(workflow_result, ensure_ascii=False)}")

    open_step = next((step for step in steps if step.get("id") == "open_health"), None)
    if not open_step:
        raise RuntimeError("open_health step missing from workflow result")
    open_result = open_step.get("result", {})
    if open_result.get("url") != health_uri:
        raise RuntimeError(f"opened wrong URL: {open_result.get('url')!r} != {health_uri!r}")
    if open_result.get("status_code") not in {200, None}:
        raise RuntimeError(f"unexpected HTTP status: {open_result.get('status_code')}")

    dom_step = next((step for step in steps if step.get("id") == "read_dom"), None)
    dom_text = (dom_step or {}).get("result", {}).get("text", "")
    if "weather-map-agent" not in (open_result.get("text", "") + dom_text):
        raise RuntimeError("browser result does not contain weather-map-agent health payload")

    return {
        "workflow_id": workflow_result.get("id"),
        "run_id": workflow_result.get("run_id"),
        "opened_url": open_result.get("url"),
        "status_code": open_result.get("status_code"),
        "open_artifact": open_step.get("artifact_uri") or open_result.get("artifact_uri"),
    }


def _validate_png_artifact(payload: dict[str, Any]) -> str | None:
    steps = payload.get("steps") or payload.get("simulation", {}).get("steps", [])
    screen_step = next((step for step in steps if step.get("id") == "screenshot"), None)
    if not screen_step:
        return None
    artifact_uri = screen_step.get("artifact_uri") or screen_step.get("result", {}).get(
        "artifact_uri"
    )
    if not isinstance(artifact_uri, str):
        raise RuntimeError("screenshot step did not return artifact_uri")
    path = _artifact_to_path(artifact_uri)
    if path is None or not path.exists():
        raise RuntimeError(f"screenshot artifact missing: {artifact_uri}")
    if path.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n":
        raise RuntimeError(f"screenshot artifact is not a PNG: {path}")
    return str(path)


def _run_uri3_flow(
    flow_path: Path,
    graph_path: Path,
    health_uri: str,
    *,
    env: dict[str, str],
    legacy_screenshot: bool,
) -> dict[str, Any]:
    previous_legacy = os.environ.get("URI3_USE_LEGACY_BROWSER")
    if legacy_screenshot:
        os.environ["URI3_USE_LEGACY_BROWSER"] = "1"
    else:
        os.environ.pop("URI3_USE_LEGACY_BROWSER", None)

    from uri2flow import expand_flow
    from uri2flow.expander import dump_yaml
    from uri3.graph import load_workflow_graph, run_workflow, validate_workflow_graph

    graph = expand_flow(str(flow_path))
    graph_path.parent.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(dump_yaml(graph), encoding="utf-8")

    errors = validate_workflow_graph(graph)
    if errors:
        raise RuntimeError("uri3 graph validation failed: " + "; ".join(errors))

    try:
        result = run_workflow(
            load_workflow_graph(graph),
            approve=True,
            dry_run=False,
            browser_mode="playwright",
        )
    finally:
        if previous_legacy is None:
            os.environ.pop("URI3_USE_LEGACY_BROWSER", None)
        else:
            os.environ["URI3_USE_LEGACY_BROWSER"] = previous_legacy

    payload = result.to_dict()
    if not result.ok:
        raise RuntimeError(f"uri3 workflow failed: {json.dumps(payload, ensure_ascii=False)}")
    summary = _validate_workflow_result(payload, health_uri)
    screenshot_path = _validate_png_artifact(payload)
    return {"screenshot_path": screenshot_path, **summary}


def _run_uri2ops_task(task_path: Path) -> dict[str, Any]:
    from uri2ops.operator.runner import run_task
    from uri2ops.operator.task import load_task
    from uri2ops.operator.validator import validate_task_file

    errors = validate_task_file(task_path)
    if errors:
        raise RuntimeError("uri2ops task validation failed: " + "; ".join(errors))
    result = run_task(load_task(str(task_path)), adapter="playwright", approve=True)
    payload = result.to_dict()
    if not result.ok:
        raise RuntimeError(f"uri2ops task failed: {json.dumps(payload, ensure_ascii=False)}")
    steps = payload.get("steps", [])
    open_step = next((step for step in steps if step.get("id") == "open_health"), {})
    return {
        "workflow_id": payload.get("task", {}).get("id") or payload.get("id"),
        "run_id": payload.get("run_id"),
        "opened_url": open_step.get("result", {}).get("url"),
        "status_code": open_step.get("result", {}).get("status_code"),
        "open_artifact": open_step.get("artifact_uri")
        or open_step.get("result", {}).get("artifact_uri"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--agent", default=DEFAULT_AGENT, help="Deployment id to inspect/repair")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "output" / "examples")
    parser.add_argument(
        "--engine",
        choices=("uri3", "uri2ops"),
        default="uri3",
        help="Execution engine to prove",
    )
    parser.add_argument("--dry-run", action="store_true", help="Only write the generated flow")
    parser.add_argument(
        "--legacy-screenshot",
        action="store_true",
        help="Use URI3 legacy browser adapter and verify a real PNG screenshot artifact",
    )
    args = parser.parse_args(argv)

    env = workspace_env(ROOT)
    inspected, health_uri = _ensure_weather_agent(args.agent, env=env)
    args.out_dir.mkdir(parents=True, exist_ok=True)

    flow_id = (
        "weather-agent-effective-health-screenshot"
        if args.legacy_screenshot
        else f"weather-agent-effective-health-{args.engine}"
    )
    flow_path = args.out_dir / f"{flow_id}.uri.flow.yaml"
    graph_path = args.out_dir / f"{flow_id}.uri.graph.yaml"
    task_path = args.out_dir / f"{flow_id}.uri2ops.task.yaml"
    flow_path.write_text(
        _flow_text(flow_id, health_uri, include_screenshot=args.legacy_screenshot),
        encoding="utf-8",
    )
    task_path.write_text(_task_text(flow_id, health_uri), encoding="utf-8")

    if args.dry_run:
        print(
            json.dumps(
                {
                    "ok": True,
                    "dry_run": True,
                    "agent": args.agent,
                    "engine": args.engine,
                    "health_uri": health_uri,
                    "flow_path": str(flow_path),
                    "task_path": str(task_path),
                    "effective_port": inspected.get("readiness", {}).get("effective_port"),
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    if args.engine == "uri2ops":
        summary = _run_uri2ops_task(task_path)
        screenshot_path = None
    else:
        summary = _run_uri3_flow(
            flow_path,
            graph_path,
            health_uri,
            env=env,
            legacy_screenshot=args.legacy_screenshot,
        )
        screenshot_path = summary.pop("screenshot_path")
    print(
        json.dumps(
            {
                "ok": True,
                "agent": args.agent,
                "engine": args.engine,
                "health_uri": health_uri,
                "flow_path": str(flow_path),
                "graph_path": str(graph_path),
                "task_path": str(task_path),
                "screenshot_path": screenshot_path,
                **summary,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
