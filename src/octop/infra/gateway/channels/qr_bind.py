"""WeCom / WeChat QR bind helpers (shared by API and CLI)."""

from __future__ import annotations

import asyncio
import platform
from typing import Any

import httpx


def wecom_plat_code() -> int:
    system = platform.system().lower()
    if system == "darwin":
        return 1
    if system == "windows":
        return 2
    if system == "linux":
        return 3
    return 0


async def wecom_qr_generate() -> dict[str, str]:
    url = f"https://work.weixin.qq.com/ai/qc/generate?source=octop&plat={wecom_plat_code()}"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
    inner = data.get("data") or {}
    scode = inner.get("scode")
    auth_url = inner.get("auth_url")
    if not scode or not auth_url:
        raise RuntimeError("unexpected WeCom QR response")
    return {"scode": str(scode), "auth_url": str(auth_url)}


async def wecom_qr_poll(scode: str) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            "https://work.weixin.qq.com/ai/qc/query_result",
            params={"scode": scode},
        )
        resp.raise_for_status()
        data = resp.json()
    inner = data.get("data") or {}
    status = inner.get("status", "pending")
    if status == "success":
        bot_info = inner.get("bot_info") or {}
        bot_id = bot_info.get("botid", "")
        secret = bot_info.get("secret", "")
        if not bot_id or not secret:
            return {"status": "error", "reason": "QR scan succeeded but bot info is missing"}
        return {"status": "success", "bot_id": bot_id, "secret": secret}
    return {"status": status}


async def weixin_qr_generate() -> dict[str, str]:
    try:
        from harness_gateway.channels.weixin.login_qr import WeixinQRLogin
    except ImportError as exc:
        raise RuntimeError(
            "WeChat QR login requires harness-gateway with weixin channel support."
        ) from exc
    login = WeixinQRLogin()
    result = await login.fetch_qr_code()
    return {
        "qrcode_token": str(result.qrcode),
        "qrcode_url": str(result.qrcode_img_content),
    }


async def weixin_qr_poll(qrcode_token: str) -> dict[str, Any]:
    try:
        from harness_gateway.channels.weixin.login_qr import WeixinQRLogin
    except ImportError as exc:
        raise RuntimeError(
            "WeChat QR login requires harness-gateway with weixin channel support."
        ) from exc
    login = WeixinQRLogin()
    try:
        result = await asyncio.wait_for(login.wait_for_login(qrcode_token), timeout=60.0)
    except TimeoutError:
        return {"status": "wait"}
    if not result.connected:
        return {"status": "error", "message": result.message}
    return {
        "status": "success",
        "account_id": result.account_id,
        "token": result.bot_token,
        "base_url": result.base_url,
    }
