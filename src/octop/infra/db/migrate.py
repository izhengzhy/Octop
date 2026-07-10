"""Apply numbered SQL migrations.

Each file is ``NNN_description.sql``; version is stored in ``_schema_version``.
Greenfield installs run ``001_initial.sql`` only. For PostgreSQL, ship a
parallel ``001_initial.pg.sql`` (or translate at deploy time) — repos already
use portable SQL patterns (``?`` placeholders, ``RETURNING id``, ``ON CONFLICT``).
"""

from __future__ import annotations

import re
from pathlib import Path

from octop.infra.db.pool import DBPool

_MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILE_RE = re.compile(r"^(\d{3})_.*\.sql$")


def _discover() -> list[tuple[int, Path]]:
    out: list[tuple[int, Path]] = []
    if not _MIGRATIONS_DIR.exists():
        return out
    for entry in sorted(_MIGRATIONS_DIR.iterdir()):
        m = _FILE_RE.match(entry.name)
        if m:
            out.append((int(m.group(1)), entry))
    return out


def _current_version(db: DBPool) -> int:
    with db.connect() as conn:
        try:
            return int(conn.execute("SELECT version FROM _schema_version").fetchone()[0])
        except Exception:
            return 0


def _table_columns(db: DBPool, table: str) -> set[str]:
    with db.connect() as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row["name"]) for row in rows}


def _table_exists(db: DBPool, table: str) -> bool:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        ).fetchone()
    return row is not None


def _ensure_column(db: DBPool, table: str, column: str, definition: str) -> None:
    """Add a missing column on databases created by older Octop builds."""
    if column in _table_columns(db, table):
        return
    with db.connect() as conn:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _repair_legacy_schema(db: DBPool) -> None:
    """Idempotent compatibility repairs for local databases from old builds."""
    if _table_exists(db, "users"):
        _ensure_column(db, "users", "locale", "TEXT NOT NULL DEFAULT 'zh'")
        _ensure_column(db, "users", "login_failed_count", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(db, "users", "login_locked_until", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(db, "users", "preferences_json", "TEXT NOT NULL DEFAULT '{}'")
    if _table_exists(db, "cron_jobs"):
        _ensure_column(
            db,
            "cron_jobs",
            "task_type",
            "TEXT NOT NULL DEFAULT 'agent' CHECK (task_type IN ('text', 'agent'))",
        )


def run_migrations(db: DBPool) -> None:
    _repair_legacy_schema(db)
    for version, path in _discover():
        if version <= _current_version(db):
            continue
        sql = path.read_text(encoding="utf-8")
        with db.connect() as conn:
            conn.executescript(sql)
