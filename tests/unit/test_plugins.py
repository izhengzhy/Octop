"""Unit tests for harness-agent plugin loader."""

from __future__ import annotations

from pathlib import Path

import pytest
from harness_agent.plugins import (
    PluginRegistry,
    build_plugin_tools,
    collect_plugin_tool_configs,
    load_plugin_dir,
)
from langchain_core.tools import StructuredTool

_FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "plugins" / "echo-tool"


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    PluginRegistry.reset()
    yield
    PluginRegistry.reset()


def test_load_echo_tool_plugin() -> None:
    loaded = load_plugin_dir(_FIXTURE, install_deps=False)
    assert loaded.manifest.id == "echo-tool"
    assert len(loaded.tools) == 1
    assert loaded.tools[0].name == "echo_message"


def test_build_plugin_tools_respects_enabled_flag() -> None:
    load_plugin_dir(_FIXTURE, install_deps=False)
    disabled = build_plugin_tools(
        agent_plugins={"echo-tool": {"tools": {"echo_message": {"enabled": False}}}},
    )
    assert disabled == []
    enabled = build_plugin_tools(
        agent_plugins={"echo-tool": {"tools": {"echo_message": {"enabled": True}}}},
    )
    assert len(enabled) == 1
    assert isinstance(enabled[0], StructuredTool)
    assert enabled[0].name == "echo_message"


def test_collect_plugin_tool_configs() -> None:
    cfg = collect_plugin_tool_configs(
        {
            "echo-tool": {
                "tools": {
                    "echo_message": {
                        "enabled": True,
                        "config": {"prefix": ">> "},
                    },
                },
            },
        },
    )
    assert cfg == {"echo_message": {"prefix": ">> "}}
