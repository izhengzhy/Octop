"""WebSocket / streaming helpers for integration tests."""

from __future__ import annotations

import asyncio
import json

import httpx
from starlette.testclient import TestClient


def ws_token(auth: dict[str, str]) -> str:
    return auth["Authorization"].split(" ", 1)[1]


def _consume_ws_chunks(
    app: object, agent_id: str, token: str, body: dict[str, object]
) -> list[dict[str, object]]:
    """Run the (blocking) starlette ``TestClient`` ws session in a worker thread.

    starlette's sync ``TestClient.websocket_connect`` blocks the calling event
    loop for the whole ``with`` block. The gateway workers that process the
    turn run on that same loop, so blocking it would deadlock. Running the
    session in a worker thread keeps the server loop free to stream chunks
    back to the socket.
    """
    chunks: list[dict[str, object]] = []
    with TestClient(app).websocket_connect(  # type: ignore[attr-defined]
        f"/api/agents/{agent_id}/chat/ws?token={token}",
    ) as ws:
        ws.send_json(body)
        while True:
            raw = ws.receive_text()
            chunk = json.loads(raw)
            chunks.append(chunk)
            if chunk.get("type") in ("done", "error"):
                break
    return chunks


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
    # httpx dropped AsyncClient.websocket_connect; use starlette's sync TestClient
    # in a worker thread (see _consume_ws_chunks).
    return await asyncio.to_thread(
        _consume_ws_chunks,
        client._octop_app,  # type: ignore[attr-defined]
        agent_id,
        ws_token(auth),
        body,
    )
