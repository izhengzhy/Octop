"""tests/integration/test_server_lifecycle.py"""

from __future__ import annotations

from pathlib import Path

import pytest

from octop.infra.server import OctopServer


@pytest.fixture
async def server(tmp_octop_home: Path):
    srv = OctopServer(home=tmp_octop_home)
    await srv.start()
    yield srv
    await srv.stop()


async def test_start_creates_root_and_db(server: OctopServer, tmp_octop_home: Path):
    assert tmp_octop_home.is_dir()
    assert (tmp_octop_home / "octop.db").exists()
    assert (tmp_octop_home / "config.json").exists()


async def test_jwt_secret_seeded(server: OctopServer):
    secret = server.services.secret_repo.get("jwt")
    assert secret is not None
    assert len(secret) >= 32


async def test_user_manager_loaded(server: OctopServer):
    assert server.user_manager.count() == 0


async def test_boot_then_stop_idempotent(tmp_octop_home: Path):
    srv = OctopServer(home=tmp_octop_home)
    await srv.start()
    await srv.stop()
    await srv.stop()  # idempotent
