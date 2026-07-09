#!/usr/bin/env python3
# Copyright (C) 2025 Tencent. All rights reserved.
#
# This software is independently developed by Tencent Lighthouse Team.
# Unauthorized copying, modification, distribution, or commercial use
# of this software, in whole or in part, is strictly prohibited.
# Violators will be held liable under applicable laws.
#
# Author: Tencent Lighthouse Team
"""Feishu / Lark Open Platform — auto-create enterprise bot.

Usage:
    python -m octop.infra.channels.bot_creators.feishu_bot_creator init
    python -m octop.infra.channels.bot_creators.feishu_bot_creator create [--platform feishu|lark]
    python -m octop.infra.channels.bot_creators.feishu_bot_creator cleanup

Migration note (2026-05-22)
---------------------------
This script previously drove Chrome via ``playwright.sync_api``. It has been
rewritten on top of ``harness-browser`` (pure CDP) so finnie no longer needs
Playwright as a runtime dependency for bot creation.

Key changes vs. the Playwright version:

* ``BrowserSession.create(profile="octop-feishu-bot")`` replaces
  ``pw.chromium.connect_over_cdp(...)``. The harness session reuses an
  existing Chrome on the same profile or launches one as needed.
* ``page.evaluate`` → ``sess.eval_js``
* ``page.goto/reload`` → ``sess.navigate / sess.reload``
* ``page.on("request"/"response")`` → CDP ``Network.*`` event listeners
* ``page.context.cookies()`` → CDP ``Network.getAllCookies``
* ``page.request.post/get`` → ``httpx.AsyncClient`` with cookies harvested
  from CDP — this preserves Feishu's CSRF / cookie-bound API contract while
  removing the Playwright dependency.
* The whole top-level dependency bootstrap (``_ensure_pip``,
  ``_install_system_deps``, ``ensure_playwright_browsers``) is gone — the
  package's normal install flow already handles ``harness-browser``;
  Chromium is provided by ``octop install-browsers`` (Playwright's
  installer is the only thing left from the old stack).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import random
import ssl
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, cast

import httpx
from harness_browser import BrowserSession

# ============================================================
# Force stdout line-buffered / write-through
# ============================================================
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(write_through=True)


# ============================================================
# Platform config (feishu / lark)
# ============================================================
PLATFORM = "feishu"

_PLATFORM_CONFIGS = {
    "feishu": {
        "base_url": "https://open.feishu.cn",
        "login_url": (
            "https://accounts.feishu.cn/accounts/page/login"
            "?app_id=7&no_trap=1"
            "&redirect_uri=https%3A%2F%2Fopen.feishu.cn%2Fapp"
        ),
        "accounts_host": "accounts.feishu.cn",
        "open_host": "open.feishu.cn",
        "admin_audit_url": "https://feishu.cn/admin/appCenter/audit",
        "primary_lang": "zh_cn",
        "default_greeting": "Hi，我是你刚刚使用 Octop 创建的飞书机器人，你现在可以跟我聊天了！",
        "state_file_prefix": "octop-feishu-bot",
        "profile_name": "octop-feishu-bot",
        "qr_default": True,
    },
    "lark": {
        "base_url": "https://open.larksuite.com",
        "login_url": (
            "https://accounts.larksuite.com/accounts/page/login"
            "?app_id=7&no_trap=1"
            "&redirect_uri=https%3A%2F%2Fopen.larksuite.com%2F%3Flang%3Dzh-CN"
        ),
        "accounts_host": "accounts.larksuite.com",
        "open_host": "open.larksuite.com",
        "admin_audit_url": "https://larksuite.com/admin/appCenter/audit",
        "primary_lang": "en_us",
        "default_greeting": "Hi, I'm the bot you just created with Octop. You can chat with me now!",
        "state_file_prefix": "octop-lark-bot",
        "profile_name": "octop-lark-bot",
        "qr_default": False,
    },
}


def _pcfg(key: str) -> Any:
    return _PLATFORM_CONFIGS[PLATFORM][key]


# ============================================================
# Constants
# ============================================================
LOGIN_TIMEOUT = 90
POLL_INTERVAL = 2
QR_MAX_RETRIES = 3

DEFAULT_AVATAR_URL = "https://cloudcache.tencent-cloud.com/qcloud/ui/static/other_external_resource/4e9ca8c5-0ce4-44a2-8c7c-4f8f43f9e73a.png"

WEBSOCKET_POLL_INTERVAL = 3
WEBSOCKET_POLL_TIMEOUT = 90

STATE_DIR = "/tmp"

BOT_PERMISSIONS = [
    "im:message",
    "im:message.p2p_msg:readonly",
    "im:message.group_at_msg:readonly",
    "im:message:send_as_bot",
    "im:resource",
    "im:message.group_msg",
    "im:message:readonly",
    "im:message:update",
    "im:message:recall",
    "im:message.reactions:read",
    "contact:user.base:readonly",
    "contact:contact.base:readonly",
    "docx:document:readonly",
    "docx:document",
    "docx:document.block:convert",
    "wiki:wiki:readonly",
    "wiki:wiki",
    "bitable:app:readonly",
    "bitable:app",
    "task:task:read",
    "task:task:write",
]

BOT_PERMISSIONS_NEED_AUDIT = [
    "drive:drive:readonly",
    "drive:drive",
]


def _gen_bot_name() -> str:
    if PLATFORM == "lark":
        return f"Octop Bot-{random.randint(1000, 9999)}"
    return f"Octop机器人-{random.randint(1000, 9999)}"


def _state_file() -> str:
    return os.path.join(STATE_DIR, f"{_pcfg('state_file_prefix')}-creator-state.json")


# ============================================================
# State file
# ============================================================
def _save_state(data: dict[str, Any]) -> None:
    with open(_state_file(), "w") as f:
        json.dump(data, f, ensure_ascii=False)


# ============================================================
# Structured JSON output (stdout)
# ============================================================
def _emit(action: str, level: str, step: str, message: str, **extra: Any) -> None:
    record = {
        "action": action,
        "level": level,
        "step": step,
        "message": message,
        "ts": int(time.time()),
    }
    record.update(extra)
    print(json.dumps(record, ensure_ascii=False), flush=True)


def _log_info(step: str, message: str, **extra: Any) -> None:
    _emit("log", "info", step, message, **extra)


def _log_success(step: str, message: str, **extra: Any) -> None:
    _emit("log", "success", step, message, **extra)


def _log_warn(step: str, message: str, **extra: Any) -> None:
    _emit("log", "warn", step, message, **extra)


def _log_error(step: str, message: str, **extra: Any) -> None:
    _emit("log", "error", step, message, **extra)


def _emit_progress(step: str, message: str, current: int, total: int) -> None:
    _emit("progress", "info", step, message, current=current, total=total)


def _emit_finish(message: str, data: dict[str, Any]) -> None:
    _emit("finish", "success", "finish", message, data=data)


def _emit_error(step: str, message: str) -> None:
    _emit("finish", "error", step, message)


# ============================================================
# Avatar / greeting helpers (no browser)
# ============================================================
def _download_avatar(avatar_url: str = "") -> str:
    url = avatar_url or DEFAULT_AVATAR_URL
    avatar_path = os.path.join(STATE_DIR, f"{_pcfg('state_file_prefix')}-avatar.png")
    if not avatar_url and os.path.isfile(avatar_path) and os.path.getsize(avatar_path) > 0:
        _log_info("create_app", f"Using cached avatar: {avatar_path}")
        return avatar_path

    _log_info("create_app", f"Downloading avatar: {url}")
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, context=ctx) as resp:
            data = resp.read()
        with open(avatar_path, "wb") as f:
            f.write(data)
        _log_info("create_app", f"Avatar downloaded: {len(data)} bytes")
        return avatar_path
    except Exception as e:
        _log_warn("create_app", f"Avatar download failed: {e}")
        return ""


def _send_greeting(app_id: str, app_secret: str, open_id: str, greeting: str = "") -> None:
    _log_info("greeting", "Sending initial greeting message")
    greeting = greeting or _pcfg("default_greeting")
    base_url = _pcfg("base_url")

    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    token_payload = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
    token_req = urllib.request.Request(
        f"{base_url}/open-apis/auth/v3/tenant_access_token/internal",
        data=token_payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(token_req, context=ctx) as resp:
            token_data = json.loads(resp.read())
        token = token_data.get("tenant_access_token")
        if not token:
            return
    except Exception:
        return

    send_payload = json.dumps(
        {
            "receive_id": open_id,
            "msg_type": "text",
            "content": json.dumps({"text": greeting}),
            "uuid": str(uuid.uuid4()),
        }
    ).encode()
    send_req = urllib.request.Request(
        f"{base_url}/open-apis/im/v1/messages?receive_id_type=open_id",
        data=send_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    try:
        with urllib.request.urlopen(send_req, context=ctx) as resp:
            resp.read()
    except Exception:
        pass


# ============================================================
# Browser helpers — thin wrappers around harness-browser
# ============================================================
async def _navigate(sess: BrowserSession, url: str) -> bool:
    """Navigate, returning True on success."""
    try:
        result = await sess.navigate(url)
        return bool(result.success)
    except Exception as e:
        _log_warn("login", f"Navigate failed: {e}")
        return False


async def _eval(sess: BrowserSession, expr: str) -> Any:
    """Evaluate a JS expression and decode the JSON-encoded result string."""
    try:
        result = await sess.eval_js(expr)
        if not result.success:
            return None
        # eval_js returns JSON-encoded string (e.g. '"hello"' or '42').
        raw = result.content if isinstance(result.content, str) else ""
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            return raw
    except Exception:
        return None


async def _current_url(sess: BrowserSession) -> str:
    val = await _eval(sess, "location.href")
    return str(val) if val else ""


async def _get_cookies(sess: BrowserSession, urls: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch all cookies for the given URLs via CDP Network.getAllCookies.

    Falls back to ``Network.getCookies`` if ``urls`` are specified.
    """
    client = sess._internal.client
    try:
        if urls:
            result = await client.send("Network.getCookies", {"urls": urls})
        else:
            result = await client.send("Network.getAllCookies")
        cookies = result.get("cookies") or []
        return list(cookies)
    except Exception:
        return []


def _cookie_header(cookies: list[dict[str, Any]]) -> str:
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies if c.get("name"))


# ============================================================
# Network capture — extract CSRF token from outgoing requests
# ============================================================
class _NetworkCapture:
    """Subscribe to CDP Network events to capture the CSRF token.

    Mirrors the previous Playwright ``page.on("request" / "response")``
    behaviour. The token is read out of ``X-CSRF-Token`` request headers
    seen on requests targeting ``open_host``.
    """

    def __init__(self, sess: BrowserSession, open_host: str) -> None:
        self._sess = sess
        self._open_host = open_host
        self.csrf_token: str | None = None
        self._on_request_listeners: list[Any] = []
        self._on_response_listeners: list[Any] = []

    async def install(self) -> None:
        client = self._sess._internal.client
        await client.send("Network.enable")

        async def _on_req(params: dict[str, Any]) -> None:
            req = params.get("request", {}) or {}
            url = req.get("url", "")
            if self._open_host not in url:
                return
            headers = req.get("headers", {}) or {}
            for k, v in headers.items():
                if k.lower() == "x-csrf-token" and v:
                    self.csrf_token = str(v)
                    break

        client.on("Network.requestWillBeSent", _on_req)

    def add_response_listener(self, listener: Any) -> None:
        """Register a callback for ``Network.responseReceived`` events.

        The callback receives the raw CDP params dict.  Use
        ``remove_response_listener`` for cleanup.
        """
        client = self._sess._internal.client
        client.on("Network.responseReceived", listener)
        self._on_response_listeners.append(listener)

    def remove_response_listener(self, listener: Any) -> None:
        client = self._sess._internal.client
        client.off("Network.responseReceived", listener)
        if listener in self._on_response_listeners:
            self._on_response_listeners.remove(listener)


async def _fetch_response_body(sess: BrowserSession, request_id: str) -> dict[str, Any] | None:
    """Pull a response body via CDP and parse it as JSON.

    Used by the QR login poller in lieu of Playwright's ``resp.json()``.
    """
    try:
        client = sess._internal.client
        result = await client.send("Network.getResponseBody", {"requestId": request_id})
        body = result.get("body", "")
        if result.get("base64Encoded"):
            import base64

            body = base64.b64decode(body).decode("utf-8", errors="replace")
        return cast(dict[str, Any] | None, json.loads(body))
    except Exception:
        return None


# ============================================================
# FeishuBotCreator — pure HTTP API wrapper, no browser interactions
# ============================================================
class FeishuBotCreator:
    """Creates a Feishu/Lark bot by hitting the developer-platform JSON API.

    The class does not use the browser directly; it relies on:
    * ``capture.csrf_token`` — populated by the ``_NetworkCapture`` listener
      when the page makes any authenticated request.
    * ``cookies`` — harvested from CDP and sent verbatim with each request.

    All HTTP traffic is plain ``httpx.AsyncClient`` with the same headers
    a real browser would send.
    """

    def __init__(
        self,
        sess: BrowserSession,
        capture: _NetworkCapture,
    ) -> None:
        self._sess = sess
        self._capture = capture
        self._base_url = _pcfg("base_url")
        self._api_base = f"{self._base_url}/developers/v1"
        self._app_page = f"{self._base_url}/app"
        self.app_id: str | None = None
        self.app_secret: str | None = None
        self.version_id: str | None = None
        self.publish_fail_reason: str = ""
        self.audit_url: str | None = None

    async def _csrf(self) -> str | None:
        if self._capture.csrf_token:
            return self._capture.csrf_token
        # Try window.csrfToken
        token = await _eval(self._sess, "window.csrfToken || ''")
        if token:
            self._capture.csrf_token = str(token)
            return self._capture.csrf_token
        # Try cookies
        cookies = await _get_cookies(self._sess, [self._base_url])
        cookie_map = {c["name"]: c["value"] for c in cookies}
        token = (
            cookie_map.get("lark_oapi_csrf_token")
            or cookie_map.get("lgw_csrf_token")
            or cookie_map.get("swp_csrf_token")
        )
        if token:
            self._capture.csrf_token = token
        return self._capture.csrf_token

    async def _headers(self, *, with_body: bool = False) -> dict[str, str]:
        h: dict[str, str] = {"accept": "*/*", "x-timezone-offset": "-480"}
        if with_body:
            h.update(
                {
                    "content-type": "application/json",
                    "origin": self._base_url,
                    "referer": self._app_page,
                }
            )
        csrf = await self._csrf()
        if csrf:
            h["x-csrf-token"] = csrf
        return h

    async def _client(self) -> httpx.AsyncClient:
        cookies = await _get_cookies(self._sess, [self._base_url])
        cookie_jar = {c["name"]: c["value"] for c in cookies}
        return httpx.AsyncClient(
            cookies=cookie_jar,
            timeout=30.0,
            verify=False,
        )

    async def _post(self, url: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        try:
            headers = await self._headers(with_body=True)
            async with await self._client() as c:
                resp = await c.post(url, json=payload, headers=headers)
                return cast(dict[str, Any] | None, resp.json())
        except Exception as e:
            _log_warn("api", f"POST {url} failed: {e}")
            return None

    async def _get(self, url: str) -> dict[str, Any] | None:
        try:
            headers = await self._headers()
            async with await self._client() as c:
                resp = await c.get(url, headers=headers)
                return cast(dict[str, Any] | None, resp.json())
        except Exception as e:
            _log_warn("api", f"GET {url} failed: {e}")
            return None

    def _ok(
        self, body: dict[str, Any] | None, step: str, log_step: str = ""
    ) -> dict[str, Any] | None:
        if body is None:
            return None
        if body.get("code") != 0:
            if log_step:
                _log_error(
                    log_step, f"{step} failed: code={body.get('code')}, msg={body.get('msg')}"
                )
            return None
        return body

    @staticmethod
    def _build_multipart(fields: dict[str, Any], files: dict[str, Any]) -> tuple[bytes, str]:
        boundary = f"----WebKitFormBoundary{uuid.uuid4().hex[:16]}"
        parts: list[bytes] = []
        for key, value in fields.items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode())
            parts.append(f"{value}\r\n".encode())
        for key, (filename, data, content_type) in files.items():
            parts.append(f"--{boundary}\r\n".encode())
            parts.append(
                f'Content-Disposition: form-data; name="{key}"; filename="{filename}"\r\n'.encode()
            )
            parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
            parts.append(data)
            parts.append(b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"

    async def _upload_avatar(self, avatar_path: str) -> str | None:
        with open(avatar_path, "rb") as f:
            img_data = f.read()

        csrf = await self._csrf()
        if not csrf:
            return None

        cookies = await _get_cookies(self._sess, [self._base_url])
        cookie_str = _cookie_header(cookies)

        body, content_type = self._build_multipart(
            fields={
                "uploadType": "4",
                "isIsv": "false",
                "scale": '{"width":240,"height":240}',
            },
            files={
                "file": (str(uuid.uuid4()), img_data, "image/png"),
            },
        )

        headers = {
            "Accept": "*/*",
            "Content-Type": content_type,
            "Cookie": cookie_str,
            "Origin": self._base_url,
            "Referer": self._app_page,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/145.0.0.0 Safari/537.36"
            ),
            "x-csrf-token": csrf,
            "x-timezone-offset": "-480",
        }

        try:
            async with httpx.AsyncClient(timeout=60.0, verify=False) as c:
                resp = await c.post(
                    f"{self._api_base}/app/upload/image",
                    content=body,
                    headers=headers,
                )
                result = resp.json()
        except Exception:
            return None

        if result.get("code") != 0:
            return None
        return cast(str | None, result["data"].get("url", ""))

    # -- Steps --------------------------------------------------------------

    async def step1_create_app(self, name: str, desc: str, avatar_path: str) -> bool:
        _log_info("create_app", f"Creating enterprise app: {name}")
        if avatar_path and os.path.isfile(avatar_path):
            _log_info("create_app", f"Uploading avatar: {os.path.basename(avatar_path)}")
            avatar_url = await self._upload_avatar(avatar_path) or ""
        else:
            avatar_url = ""

        lang = _pcfg("primary_lang")
        body = await self._post(
            f"{self._api_base}/app/create",
            {
                "appSceneType": 0,
                "name": name,
                "desc": desc,
                "avatar": avatar_url,
                "i18n": {lang: {"name": name, "description": desc}},
                "primaryLang": lang,
            },
        )
        if not self._ok(body, "Create app", "create_app"):
            return False
        self.app_id = body["data"]["ClientID"]  # type: ignore[index]
        _log_success("create_app", "App created", app_id=self.app_id)
        return True

    async def step2_get_credentials(self) -> bool:
        _log_info("credential", "Getting app credentials")
        body = await self._get(f"{self._api_base}/secret/{self.app_id}")
        if not self._ok(body, "Get App Secret", "credential"):
            return False
        d = body.get("data", {})  # type: ignore[union-attr]
        self.app_secret = (
            d.get("appSecret") or d.get("app_secret") or d.get("secret") or d.get("AppSecret")
        )
        if not self.app_secret:
            _log_error("credential", f"App Secret not found, keys={list(d.keys())}")
            return False
        _log_success(
            "credential", "Credentials obtained", app_id=self.app_id, app_secret=self.app_secret
        )
        return True

    async def step3_add_bot(self) -> bool:
        _log_info("bot_ability", "Enabling bot capability")
        body = await self._post(f"{self._api_base}/robot/switch/{self.app_id}", {"enable": True})
        if self._ok(body, "Enable bot", "bot_ability") is not None:
            _log_success("bot_ability", "Bot capability enabled")
            return True
        return False

    async def step4_event_mode(self) -> bool:
        _log_info("event_mode", "Switching event mode to WebSocket")
        deadline = time.time() + WEBSOCKET_POLL_TIMEOUT
        attempt = 0
        total = WEBSOCKET_POLL_TIMEOUT // WEBSOCKET_POLL_INTERVAL
        while time.time() < deadline:
            attempt += 1
            body = await self._post(
                f"{self._api_base}/event/switch/{self.app_id}", {"eventMode": 4}
            )
            if body and body.get("code") == 10068:
                _emit_progress(
                    "event_mode",
                    "Waiting for WebSocket connection...",
                    current=attempt,
                    total=total,
                )
                await asyncio.sleep(WEBSOCKET_POLL_INTERVAL)
                continue
            if self._ok(body, "Switch event mode → WebSocket(4)", "event_mode") is not None:
                _log_success("event_mode", "Event mode switched")
                return True
            return False
        _log_error("event_mode", f"WebSocket connection timeout ({WEBSOCKET_POLL_TIMEOUT}s)")
        return False

    async def step5_add_event(self) -> bool:
        _log_info("event", "Adding im.message.receive_v1 event")
        ev = await self._get(f"{self._api_base}/event/{self.app_id}")
        mode = ev.get("data", {}).get("eventMode", 1) if ev and ev.get("code") == 0 else 1
        body = await self._post(
            f"{self._api_base}/event/update/{self.app_id}",
            {
                "operation": "add",
                "events": ["im.message.receive_v1"],
                "eventMode": mode,
            },
        )
        if not self._ok(body, "Add im.message.receive_v1", "event"):
            return False
        verify = await self._get(f"{self._api_base}/event/{self.app_id}")
        if verify and verify.get("code") == 0:
            events = verify["data"].get("events", [])
            if "im.message.receive_v1" in events:
                _log_success("event", "im.message.receive_v1 added")
            else:
                _log_warn("event", f"im.message.receive_v1 not in event list: {events}")
        return True

    async def step6_callback_mode(self) -> bool:
        _log_info("callback", "Configuring long connection callback")
        deadline = time.time() + WEBSOCKET_POLL_TIMEOUT
        attempt = 0
        total = WEBSOCKET_POLL_TIMEOUT // WEBSOCKET_POLL_INTERVAL
        while time.time() < deadline:
            attempt += 1
            body = await self._post(
                f"{self._api_base}/callback/switch/{self.app_id}", {"callbackMode": 4}
            )
            if body and body.get("code") == 10068:
                _emit_progress(
                    "callback", "Waiting for WebSocket connection...", current=attempt, total=total
                )
                await asyncio.sleep(WEBSOCKET_POLL_INTERVAL)
                continue
            if self._ok(body, "Switch callback mode → long connection(4)", "callback") is not None:
                _log_success("callback", "Callback mode switched")
                return True
            return False
        _log_error("callback", f"WebSocket connection timeout ({WEBSOCKET_POLL_TIMEOUT}s)")
        return False

    async def step7_permissions(self) -> bool:
        _log_info("basic_perm", "Importing permissions")
        body = await self._get(f"{self._api_base}/scope/all/{self.app_id}")
        if not self._ok(body, "Get permission list", "basic_perm"):
            return False
        name_to_id: dict[str, str] = {}
        for s in body.get("data", {}).get("scopes", []):  # type: ignore[union-attr]
            name = s.get("name") or s.get("scopeName", "")
            sid = s.get("id", "")
            if name and sid:
                name_to_id[name] = str(sid)
        ids = [name_to_id[n] for n in BOT_PERMISSIONS if n in name_to_id]
        missing = [n for n in BOT_PERMISSIONS if n not in name_to_id]
        _log_info("basic_perm", f"Matched {len(ids)}/{len(BOT_PERMISSIONS)} permissions")
        if missing:
            _log_warn(
                "basic_perm",
                f"{len(missing)} permissions not matched: {json.dumps(missing, ensure_ascii=False)}",
            )
        if not ids:
            _log_error("basic_perm", "No available permission IDs")
            return False
        body = await self._post(
            f"{self._api_base}/scope/update/{self.app_id}",
            {
                "clientId": self.app_id,
                "appScopeIDs": ids,
                "userScopeIDs": [],
                "scopeIds": [],
                "operation": "add",
            },
        )
        if self._ok(body, "Batch add permissions", "basic_perm") is not None:
            _log_success("basic_perm", "Permissions added")
            return True
        return False

    async def _get_scope_name_to_id(self) -> dict[str, str]:
        body = await self._get(f"{self._api_base}/scope/all/{self.app_id}")
        if not self._ok(body, "Get permission list", "permission"):
            return {}
        name_to_id: dict[str, str] = {}
        for s in body.get("data", {}).get("scopes", []):  # type: ignore[union-attr]
            name = s.get("name") or s.get("scopeName", "")
            sid = s.get("id", "")
            if name and sid:
                name_to_id[name] = str(sid)
        return name_to_id

    async def step_add_audit_permissions(self) -> dict[str, Any]:
        result: dict[str, Any] = {"added": False, "need_audit": False, "audit_url": None}
        name_to_id = await self._get_scope_name_to_id()
        if not name_to_id:
            _log_error("advanced_perm", "Failed to get permission map")
            return result
        ids = [name_to_id[n] for n in BOT_PERMISSIONS_NEED_AUDIT if n in name_to_id]
        missing = [n for n in BOT_PERMISSIONS_NEED_AUDIT if n not in name_to_id]
        if missing:
            _log_warn("advanced_perm", f"Advanced permissions not matched: {missing}")
        if not ids:
            result["added"] = True
            return result

        body = await self._post(
            f"{self._api_base}/scope/update/{self.app_id}",
            {
                "clientId": self.app_id,
                "appScopeIDs": ids,
                "userScopeIDs": [],
                "scopeIds": [],
                "operation": "add",
            },
        )
        if not self._ok(body, "Add advanced permissions", "permission"):
            return result
        result["added"] = True

        audit_url = _pcfg("admin_audit_url")
        _log_info("advanced_perm", "Publishing advanced permissions...")
        publish_ok = await self.step8_publish(version="1.0.1", silent=True)

        if not publish_ok:
            _log_error("advanced_perm", "Advanced permission publish failed")
            result["need_audit"] = True
            result["audit_url"] = self.audit_url or audit_url
            return result

        await asyncio.sleep(2)

        info = await self._get(f"{self._api_base}/app/{self.app_id}")
        if info and info.get("code") == 0:
            data = info.get("data", {})
            audit_version_id = data.get("auditVersionId")
            audit_status = data.get("auditStatus")
            is_new_version = audit_version_id and str(audit_version_id) == str(self.version_id)
            if is_new_version and audit_status == 100:
                _log_success("advanced_perm", "Advanced permissions published")
                result["need_audit"] = False
            else:
                _log_error("advanced_perm", "Auto-publish advanced permissions failed")
                result["need_audit"] = True
                result["audit_url"] = audit_url
        else:
            _log_error("advanced_perm", "Auto-publish advanced permissions failed")
            result["need_audit"] = True
            result["audit_url"] = audit_url

        return result

    async def step8_publish(self, version: str = "1.0.0", silent: bool = False) -> bool:
        self.publish_fail_reason = ""
        self.audit_url = None
        admin_audit_url = _pcfg("admin_audit_url")
        changelog = "Initial version" if PLATFORM == "lark" else "初始版本"

        if not silent:
            _log_info("publish", "Publishing...")
        body = await self._post(
            f"{self._api_base}/app_version/create/{self.app_id}",
            {
                "clientId": self.app_id,
                "appVersion": version,
                "changeLog": changelog,
                "autoPublish": False,
                "pcDefaultAbility": "bot",
                "mobileDefaultAbility": "bot",
            },
        )
        if not self._ok(body, "Create version", "publish"):
            self.publish_fail_reason = f"Create version failed: code={(body or {}).get('code')}, msg={(body or {}).get('msg')}"
            return False
        self.version_id = (
            body.get("data", {}).get("versionId") or body["data"].get("version_id")  # type: ignore[union-attr,index]
        )
        if not self.version_id:
            _log_error("publish", "Publish failed")
            self.publish_fail_reason = "Version ID not obtained"
            return False

        await asyncio.sleep(1)
        body = await self._post(
            f"{self._api_base}/publish/commit/{self.app_id}/{self.version_id}", {}
        )
        if not self._ok(body, "Submit for review", "publish"):
            self.publish_fail_reason = (
                f"Submit failed: code={(body or {}).get('code')}, msg={(body or {}).get('msg')}"
            )
            return False

        await asyncio.sleep(1)
        body = await self._post(
            f"{self._api_base}/publish/release/{self.app_id}/{self.version_id}",
            {"clientId": self.app_id, "versionId": self.version_id},
        )
        release_code = (body or {}).get("code")

        if release_code == 0:
            if not silent:
                _log_success("publish", "Published", version_id=self.version_id)
            return True

        if release_code == 10002:
            await asyncio.sleep(1)
            info = await self._get(f"{self._api_base}/app/{self.app_id}")
            if info and info.get("code") == 0:
                app_status = info.get("data", {}).get("appStatus")
                if app_status == 1:
                    if not silent:
                        _log_success("publish", "Published", version_id=self.version_id)
                    return True
                self.audit_url = admin_audit_url
                _log_error("publish", "Auto-publish failed")
                self.publish_fail_reason = (
                    f"Admin approval required: appStatus={app_status}, "
                    f"release code={release_code}, msg={(body or {}).get('msg')}"
                )
                return False
            if not silent:
                _log_success("publish", "Published", version_id=self.version_id)
            return True

        if release_code is None:
            await asyncio.sleep(1)
            info = await self._get(f"{self._api_base}/app/{self.app_id}")
            if info and info.get("code") == 0:
                app_status = info.get("data", {}).get("appStatus")
                if app_status == 1:
                    if not silent:
                        _log_success("publish", "Published", version_id=self.version_id)
                    return True

        fail_msg = (body or {}).get("msg", "Unknown error")
        _log_error("publish", f"Publish failed: {fail_msg}")
        self.publish_fail_reason = f"Publish failed: code={release_code}, msg={fail_msg}"
        return False

    async def step9_get_owner_open_id(self) -> str | None:
        _log_info("owner", "Getting app owner open_id")
        if not self.app_id or not self.app_secret:
            _log_warn("owner", "Missing app_id or app_secret, skipping")
            return None

        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        payload = json.dumps({"app_id": self.app_id, "app_secret": self.app_secret}).encode()
        req = urllib.request.Request(
            f"{self._base_url}/open-apis/auth/v3/tenant_access_token/internal",
            data=payload,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, context=ctx) as resp:
                token_data = json.loads(resp.read())
        except Exception:
            _log_error("owner", "Failed to get tenant_access_token")
            return None

        token = token_data.get("tenant_access_token")
        if not token:
            _log_error("owner", "Failed to get tenant_access_token")
            return None

        req2 = urllib.request.Request(
            f"{self._base_url}/open-apis/contact/v3/users?page_size=50&user_id_type=open_id",
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Authorization": f"Bearer {token}",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(req2, context=ctx) as resp:
                user_data = json.loads(resp.read())
        except Exception:
            _log_error("owner", "Failed to query user list")
            return None

        items = user_data.get("data", {}).get("items", [])
        if not items:
            _log_error("owner", "User list is empty")
            return None

        owner = items[0]
        open_id = owner.get("open_id", "")
        name = owner.get("name", "unknown")
        _log_success("owner", f"User: {name}, open_id: {open_id}")
        return cast(str | None, open_id)


# ============================================================
# Command: init  — verify harness-browser + Chromium are available
# ============================================================
def cmd_init() -> None:
    _log_info("init", "Checking dependencies (harness-browser + Chromium)...")

    try:
        import harness_browser  # noqa: F401
    except ImportError:
        _emit_error("init", "harness-browser not installed. Run `pip install harness-browser`.")
        sys.exit(1)

    from harness_browser.cdp.launcher import find_chrome

    if find_chrome() is None:
        _emit_error(
            "init",
            "Chrome/Chromium not found. Run `octop install-browsers` "
            "or install Chrome via your system package manager.",
        )
        sys.exit(1)

    _log_success("init", "Dependencies ready")
    sys.exit(0)


# ============================================================
# Command: create
# ============================================================
async def _cmd_create(avatar_url: str = "", greeting: str = "") -> None:
    base_url = _pcfg("base_url")
    login_url = _pcfg("login_url")
    open_host = _pcfg("open_host")
    accounts_host = _pcfg("accounts_host")
    app_page = f"{base_url}/app"
    admin_audit_url = _pcfg("admin_audit_url")
    platform_label = "Lark" if PLATFORM == "lark" else "飞书"

    _log_info("login", "Starting browser, fetching QR code...")
    _t_qr_total = time.monotonic()

    # ---- Launch harness-browser session ----
    _t_browser = time.monotonic()
    sess: BrowserSession
    try:
        sess = await BrowserSession.create(
            profile=_pcfg("profile_name"),
            mode="auto",
        )
    except Exception as exc:
        _emit_error("login", f"Failed to launch browser: {exc}")
        sys.exit(1)

    _log_info("login", f"Browser ready ({time.monotonic() - _t_browser:.2f}s)")

    # Bind the CDP client once outside the try blocks below so subsequent
    # cleanup steps can still reach it even if an earlier mitigation step
    # fails — otherwise the second ``try`` block would hit ``UnboundLocalError``
    # when trying to call ``Network.clearBrowserCookies``.
    _ua_client = sess._internal.client

    # ---- Anti-headless fingerprint mitigation ------------------------------
    # Feishu's login page returns a stripped-down variant (no QR DOM, no
    # ``.switch-login-mode-box``) when it detects HeadlessChrome via the
    # User-Agent or the ``navigator.webdriver`` flag. Override both via CDP
    # before any navigation so the page renders the standard QR-capable form.
    try:
        # Use a desktop Chrome UA matching the current Chromium major version.
        await _ua_client.send(
            "Network.setUserAgentOverride",
            {
                "userAgent": (
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/145.0.7632.6 Safari/537.36"
                ),
                "acceptLanguage": "zh-CN,zh;q=0.9,en;q=0.8",
                "platform": "Linux x86_64",
            },
        )
        # Hide navigator.webdriver and a few other common automation tells on
        # every new document so SPA navigations stay clean too.
        await _ua_client.send(
            "Page.addScriptToEvaluateOnNewDocument",
            {
                "source": (
                    "Object.defineProperty(navigator, 'webdriver', "
                    "{get: () => undefined});"
                    "Object.defineProperty(navigator, 'languages', "
                    "{get: () => ['zh-CN', 'zh', 'en']});"
                    "Object.defineProperty(navigator, 'plugins', "
                    "{get: () => [1, 2, 3, 4, 5]});"
                ),
            },
        )
        _log_info("login", "Anti-headless fingerprint mitigation applied")
    except Exception as exc:
        _log_info("login", f"Anti-headless mitigation skipped ({exc})")

    # ---- Per-run session cleanup -------------------------------------------
    # ``harness_browser.launch_or_attach`` keeps Chrome alive across runs and
    # *attaches* on the second start instead of launching a fresh process.
    # That means cookies / localStorage from the previous QR attempt persist
    # and cause Feishu to skip the QR form on subsequent runs (e.g. when it
    # sees an existing ``__tcouv__``/session cookie). Clear them via CDP so
    # every QR attempt starts from a clean session.
    try:
        await _ua_client.send("Network.clearBrowserCookies")
        await _ua_client.send("Network.clearBrowserCache")
        _log_info("login", "Session cookies & cache cleared for fresh QR attempt")
    except Exception as exc:
        _log_info("login", f"Session cleanup skipped ({exc})")

    capture = _NetworkCapture(sess, open_host)
    await capture.install()

    async def _cleanup_browser() -> None:
        with contextlib.suppress(Exception):
            await sess.close()

    # ---- QR token capture via CDP responseReceived ----
    state: dict[str, Any] = {"qr_token": None, "qr_token_at": None}

    # Map requestId → url so we can fetch bodies asynchronously when needed.
    request_url_by_id: dict[str, str] = {}

    async def _on_request_will_be_sent(params: dict[str, Any]) -> None:
        rid = params.get("requestId", "")
        url = params.get("request", {}).get("url", "")
        if rid and url:
            request_url_by_id[rid] = url

    sess._internal.client.on("Network.requestWillBeSent", _on_request_will_be_sent)

    async def _on_response(params: dict[str, Any]) -> None:
        rid = params.get("requestId", "")
        url = request_url_by_id.get(rid) or params.get("response", {}).get("url", "")
        if "qrlogin/init" in url:
            body = await _fetch_response_body(sess, rid)
            if body and body.get("code") == 0:
                token = body.get("data", {}).get("step_info", {}).get("token")
                if token:
                    state["qr_token"] = token
                    state["qr_token_at"] = time.monotonic()
                    _log_info(
                        "login",
                        f"QR token acquired ({state['qr_token_at'] - _t_qr_total:.2f}s since start)",
                    )

    capture.add_response_listener(_on_response)

    async def _switch_to_qr_mode() -> None:
        try:
            _t_switch = time.monotonic()
            await asyncio.sleep(2)
            await _eval(
                sess,
                """(() => {
                    const el = document.querySelector('.switch-login-mode-box');
                    if (el) el.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    return true;
                })()""",
            )
            await asyncio.sleep(1.5)
            _log_info("login", f"Switched to QR mode ({time.monotonic() - _t_switch:.2f}s)")
        except Exception:
            _log_info("login", "QR mode switch skipped or failed")

    async def _fetch_qr_token() -> bool:
        state["qr_token"] = None
        _t_fetch = time.monotonic()
        _log_info("login", "Navigating to login page...")
        if not await _navigate(sess, login_url):
            _log_info("login", f"Login page load failed ({time.monotonic() - _t_fetch:.2f}s)")
            return False
        _log_info("login", f"Login page loaded ({time.monotonic() - _t_fetch:.2f}s)")
        if not _pcfg("qr_default"):
            await _switch_to_qr_mode()
        for _ in range(25):
            if state["qr_token"]:
                _log_info(
                    "login", f"QR token ready (first poll) ({time.monotonic() - _t_fetch:.2f}s)"
                )
                return True
            await asyncio.sleep(0.1)

        _log_info("login", "QR token not found in first attempt, reloading page...")
        try:
            await sess.reload()
        except Exception:
            if not await _navigate(sess, login_url):
                _log_info("login", f"Reload failed ({time.monotonic() - _t_fetch:.2f}s)")
                return False
        if not _pcfg("qr_default"):
            await _switch_to_qr_mode()
        for _ in range(25):
            if state["qr_token"]:
                _log_info(
                    "login", f"QR token ready (second poll) ({time.monotonic() - _t_fetch:.2f}s)"
                )
                return True
            await asyncio.sleep(0.2)
        _log_info("login", f"QR token acquisition failed ({time.monotonic() - _t_fetch:.2f}s)")
        return False

    async def _poll_qr_login() -> bool:
        login_state: dict[str, Any] = {"login_ok": False, "scanned": False}

        async def _on_poll_resp(params: dict[str, Any]) -> None:
            rid = params.get("requestId", "")
            url = request_url_by_id.get(rid) or params.get("response", {}).get("url", "")
            if "qrlogin/polling" not in url:
                return
            body = await _fetch_response_body(sess, rid)
            if not body or body.get("code") != 0:
                return
            data = body.get("data", {})
            info = data.get("step_info", {})
            status = info.get("status")
            redirect_url = data.get("redirect_url", "")
            if status == 2 and not login_state["scanned"]:
                login_state["scanned"] = True
                _log_info("login", "Scanned, please confirm on phone")
                _emit_progress("login", "已扫码，请在手机上确认登录", current=0, total=1)
            if redirect_url:
                login_state["login_ok"] = True

        capture.add_response_listener(_on_poll_resp)
        try:
            poll_deadline = time.time() + LOGIN_TIMEOUT
            while time.time() < poll_deadline:
                if login_state["login_ok"]:
                    break
                if login_state["scanned"]:
                    cur = await _current_url(sess)
                    if open_host in cur and accounts_host not in cur:
                        login_state["login_ok"] = True
                        break
                await asyncio.sleep(0.5)
        finally:
            capture.remove_response_listener(_on_poll_resp)
        return bool(login_state["login_ok"])

    # ---- QR retry loop ----
    for attempt in range(1, QR_MAX_RETRIES + 1):
        _log_info("login", f"Fetching QR token (attempt {attempt}/{QR_MAX_RETRIES})...")
        if not await _fetch_qr_token():
            if attempt < QR_MAX_RETRIES:
                _log_warn("login", f"Failed to get QR token, retrying ({attempt}/{QR_MAX_RETRIES})")
                await asyncio.sleep(2)
                continue
            _log_info(
                "login", f"All QR attempts exhausted ({time.monotonic() - _t_qr_total:.2f}s total)"
            )
            await _cleanup_browser()
            _emit_error("login", "Failed to get QR token")
            sys.exit(1)

        _log_info(
            "login",
            f"QR code ready — total acquisition time: {time.monotonic() - _t_qr_total:.2f}s (attempt {attempt})",
        )

        qr_content = {"qrlogin": {"token": state["qr_token"]}}
        _save_state(
            {
                "phase": "create",
                "qr_token": state["qr_token"],
                "qr_content": json.dumps(qr_content),
                "deadline": int(time.time()) + LOGIN_TIMEOUT,
            }
        )
        _emit(
            "show_qrcode",
            "info",
            "login",
            f"Please scan to login {platform_label}",
            content=json.dumps(qr_content, ensure_ascii=False),
        )
        _emit_progress("login", "Waiting for scan...", current=attempt, total=QR_MAX_RETRIES)

        if await _poll_qr_login():
            break

        if attempt < QR_MAX_RETRIES:
            _log_warn("login", f"QR expired, refreshing ({attempt}/{QR_MAX_RETRIES})")
            await asyncio.sleep(1)
        else:
            await _cleanup_browser()
            _emit_error("login", f"{QR_MAX_RETRIES} timeouts, exiting")
            sys.exit(1)

    # ---- Wait for redirect ----
    _log_info("login", "Page redirected to open platform, login successful")
    jump_deadline = time.time() + 15
    while time.time() < jump_deadline:
        cur = await _current_url(sess)
        if open_host in cur and accounts_host not in cur:
            break
        await asyncio.sleep(0.5)
    else:
        await _navigate(sess, app_page)

    _log_success("login", "Login successful!")
    _emit_progress("create", "登录成功，正在自动创建机器人，请稍候…", current=0, total=1)
    await asyncio.sleep(2)

    # ---- Bot creation ----
    bot_name = _gen_bot_name()
    bot_desc = bot_name
    avatar_path = _download_avatar(avatar_url)

    creator = FeishuBotCreator(sess, capture)

    await _navigate(sess, app_page)
    await asyncio.sleep(2)
    csrf = await creator._csrf()
    _log_info("create_app", f"CSRF token: {'obtained' if csrf else 'not obtained, continuing'}")

    if not await creator.step1_create_app(bot_name, bot_desc, avatar_path):
        await _cleanup_browser()
        _emit_error("create_app", "Failed to create app")
        sys.exit(1)

    if not await creator.step2_get_credentials():
        await _cleanup_browser()
        _emit_error("credential", "Failed to get credentials")
        sys.exit(1)

    # orca: credentials are returned via finish event, not written to config
    _log_info("config", "Credentials ready — octop will handle storage")

    _step_error_messages = {
        "step3_add_bot": ("bot_ability", "Failed to enable bot capability"),
        "step4_event_mode": (
            "event_mode",
            "Failed to establish long connection, check if octop is running",
        ),
        "step5_add_event": ("event", "Failed to add message receive event"),
        "step6_callback_mode": (
            "callback",
            "Failed to configure callback, check if octop is running",
        ),
        "step7_permissions": ("basic_perm", "Failed to import permissions"),
    }
    steps = [
        creator.step3_add_bot,
        creator.step4_event_mode,
        creator.step5_add_event,
        creator.step6_callback_mode,
        creator.step7_permissions,
    ]
    for fn in steps:
        if not await fn():
            await _cleanup_browser()
            step_name = fn.__name__
            err_step, err_msg = _step_error_messages.get(
                step_name, (step_name, f"{step_name} failed")
            )
            _emit_error(err_step, err_msg)
            sys.exit(1)

    manage_url = f"{base_url}/app/{creator.app_id}"
    publish_ok = await creator.step8_publish()

    if not publish_ok:
        await _cleanup_browser()
        fail_reason = creator.publish_fail_reason or "Publish failed"
        audit_url = creator.audit_url or admin_audit_url
        msg_lines = [
            f"Current user cannot auto-publish {platform_label} bot, please contact admin for approval.",
            f"Bot name: {bot_name}",
            f"Manage URL: {manage_url}",
            f"Approval URL: {audit_url}",
        ]
        finish_data = {
            "app_id": creator.app_id,
            "app_secret": creator.app_secret,
            "bot_name": bot_name,
            "manage_url": manage_url,
            "audit_url": audit_url,
            "publish_fail_reason": fail_reason,
        }
        _emit("finish", "error", "publish", "\n".join(msg_lines), data=finish_data)
        sys.exit(1)

    _log_info("advanced_perm", "Adding advanced permissions...")
    audit_result = await creator.step_add_audit_permissions()
    open_id = await creator.step9_get_owner_open_id()

    if open_id:
        _send_greeting(creator.app_id or "", creator.app_secret or "", open_id, greeting)
    else:
        _log_warn("owner", "open_id not obtained, skipping greeting")

    await _cleanup_browser()

    result: dict[str, Any] = {
        "app_id": creator.app_id,
        "app_secret": creator.app_secret,
        "bot_name": bot_name,
        "version_id": creator.version_id,
        "open_id": open_id,
        "manage_url": manage_url,
    }

    if audit_result.get("need_audit"):
        audit_url = audit_result.get("audit_url") or admin_audit_url
        result["audit_url"] = audit_url
        result["audit_permissions"] = BOT_PERMISSIONS_NEED_AUDIT
        finish_msg_lines = [
            f"✅ Bot「{bot_name}」created and published.",
            f"Manage URL: {manage_url}",
            "",
            "⚠️ The following advanced permissions require admin approval:",
            "   · View, comment and download all files in cloud space",
            "   · View, comment, edit and manage all files in cloud space",
            f"Contact admin for approval: {audit_url}",
        ]
    else:
        finish_msg_lines = [
            f"✅ Bot「{bot_name}」created and published, all permissions active.",
            f"Manage URL: {manage_url}",
        ]

    _save_state({"phase": "done", **result})
    _emit_finish("\n".join(finish_msg_lines), result)


def cmd_create(avatar_url: str = "", greeting: str = "") -> None:
    asyncio.run(_cmd_create(avatar_url=avatar_url, greeting=greeting))


# ============================================================
# Command: cleanup
# ============================================================
async def _cmd_cleanup() -> None:
    """Close any harness session for the bot profile and remove state file."""
    try:
        from harness_browser.tool_interface import _registry as _hr

        sess = _hr.get(_pcfg("profile_name"))
        if sess is not None:
            with contextlib.suppress(Exception):
                await sess.close()
            _hr.pop(_pcfg("profile_name"), None)
    except Exception:
        pass

    sf = _state_file()
    if os.path.isfile(sf):
        with contextlib.suppress(OSError):
            os.remove(sf)
    _log_success("cleanup", "Cleaned up")


def cmd_cleanup() -> None:
    asyncio.run(_cmd_cleanup())


# ============================================================
# Entry point
# ============================================================
def main() -> None:
    global PLATFORM

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "init":
        cmd_init()
    elif cmd == "create":
        avatar_url = ""
        greeting = ""
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--avatar-url" and i + 1 < len(args):
                avatar_url = args[i + 1]
                i += 2
            elif args[i] == "--greeting" and i + 1 < len(args):
                greeting = args[i + 1]
                i += 2
            elif args[i] == "--platform" and i + 1 < len(args):
                p = args[i + 1].lower()
                if p not in ("feishu", "lark"):
                    _emit_error("main", f"Unsupported platform: {p}, use feishu or lark")
                    sys.exit(1)
                PLATFORM = p
                i += 2
            else:
                i += 1
        cmd_create(avatar_url=avatar_url, greeting=greeting)
    elif cmd == "cleanup":
        args = sys.argv[2:]
        i = 0
        while i < len(args):
            if args[i] == "--platform" and i + 1 < len(args):
                p = args[i + 1].lower()
                if p in ("feishu", "lark"):
                    PLATFORM = p
                i += 2
            else:
                i += 1
        cmd_cleanup()
    else:
        _emit_error("main", f"Unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
