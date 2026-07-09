"""Integration tests for admin provider test-draft endpoint."""

from __future__ import annotations

from typing import Any


async def test_admin_test_draft_requires_api_key(env: Any) -> None:
    client, _srv, auth = env
    r = await client.post(
        "/api/admin/providers/test-draft",
        headers=auth,
        json={
            "name": "draft",
            "kind": "openai",
            "api_key": "",
            "base_url": "https://api.example.com/v1",
            "model_id": "gpt-4o-mini",
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False


async def test_admin_test_draft_requires_model_id(env: Any) -> None:
    client, _srv, auth = env
    r = await client.post(
        "/api/admin/providers/test-draft",
        headers=auth,
        json={
            "name": "draft",
            "kind": "openai",
            "api_key": "sk-test",
            "base_url": "https://api.example.com/v1",
            "model_id": "",
        },
    )
    assert r.status_code == 200
    assert r.json()["ok"] is False


async def test_admin_codex_oauth_start(env: Any) -> None:
    client, _srv, auth = env
    r = await client.post(
        "/api/admin/providers/codex-oauth/start",
        headers=auth,
        json={"redirect_after": "/admin/models"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "authorize_url" in body
    assert "state_id" in body
    assert "auth.openai.com" in body["authorize_url"]
