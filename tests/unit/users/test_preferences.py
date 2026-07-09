"""tests/unit/users/test_preferences.py"""

from __future__ import annotations

import pytest

from octop.infra.errors import ErrorCode, OctopError
from octop.infra.users.preferences import (
    get_remote_browser_bookmarks_from_json,
    merge_preferences_json,
    validate_remote_browser_bookmarks,
)


def test_validate_normalizes_and_dedupes_urls() -> None:
    items = [
        {"url": "example.com", "title": "A"},
        {"url": "https://example.com", "title": "B"},
        {"url": "https://other.test", "title": "Other"},
    ]
    out = validate_remote_browser_bookmarks(items)
    assert len(out) == 2
    assert out[0].url == "https://example.com"
    assert out[0].title == "A"
    assert out[1].url == "https://other.test"


def test_validate_skips_invalid_urls() -> None:
    out = validate_remote_browser_bookmarks(
        [{"url": "ftp://bad", "title": "x"}, {"url": "", "title": "y"}]
    )
    assert out == []


def test_validate_title_fallback_to_hostname() -> None:
    out = validate_remote_browser_bookmarks([{"url": "https://cloud.tencent.com", "title": ""}])
    assert out[0].title == "cloud.tencent.com"


def test_validate_rejects_over_limit() -> None:
    items = [{"url": f"https://site{i}.test", "title": f"S{i}"} for i in range(13)]
    with pytest.raises(OctopError) as ei:
        validate_remote_browser_bookmarks(items)
    assert ei.value.code is ErrorCode.SLASH_BAD_ARGS


def test_get_remote_browser_bookmarks_from_json_roundtrip() -> None:
    raw = merge_preferences_json(
        "{}",
        validate_remote_browser_bookmarks(
            [{"url": "https://a.test", "title": "A"}],
        ),
    )
    out = get_remote_browser_bookmarks_from_json(raw)
    assert len(out) == 1
    assert out[0].url == "https://a.test"


def test_get_remote_browser_bookmarks_from_json_invalid_payload() -> None:
    assert get_remote_browser_bookmarks_from_json("not-json") == []
    assert get_remote_browser_bookmarks_from_json('{"remote_browser_bookmarks": "x"}') == []


def test_merge_preserves_other_keys() -> None:
    merged = merge_preferences_json(
        '{"foo": 1}',
        validate_remote_browser_bookmarks(
            [{"url": "https://a.test", "title": "A"}],
        ),
    )
    import json

    data = json.loads(merged)
    assert data["foo"] == 1
    assert len(data["remote_browser_bookmarks"]) == 1
