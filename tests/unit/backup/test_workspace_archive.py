"""Unit tests for workspace zip archives."""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from deepagents.backends.local_shell import LocalShellBackend
from harness_agent.backends.workspace import BackendWorkspace

from octop.infra.backup.workspace_archive import export_workspace_zip, import_workspace_zip


@pytest.mark.asyncio
async def test_export_and_merge_import(tmp_path: Path) -> None:
    (tmp_path / "hello.txt").write_bytes(b"hello")
    (tmp_path / "dir").mkdir()
    (tmp_path / "dir" / "note.md").write_bytes(b"note")
    backend = LocalShellBackend(root_dir=str(tmp_path), virtual_mode=False)
    workspace = BackendWorkspace(backend, tmp_path)

    blob = await export_workspace_zip(workspace)
    with zipfile.ZipFile(io.BytesIO(blob), "r") as zf:
        names = set(zf.namelist())
    assert "hello.txt" in names
    assert "dir/note.md" in names

    for path in tmp_path.rglob("*"):
        if path.is_file():
            path.unlink()
    for path in sorted(tmp_path.rglob("*"), reverse=True):
        if path.is_dir():
            path.rmdir()

    result = await import_workspace_zip(workspace, blob, mode="merge", local_workspace_dir=None)
    assert result["imported"] == 2
    assert (tmp_path / "hello.txt").read_bytes() == b"hello"


@pytest.mark.asyncio
async def test_replace_clears_local_dir(tmp_path: Path) -> None:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "old.txt").write_text("old", encoding="utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("new.txt", "new")
    data = buf.getvalue()

    backend = LocalShellBackend(root_dir=str(ws), virtual_mode=False)
    workspace = BackendWorkspace(backend, ws)
    result = await import_workspace_zip(workspace, data, mode="replace", local_workspace_dir=ws)
    assert result["imported"] == 1
    assert not (ws / "old.txt").exists()
    assert (ws / "new.txt").read_bytes() == b"new"
