"""Sniff harness stream chunks for token usage and append to the ledger."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any


def extract_usage_from_chunk(chunk: dict[str, Any]) -> dict[str, Any] | None:
    """Best-effort extraction of usage_metadata from a streaming chunk."""
    if not isinstance(chunk, dict):
        return None

    direct = chunk.get("usage")
    if isinstance(direct, dict):
        return direct

    if chunk.get("type") not in ("state_snapshot", "state_update"):
        return None

    data = chunk.get("data") or {}
    messages: list[Any] = []
    if isinstance(data, dict):
        messages = list(data.get("messages") or [])

    for msg in reversed(messages):
        usage = getattr(msg, "usage_metadata", None)
        if usage is None and isinstance(msg, dict):
            usage = msg.get("usage_metadata")
        if isinstance(usage, dict) and usage:
            model = ""
            response_metadata = getattr(msg, "response_metadata", None)
            if isinstance(response_metadata, dict):
                model = str(
                    response_metadata.get("model_name") or response_metadata.get("model") or ""
                )
            elif isinstance(msg, dict):
                rm = msg.get("response_metadata") or {}
                if isinstance(rm, dict):
                    model = str(rm.get("model_name") or rm.get("model") or "")
            return {**usage, "model": model}
    return None


@dataclass
class UsageTracker:
    """Collect the latest usage payload seen while iterating a harness stream."""

    usage: dict[str, Any] | None = field(default=None, init=False)

    def observe(self, chunk: dict[str, Any]) -> None:
        found = extract_usage_from_chunk(chunk)
        if found:
            self.usage = found


def record_turn_usage(
    usage_repo: Any,
    *,
    agent_id: str,
    user_id: int,
    thread_id: str,
    usage: dict[str, Any],
    source: str = "chat",
) -> None:
    """Append one usage row. Best-effort — malformed payloads must not break chat."""
    with contextlib.suppress(Exception):
        usage_repo.record(
            agent_id=agent_id,
            user_id=user_id,
            thread_id=thread_id,
            model=str(usage.get("model") or ""),
            input_tokens=int(usage.get("input_tokens") or usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("output_tokens") or usage.get("completion_tokens") or 0),
            source=source,
        )
