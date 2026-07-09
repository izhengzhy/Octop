"""Unit tests for Codex OAuth helpers."""

from __future__ import annotations

from octop.infra.providers.codex_apply import CODEX_MODELS, CODEX_PROVIDER_NAME
from octop.infra.providers.codex_oauth import build_codex_headers, prepare_pkce_authorize


def test_prepare_pkce_authorize_contains_required_params() -> None:
    url, state, verifier = prepare_pkce_authorize(
        redirect_uri="http://localhost/api/providers/codex-oauth/callback"
    )
    assert state
    assert verifier
    assert "auth.openai.com/oauth/authorize" in url
    assert "code_challenge=" in url
    assert f"state={state}" in url


def test_build_codex_headers_includes_account_id() -> None:
    headers = build_codex_headers("acct-123")
    assert headers["originator"] == "openclaw"
    assert headers["chatgpt-account-id"] == "acct-123"
    assert "User-Agent" in headers


def test_codex_provider_constants() -> None:
    assert CODEX_PROVIDER_NAME == "openai-codex"
    assert any(m["id"] == "gpt-5.4" for m in CODEX_MODELS)
