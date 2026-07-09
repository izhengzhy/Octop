"""Cron job delivery mode — shared domain type (no DB / gateway imports)."""

from __future__ import annotations

from typing import Literal

CronTaskType = Literal["text", "agent"]
DEFAULT_CRON_TASK_TYPE: CronTaskType = "agent"
CRON_PROMPT_MAX_LEN = 2000
_CRON_TASK_TYPES = frozenset({"text", "agent"})


def normalize_cron_task_type(value: str | None) -> CronTaskType:
    """Coerce unknown values to the default delivery mode."""
    if value in _CRON_TASK_TYPES:
        return value  # type: ignore[return-value]
    return DEFAULT_CRON_TASK_TYPE


def require_cron_task_type(value: str) -> CronTaskType:
    """Validate user/agent input for task_type."""
    if value not in _CRON_TASK_TYPES:
        raise ValueError("task_type must be 'text' or 'agent'")
    return value  # type: ignore[return-value]


def require_cron_prompt(prompt: str) -> str:
    """Validate cron instruction length and non-empty content."""
    text = prompt.strip()
    if not text:
        raise ValueError("prompt must not be empty")
    if len(text) > CRON_PROMPT_MAX_LEN:
        raise ValueError(f"prompt must be at most {CRON_PROMPT_MAX_LEN} characters")
    return text
