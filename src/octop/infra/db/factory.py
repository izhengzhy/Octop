"""Open a database pool from process configuration."""

from __future__ import annotations

from octop.config import OctopConfig, database_env_configured
from octop.infra.db.pool import DBPool
from octop.infra.utils.paths import PathLayout


def open_database(config: OctopConfig, paths: PathLayout) -> DBPool:
    """Return a DB pool for the configured driver.

    When ``config.json`` has no ``database`` section and no ``OCTOP_DATABASE_*``
    env overrides are set, falls back to ``paths.db`` (legacy layout).
    """
    db_cfg = config.database
    if db_cfg.is_postgresql:
        msg = (
            "PostgreSQL is not implemented yet; set database.driver to sqlite "
            "or unset OCTOP_DATABASE_URL / OCTOP_DATABASE_DRIVER."
        )
        raise NotImplementedError(msg)

    if config.database_in_file or database_env_configured():
        db_path = db_cfg.resolve_sqlite_path(paths.root)
    else:
        db_path = paths.db
    return DBPool(db_path)
