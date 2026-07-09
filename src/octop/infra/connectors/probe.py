"""Connector credential probe — validate connectivity and list tools."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from octop.config import OctopConfig
from octop.infra.connectors.builder import (
    build_http_mcp_spec,
    normalize_weiyun_mcp_token,
    validate_create_credentials,
)
from octop.infra.connectors.catalog import ConnectorCatalogEntry, get_catalog_entry
from octop.infra.connectors.gateway.protocol import handle_mcp_request
from octop.infra.utils.ssrf_guard import UnsafeOutboundUrl, safe_request

logger = logging.getLogger(__name__)

_REMOTE_STATIC_TOOL_KINDS = frozenset({"baidu-netdisk", "tencent-weiyun"})


def normalize_tools(raw: list[Any] | None) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        out.append(
            {
                "name": name,
                "description": str(item.get("description") or ""),
            }
        )
    return out


def http_error_message(response: httpx.Response) -> str | None:
    if response.status_code < 400:
        return None
    try:
        body = response.json()
        if isinstance(body, dict):
            for key in ("show_msg", "message", "desc", "detail", "error"):
                val = body.get(key)
                if val and str(val).strip() and not str(val).strip().isdigit():
                    return str(val).strip()
    except Exception:
        pass
    if response.status_code == 401:
        return "认证失败，请检查 Token 或授权码"
    return f"HTTP {response.status_code}"


def static_probe_tools(kind: str) -> list[dict[str, str]]:
    if kind == "tencent-weiyun":
        entry = get_catalog_entry(kind)
        if entry and entry.allowed_tools:
            return [{"name": name, "description": ""} for name in entry.allowed_tools]
    if kind not in _REMOTE_STATIC_TOOL_KINDS:
        return []
    from octop.infra.connectors.baidu_token import baidu_probe_tools

    return baidu_probe_tools()


async def prepare_probe_credentials(
    kind: str,
    credentials: dict[str, Any],
    *,
    full_prepare: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Like credential creation but allows empty token for remote connectivity probes."""
    entry = get_catalog_entry(kind)
    if entry is None:
        raise ValueError(f"unknown connector kind: {kind}")
    if entry.kind == "tencent-weiyun" and entry.auth_kind == "personal_token":
        raw = str(credentials.get("token") or credentials.get("access_token") or "").strip()
        token = normalize_weiyun_mcp_token(raw)
        return {"token": token} if token else {}
    if entry.kind == "youdao-note" and entry.auth_kind == "personal_token":
        api_key = str(
            credentials.get("token")
            or credentials.get("api_key")
            or credentials.get("access_token")
            or ""
        ).strip()
        return {"token": api_key} if api_key else {}
    if full_prepare is not None:
        return await full_prepare(kind, credentials)
    return validate_create_credentials(kind, credentials)


async def probe_youdao_note(api_key: str) -> dict[str, Any]:
    """Probe Youdao Note via MCP SSE (streamable HTTP POST is not supported)."""
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    url = "https://open.mail.163.com/api/ynote/mcp/sse"
    headers = {"x-api-key": api_key}
    try:
        async with (
            sse_client(url, headers, timeout=20, sse_read_timeout=20) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            listed = await session.list_tools()
            tools = normalize_tools(
                [{"name": t.name, "description": t.description or ""} for t in listed.tools]
            )
            return {"ok": True, "tool_count": len(tools), "tools": tools}
    except httpx.HTTPStatusError as exc:
        return _probe_youdao_note_http_error(exc)
    except BaseExceptionGroup as exc:
        for sub in exc.exceptions:
            if isinstance(sub, httpx.HTTPStatusError):
                return _probe_youdao_note_http_error(sub)
        logger.exception("youdao-note SSE probe failed")
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        logger.exception("youdao-note SSE probe failed")
        return {"ok": False, "error": str(exc)}


def _probe_youdao_note_http_error(exc: httpx.HTTPStatusError) -> dict[str, Any]:
    if exc.response.status_code == 401:
        try:
            body = exc.response.json()
            if isinstance(body, dict) and body.get("desc"):
                return {"ok": False, "error": str(body["desc"]), "status_code": 401}
        except Exception:
            pass
        return {
            "ok": False,
            "error": "API Key 无效，请检查或在 MCP 平台重新创建",
            "status_code": 401,
        }
    err = http_error_message(exc.response)
    return {
        "ok": False,
        "error": err or str(exc),
        "status_code": exc.response.status_code,
    }


async def probe_connector(
    entry: ConnectorCatalogEntry,
    cred_payload: dict[str, Any],
    *,
    instance_id: str,
    config: OctopConfig,
) -> dict[str, Any]:
    if entry.mcp_mode == "gateway":
        resp = handle_mcp_request(
            kind=entry.kind,
            creds=cred_payload,
            body={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
        if isinstance(resp, dict) and resp.get("error"):
            msg = str((resp.get("error") or {}).get("message") or "gateway error")
            return {"ok": False, "error": msg}
        tools = normalize_tools(
            (resp.get("result") or {}).get("tools") if isinstance(resp, dict) else None
        )
        return {"ok": True, "tool_count": len(tools), "tools": tools}

    if entry.kind == "baidu-netdisk":
        from octop.infra.connectors.baidu_token import validate_baidu_access_token

        token = str(cred_payload.get("access_token") or cred_payload.get("token") or "")
        ok, err = await validate_baidu_access_token(token)
        if not ok:
            return {"ok": False, "error": err or "百度 Token 无效"}
        tools = static_probe_tools(entry.kind)
        return {"ok": True, "tool_count": len(tools), "tools": tools}

    if entry.kind == "youdao-note":
        api_key = str(
            cred_payload.get("token")
            or cred_payload.get("api_key")
            or cred_payload.get("access_token")
            or ""
        ).strip()
        if not api_key:
            return {"ok": False, "error": "请填写 API Key"}
        return await probe_youdao_note(api_key)

    spec = build_http_mcp_spec(
        entry=entry,
        instance_id=instance_id,
        creds=cred_payload,
        config=config,
    )
    headers = dict(spec.get("headers") or {})
    url = str(spec["url"])
    try:
        r = await safe_request(
            "POST",
            url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "octop", "version": "0.1"},
                },
            },
            headers=headers,
            timeout=20.0,
        )
    except UnsafeOutboundUrl as exc:
        logger.warning("connector probe blocked (SSRF guard): %s", exc)
        return {"ok": False, "error": str(exc)}
    except Exception as exc:
        logger.exception("connector probe failed for %s", entry.kind)
        return {"ok": False, "error": str(exc)}

    err = http_error_message(r)
    if err:
        return {"ok": False, "error": err, "status_code": r.status_code}
    if r.status_code >= 500:
        return {
            "ok": False,
            "error": f"远端服务错误 HTTP {r.status_code}",
            "status_code": r.status_code,
        }

    probed_tools: list[dict[str, str]] = []
    try:
        r2 = await safe_request(
            "POST",
            url,
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            },
            headers=headers,
            timeout=20.0,
        )
        list_err = http_error_message(r2)
        if list_err and entry.kind not in _REMOTE_STATIC_TOOL_KINDS:
            return {"ok": False, "error": list_err, "status_code": r2.status_code}
        if r2.status_code < 400:
            body = r2.json()
            if isinstance(body, dict):
                probed_tools = normalize_tools((body.get("result") or {}).get("tools"))
    except Exception:
        logger.debug("connector tools/list probe skipped for %s", entry.kind)

    if not probed_tools:
        probed_tools = static_probe_tools(entry.kind)

    return {
        "ok": True,
        "status_code": r.status_code,
        "tool_count": len(probed_tools),
        "tools": probed_tools,
    }
