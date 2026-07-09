"""Format HITL approval cards for IM channels."""

from __future__ import annotations

import json
from typing import Any

from octop.i18n import tool_display_name, tr
from octop.infra.utils.locale import Locale, normalize_locale


def parse_action_requests(raw: dict[str, Any]) -> list[dict[str, Any]]:
    requests = raw.get("action_requests")
    if not isinstance(requests, list):
        return []
    out: list[dict[str, Any]] = []
    for item in requests:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "tool")
        args = item.get("args") if isinstance(item.get("args"), dict) else {}
        description = item.get("description")
        row: dict[str, Any] = {"name": name, "args": args}
        if isinstance(description, str) and description.strip():
            row["description"] = description.strip()
        out.append(row)
    return out


def parse_review_configs(raw: dict[str, Any]) -> list[dict[str, Any]] | None:
    configs = raw.get("review_configs")
    if not isinstance(configs, list):
        return None
    out = [c for c in configs if isinstance(c, dict)]
    return out or None


def _format_args(args: dict[str, Any], *, limit: int = 400) -> str:
    try:
        text = json.dumps(args, ensure_ascii=False, indent=2)
    except TypeError:
        text = str(args)
    if len(text) > limit:
        return text[: limit - 3] + "..."
    return text


def format_hitl_card(
    record_action_requests: list[dict[str, Any]],
    *,
    pending_id: str,
    locale: str | Locale,
) -> str:
    loc = normalize_locale(str(locale))
    lines = [
        tr("slash.hitl.card_title", loc),
        "",
        tr("slash.hitl.card_intro", loc),
        "",
    ]
    for idx, action in enumerate(record_action_requests, start=1):
        name = str(action.get("name") or "tool")
        label = tool_display_name(name, loc)
        args = action.get("args")
        if not isinstance(args, dict):
            args = {}
        args_text = _format_args(args)
        lines.append(tr("slash.hitl.action_line", loc, index=idx, name=label))
        if args_text.strip() and args_text.strip() != "{}":
            lines.append(f"```\n{args_text}\n```")
        desc = action.get("description")
        if isinstance(desc, str) and desc.strip():
            lines.append(desc.strip())
        lines.append("")
    lines.extend(
        [
            tr("slash.hitl.card_footer", loc),
            tr("slash.hitl.card_pending_id", loc, pending_id=pending_id),
        ]
    )
    return "\n".join(lines).strip()
