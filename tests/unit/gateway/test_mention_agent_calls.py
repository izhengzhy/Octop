"""tests/unit/test_mention_agent_calls.py"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from harness_agent.config import HarnessAgentConfig, ModelConfig, ProviderConfig
from harness_agent.manager import HarnessAgentManager
from harness_agent.messages import first_user_text


def _config(tmp_path: Path) -> HarnessAgentConfig:
    return HarnessAgentConfig(
        workspace_dir=tmp_path,
        providers=[
            ProviderConfig(
                id="openai",
                base_url="https://api.openai.com/v1",
                api_key="sk-test",
                models=[ModelConfig(id="gpt-4", enabled=True)],
            )
        ],
        default_model="openai/gpt-4",
        name="agent",
    )


def test_first_user_text_string_content() -> None:
    assert first_user_text([{"role": "user", "content": "hello"}]) == "hello"


def test_first_user_text_blocks() -> None:
    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": "hi there"}],
        }
    ]
    assert first_user_text(messages) == "hi there"


@pytest.mark.asyncio
async def test_apply_mentions_injects_system_message(tmp_path: Path) -> None:
    mock_agent = MagicMock()
    mock_agent.init_workspace.return_value = MagicMock()
    mock_agent.call = AsyncMock(
        return_value={"messages": [{"role": "assistant", "content": "findings"}]}
    )

    with patch("harness_agent.manager.HarnessAgent", return_value=mock_agent):
        mgr = HarnessAgentManager()
        mgr.create_agent(_config(tmp_path), agent_id="main", metadata={"user_id": 7})
        mgr.create_agent(_config(tmp_path / "b"), agent_id="agent-b", metadata={"user_id": 7})

    messages = [{"role": "user", "content": "summarize"}]
    out = await mgr.team.apply_mentions(
        from_agent_id="main",
        user_id=7,
        mention_agent_ids=["agent-b"],
        prompt="summarize",
        messages=messages,
    )

    assert len(out) == 2
    assert out[0]["role"] == "system"
    assert "findings" in out[0]["content"]
    assert out[1] == messages[0]


def test_filter_peer_ids(tmp_path: Path) -> None:
    mock_agent = MagicMock()
    mock_agent.init_workspace.return_value = MagicMock()

    with patch("harness_agent.manager.HarnessAgent", return_value=mock_agent):
        mgr = HarnessAgentManager()
        mgr.create_agent(_config(tmp_path / "a"), agent_id="agent-a", metadata={"user_id": 1})
        mgr.create_agent(_config(tmp_path / "b"), agent_id="agent-b", metadata={"user_id": 1})

    filtered = mgr.team.filter_peer_ids(1, "agent-a", ["agent-a", "agent-b", "agent-x"])
    assert filtered == ["agent-b"]
