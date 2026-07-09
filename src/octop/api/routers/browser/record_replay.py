"""Browser record/replay endpoints backed by harness-browser."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from octop.api.deps import current_user
from octop.infra.errors import ErrorCode, OctopError

router = APIRouter()


class RecordStartBody(BaseModel):
    profile: str = "default"
    agent_profile: str | None = Field(default=None, alias="agentProfile")
    name: str | None = None
    privacy: str = "mask-sensitive"


class RecordStopBody(BaseModel):
    recording_id: str | None = Field(default=None, alias="recordingId")
    name: str | None = None
    generate_steps: bool = Field(default=True, alias="generateSteps")


class RecordStopAndGenerateSkillBody(BaseModel):
    """Stop recording, generate steps, generate skill, and return skill content."""

    recording_id: str | None = Field(default=None, alias="recordingId")
    name: str | None = None
    generate_steps: bool = Field(default=True, alias="generateSteps")


class ReplayBody(BaseModel):
    recording_id: str = Field(alias="recordingId")
    profile: str = "default"
    inputs: dict[str, str] = Field(default_factory=dict)


class SkillContentBody(BaseModel):
    """Request body to read generated skill content for a recording."""

    recording_id: str = Field(alias="recordingId")


async def ensure_record_daemon() -> dict[str, Any]:
    try:
        from harness_browser.record.daemon import ensure_daemon
    except ImportError as exc:
        raise OctopError(
            ErrorCode.INTERNAL_ERROR,
            "harness-browser record/replay is not installed",
            status=503,
        ) from exc
    return await ensure_daemon()


async def send_record_request(request: dict[str, Any]) -> dict[str, Any]:
    try:
        from harness_browser.record.daemon import send_request
    except ImportError as exc:
        raise OctopError(
            ErrorCode.INTERNAL_ERROR,
            "harness-browser record/replay is not installed",
            status=503,
        ) from exc
    return await send_request(request)


async def run_replay_recording(
    recording_id: str,
    *,
    profile: str,
    inputs: dict[str, str],
) -> dict[str, Any]:
    try:
        from harness_browser.record.replay import ReplayRunner
    except ImportError as exc:
        raise OctopError(
            ErrorCode.INTERNAL_ERROR,
            "harness-browser record/replay is not installed",
            status=503,
        ) from exc
    return await ReplayRunner().run(recording_id, profile=profile, inputs=inputs)


def _latest_recording_id() -> str | None:
    try:
        from harness_browser.record.store import RecordingStore
    except ImportError:
        return None
    recordings = RecordingStore().list_recordings()
    if not recordings:
        return None
    latest = max(recordings, key=lambda m: m.created_at)
    return latest.recording_id


def _effective_profile(profile: str | None, agent_profile: str | None = None) -> str:
    chosen = (agent_profile or profile or "default").strip()
    return chosen or "default"


def _raise_if_not_ok(data: dict[str, Any], *, status: int = 500) -> None:
    if data.get("ok", True):
        return
    raise OctopError(
        ErrorCode.INTERNAL_ERROR,
        str(data.get("error") or "record/replay operation failed"),
        status=status,
        details={"recordReplay": data},
    )


@router.get("/browser/record-replay/status")
async def record_status(_: Any = Depends(current_user)) -> dict[str, Any]:
    try:
        data = await send_record_request({"command": "status"})
    except Exception:
        data = {"ok": True, "active": None}
    data["latestRecordingId"] = _latest_recording_id()
    return data


@router.post("/browser/record-replay/start")
async def record_start(
    body: RecordStartBody,
    _: Any = Depends(current_user),
) -> dict[str, Any]:
    daemon = await ensure_record_daemon()
    _raise_if_not_ok(daemon, status=503)
    data = await send_record_request(
        {
            "command": "start",
            "profile": _effective_profile(body.profile, body.agent_profile),
            "name": body.name,
            "privacy": body.privacy or "mask-sensitive",
            "screenshots": "off",
        }
    )
    _raise_if_not_ok(data, status=409)
    return data


@router.post("/browser/record-replay/stop")
async def record_stop(
    body: RecordStopBody,
    _: Any = Depends(current_user),
) -> dict[str, Any]:
    data = await send_record_request(
        {
            "command": "stop",
            "recording_id": body.recording_id,
            "generate_steps": body.generate_steps,
            "name": body.name,
        }
    )
    _raise_if_not_ok(data, status=409)
    return data


@router.post("/browser/record-replay/stop-and-generate-skill")
async def record_stop_and_generate_skill(
    body: RecordStopAndGenerateSkillBody,
    _: Any = Depends(current_user),
) -> dict[str, Any]:
    """Stop recording, generate steps + skill draft, and return the skill content.

    This is a convenience endpoint that combines stop + generate-steps +
    generate-skill into a single call, returning the generated skill markdown
    content so the frontend can display it for user confirmation.
    """
    # 1) Stop the recording
    data = await send_record_request(
        {
            "command": "stop",
            "recording_id": body.recording_id,
            "generate_steps": body.generate_steps,
            "name": body.name,
        }
    )
    _raise_if_not_ok(data, status=409)

    recording_id = data.get("recordingId") or body.recording_id
    if not recording_id:
        return {**data, "skillContent": None, "skillName": None}

    # 2) Generate skill from the recording
    await send_record_request(
        {
            "command": "generate_skill",
            "recording_id": recording_id,
        }
    )

    # 3) Read the generated skill content from the recording store
    skill_content = None
    skill_name = None
    try:
        from harness_browser.record.store import RecordingStore

        store = RecordingStore()
        # Find the recording directory
        manifest = store.read_manifest(recording_id)
        if manifest is not None:
            import pathlib

            rec_dir = pathlib.Path(store.recordings_dir) / recording_id
            skill_path = rec_dir / "draft.skill.md"
            if skill_path.exists():
                skill_content = skill_path.read_text(encoding="utf-8")
                # Derive a skill name from the recording name or ID
                skill_name = manifest.target.title.strip() or recording_id
    except ImportError:
        # harness-browser not installed — skill generation not possible
        pass
    except Exception:
        # Non-critical: if we can't read the skill file, just return without it
        pass

    return {
        **data,
        "skillContent": skill_content,
        "skillName": skill_name,
        "recordingId": recording_id,
    }


@router.post("/browser/record-replay/skill-content")
async def get_skill_content(
    body: SkillContentBody,
    _: Any = Depends(current_user),
) -> dict[str, Any]:
    """Read the generated skill content (draft.skill.md) for a given recording."""
    skill_content = None
    skill_name = None
    skill_exists = False

    try:
        from harness_browser.record.store import RecordingStore

        store = RecordingStore()
        manifest = store.read_manifest(body.recording_id)
        if manifest is not None:
            import pathlib

            rec_dir = pathlib.Path(store.recordings_dir) / body.recording_id
            skill_path = rec_dir / "draft.skill.md"
            if skill_path.exists():
                skill_content = skill_path.read_text(encoding="utf-8")
                skill_exists = True
                skill_name = manifest.target.title.strip() or body.recording_id
    except ImportError as exc:
        raise OctopError(
            ErrorCode.INTERNAL_ERROR,
            "harness-browser record/replay is not installed",
            status=503,
        ) from exc
    except Exception as exc:
        raise OctopError(ErrorCode.INTERNAL_ERROR, str(exc)) from exc

    return {
        "ok": True,
        "recordingId": body.recording_id,
        "skillContent": skill_content,
        "skillName": skill_name,
        "skillExists": skill_exists,
    }


@router.post("/browser/record-replay/replay")
async def replay_recording(
    body: ReplayBody,
    _: Any = Depends(current_user),
) -> dict[str, Any]:
    data = await run_replay_recording(
        body.recording_id,
        profile=body.profile or "default",
        inputs=body.inputs,
    )
    return data
