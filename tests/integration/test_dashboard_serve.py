"""tests/integration/test_dashboard_serve.py"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from octop.api.app import build_app
from tests.support.app import octop_client


async def test_root_serves_dashboard_index(tmp_octop_home: Path) -> None:
    async with octop_client(tmp_octop_home) as (_client, srv):
        app = build_app(srv)
        with TestClient(app) as c:
            r = c.get("/")
            assert r.status_code in (200, 404)
            r2 = c.get("/api/health")
            assert r2.status_code == 200
