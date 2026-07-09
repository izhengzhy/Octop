"""Unit tests for provider connectivity probe helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from octop.infra.agents.providers.probe import build_probe_chat_model as _build_chat_model


def test_build_chat_model_includes_provider_id_and_model_name() -> None:
    row = SimpleNamespace(
        name="HAI",
        kind="openai",
        base_url="https://api.example.com/v1",
        api_key="sk-test",
        get_models=lambda: [{"id": "MiniMax-M2.7", "name": "MiniMax-M2.7"}],
    )

    with patch("harness_agent.llm.factory.build_chat_model") as mock_build:
        mock_build.return_value = object()
        _build_chat_model(row, model_id="MiniMax-M2.7")

    provider, model = mock_build.call_args[0]
    assert provider.id == "HAI"
    assert provider.name == "HAI"
    assert model.id == "MiniMax-M2.7"
    assert model.name == "MiniMax-M2.7"
