from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch


async def test_record_replay_status_returns_daemon_status(env: Any) -> None:
    client, _srv, auth = env

    with (
        patch(
            "octop.api.routers.browser.record_replay.send_record_request",
            new=AsyncMock(return_value={"ok": True, "active": None}),
        ) as mock_send,
        patch(
            "octop.api.routers.browser.record_replay._latest_recording_id",
            return_value="rec_latest",
        ),
    ):
        r = await client.get("/api/browser/record-replay/status", headers=auth)

    assert r.status_code == 200
    assert r.json() == {"ok": True, "active": None, "latestRecordingId": "rec_latest"}
    mock_send.assert_awaited_once_with({"command": "status"})


async def test_record_replay_start_ensures_daemon_and_starts_recording(env: Any) -> None:
    client, _srv, auth = env

    with (
        patch(
            "octop.api.routers.browser.record_replay.ensure_record_daemon",
            new=AsyncMock(return_value={"ok": True, "pid": 123}),
        ) as mock_ensure,
        patch(
            "octop.api.routers.browser.record_replay.send_record_request",
            new=AsyncMock(return_value={"ok": True, "recordingId": "rec_1", "daemon": True}),
        ) as mock_send,
    ):
        r = await client.post(
            "/api/browser/record-replay/start",
            headers=auth,
            json={"profile": "thr_demo", "name": "demo"},
        )

    assert r.status_code == 200
    assert r.json()["recordingId"] == "rec_1"
    mock_ensure.assert_awaited_once_with()
    mock_send.assert_awaited_once_with(
        {
            "command": "start",
            "profile": "thr_demo",
            "name": "demo",
            "privacy": "mask-sensitive",
            "screenshots": "off",
        }
    )


async def test_record_replay_start_falls_back_to_profile_without_agent_profile(env: Any) -> None:
    client, _srv, auth = env

    with (
        patch(
            "octop.api.routers.browser.record_replay.ensure_record_daemon",
            new=AsyncMock(return_value={"ok": True, "pid": 123}),
        ),
        patch(
            "octop.api.routers.browser.record_replay.send_record_request",
            new=AsyncMock(return_value={"ok": True, "recordingId": "rec_1"}),
        ) as mock_send,
    ):
        r = await client.post(
            "/api/browser/record-replay/start",
            headers=auth,
            json={"profile": "thr_demo", "name": "demo"},
        )

    assert r.status_code == 200
    mock_send.assert_awaited_once_with(
        {
            "command": "start",
            "profile": "thr_demo",
            "name": "demo",
            "privacy": "mask-sensitive",
            "screenshots": "off",
        }
    )


async def test_record_replay_start_returns_503_when_daemon_fails(env: Any) -> None:
    client, _srv, auth = env

    with patch(
        "octop.api.routers.browser.record_replay.ensure_record_daemon",
        new=AsyncMock(return_value={"ok": False, "error": "Daemon did not start"}),
    ):
        r = await client.post(
            "/api/browser/record-replay/start",
            headers=auth,
            json={"profile": "thr_demo"},
        )

    assert r.status_code == 503
    body = r.json()
    assert body["error"]["details"]["recordReplay"]["error"] == "Daemon did not start"


async def test_record_replay_stop_generates_steps(env: Any) -> None:
    client, _srv, auth = env

    with patch(
        "octop.api.routers.browser.record_replay.send_record_request",
        new=AsyncMock(return_value={"ok": True, "recordingId": "rec_1", "events": 4, "steps": 2}),
    ) as mock_send:
        r = await client.post(
            "/api/browser/record-replay/stop",
            headers=auth,
            json={"recordingId": "rec_1", "name": "demo"},
        )

    assert r.status_code == 200
    assert r.json()["steps"] == 2
    mock_send.assert_awaited_once_with(
        {
            "command": "stop",
            "recording_id": "rec_1",
            "generate_steps": True,
            "name": "demo",
        }
    )


async def test_record_replay_start_uses_agent_profile_when_requested(env: Any) -> None:
    client, _srv, auth = env

    with (
        patch(
            "octop.api.routers.browser.record_replay.ensure_record_daemon",
            new=AsyncMock(return_value={"ok": True, "pid": 123}),
        ),
        patch(
            "octop.api.routers.browser.record_replay.send_record_request",
            new=AsyncMock(return_value={"ok": True, "recordingId": "rec_default"}),
        ) as mock_send,
    ):
        r = await client.post(
            "/api/browser/record-replay/start",
            headers=auth,
            json={"profile": "thr_123", "agentProfile": "default"},
        )

    assert r.status_code == 200
    mock_send.assert_awaited_once_with(
        {
            "command": "start",
            "profile": "default",
            "name": None,
            "privacy": "mask-sensitive",
            "screenshots": "off",
        }
    )


async def test_record_replay_replay_runs_runner(env: Any) -> None:
    client, _srv, auth = env
    runner = AsyncMock(return_value={"status": "passed", "recordingId": "rec_1"})

    with patch(
        "octop.api.routers.browser.record_replay.run_replay_recording",
        new=runner,
    ):
        r = await client.post(
            "/api/browser/record-replay/replay",
            headers=auth,
            json={"recordingId": "rec_1", "profile": "thr_demo-replay"},
        )

    assert r.status_code == 200
    assert r.json()["status"] == "passed"
    runner.assert_awaited_once_with("rec_1", profile="thr_demo-replay", inputs={})
