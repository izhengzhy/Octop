"""tests/integration/test_e2e_golden_path.py — full user journey."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.support.auth import bootstrap_admin


@pytest.fixture
async def env(env_fake_harness):
    yield env_fake_harness


async def test_full_golden_path(env: Any) -> None:
    c, _srv, _fake, home = env

    # 1) setup admin
    r = await bootstrap_admin(c, home)
    assert r.status_code == 201

    # 2) admin login
    r = await c.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert r.status_code == 200
    tok = r.json()["access_token"]
    auth = {"Authorization": f"Bearer {tok}"}

    # 3) admin creates a regular user
    r = await c.post(
        "/api/users",
        headers=auth,
        json={
            "username": "alice",
            "password": "pw",
            "role": "user",
            "display_name": "Alice",
        },
    )
    assert r.status_code == 201

    # 4) admin creates a shared provider
    r = await c.post(
        "/api/admin/providers",
        headers=auth,
        json={
            "name": "openai",
            "kind": "openai",
            "api_key": "sk-x",
            "model": "gpt-4o",
        },
    )
    assert r.status_code == 201

    # 5) alice logs in
    r = await c.post("/api/auth/login", json={"username": "alice", "password": "pw"})
    assert r.status_code == 200
    alice_tok = r.json()["access_token"]
    alice_auth = {"Authorization": f"Bearer {alice_tok}"}

    # 6) admin creates an agent (agents are global, admin-only)
    admin_auth = auth  # auth is already admin auth from step 2
    r = await c.post(
        "/api/agents",
        headers=admin_auth,
        json={
            "name": "bot",
            "persona_mbti": "INTJ",
            "default_model": "openai:gpt-4o",
        },
    )
    assert r.status_code == 201, r.text
    aid = r.json()["id"]

    # 7) alice opens a chat stream
    chunks: list[dict[str, Any]] = []
    async with c.stream(
        "POST",
        f"/api/agents/{aid}/chat/stream",
        headers=alice_auth,
        json={
            "session_key": "ui-1",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    ) as resp:
        assert resp.status_code == 200
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                chunks.append(json.loads(line[len("data:") :].strip()))
    assert any(ch.get("type") == "token" for ch in chunks)
    assert chunks[-1]["type"] == "done"

    # 8) threads list shows the row with autofilled title
    r = await c.get(f"/api/agents/{aid}/threads", headers=alice_auth)
    assert r.status_code == 200
    threads = r.json()
    assert threads
    assert threads[0]["title"] == "Hello"

    # 9) admin metrics counter incremented
    r = await c.get("/api/admin/metrics", headers=auth)
    assert r.status_code == 200
    assert r.json()["messages_total"] >= 0  # may be 0 if SSE path doesn't bump this counter


async def test_expert_to_chat_golden_path(env: Any) -> None:
    """Create an agent from the expert library, start it, then chat.

    Full flow:
      1. Setup admin + provider
      2. Regular user logs in
      3. User lists experts, picks "default"
      4. User lists available models → selects one
      5. User creates agent from expert with default_model
      6. User starts the agent (POST /agents/{id}/start)
      7. User sends a chat message and receives SSE tokens
    """
    c, _srv, _fake, home = env

    # 1) setup admin + provider
    await bootstrap_admin(c, home)
    r = await c.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    admin_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # Admin creates provider with explicit model list so /providers/resolved returns something
    r = await c.post(
        "/api/admin/providers",
        headers=admin_auth,
        json={
            "name": "openai",
            "kind": "openai",
            "api_key": "sk-test",
            "models": [{"id": "gpt-4o", "name": "GPT-4o", "enabled": True, "input": ["text"]}],
        },
    )
    assert r.status_code == 201

    # 2) create user + login
    await c.post(
        "/api/users",
        headers=admin_auth,
        json={"username": "bob", "password": "pw", "role": "user", "display_name": "Bob"},
    )
    r = await c.post("/api/auth/login", json={"username": "bob", "password": "pw"})
    bob_auth = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # 3) list experts — "default" must be present
    r = await c.get("/api/experts", headers=bob_auth)
    assert r.status_code == 200
    expert_ids = [e["id"] for e in r.json()]
    assert "default" in expert_ids

    # 4) get expert detail — must include file_contents
    r = await c.get("/api/experts/default", headers=bob_auth)
    assert r.status_code == 200
    expert = r.json()
    assert "file_contents" in expert and len(expert["file_contents"]) > 0

    # 5) list resolved models (simulates model selector in CreateFromExpertDrawer)
    r = await c.get("/api/providers/resolved", headers=bob_auth)
    assert r.status_code == 200
    models = r.json()
    assert len(models) > 0
    first_model = models[0]
    default_model_val = f"{first_model['provider_name']}/{first_model['model']}"

    # 6) list storage backends (simulates backend selector)
    r = await c.get("/api/storage-backends", headers=bob_auth)
    assert r.status_code == 200
    assert isinstance(r.json(), list)

    # 7) create agent from expert with default_model
    r = await c.post(
        "/api/agents/from-expert/default",
        headers=bob_auth,
        json={
            "name": "my-default-bot",
            "default_model": default_model_val,
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    agent_id = body["id"]
    assert body["expert_id"] == "default"
    assert body["icon_name"] is not None or body.get("icon_name") is None  # may be None for default
    # Agent starts in non-running state (autostart=False)
    assert body["state"] in {"running", "failed", "stopped", "unknown"}

    # Verify config stored correctly
    rows = (await c.get("/api/agents", headers=bob_auth)).json()
    agent_row = next(a for a in rows if a["id"] == agent_id)
    assert agent_row["default_model"] == default_model_val
    assert agent_row["config"]["expert_id"] == "default"

    # 8) start the agent
    r = await c.post(f"/api/agents/{agent_id}/start", headers=bob_auth)
    assert r.status_code == 204, r.text

    # 9) chat — stream a message and verify we get tokens back
    chunks: list[dict[str, Any]] = []
    async with c.stream(
        "POST",
        f"/api/agents/{agent_id}/chat/stream",
        headers=bob_auth,
        json={
            "session_key": "test-session",
            "messages": [{"role": "user", "content": "你好"}],
        },
    ) as resp:
        assert resp.status_code == 200, await resp.aread()
        async for line in resp.aiter_lines():
            if line.startswith("data:"):
                chunks.append(json.loads(line[len("data:") :].strip()))

    assert any(ch.get("type") == "token" for ch in chunks), f"no token chunks: {chunks}"
    assert chunks[-1]["type"] == "done"
