"""Gateway adapter registry — kind → list_tools / call_tool."""

from __future__ import annotations

from typing import Any, Protocol

from octop.infra.connectors.gateway.adapters import (
    qq_mail,
    tencent_ima,
    tencent_news,
    wechat_reading,
)


class GatewayAdapter(Protocol):
    def list_tools(self) -> list[dict[str, Any]]: ...

    def call_tool(self, creds: dict[str, Any], name: str, args: dict[str, Any]) -> str: ...


_ADAPTERS: dict[str, GatewayAdapter] = {
    "qq-mail": qq_mail,
    "tencent-ima": tencent_ima,
    "tencent-news": tencent_news,
    "wechat-reading": wechat_reading,
}


def get_gateway_adapter(kind: str) -> GatewayAdapter | None:
    return _ADAPTERS.get(kind)


def mcp_tools_for_kind(kind: str) -> list[dict[str, Any]]:
    adapter = get_gateway_adapter(kind)
    if adapter is None:
        return []
    return adapter.list_tools()


def call_gateway_tool(
    kind: str,
    creds: dict[str, Any],
    name: str,
    args: dict[str, Any],
) -> str:
    adapter = get_gateway_adapter(kind)
    if adapter is None:
        raise ValueError(f"unknown tool: {name}")
    return adapter.call_tool(creds, name, args)
