"""Unit tests for system backup archives."""

from __future__ import annotations

import json
import tarfile
from io import BytesIO
from pathlib import Path

import pytest

from octop.infra.backup.manifest import MANIFEST_VERSION
from octop.infra.backup.system_archive import create_system_backup, restore_system_backup
from octop.infra.db.migrate import run_migrations
from octop.infra.db.pool import DBPool
from octop.infra.utils.paths import PathLayout


@pytest.fixture
def layout(tmp_path: Path) -> PathLayout:
    root = tmp_path / ".octop"
    root.mkdir()
    return PathLayout(root)


def test_roundtrip_backup(layout: PathLayout) -> None:
    db_path = layout.db
    pool = DBPool(db_path)
    run_migrations(pool)
    with pool.connect() as conn:
        conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            ("alice", "hash", "admin", 1),
        )
    pool.close()

    ws = layout.ensure_agent_workspace("agent01")
    (ws / "SOUL.md").write_text("# soul", encoding="utf-8")
    layout.config.write_text('{"port": 8088}', encoding="utf-8")

    class Row:
        agent_id = "agent01"
        name = "Test"

    data, _name = create_system_backup(paths=layout, db_path=db_path, agent_rows=[Row()])

    restore_root = layout.root.parent / "restored"
    restore_layout = PathLayout(restore_root)
    restore_db = restore_layout.db
    restore_pool = DBPool(restore_db)
    run_migrations(restore_pool)

    result = restore_system_backup(
        data,
        paths=restore_layout,
        db_path=restore_db,
        pool=restore_pool,
        restore_config=True,
    )
    restore_pool.close()

    assert result["agents"] == 1
    assert (restore_layout.agent_workspace("agent01") / "SOUL.md").read_text(
        encoding="utf-8"
    ) == "# soul"
    assert json.loads(restore_layout.config.read_text(encoding="utf-8"))["port"] == 8088

    with tarfile.open(fileobj=BytesIO(data), mode="r:gz") as tf:
        manifest = json.loads(tf.extractfile("manifest.json").read().decode("utf-8"))
    assert manifest["manifest_version"] == MANIFEST_VERSION
