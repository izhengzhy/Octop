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

    with patch.object(harness_mod, "_fetch_cdp_targets", AsyncMock(return_value=targets)):
        tabs = await harness_mod.harness_list_tabs(sess)

    assert [t["id"] for t in tabs] == ["TAB-A", "TAB-B"]
    assert tabs[1]["active"] is True
    assert tabs[0]["active"] is False


@pytest.mark.asyncio
async def test_harness_prepare_screencast_sets_white_background() -> None:
    sess = _fake_sess()
    sess._internal._client.send = AsyncMock()

    await harness_mod.harness_prepare_screencast(sess)

    sess._internal._client.send.assert_awaited_once()
    call = sess._internal._client.send.await_args
    assert call.args[0] == "Emulation.setDefaultBackgroundColorOverride"
    assert call.args[1]["color"] == {"r": 255, "g": 255, "b": 255, "a": 1}


@pytest.mark.asyncio
async def test_harness_switch_tab_reconnects_cdp_client() -> None:
    sess = _fake_sess(active_id="OLD")
    pages = [
        {
            "type": "page",
            "id": "NEW",
            "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/NEW",
        }
    ]

    with (
        patch.object(harness_mod, "_fetch_cdp_targets", AsyncMock(return_value=pages)),
        patch("aiohttp.ClientSession") as session_cls,
    ):
        http = session_cls.return_value.__aenter__.return_value
        http.get = AsyncMock()
        await harness_mod.harness_switch_tab(sess, "NEW")

    sess._internal._profile.save_target.assert_called_once_with("NEW")
    sess._internal._client.close.assert_awaited_once()
    sess._internal._client.connect.assert_awaited_once_with(
        "ws://127.0.0.1:9222/devtools/page/NEW",
    )
