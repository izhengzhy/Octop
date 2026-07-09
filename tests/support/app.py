"""OctopServer + ASGI client lifecycle for integration tests."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext
from pathlib import Path
from typing import Any

import httpx

from octop.api.app import build_app
from octop.config import load_config
from octop.infra.server import OctopServer
from tests.support.harness import patch_harness


def write_octop_config(home: Path, **overrides: object) -> None:
    """Ensure ``home/config.json`` exists and apply overrides (for tests)."""
    cfg_path = home / "config.json"
    load_config(cfg_path)
    data = json.loads(cfg_path.read_text(encoding="utf-8"))
    data.update(overrides)
    cfg_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


@asynccontextmanager
async def octop_client(
    home: Path,
    *,
    fake_agent: Any | None = None,
    patch_llm: bool = True,
) -> AsyncIterator[tuple[httpx.AsyncClient, OctopServer]]:
    """Start OctopServer, yield ``(httpx client, server)``, then stop."""
    ctx = patch_harness(fake_agent) if patch_llm else nullcontext(fake_agent)
    with ctx:
        srv = OctopServer(home=home)
        await srv.start()
        app = build_app(srv)
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                yield client, srv
        finally:
            await srv.stop()
