from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from octop.infra.agents.context_breakdown import (
    compute_context_breakdown,
    conversation_tokens_from_messages,
    estimate_tokens,
)


def test_estimate_tokens_empty() -> None:
    assert estimate_tokens("") == 0


def test_conversation_tokens_from_messages() -> None:
    msgs = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]
    assert conversation_tokens_from_messages(msgs) == estimate_tokens("hello") + estimate_tokens(
        "hi there"
    )


def _registry_with_harness(
    *,
    system_prompt: str = "You are helpful.",
    tools: list[MagicMock] | None = None,
    history: list[dict[str, str]] | None = None,
    workspace: dict[str, str] | None = None,
) -> tuple[MagicMock, MagicMock]:
    tool = MagicMock()
    tool.name = "read_file"
    tools = tools if tools is not None else [tool]

    registry = MagicMock()
    row = MagicMock()
    row.system_prompt = system_prompt
    registry.get_row.return_value = row

    harness = MagicMock()
    harness.config.mcp_server_configs = {}
    harness._mcp_tool_name_set = frozenset()
    harness._build_tools.return_value = tools
    harness.aget_history = AsyncMock(return_value=history or [])
    files = workspace or {
        "AGENTS.md": "# rules\n",
        "USER.md": "user prefs",
        "MEMORY.md": "",
        "SOUL.md": "",
    }
    harness.workspace.aread_text = AsyncMock(side_effect=lambda name: files.get(name, ""))
    registry.get_agent.return_value = harness
    registry.list_skill_summaries = AsyncMock(return_value=[])
    return registry, harness


@pytest.mark.asyncio
async def test_with_input_tokens_skips_history_and_puts_remainder_in_conversation() -> None:
    registry, harness = _registry_with_harness(
        history=[{"role": "user", "content": "should not be read"}],
    )

    result = await compute_context_breakdown(
        registry,
        agent_id="agt_test",
        thread_id="thread_1",
        max_tokens=100_000,
        input_tokens=10_000,
        mcp_servers=[],
        skills=[],
    )

    assert result.max_tokens == 100_000
    assert result.used_tokens == 10_000
    assert sum(result.segments.values()) == 10_000
    static = sum(v for k, v in result.segments.items() if k != "conversation")
    assert result.segments["conversation"] == 10_000 - static
    assert result.segments["conversation"] > 0
    harness.aget_history.assert_not_awaited()


@pytest.mark.asyncio
async def test_without_input_tokens_loads_history_for_conversation() -> None:
    registry, harness = _registry_with_harness(
        history=[{"role": "user", "content": "hi"}],
        workspace={
            "AGENTS.md": "",
            "USER.md": "",
            "MEMORY.md": "",
            "SOUL.md": "",
        },
    )

    result = await compute_context_breakdown(
        registry,
        agent_id="agt_test",
        thread_id="thread_1",
        max_tokens=100_000,
    )
    assert result.segments["conversation"] > 0
    harness.aget_history.assert_awaited_once_with(
        "thread_1",
        limit=500,
        annotate_timestamps=False,
    )


@pytest.mark.asyncio
async def test_without_input_tokens_legacy_aget_history_without_annotate() -> None:
    registry, harness = _registry_with_harness()
    harness.aget_history = AsyncMock(
        side_effect=[TypeError("unexpected kw"), [{"role": "user", "content": "hi"}]],
    )
    harness.workspace.aread_text = AsyncMock(return_value="")

    result = await compute_context_breakdown(
        registry,
        agent_id="agt_test",
        thread_id="thread_1",
        max_tokens=100_000,
    )
    assert result.segments["conversation"] > 0
    assert harness.aget_history.await_count == 2


@pytest.mark.asyncio
async def test_input_tokens_smaller_than_static_scales_static_down() -> None:
    registry, _harness = _registry_with_harness(
        system_prompt="x" * 4000,
        workspace={
            "AGENTS.md": "y" * 4000,
            "USER.md": "z" * 4000,
            "MEMORY.md": "",
            "SOUL.md": "",
        },
    )

    result = await compute_context_breakdown(
        registry,
        agent_id="agt_test",
        thread_id="thread_1",
        max_tokens=100_000,
        input_tokens=100,
    )
    assert result.used_tokens == 100
    assert sum(result.segments.values()) == 100
    assert result.segments["conversation"] == 0
