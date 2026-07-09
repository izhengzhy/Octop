"""In-memory upgrade task tracking for ``/api/update/*``."""

from __future__ import annotations

import asyncio
import time
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class UpgradeTaskStatus(StrEnum):
    RUNNING = "running"
    COMPLETE = "complete"
    ERROR = "error"


class UpgradeTask(BaseModel):
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: UpgradeTaskStatus = UpgradeTaskStatus.RUNNING
    stage: str | None = "starting"
    percent: int | None = 0
    new_version: str | None = None
    success: bool | None = None
    error: str | None = None
    mirror_errors: list[str] | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)


_tasks: dict[str, UpgradeTask] = {}
_lock = asyncio.Lock()
_last_status: dict[str, Any] | None = None


def cache_status(payload: dict[str, Any]) -> None:
    global _last_status
    _last_status = payload


def get_cached_status() -> dict[str, Any] | None:
    return _last_status


async def create_task() -> UpgradeTask:
    async with _lock:
        task = UpgradeTask()
        _tasks[task.task_id] = task
        return task


async def update_task(task_id: str, **fields: Any) -> UpgradeTask | None:
    async with _lock:
        task = _tasks.get(task_id)
        if task is None:
            return None
        data = task.model_dump()
        data.update(fields)
        data["updated_at"] = time.time()
        updated = UpgradeTask.model_validate(data)
        _tasks[task_id] = updated
        return updated


async def get_task(task_id: str) -> UpgradeTask | None:
    async with _lock:
        return _tasks.get(task_id)
