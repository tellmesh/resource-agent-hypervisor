"""Basic tests for hypervisor package."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from hypervisor import Hypervisor, __version__, get_config, load_config
from hypervisor.config import get_default_config
from hypervisor.core import Hypervisor as HVCore


def test_version_present():
    assert __version__
    assert isinstance(__version__, str)


def test_default_config_has_hypervisor_section():
    cfg = get_default_config()
    assert "hypervisor" in cfg
    assert cfg["hypervisor"].get("max_agents") == 8


def test_load_config_merges_user_file(tmp_path: Path):
    user_cfg = tmp_path / "nlp2uri.yaml"
    user_cfg.write_text(
        """
platform: linux
hypervisor:
  max_agents: 4
  default_profile: fast
""",
        encoding="utf-8",
    )
    cfg = load_config(user_cfg)
    assert cfg["platform"] == "linux"
    assert cfg["hypervisor"]["max_agents"] == 4
    assert cfg["hypervisor"]["default_profile"] == "fast"
    assert "_config_path" in cfg


def test_hypervisor_object():
    hv = Hypervisor()
    assert not hv.running
    assert hv.max_agents == 8
    assert hv.profile in ("normal", "fast", "full")

    hv.register_agent("test-agent-1")
    assert "test-agent-1" in hv.agents

    st = hv.status()
    assert st["registered_agents"] == ["test-agent-1"]
    assert st["max_agents"] == 8


def test_hypervisor_from_config_and_limits():
    hv = Hypervisor.from_config()
    # force low limit
    hv.max_agents = 1
    hv.register_agent("only-one")
    with pytest.raises(RuntimeError):
        hv.register_agent("second")


def test_cli_status_runs(capsys):
    from hypervisor.cli import main

    rc = main(["status"])
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["profile"] in ("normal", "fast", "full")
    assert "max_agents" in payload


def test_cli_config_path(capsys):
    from hypervisor.cli import main

    rc = main(["config", "--path"])
    assert rc == 0
    # either embedded or real file
    out = capsys.readouterr().out.strip()
    assert out  # not empty
