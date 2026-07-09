"""``tools.*`` — built-in agent tool display names."""

from __future__ import annotations

from typing import Any

from octop.i18n.loader import _load_all, lookup
from octop.infra.utils.locale import Locale, normalize_locale

__all__ = ["all_tool_labels", "tool_display_name"]


def tool_display_name(name: str | None, locale: str | Locale = "en") -> str:
    if not name:
        return lookup("tools.unknown", locale) or "unknown"
    text = lookup(f"tools.{name}", locale)
    return text if text is not None else name


def all_tool_labels(locale: str | Locale = "en") -> dict[str, str]:
    loc = normalize_locale(str(locale))
    tables = _load_all()
    node: Any = tables.get(loc, {}).get("tools")
    if not isinstance(node, dict):
        node = tables.get("en", {}).get("tools")
    if not isinstance(node, dict):
        return {}
    return {str(k): str(v) for k, v in node.items() if isinstance(v, str)}
