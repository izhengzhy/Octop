"""WebSocket / streaming helpers for integration tests."""

from __future__ import annotations

import json

import httpx


def ws_token(auth: dict[str, str]) -> str:
    return auth["Authorization"].split(" ", 1)[1]


async def ws_chat_turn(
    client: httpx.AsyncClient,
    agent_id: str,
    auth: dict[str, str],
    *,
    mcp_servers: list[str] | None = None,
    text: str = "hi",
) -> list[dict[str, object]]:
    body: dict[str, object] = {
        "type": "user_turn",
        "text": text,
        "messages": [{"role": "user", "content": text}],
    }
    if mcp_servers is not None:
        body["mcp_servers"] = mcp_servers
    chunks: list[dict[str, object]] = []
    async with client.websocket_connect(
        f"/api/agents/{agent_id}/chat/ws?token={ws_token(auth)}",
    ) as ws:
        await ws.send_json(body)
        while True:
            raw = await ws.receive_text()
            chunk = json.loads(raw)
            chunks.append(chunk)
            if chunk.get("type") in ("done", "error"):
                break
    return chunks
