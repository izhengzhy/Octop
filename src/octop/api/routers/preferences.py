"""Per-user preferences (locale, etc.)."""

from __future__ import annotations

from typing import Any, Self

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, model_validator

from octop.api.deps import current_user, get_server
from octop.infra.users.preferences import (
    MAX_REMOTE_BROWSER_BOOKMARKS,
    get_remote_browser_bookmarks_from_json,
)
from octop.infra.utils.locale import normalize_locale

router = APIRouter()


class RemoteBrowserBookmarkModel(BaseModel):
    url: str = Field(description="Bookmark URL (`http://` or `https://`).")
    title: str = Field(description="Short display label.")


class PreferencesResponse(BaseModel):
    locale: str = Field(description="UI locale: `zh` or `en`.")
    remote_browser_bookmarks: list[RemoteBrowserBookmarkModel] = Field(
        default_factory=list,
        description="Saved URLs for the remote-browser page.",
    )


class PatchPreferencesBody(BaseModel):
    locale: str | None = Field(default=None, description="UI locale: `zh` or `en`.")
    remote_browser_bookmarks: list[RemoteBrowserBookmarkModel] | None = Field(
        default=None,
        description="Replace remote-browser bookmarks (max 12).",
    )

    @model_validator(mode="after")
    def at_least_one_field(self) -> Self:
        if self.locale is None and self.remote_browser_bookmarks is None:
            raise ValueError("at least one of locale or remote_browser_bookmarks is required")
        if (
            self.remote_browser_bookmarks is not None
            and len(self.remote_browser_bookmarks) > MAX_REMOTE_BROWSER_BOOKMARKS
        ):
            raise ValueError(
                f"remote_browser_bookmarks must have at most {MAX_REMOTE_BROWSER_BOOKMARKS} items"
            )
        return self


def _bookmarks_response(row: Any) -> list[RemoteBrowserBookmarkModel]:
    raw = row.preferences_json if row else None
    return [
        RemoteBrowserBookmarkModel(url=b.url, title=b.title)
        for b in get_remote_browser_bookmarks_from_json(raw)
    ]


@router.get("/preferences", summary="Current user preferences", response_model=PreferencesResponse)
async def get_preferences(
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> PreferencesResponse:
    row = server.services.user_repo.get(user.id)
    return PreferencesResponse(
        locale=normalize_locale(row.locale if row else None),
        remote_browser_bookmarks=_bookmarks_response(row),
    )


@router.patch("/preferences", summary="Update user preferences", response_model=PreferencesResponse)
async def patch_preferences(
    body: PatchPreferencesBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> PreferencesResponse:
    if body.locale is not None:
        await server.user_manager.set_locale(user.username, body.locale)
    if body.remote_browser_bookmarks is not None:
        items = [b.model_dump() for b in body.remote_browser_bookmarks]
        await server.user_manager.set_remote_browser_bookmarks(user.username, items)
    row = server.services.user_repo.get(user.id)
    return PreferencesResponse(
        locale=normalize_locale(row.locale if row else None),
        remote_browser_bookmarks=_bookmarks_response(row),
    )
