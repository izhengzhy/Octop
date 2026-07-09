"""Estimate context window usage breakdown for the dashboard."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

SEGMENT_KEYS: tuple[str, ...] = (
    "system_prompt",
    "tool_definitions",
    "rules",
    "skills",
    "mcp",
    "subagent_definitions",
    "conversation",
)

_TEAM_TOOL_NAMES = frozenset({"agent_list", "ask_agent"})
_SKILLS_TEMPLATE_OVERHEAD = 600


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def _tool_schema_tokens(tool: Any) -> int:
    try:
        from langchain_core.utils.function_calling import convert_to_openai_tool

        schema = convert_to_openai_tool(tool)
        return estimate_tokens(json.dumps(schema, ensure_ascii=False))
    except Exception:
        name = getattr(tool, "name", None) or ""
        return estimate_tokens(str(name)) + 50


async def _read_workspace_text(ws: Any, name: str) -> str:
    text = await ws.aread_text(name)
    return text or ""


def _message_content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                btype = str(block.get("type") or "").lower()
                if btype in ("thinking", "reasoning"):
                    continue
                if btype == "text":
                    parts.append(str(block.get("text") or ""))
                elif btype == "tool_use":
                    parts.append(json.dumps(block.get("input") or {}, ensure_ascii=False))
                elif btype == "tool_result":
                    output = str(block.get("output") or "")
                    if len(output) > 500:
                        parts.append(f"[tool_result truncated: {len(output)} chars]")
                    else:
                        parts.append(output)
                elif btype in ("file", "image", "image_url", "input_image", "audio", "video"):
                    parts.append(f"[{btype} block omitted]")
                else:
                    raw = json.dumps(block, ensure_ascii=False)
                    if len(raw) > 500:
                        parts.append(f"[{btype or 'block'} truncated: {len(raw)} chars]")
                    else:
                        parts.append(raw)
        return "\n".join(p for p in parts if p)
    return str(content or "")


def conversation_tokens_from_messages(messages: list[Any]) -> int:
    total = 0
    for msg in messages:
        if isinstance(msg, dict):
            role = str(msg.get("role") or msg.get("type") or "")
            if role == "system":
                continue
            total += estimate_tokens(_message_content_text(msg.get("content")))
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += estimate_tokens(json.dumps(tool_calls, ensure_ascii=False, default=str))
            continue
        role = str(getattr(msg, "type", "") or "")
        if role == "system":
            continue
        total += estimate_tokens(_message_content_text(getattr(msg, "content", "")))
        tool_calls = getattr(msg, "tool_calls", None)
        if tool_calls:
            total += estimate_tokens(json.dumps(tool_calls, ensure_ascii=False, default=str))
    return total


def _scale_segments(raw: dict[str, int], target: int) -> dict[str, int]:
    if target <= 0:
        return dict.fromkeys(SEGMENT_KEYS, 0)
    total = sum(raw.get(k, 0) for k in SEGMENT_KEYS)
    if total <= 0:
        return dict.fromkeys(SEGMENT_KEYS, 0)
    scaled = {k: int(round(raw.get(k, 0) * target / total)) for k in SEGMENT_KEYS}
    drift = target - sum(scaled.values())
    if drift:
        largest = max(SEGMENT_KEYS, key=lambda key: scaled[key])
        scaled[largest] = max(0, scaled[largest] + drift)
    return scaled


def _skills_tokens(
    summaries: list[dict[str, Any]],
    *,
    allowed: list[str] | None,
) -> int:
    if allowed is not None and not allowed:
        return 0
    allowed_set = {str(name) for name in allowed} if allowed is not None else None
    total = _SKILLS_TEMPLATE_OVERHEAD
    for item in summaries:
        if allowed_set is None and not item.get("enabled", True):
            continue
        name = str(item.get("name") or "")
        if allowed_set is not None and name not in allowed_set:
            continue
        desc = str(item.get("description") or "")
        total += estimate_tokens(name) + estimate_tokens(desc) + 40
    return total


def _tool_buckets(
    tools: list[Any],
    *,
    mcp_tool_names: frozenset[str],
    mcp_server_names: frozenset[str],
    mcp_servers: list[str] | None,
) -> tuple[int, int, int]:
    from harness_agent.mcp import filter_tools_for_mcp_servers

    tool_def = 0
    mcp_total = 0
    subagent = 0
    mcp_tools = [tool for tool in tools if getattr(tool, "name", "") in mcp_tool_names]
    active_mcp: list[Any] = []
    if mcp_servers:
        active_mcp = filter_tools_for_mcp_servers(
            mcp_tools,
            mcp_tool_names=mcp_tool_names,
            server_names=mcp_server_names,
            active_servers=mcp_servers,
        )

    for tool in tools:
        name = str(getattr(tool, "name", "") or "")
        tokens = _tool_schema_tokens(tool)
        if name in mcp_tool_names:
            if any(getattr(t, "name", "") == name for t in active_mcp):
                mcp_total += tokens
            continue
        if name in _TEAM_TOOL_NAMES:
            subagent += tokens
            continue
        tool_def += tokens
    return tool_def, mcp_total, subagent


@dataclass(frozen=True)
class ContextBreakdownResult:
    max_tokens: int
    used_tokens: int
    segments: dict[str, int]


_STATIC_SEGMENT_KEYS: tuple[str, ...] = tuple(k for k in SEGMENT_KEYS if k != "conversation")


async def _load_history_messages(harness: Any, thread_id: str) -> list[Any]:
    """Load transcript for token estimate — timestamps are not needed here.

    Only used when the caller has no measured ``input_tokens``; with a real
    usage total, conversation is derived as the remainder after static segments.
    """
    if not hasattr(harness, "aget_history"):
        return []
    try:
        try:
            return list(
                await harness.aget_history(
                    thread_id,
                    limit=500,
                    annotate_timestamps=False,
                )
            )
        except TypeError:
            return list(await harness.aget_history(thread_id, limit=500))
    except Exception:
        logger.debug(
            "context breakdown: history unavailable for thread=%s",
            thread_id,
            exc_info=True,
        )
        return []


def _segments_from_static_and_usage(
    static: dict[str, int],
    *,
    input_tokens: int,
) -> dict[str, int]:
    """Put unused budget into ``conversation`` instead of rescanning history."""
    static_only = {k: max(0, int(static.get(k, 0))) for k in _STATIC_SEGMENT_KEYS}
    static_sum = sum(static_only.values())
    if static_sum >= input_tokens:
        return _scale_segments({**static_only, "conversation": 0}, input_tokens)
    return {**static_only, "conversation": input_tokens - static_sum}


async def compute_context_breakdown(
    registry: Any,
    *,
    agent_id: str,
    thread_id: str,
    max_tokens: int,
    input_tokens: int | None = None,
    mcp_servers: list[str] | None = None,
    skills: list[str] | None = None,
) -> ContextBreakdownResult:
    row = registry.get_row(agent_id)
    if row is None:
        raise ValueError(f"agent {agent_id!r} not found")

    harness = registry.get_agent(agent_id)
    ws = harness.workspace
    mcp_tool_names: frozenset[str] = getattr(harness, "_mcp_tool_name_set", frozenset())
    mcp_server_names = frozenset(harness.config.mcp_server_configs or {})
    tools: list[Any] = harness._build_tools()  # noqa: SLF001

    system_prompt = (row.system_prompt or "").strip()
    need_soul = not system_prompt
    has_usage = bool(input_tokens and input_tokens > 0)

    (
        agents_md,
        user_md,
        memory_md,
        soul_md,
        skill_summaries,
        raw_messages,
    ) = await asyncio.gather(
        _read_workspace_text(ws, "AGENTS.md"),
        _read_workspace_text(ws, "USER.md"),
        _read_workspace_text(ws, "MEMORY.md"),
        _read_workspace_text(ws, "SOUL.md") if need_soul else asyncio.sleep(0, result=""),
        registry.list_skill_summaries(agent_id),
        (asyncio.sleep(0, result=[]) if has_usage else _load_history_messages(harness, thread_id)),
    )
    if need_soul and soul_md.strip():
        system_prompt = soul_md

    system_tokens = (
        estimate_tokens(system_prompt) + estimate_tokens(user_md) + estimate_tokens(memory_md)
    )
    rules_tokens = estimate_tokens(agents_md)
    skills_tokens = _skills_tokens(skill_summaries, allowed=skills)

    tool_def_tokens, mcp_tokens, subagent_tokens = _tool_buckets(
        tools,
        mcp_tool_names=mcp_tool_names,
        mcp_server_names=mcp_server_names,
        mcp_servers=mcp_servers,
    )

    static = {
        "system_prompt": system_tokens,
        "tool_definitions": tool_def_tokens,
        "rules": rules_tokens,
        "skills": skills_tokens,
        "mcp": mcp_tokens,
        "subagent_definitions": subagent_tokens,
    }

    if has_usage:
        assert input_tokens is not None  # narrow for type checkers
        segments = _segments_from_static_and_usage(static, input_tokens=input_tokens)
        used_tokens = input_tokens
    else:
        conversation_tokens = conversation_tokens_from_messages(raw_messages)
        segments = {**static, "conversation": conversation_tokens}
        used_tokens = sum(segments.values())

    cap = max_tokens if max_tokens > 0 else 128_000
    return ContextBreakdownResult(
        max_tokens=cap,
        used_tokens=min(used_tokens, cap),
        segments=segments,
    )
