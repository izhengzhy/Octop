"""Baidu Netdisk access-token validation helpers."""

from __future__ import annotations

import re

import httpx

BAIDU_USERINFO_URL = "https://openapi.baidu.com/rest/2.0/passport/users/getLoggedInUser"
_BAIDU_AUTH_CODE_RE = re.compile(r"^[0-9a-f]{32}$", re.I)

_BAIDU_AUTH_CODE_HINT = (
    "请粘贴 Access Token，或打开「打开授权页」从跳转链接复制 access_token= 后的内容。"
    "32 位授权码仅在使用自配 client_secret 时可用"
)


def looks_like_baidu_auth_code(value: str) -> bool:
    return bool(_BAIDU_AUTH_CODE_RE.match(value.strip()))


def _reject_baidu_auth_code(token: str) -> tuple[bool, str | None] | None:
    if looks_like_baidu_auth_code(token):
        return False, _BAIDU_AUTH_CODE_HINT
    return None


async def validate_baidu_access_token(access_token: str) -> tuple[bool, str | None]:
    """Return (ok, error_message)."""
    token = access_token.strip()
    if not token:
        return False, "Token 不能为空"
    rejected = _reject_baidu_auth_code(token)
    if rejected is not None:
        return rejected
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.get(BAIDU_USERINFO_URL, params={"access_token": token})
        data = r.json()
    except Exception as exc:
        return False, str(exc)
    if not isinstance(data, dict):
        return False, "百度 Token 校验失败"
    if data.get("error_code"):
        msg = str(data.get("error_msg") or "Access token invalid or no longer valid")
        if "invalid" in msg.lower() or data.get("error_code") == 110:
            return (
                False,
                "Token 无效或已过期。请打开授权页重新授权，粘贴新的 32 位授权码",
            )
        return False, msg
    return True, None


def validate_baidu_access_token_sync(access_token: str) -> tuple[bool, str | None]:
    token = access_token.strip()
    if not token:
        return False, "Token 不能为空"
    rejected = _reject_baidu_auth_code(token)
    if rejected is not None:
        return rejected
    try:
        with httpx.Client(timeout=15.0) as client:
            r = client.get(BAIDU_USERINFO_URL, params={"access_token": token})
        data = r.json()
    except Exception as exc:
        return False, str(exc)
    if not isinstance(data, dict):
        return False, "百度 Token 校验失败"
    if data.get("error_code"):
        msg = str(data.get("error_msg") or "Access token invalid or no longer valid")
        if "invalid" in msg.lower() or data.get("error_code") == 110:
            return (
                False,
                "Token 无效或已过期。请打开授权页重新授权，粘贴新的 32 位授权码",
            )
        return False, msg
    return True, None


# Baidu MCP SSE endpoint does not support POST tools/list; probe returns this static list.
BAIDU_PROBE_TOOLS: list[dict[str, str]] = [
    {"name": "list_files", "description": "列出网盘目录下的文件与文件夹"},
    {"name": "search_files", "description": "按关键词搜索网盘文件"},
    {"name": "get_file_meta", "description": "获取文件元信息与下载链接"},
]


def baidu_probe_tools() -> list[dict[str, str]]:
    return list(BAIDU_PROBE_TOOLS)
