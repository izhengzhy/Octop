"""Unit tests for Octop plugin manager."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from harness_agent.plugins import PluginRegistry

from octop.infra.agents.plugins.manager import PluginManager

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plugins" / "echo-tool"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    PluginRegistry.reset()
    yield
    PluginRegistry.reset()


def test_install_and_list(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text("{}", encoding="utf-8")
    plugins_dir = tmp_path / "plugins"
    mgr = PluginManager(plugins_dir=plugins_dir, config_path=config_path)
    loaded = mgr.install_path(_FIXTURE, force=True)
    assert loaded.manifest.id == "echo-tool"
    items = mgr.list_installed()
    assert any(i.get("id") == "echo-tool" for i in items)


def test_global_disable(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps({"plugins": {"echo-tool": {"enabled": False}}}),
        encoding="utf-8",
    )
    plugins_dir = tmp_path / "plugins"
    mgr = PluginManager(plugins_dir=plugins_dir, config_path=config_path)
    mgr.install_path(_FIXTURE, force=True)
    loaded = mgr.load_installed(install_deps=False)
    assert loaded == []
