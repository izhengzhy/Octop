"""Dashboard chat routers — WebSocket turns, thread CRUD, polish, HITL."""

from __future__ import annotations

from fastapi import APIRouter

from octop.api.routers.chat.history import router as history_router
from octop.api.routers.chat.routes import router as routes_router
from octop.api.routers.chat.ws import router as ws_router

router = APIRouter()
router.include_router(routes_router)
router.include_router(history_router)
router.include_router(ws_router)

__all__ = ["router"]
