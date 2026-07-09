"""Unit tests for JWT auth middleware."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from tests.support.app import write_octop_config
from tests.support.auth import bootstrap_admin

from octop.api.app import build_app
from octop.api.deps import is_jwt_exempt_path
from octop.infra.server import OctopServer


def test_exempt_paths() -> None:
    assert is_jwt_exempt_path("/api/health")
    assert is_jwt_exempt_path("/api/health/")
    assert is_jwt_exempt_path("/api/setup/status")
    assert is_jwt_exempt_path("/api/auth/login")
    assert is_jwt_exempt_path("/api/docs")
    assert is_jwt_exempt_path("/api/openapi.json")
    assert not is_jwt_exempt_path("/api/auth/me")
    assert not is_jwt_exempt_path("/api/agents")


@pytest.fixture
async def client(tmp_path: Path):
    srv = OctopServer(home=tmp_path)
    await srv.start()
    app = build_app(srv)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as c:
        yield c, srv, tmp_path
    await srv.stop()


async def test_middleware_blocks_unauthenticated_api(client) -> None:
    c, _srv, home = client
    await bootstrap_admin(c, home)
    r = await c.get("/api/agents")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "AUTH_FAILED"


async def test_middleware_allows_login_without_token(client) -> None:
    c, _srv, home = client
    await bootstrap_admin(c, home)
    r = await c.post("/api/auth/login", json={"username": "admin", "password": "pw"})
    assert r.status_code == 200


async def test_middleware_allows_api_docs_without_token(tmp_path: Path) -> None:
    write_octop_config(tmp_path, enable_api_docs=True)
    srv = OctopServer(home=tmp_path)
    await srv.start()
    app = build_app(srv)
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://testserver"
        ) as c:
            await bootstrap_admin(c, tmp_path)
            r = await c.get("/api/docs")
            assert r.status_code == 200
            spec = await c.get("/api/openapi.json")
            assert spec.status_code == 200
    finally:
        await srv.stop()
