"""Full-system backup and restore (database + local agent workspaces + config)."""

from __future__ import annotations

import io
import json
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from octop import __version__
from octop.infra.backup.manifest import MANIFEST_VERSION, AgentBackupEntry, BackupManifest
from octop.infra.backup.snapshot import (
    restore_sqlite_file,
    restore_sqlite_into_pool,
    snapshot_sqlite_file,
)
from octop.infra.db.migrate import _current_version
from octop.infra.db.pool import DBPool
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.env_file import env_file_path
from octop.infra.utils.paths import PathLayout

_CONFIG_DIR = "config"
_DB_DIR = "db"
_WORKSPACES_DIR = "workspaces"
_MANIFEST_NAME = "manifest.json"


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _add_dir(tf: tarfile.TarFile, src: Path, arc_root: str) -> None:
    if not src.is_dir():
        return
    for path in sorted(src.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src).as_posix()
        tf.add(path, arcname=f"{arc_root}/{rel}")


def create_system_backup(
    *,
    paths: PathLayout,
    db_path: Path,
    agent_rows: list[Any],
) -> tuple[bytes, str]:
    """Build a ``.tar.gz`` archive and return ``(bytes, suggested_filename)``."""
    if not db_path.is_file():
        raise OctopError(ErrorCode.NOT_FOUND, f"database not found: {db_path}")

    schema_version = 0
    try:
        pool = DBPool(db_path)
        try:
            schema_version = _current_version(pool)
        finally:
            pool.close()
    except Exception:
        schema_version = 0

    agents = [
        AgentBackupEntry(
            agent_id=str(row.agent_id),
            name=str(row.name),
            workspace_included=True,
        )
        for row in agent_rows
    ]
    env_path = env_file_path(paths.root)
    manifest = BackupManifest(
        manifest_version=MANIFEST_VERSION,
        octop_version=__version__,
        schema_version=schema_version,
        created_at=datetime.now(UTC).isoformat(),
        home=str(paths.root),
        agents=agents,
        includes_config=paths.config.is_file(),
        includes_env=env_path.is_file(),
    )

    buf = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        db_dest = root / _DB_DIR / "octop.db"
        snapshot_sqlite_file(db_path, db_dest)

        manifest_path = root / _MANIFEST_NAME
        manifest_path.write_text(manifest.to_json(), encoding="utf-8")

        if paths.config.is_file():
            cfg_dir = root / _CONFIG_DIR
            cfg_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(paths.config, cfg_dir / "config.json")
        if env_path.is_file():
            cfg_dir = root / _CONFIG_DIR
            cfg_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(env_path, cfg_dir / "env")

        with tarfile.open(fileobj=buf, mode="w:gz") as tf:
            tf.add(manifest_path, arcname=_MANIFEST_NAME)
            tf.add(db_dest, arcname=f"{_DB_DIR}/octop.db")
            if paths.config.is_file():
                tf.add(root / _CONFIG_DIR / "config.json", arcname=f"{_CONFIG_DIR}/config.json")
            if env_path.is_file():
                tf.add(root / _CONFIG_DIR / "env", arcname=f"{_CONFIG_DIR}/env")
            for row in agent_rows:
                ws = paths.agent_workspace(str(row.agent_id))
                if ws.is_dir():
                    _add_dir(tf, ws, f"{_WORKSPACES_DIR}/{row.agent_id}")

    filename = f"octop-backup-{_timestamp()}.tar.gz"
    return buf.getvalue(), filename


def _extract_manifest(members: dict[str, bytes]) -> BackupManifest:
    raw = members.get(_MANIFEST_NAME)
    if raw is None:
        raise OctopError(ErrorCode.SLASH_BAD_ARGS, "backup archive missing manifest.json")
    try:
        manifest = BackupManifest.load_text(raw.decode("utf-8"))
    except (json.JSONDecodeError, ValueError, TypeError) as exc:
        raise OctopError(ErrorCode.SLASH_BAD_ARGS, f"invalid manifest: {exc}") from exc
    if manifest.manifest_version != MANIFEST_VERSION:
        raise OctopError(
            ErrorCode.SLASH_BAD_ARGS,
            f"unsupported manifest version {manifest.manifest_version}",
        )
    return manifest


def _read_tar_members(data: bytes) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:*") as tf:
        for member in tf.getmembers():
            if not member.isfile():
                continue
            extracted = tf.extractfile(member)
            if extracted is None:
                continue
            out[member.name.replace("\\", "/")] = extracted.read()
    return out


def restore_system_backup(
    data: bytes,
    *,
    paths: PathLayout,
    db_path: Path,
    pool: DBPool | None = None,
    restore_config: bool = True,
) -> dict[str, Any]:
    """Restore database, workspaces, and optional config from a tar.gz archive."""
    members = _read_tar_members(data)
    manifest = _extract_manifest(members)

    db_blob = members.get(manifest.db_file)
    if db_blob is None:
        raise OctopError(ErrorCode.SLASH_BAD_ARGS, "backup archive missing database file")

    with tempfile.TemporaryDirectory() as tmp:
        backup_db = Path(tmp) / "octop.db"
        backup_db.write_bytes(db_blob)
        if pool is not None:
            restore_sqlite_into_pool(backup_db, pool)
        else:
            restore_sqlite_file(backup_db, db_path)

        if restore_config:
            cfg_blob = members.get(f"{_CONFIG_DIR}/config.json")
            if cfg_blob is not None:
                paths.config.parent.mkdir(parents=True, exist_ok=True)
                paths.config.write_bytes(cfg_blob)
            env_blob = members.get(f"{_CONFIG_DIR}/env")
            if env_blob is not None:
                env_path = env_file_path(paths.root)
                env_path.parent.mkdir(parents=True, exist_ok=True)
                env_path.write_bytes(env_blob)

        restored_workspaces = 0
        prefix = f"{_WORKSPACES_DIR}/"
        for name, blob in members.items():
            if not name.startswith(prefix):
                continue
            rel = name[len(prefix) :]
            if "/" not in rel:
                continue
            agent_id, _, file_rel = rel.partition("/")
            if not agent_id or not file_rel:
                continue
            dest = paths.agent_workspace(agent_id) / file_rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(blob)
            restored_workspaces += 1

    return {
        "schema_version": manifest.schema_version,
        "octop_version": manifest.octop_version,
        "agents": len(manifest.agents),
        "workspace_files": restored_workspaces,
        "restore_config": restore_config,
    }
