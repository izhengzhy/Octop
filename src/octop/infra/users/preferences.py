"""Per-user JSON preferences (remote-browser bookmarks, etc.)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.url import normalize_nav_url

MAX_REMOTE_BROWSER_BOOKMARKS = 12
PREFERENCES_KEY_REMOTE_BROWSER_BOOKMARKS = "remote_browser_bookmarks"
MAX_BOOKMARK_TITLE_LEN = 80


@dataclass(frozen=True)
class RemoteBrowserBookmark:
    url: str
    title: str


def parse_preferences_json(raw: str | None) -> dict[str, Any]:
    if not raw or not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def validate_remote_browser_bookmarks(items: list[Any]) -> list[RemoteBrowserBookmark]:
    out: list[RemoteBrowserBookmark] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        url = normalize_nav_url(str(item.get("url") or ""))
        if not url.startswith(("http://", "https://")):
            continue
        if url in seen:
            continue
        seen.add(url)
        title_raw = str(item.get("title") or "").strip()
        if not title_raw:
            title_raw = urlparse(url).hostname or url
        out.append(RemoteBrowserBookmark(url=url, title=title_raw[:MAX_BOOKMARK_TITLE_LEN]))
    if len(out) > MAX_REMOTE_BROWSER_BOOKMARKS:
        raise OctopError(
            ErrorCode.SLASH_BAD_ARGS,
            f"remote_browser_bookmarks limit is {MAX_REMOTE_BROWSER_BOOKMARKS}",
        )
    return out


def get_remote_browser_bookmarks_from_json(raw: str | None) -> list[RemoteBrowserBookmark]:
    data = parse_preferences_json(raw)
    items = data.get(PREFERENCES_KEY_REMOTE_BROWSER_BOOKMARKS, [])
    if not isinstance(items, list):
        return []
    return validate_remote_browser_bookmarks(items)


def merge_preferences_json(
    current_raw: str | None,
    bookmarks: list[RemoteBrowserBookmark],
) -> str:
    data = parse_preferences_json(current_raw)
    data[PREFERENCES_KEY_REMOTE_BROWSER_BOOKMARKS] = [
        {"url": b.url, "title": b.title} for b in bookmarks
    ]
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))
