"""Zip export/import for a single agent workspace."""

from __future__ import annotations

import io
import shutil
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from harness_agent.backends.workspace import BackendWorkspace

WorkspaceImportMode = Literal["merge", "replace"]

_SKIP_DIR_NAMES = frozenset({".git", "__pycache__", ".venv", "node_modules"})


def _safe_zip_name(name: str) -> str | None:
    raw = name.replace("\\", "/").strip().lstrip("/")
    if not raw or raw.endswith("/"):
        return None
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if any(part == ".." for part in parts):
        return None
    return "/".join(parts)


async def _list_file_paths(workspace: BackendWorkspace) -> list[str]:
    result = await workspace.aglob("**/*", ".")
    if result is None:
        return []
    matches = getattr(result, "matches", None) or []
    paths: list[str] = []
    for item in matches:
        if isinstance(item, dict):
            path = item.get("path")
            is_dir = item.get("is_dir")
        else:
            path = getattr(item, "path", None)
            is_dir = getattr(item, "is_dir", False)
        if not path or is_dir:
            continue
        storage = str(path)
        ws_root = str(workspace.workspace_dir)
        if storage.startswith(ws_root):
            rel = storage[len(ws_root) :].lstrip("/\\")
            if rel:
                paths.append(rel)
                continue
        paths.append(storage.lstrip("/"))
    return sorted(set(paths))


def _clear_local_workspace(workspace_dir: Path) -> None:
    if not workspace_dir.is_dir():
        return
    for child in workspace_dir.iterdir():
        if child.name in _SKIP_DIR_NAMES:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def _iter_zip_entries(data: bytes) -> list[tuple[str, bytes]]:
    out: list[tuple[str, bytes]] = []
    with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            safe = _safe_zip_name(info.filename)
            if safe is None:
                continue
            out.append((safe, zf.read(info)))
    return out


async def export_workspace_zip(workspace: BackendWorkspace) -> bytes:
    """Pack workspace files into a zip archive."""
    paths = await _list_file_paths(workspace)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in paths:
            blob = await workspace.adownload_bytes(path)
            if blob is None:
                continue
            zf.writestr(path.lstrip("/"), blob)
    return buf.getvalue()


async def import_workspace_zip(
    workspace: BackendWorkspace,
    data: bytes,
    *,
    mode: WorkspaceImportMode,
    local_workspace_dir: Path | None = None,
) -> dict[str, int | str | list[str]]:
    """Import a zip archive into the workspace."""
    entries = _iter_zip_entries(data)
    warnings: list[str] = []

    if mode == "replace" and local_workspace_dir is not None:
        _clear_local_workspace(local_workspace_dir)
    elif mode == "replace":
        warnings.append(
            "replace mode cleared only the local harness workspace; remote-only files may remain"
        )

    pairs = [(rel_path, blob) for rel_path, blob in entries]
    if pairs:
        await workspace.aupload_many(pairs)

    return {
        "mode": mode,
        "imported": len(pairs),
        "warnings": warnings,
    }
