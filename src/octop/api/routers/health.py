"""Liveness probe (no auth)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from octop.api.deps import get_server

router = APIRouter()


@router.get("", summary="Health check")
async def health(server: Any = Depends(get_server)) -> dict[str, Any]:
    """Liveness probe: database reachability, user count, and loaded agents. No auth required."""
    assert server.app_runtime is not None
    return {
        "ok": True,
        "started_at": server._started_at,
        "db": True,
        "users_loaded": server.user_manager.count(),
        "agents_running": len(server.app_runtime.agent_registry.list_rows()),
    }
