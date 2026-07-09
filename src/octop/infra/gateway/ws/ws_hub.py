"""In-process registry of Dashboard WebSocket connections."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

SendFn = Callable[[dict[str, Any]], Awaitable[None]]


class WebSocketHub:
    """Maps connection ids to async send callbacks for Dashboard chat."""

    def __init__(self) -> None:
        self._connections: dict[str, SendFn] = {}
        self._lock = asyncio.Lock()

    def register(self, connection_id: str, send_fn: SendFn) -> None:
        self._connections[connection_id] = send_fn

    def unregister(self, connection_id: str) -> None:
        self._connections.pop(connection_id, None)

    async def push(self, connection_id: str, frame: dict[str, Any]) -> None:
        send_fn = self._connections.get(connection_id)
        if send_fn is None:
            logger.debug("ws hub: connection %s not found", connection_id)
            return
        try:
            await send_fn(frame)
        except Exception:
            logger.exception("ws hub: push failed for %s", connection_id)

    async def push_json(self, connection_id: str, payload: str) -> None:
        try:
            frame = json.loads(payload)
        except (TypeError, ValueError):
            logger.warning("ws hub: invalid json for %s", connection_id)
            return
        if isinstance(frame, dict):
            await self.push(connection_id, frame)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


__all__ = ["SendFn", "WebSocketHub"]
