"""tests/integration/test_chat_sse.py — dashboard WebSocket chat + thread CRUD."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest

from tests.support.app import octop_client
from tests.support.auth import (
    auth_header,
    bootstrap_admin,
    create_agent,
    ensure_users,
    seed_openai_provider,
)
from tests.support.fakes import FakeHarnessAgent
from tests.support.http import ws_token


@pytest.fixture
async def env(tmp_octop_home: Path) -> AsyncIterator[Any]:
    fake = FakeHarnessAgent(
        chunks=[
            {"type": "token", "node": "agent", "content": "Hello "},
            {"type": "token", "node": "agent", "content": "Bob."},
        ]
    )
    async with octop_client(tmp_octop_home, fake_agent=fake) as (c, srv):
        await bootstrap_admin(c, tmp_octop_home)
        admin_auth = await auth_header(c)
        await seed_openai_provider(c, admin_auth)
        users = await ensure_users(c, admin_auth, "alice", "bob")
        aid = await create_agent(c, admin_auth)
        yield c, srv, fake, users["alice"], users["bob"], aid


async def _consume_ws_turn(
    c: httpx.AsyncClient,
    aid: str,
    auth: dict[str, str],
    *,
    text: str = "Hello",
    thread_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    body: dict[str, Any] = {
        "type": "user_turn",
        "text": text,
        "messages": [{"role": "user", "content": text}],
    }
    if thread_id:
        body["thread_id"] = thread_id
    if extra:
        body.update(extra)

    chunks: list[dict[str, Any]] = []
    async with c.websocket_connect(f"/api/agents/{aid}/chat/ws?token={ws_token(auth)}") as ws:
        await ws.send_json(body)
        while True:
            raw = await ws.receive_text()
            chunk = json.loads(raw)
            chunks.append(chunk)
            if chunk.get("type") in ("done", "error"):
                break
    return chunks


async def test_ws_emits_chunks_then_done(env: Any) -> None:
    c, _srv, _fake, alice_auth, _bob_auth, aid = env
    chunks = await _consume_ws_turn(c, aid, alice_auth)
    await asyncio.sleep(0.05)
    types = [ch.get("type") for ch in chunks]
    assert "token" in types
    assert chunks[-1]["type"] == "done"


async def test_ws_emits_error_frame_on_exception(env: Any) -> None:
    c, srv, _fake, alice_auth, _bob_auth, aid = env
    boom = FakeHarnessAgent(raise_on_stream=RuntimeError("upstream blew up"))
    entry = srv.app_runtime.agent_registry._entries.get(aid)  # noqa: SLF001
    if entry is not None:
        entry.agent = boom

    chunks = await _consume_ws_turn(c, aid, alice_auth, text="err")
    assert chunks[-1]["type"] == "error"


async def test_ws_bad_agent_rejected(env: Any) -> None:
    c, _srv, _fake, alice_auth, _bob_auth, _aid = env
    with pytest.raises(httpx.HTTPError):
        async with c.websocket_connect(
            f"/api/agents/01HMISSING0000000000000000/chat/ws?token={ws_token(alice_auth)}"
        ):
            pass


async def test_ws_cross_user_rejected(env: Any) -> None:
    c, _srv, _fake, _admin_auth, bob_auth, aid = env
    with pytest.raises(httpx.HTTPError):
        async with c.websocket_connect(f"/api/agents/{aid}/chat/ws?token={ws_token(bob_auth)}"):
            pass


async def test_ws_accepts_skills_and_model(env: Any) -> None:
    c, _srv, _fake, auth, _bob_auth, aid = env
    chunks = await _consume_ws_turn(
        c,
        aid,
        auth,
        extra={"skills": [], "model": "openai/gpt-4o"},
    )
    assert chunks[-1]["type"] == "done"


async def test_polish_rejects_empty_text(env: Any) -> None:
    c, _srv, _fake, alice_auth, _bob_auth, aid = env
    r = await c.post(
        f"/api/agents/{aid}/chat/polish",
        headers=alice_auth,
        json={"text": "   "},
    )
    assert r.status_code == 400


async def test_threads_list_after_stream(env: Any) -> None:
    c, _srv, _fake, alice_auth, _bob_auth, aid = env
    await _consume_ws_turn(c, aid, alice_auth, text="What's up?")
    await asyncio.sleep(0.05)

    r = await c.get(f"/api/agents/{aid}/threads", headers=alice_auth)
    assert r.status_code == 200
    threads = r.json()
    assert len(threads) >= 1
    assert any(t.get("has_messages") for t in threads)


async def test_thread_history_after_stream(env: Any) -> None:
    c, _srv, _fake, alice_auth, _bob_auth, aid = env
    await _consume_ws_turn(c, aid, alice_auth, text="History test")
    await asyncio.sleep(0.05)

    r = await c.get(f"/api/agents/{aid}/threads", headers=alice_auth)
    tid = r.json()[0]["thread_id"]
    hist = await c.get(f"/api/agents/{aid}/threads/{tid}/history", headers=alice_auth)
    assert hist.status_code == 200
    assert "messages" in hist.json()


async def test_create_thread(env: Any) -> None:
    c, _srv, _fake, alice_auth, _bob_auth, aid = env
    r = await c.post(f"/api/agents/{aid}/threads", headers=alice_auth)
    assert r.status_code == 201
    body = r.json()
    assert "thread_id" in body
    assert "session_key" in body
