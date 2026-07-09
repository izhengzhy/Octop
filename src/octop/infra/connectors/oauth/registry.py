"""Dispatch connector OAuth flows by kind."""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import unquote

from octop.infra.connectors.catalog import get_catalog_entry
from octop.infra.connectors.oauth.baidu import (
    BAIDU_MCP_EXPERIENCE_CLIENT_ID,
    baidu_personal_token_authorize_url,
    build_baidu_authorize_url,
    exchange_baidu_code,
    refresh_baidu_token,
    resolve_baidu_client_credentials,
)
from octop.infra.connectors.oauth.builtin import resolve_client
from octop.infra.connectors.oauth.mcp import (
    build_authorize_url,
    exchange_authorization_code,
    fetch_authorization_metadata,
    issuer_for_kind,
    mcp_oauth_kinds,
    refresh_access_token,
    register_dynamic_client,
)
from octop.infra.connectors.oauth.pkce import new_pkce_pair

OAUTH_CTX_PREFIX = "connector.oauth.ctx."

_BUILTIN_OAUTH_KINDS = frozenset(
    {
        "baidu-netdisk",
        "notion",
        "figma",
    }
)

_AUTH_CODE_PASSTHROUGH_KINDS = frozenset({"tencent-news"})


def _extract_baidu_access_token(text: str) -> str | None:
    trimmed = text.strip()
    if not trimmed:
        return None
    match = re.search(r"access_token=([^&\s#]+)", trimmed, re.I)
    if match:
        try:
            return unquote(match.group(1))
        except Exception:
            return match.group(1)
    return trimmed


def oauth_supported_kinds() -> frozenset[str]:
    return _BUILTIN_OAUTH_KINDS


def save_oauth_ctx(settings_repo: Any, state_id: str, ctx: dict[str, Any]) -> None:
    settings_repo.set(f"{OAUTH_CTX_PREFIX}{state_id}", json.dumps(ctx))


def load_oauth_ctx(settings_repo: Any, state_id: str) -> dict[str, Any]:
    raw = settings_repo.get(f"{OAUTH_CTX_PREFIX}{state_id}")
    if not raw:
        return {}
    data = json.loads(raw)
    return data if isinstance(data, dict) else {}


def delete_oauth_ctx(settings_repo: Any, state_id: str) -> None:
    settings_repo.delete(f"{OAUTH_CTX_PREFIX}{state_id}")


def resolve_figma_client_credentials(settings_repo: Any) -> tuple[str, str]:
    return resolve_client(
        "figma",
        settings_repo=settings_repo,
        env_id_key="OCTOP_FIGMA_CLIENT_ID",
        env_secret_key="OCTOP_FIGMA_CLIENT_SECRET",
        settings_id_key="connector.figma.client_id",
        settings_secret_key="connector.figma.client_secret",
    )


def oauth_ready_for_kind(kind: str, settings_repo: Any) -> bool:
    del settings_repo
    return kind in (
        "notion",
        "figma",
        *_AUTH_CODE_PASSTHROUGH_KINDS,
    )


def oauth_mode_for_kind(kind: str) -> str | None:
    if kind == "notion":
        return "dynamic"
    if kind in _BUILTIN_OAUTH_KINDS:
        return "configured"
    return None


def authorize_url_for_paste(kind: str, settings_repo: Any) -> str | None:
    if kind == "baidu-netdisk":
        client_id, _ = resolve_baidu_client_credentials(settings_repo)
        cid = (client_id or BAIDU_MCP_EXPERIENCE_CLIENT_ID).strip()
        return baidu_personal_token_authorize_url(client_id=cid)
    entry = get_catalog_entry(kind)
    return entry.quick_auth_url if entry else None


def auth_info_for_kind(kind: str, settings_repo: Any) -> dict[str, str | None]:
    entry = get_catalog_entry(kind)
    if entry is None:
        return {
            "authorize_url": None,
            "login_url": None,
            "guide_url": None,
            "manual_url": None,
            "auth_hint": None,
        }
    return {
        "authorize_url": authorize_url_for_paste(kind, settings_repo),
        "login_url": entry.login_url,
        "guide_url": entry.guide_url or entry.doc_url,
        "manual_url": entry.manual_url or entry.guide_url or entry.doc_url,
        "auth_hint": entry.auth_hint,
    }


async def exchange_pasted_auth_code(
    *,
    kind: str,
    code: str,
    settings_repo: Any,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Exchange a user-pasted authorization code (QClaw-style copy-paste flow)."""
    code = code.strip()
    if not code:
        raise ValueError("授权码不能为空")

    if kind in _AUTH_CODE_PASSTHROUGH_KINDS and kind == "tencent-news":
        return {"cookie": code}

    if kind == "baidu-netdisk":
        from octop.infra.connectors.oauth.baidu import resolve_baidu_pasted_credential

        return await resolve_baidu_pasted_credential(raw=code, settings_repo=settings_repo)

    raise ValueError(f"auth code exchange not supported for {kind}")


async def start_oauth(
    *,
    kind: str,
    redirect_uri: str,
    state: str,
    settings_repo: Any,
) -> tuple[str, str, dict[str, Any]]:
    """Return authorize_url, code_verifier, ctx to persist for callback."""
    verifier, challenge = new_pkce_pair()

    if kind == "baidu-netdisk":
        client_id, _ = resolve_baidu_client_credentials(settings_repo)
        if not client_id:
            raise ValueError("百度网盘授权暂不可用，请稍后再试")
        url = build_baidu_authorize_url(
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
        )
        return url, verifier, {"flow": "baidu"}

    if kind in mcp_oauth_kinds():
        issuer = issuer_for_kind(kind)
        metadata = await fetch_authorization_metadata(issuer)
        client_id = ""
        client_secret: str | None = None
        if kind == "figma":
            client_id, client_secret = resolve_figma_client_credentials(settings_repo)
        if not client_id:
            reg = await register_dynamic_client(metadata, issuer=issuer, redirect_uri=redirect_uri)
            client_id = str(reg["client_id"])
            client_secret = str(reg.get("client_secret") or "") or None
        scope = "mcp:connect" if kind == "figma" else None
        url = build_authorize_url(
            metadata,
            client_id=client_id,
            redirect_uri=redirect_uri,
            state=state,
            code_challenge=challenge,
            scope=scope,
        )
        ctx = {
            "flow": "mcp",
            "kind": kind,
            "metadata": metadata,
            "client_id": client_id,
            "client_secret": client_secret,
        }
        return url, verifier, ctx

    raise ValueError(f"oauth not supported for {kind}")


async def exchange_oauth_code(
    *,
    kind: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
    settings_repo: Any,
    state_id: str,
) -> dict[str, Any]:
    ctx = load_oauth_ctx(settings_repo, state_id)
    flow = ctx.get("flow")

    if kind == "baidu-netdisk" or flow == "baidu":
        client_id, client_secret = resolve_baidu_client_credentials(settings_repo)
        return await exchange_baidu_code(
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

    if flow == "mcp" or kind in mcp_oauth_kinds():
        metadata = ctx.get("metadata")
        if not isinstance(metadata, dict):
            metadata = await fetch_authorization_metadata(issuer_for_kind(kind))
        client_id = str(ctx.get("client_id") or "")
        client_secret_raw = ctx.get("client_secret")
        secret = str(client_secret_raw) if client_secret_raw else None
        if not client_id and kind == "figma":
            client_id, secret = resolve_figma_client_credentials(settings_repo)
        if not client_id:
            raise ValueError("missing MCP oauth client_id")
        return await exchange_authorization_code(
            metadata,
            issuer=issuer_for_kind(kind),
            client_id=client_id,
            client_secret=secret,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        )

    raise ValueError(f"oauth exchange not supported for {kind}")


async def refresh_oauth_credentials(
    *,
    kind: str,
    creds: dict[str, Any],
    settings_repo: Any,
) -> dict[str, Any]:
    refresh = str(creds.get("refresh_token") or "")
    if not refresh:
        return creds

    if kind == "baidu-netdisk":
        client_id, client_secret = resolve_baidu_client_credentials(settings_repo)
        if not client_id or not client_secret:
            return creds
        return await refresh_baidu_token(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh,
        )

    if kind in mcp_oauth_kinds():
        issuer = issuer_for_kind(kind)
        metadata = await fetch_authorization_metadata(issuer)
        client_id = str(creds.get("oauth_client_id") or "")
        client_secret_raw = creds.get("oauth_client_secret")
        secret = str(client_secret_raw) if client_secret_raw else None
        if kind == "figma" and not client_id:
            client_id, secret = resolve_figma_client_credentials(settings_repo)
        if not client_id:
            return creds
        return await refresh_access_token(
            metadata,
            issuer=issuer,
            client_id=client_id,
            client_secret=secret,
            refresh_token=refresh,
        )

    return creds
