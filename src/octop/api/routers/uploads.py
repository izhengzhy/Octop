"""Dashboard chat attachments — stored in agent workspace ``inbound/``."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile

from octop.api.common.attachments import (
    StoredAttachment,
    dashboard_inbound_preview_url,
    save_attachment,
)
from octop.api.common.workspace import require_running_workspace
from octop.api.deps import current_user, get_server
from octop.infra.gateway.media.attachment_hints import sniff_image_media_type

router = APIRouter()

_EXTENSION_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
    ".json": "application/json",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".zip": "application/zip",
}


def _resolve_media_type(filename: str, content_type: str | None, data: bytes = b"") -> str:
    raw = (content_type or "").split(";", 1)[0].strip().lower()
    if raw and raw != "application/octet-stream":
        return raw
    ext = Path(filename or "").suffix.lower()
    if ext in _EXTENSION_MEDIA_TYPES:
        return _EXTENSION_MEDIA_TYPES[ext]
    guessed, _ = mimetypes.guess_type(filename or "")
    if guessed:
        return guessed.lower()
    sniffed = sniff_image_media_type(data)
    if sniffed:
        return sniffed
    return "application/octet-stream"


def _attachment_payload(agent_id: str, stored: StoredAttachment) -> dict[str, str]:
    path = stored.data_path
    preview_url = dashboard_inbound_preview_url(
        agent_id,
        path,
        media_type=stored.media_type,
    )
    return {
        "path": path,
        "workspace_path": path,
        "url": preview_url,
        "access_url": preview_url,
        "filename": stored.filename,
        "media_type": stored.media_type,
    }


@router.post("/agents/{agent_id}/upload", summary="Upload a chat attachment")
async def upload_attachment(
    agent_id: str,
    file: UploadFile = File(...),  # noqa: B008
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, str]:
    ws = await require_running_workspace(agent_id, user=user, as_user=as_user, server=server)
    data = await file.read()
    filename = file.filename or "upload.bin"
    media_type = _resolve_media_type(filename, file.content_type, data)
    stored = await save_attachment(
        ws,
        owner_id=user.id,
        filename=filename,
        media_type=media_type,
        data=data,
    )
    return _attachment_payload(agent_id, stored)
