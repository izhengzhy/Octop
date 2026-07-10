"""tests/unit/api/test_harness_tabs.py"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from octop.api.routers.browser import harness as harness_mod


def _fake_sess(*, active_id: str | None = "T1", port: int = 9222) -> SimpleNamespace:
    profile = SimpleNamespace(
        cdp_port=port,
        load_target=MagicMock(return_value=active_id),
        save_target=MagicMock(),
    )
    client = SimpleNamespace(
        close=AsyncMock(),
        connect=AsyncMock(),
        enable_domain=AsyncMock(),
    )
    internal = SimpleNamespace(
        _profile=profile,
        _cfg=SimpleNamespace(cdp_host="127.0.0.1"),
        _client=client,
        _apply_viewport=AsyncMock(),
        _connected=False,
    )
    return SimpleNamespace(_internal=internal)


@pytest.mark.asyncio
async def test_harness_list_tabs_marks_profile_target_active() -> None:
    sess = _fake_sess(active_id="TAB-B")
    targets = [
        {"type": "page", "id": "TAB-A", "url": "https://a.test", "title": "A"},
        {"type": "page", "id": "TAB-B", "url": "https://b.test", "title": "B"},
    ]

    class _JsonResp:
        def __init__(self, data: list[dict[str, object]]) -> None:
            self._data = data

        async def __aenter__(self) -> _JsonResp:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

        async def json(self, content_type: object = None) -> list[dict[str, object]]:
            return self._data

    class _Session:
        def __init__(self, data: list[dict[str, object]]) -> None:
            self._data = data

        async def __aenter__(self) -> _Session:
            return self

        async def __aexit__(self, *exc: object) -> bool:
            return False

        def get(self, url: str, timeout: object = None) -> _JsonResp:
            return _JsonResp(self._data)

    with patch("aiohttp.ClientSession", new=lambda: _Session(targets)):
        tabs = await harness_mod.harness_list_tabs(sess)

    assert [t["id"] for t in tabs] == ["TAB-A", "TAB-B"]
    assert tabs[1]["active"] is True
    assert tabs[0]["active"] is False
