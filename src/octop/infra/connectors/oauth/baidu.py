"""Baidu Netdisk OAuth2 helpers."""

from __future__ import annotations

import hashlib
import secrets
import time
from base64 import urlsafe_b64encode
from typing import Any
from urllib.parse import urlencode

import httpx

from octop.infra.connectors.oauth.builtin import resolve_client

BAIDU_AUTHORIZE_URL = "https://openapi.baidu.com/oauth/2.0/authorize"
BAIDU_TOKEN_URL = "https://openapi.baidu.com/oauth/2.0/token"
# Baidu Netdisk MCP official demo client_id (personal Token auth, no client_secret needed)
BAIDU_MCP_EXPERIENCE_CLIENT_ID = "zF5kkNsCvckX4aIpRdHxpFkcSMxnGZky"


def _pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def resolve_baidu_client_credentials(settings_repo: Any) -> tuple[str, str]:
    return resolve_client(
        "baidu-netdisk",
        settings_repo=settings_repo,
        env_id_key="OCTOP_BAIDU_NETDISK_CLIENT_ID",
        env_secret_key="OCTOP_BAIDU_NETDISK_CLIENT_SECRET",
        settings_id_key="connector.baidu.client_id",
        settings_secret_key="connector.baidu.client_secret",
    )


def start_baidu_oauth(
    *,
    redirect_uri: str,
    state: str,
) -> tuple[str, str]:
    verifier, challenge = _pkce_pair()
    params = {
        "response_type": "code",
        "client_id": "",  # filled by caller
        "redirect_uri": redirect_uri,
        "scope": "basic,netdisk",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return verifier, urlencode(params)


def build_baidu_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    state: str,
    code_challenge: str,
) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": "basic,netdisk",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{BAIDU_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_baidu_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            BAIDU_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        raise ValueError(f"baidu token exchange failed: {data!r}")
    expires_in = int(data.get("expires_in") or 0)
    expires_at = int(time.time()) + expires_in if expires_in else None
    return {
        "access_token": str(data["access_token"]),
        "refresh_token": str(data.get("refresh_token") or ""),
        "expires_at": expires_at,
    }


async def exchange_baidu_oob_code(
    *,
    client_id: str,
    client_secret: str,
    code: str,
) -> dict[str, Any]:
    """Exchange authorization code from Baidu 'oob' (copy-paste) flow."""
    data: dict[str, str] = {
        "grant_type": "authorization_code",
        "code": code.strip(),
        "client_id": client_id,
        "redirect_uri": "oob",
    }
    if client_secret.strip():
        data["client_secret"] = client_secret.strip()
    headers = {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "pan.baidu.com"}
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(BAIDU_TOKEN_URL, data=data, headers=headers)
        if r.status_code >= 400:
            raise ValueError(_baidu_exchange_error_message(r))
        body = r.json()
    if not isinstance(body, dict) or not body.get("access_token"):
        raise ValueError(f"baidu token exchange failed: {body!r}")
    expires_in = int(body.get("expires_in") or 0)
    expires_at = int(time.time()) + expires_in if expires_in else None
    return {
        "access_token": str(body["access_token"]),
        "refresh_token": str(body.get("refresh_token") or ""),
        "expires_at": expires_at,
    }


async def resolve_baidu_pasted_credential(
    *,
    raw: str,
    settings_repo: Any,
) -> dict[str, Any]:
    """Accept a 32-char OOB auth code or an access_token / #access_token= URL."""
    from octop.infra.connectors.baidu_token import looks_like_baidu_auth_code
    from octop.infra.connectors.oauth.registry import _extract_baidu_access_token

    text = (_extract_baidu_access_token(raw) or raw).strip()
    if not text:
        raise ValueError("请填写百度网盘授权码或 Access Token")
    if looks_like_baidu_auth_code(text):
        client_id, client_secret = resolve_baidu_client_credentials(settings_repo)
        if not client_id:
            raise ValueError("百度网盘授权暂不可用，请稍后再试")
        if not client_secret.strip():
            raise ValueError(
                "百度体验应用请使用 Token 授权：打开「打开授权页」登录授权后，"
                "从跳转链接中复制 access_token= 后的完整 Access Token（不是 32 位授权码）"
            )
        return await exchange_baidu_oob_code(
            client_id=client_id,
            client_secret=client_secret,
            code=text,
        )
    return {"access_token": text, "refresh_token": "", "expires_at": None}


def baidu_oob_authorize_url(*, client_id: str) -> str:
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": "oob",
        "scope": "basic,netdisk",
        "display": "popup",
        "qrcode": "1",
        "force_login": "1",
    }
    return f"{BAIDU_AUTHORIZE_URL}?{urlencode(params)}"


def baidu_personal_token_authorize_url(*, client_id: str | None = None) -> str:
    """Implicit grant (response_type=token) — user copies access_token from redirect URL."""
    cid = (client_id or BAIDU_MCP_EXPERIENCE_CLIENT_ID).strip()
    params = {
        "response_type": "token",
        "client_id": cid,
        "redirect_uri": "oob",
        "scope": "basic,netdisk",
        "display": "popup",
        "qrcode": "1",
        "force_login": "1",
    }
    return f"{BAIDU_AUTHORIZE_URL}?{urlencode(params)}"


def _baidu_exchange_error_message(response: httpx.Response) -> str:
    try:
        body = response.json()
        if isinstance(body, dict):
            desc = body.get("error_description") or body.get("error")
            if desc and str(desc).strip():
                return str(desc).strip()
    except Exception:
        pass
    return f"HTTP {response.status_code}"


async def refresh_baidu_token(
    *,
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            BAIDU_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict) or not data.get("access_token"):
        raise ValueError(f"baidu token refresh failed: {data!r}")
    expires_in = int(data.get("expires_in") or 0)
    expires_at = int(time.time()) + expires_in if expires_in else None
    return {
        "access_token": str(data["access_token"]),
        "refresh_token": str(data.get("refresh_token") or refresh_token),
        "expires_at": expires_at,
    }
