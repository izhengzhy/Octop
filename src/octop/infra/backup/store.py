"""On-disk backup archive store under ``PathLayout.backups_dir``."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.paths import PathLayout

_BACKUP_SUFFIXES = (".tar.gz", ".tgz")


@dataclass(frozen=True)
class BackupFileInfo:
    name: str
    size: int
    modified_at: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "name": self.name,
            "size": self.size,
            "modified_at": self.modified_at,
        }


def normalize_backup_filename(name: str) -> str:
    """Return a safe basename for a backup archive under ``backups_dir``."""
    base = Path(name).name.strip()
    if not base or base != name.strip() or "/" in base or "\\" in base:
        raise OctopError(ErrorCode.SLASH_BAD_ARGS, f"invalid backup filename: {name!r}")
    if not any(base.endswith(suffix) for suffix in _BACKUP_SUFFIXES):
        raise OctopError(ErrorCode.SLASH_BAD_ARGS, "backup file must end with .tar.gz or .tgz")
    return base


def list_backup_files(paths: PathLayout) -> list[BackupFileInfo]:
    root = paths.backups_dir
    if not root.is_dir():
        return []
    out: list[BackupFileInfo] = []
    for path in sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not path.is_file():
            continue
        if not any(path.name.endswith(suffix) for suffix in _BACKUP_SUFFIXES):
            continue
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat()
        out.append(BackupFileInfo(name=path.name, size=stat.st_size, modified_at=modified))
    return out


def write_backup_file(paths: PathLayout, filename: str, data: bytes) -> BackupFileInfo:
    paths.ensure_backups_dir()
    safe = normalize_backup_filename(filename)
    dest = paths.backup_file(safe)
    dest.write_bytes(data)
    stat = dest.stat()
    return BackupFileInfo(
        name=safe,
        size=stat.st_size,
        modified_at=datetime.fromtimestamp(stat.st_mtime, tz=UTC).isoformat(),
    )


def read_backup_file(paths: PathLayout, filename: str) -> bytes:
    safe = normalize_backup_filename(filename)
    path = paths.backup_file(safe)
    if not path.is_file():
        raise OctopError(ErrorCode.NOT_FOUND, f"backup not found: {safe}")
    return path.read_bytes()


def delete_backup_file(paths: PathLayout, filename: str) -> None:
    safe = normalize_backup_filename(filename)
    path = paths.backup_file(safe)
    if not path.is_file():
        raise OctopError(ErrorCode.NOT_FOUND, f"backup not found: {safe}")
    path.unlink()
