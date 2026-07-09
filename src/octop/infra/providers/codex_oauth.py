"""OpenAI Codex (ChatGPT) OAuth — PKCE browser flow.

Ported from finnie/lightclaw; constants match openclaw wire contract.
Tokens live at ``~/.octop/codex_oauth.json``.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import logging
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import TypedDict

from octop.infra.utils.paths import PathLayout

logger = logging.getLogger(__name__)

CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
AUTHORIZE_URL = "https://auth.openai.com/oauth/authorize"
TOKEN_URL = "https://auth.openai.com/oauth/token"
SCOPE = "openid profile email offline_access"
TOKEN_REQUEST_TIMEOUT_S = 30
TOKEN_EXPIRY_BUFFER_MS = 5 * 60 * 1000
CODEX_ATTRIBUTION_ORIGINATOR = "openclaw"
_OPENCLAW_UPSTREAM_VERSION = "2026.6.9"
CODEX_ATTRIBUTION_VERSION = (
    os.environ.get("OCTOP_CODEX_ATTRIBUTION_VERSION", "").strip() or _OPENCLAW_UPSTREAM_VERSION
)
CODEX_BASE_URL = "https://chatgpt.com/backend-api/codex"


class CodexOAuthCredentials(TypedDict):
    access: str
    refresh: str
    expires: int
    account_id: str


class CodexOAuthRefreshError(RuntimeError):
    def __init__(self, message: str, *, reason: str = "unknown") -> None:
        super().__init__(message)
        self.reason = reason


def oauth_token_file(paths: PathLayout) -> Path:
    return paths.root / "codex_oauth.json"


def _generate_pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    return verifier, challenge


def _decode_jwt_payload(access_token: str) -> dict[str, object] | None:
    parts = access_token.split(".")
    if len(parts) != 3:
        return None
    try:
        padded = parts[1] + "=="[: (4 - len(parts[1]) % 4) % 4]
        decoded = base64.urlsafe_b64decode(padded).decode("utf-8")
        result: dict[str, object] = json.loads(decoded)
        return result
    except Exception:
        return None


def extract_account_id(access_token: str) -> str:
    payload = _decode_jwt_payload(access_token)
    if not payload:
        return ""
    auth = payload.get("https://api.openai.com/auth", {})
    if not isinstance(auth, dict):
        return ""
    account_id = auth.get("chatgpt_account_id", "")
    return str(account_id).strip() if account_id else ""


def extract_token_expiry_ms(access_token: str, fallback_expires_in_s: int = 3600) -> int:
    payload = _decode_jwt_payload(access_token)
    if payload:
        exp = payload.get("exp")
        if isinstance(exp, int | float) and exp > 0:
            return int(exp) * 1000
    return int(time.time() * 1000) + fallback_expires_in_s * 1000


def save_codex_token(paths: PathLayout, cred: CodexOAuthCredentials) -> None:
    path = oauth_token_file(paths)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cred, indent=2), encoding="utf-8")
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)


def load_codex_token(paths: PathLayout) -> CodexOAuthCredentials | None:
    path = oauth_token_file(paths)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if all(k in data for k in ("access", "refresh", "expires")):
            return CodexOAuthCredentials(
                access=data["access"],
                refresh=data["refresh"],
                expires=int(data["expires"]),
                account_id=data.get("account_id", ""),
            )
    except Exception as exc:
        logger.warning("Failed to load Codex OAuth token: %s", exc)
    return None


def delete_codex_token(paths: PathLayout) -> None:
    path = oauth_token_file(paths)
    if path.exists():
        path.unlink()


def is_token_valid(cred: CodexOAuthCredentials) -> bool:
    return time.time() * 1000 < cred["expires"] - TOKEN_EXPIRY_BUFFER_MS


def refresh_codex_token(paths: PathLayout, cred: CodexOAuthCredentials) -> CodexOAuthCredentials:
    body = urllib.parse.urlencode(
        {
            "grant_type": "refresh_token",
            "refresh_token": cred["refresh"],
            "client_id": CLIENT_ID,
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TOKEN_REQUEST_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise CodexOAuthRefreshError(
            f"Codex token refresh failed (HTTP {exc.code}): {body_text}"
        ) from exc
    new_access = data["access_token"]
    new_cred = CodexOAuthCredentials(
        access=new_access,
        refresh=data.get("refresh_token", cred["refresh"]),
        expires=extract_token_expiry_ms(new_access, int(data.get("expires_in", 3600))),
        account_id=extract_account_id(new_access) or cred.get("account_id", ""),
    )
    save_codex_token(paths, new_cred)
    return new_cred


def get_valid_access_token(paths: PathLayout) -> str | None:
    cred = load_codex_token(paths)
    if cred is None:
        return None
    if not is_token_valid(cred):
        try:
            cred = refresh_codex_token(paths, cred)
        except CodexOAuthRefreshError as exc:
            logger.warning("Codex OAuth refresh failed: %s", exc)
            return None
    return cred["access"]


def build_codex_headers(account_id: str) -> dict[str, str]:
    headers = {
        "originator": CODEX_ATTRIBUTION_ORIGINATOR,
        "version": CODEX_ATTRIBUTION_VERSION,
        "User-Agent": f"{CODEX_ATTRIBUTION_ORIGINATOR}/{CODEX_ATTRIBUTION_VERSION}",
    }
    if account_id:
        headers["chatgpt-account-id"] = account_id
    return headers


def prepare_pkce_authorize(*, redirect_uri: str) -> tuple[str, str, str]:
    """Return ``(authorize_url, pkce_state, code_verifier)``."""
    verifier, challenge = _generate_pkce()
    pkce_state = secrets.token_hex(16)
    params = urllib.parse.urlencode(
        {
            "response_type": "code",
            "client_id": CLIENT_ID,
            "redirect_uri": redirect_uri,
            "scope": SCOPE,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "state": pkce_state,
            "id_token_add_organizations": "true",
            "codex_cli_simplified_flow": "true",
            "originator": "octop",
        }
    )
    return f"{AUTHORIZE_URL}?{params}", pkce_state, verifier


def exchange_authorization_code(
    *,
    code: str,
    verifier: str,
    redirect_uri: str,
) -> CodexOAuthCredentials:
    body = urllib.parse.urlencode(
        {
            "grant_type": "authorization_code",
            "client_id": CLIENT_ID,
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri,
        }
    ).encode()
    req = urllib.request.Request(
        TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=TOKEN_REQUEST_TIMEOUT_S) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(f"Codex token exchange failed (HTTP {exc.code}): {body_text}") from exc
    access = data["access_token"]
    return CodexOAuthCredentials(
        access=access,
        refresh=data["refresh_token"],
        expires=extract_token_expiry_ms(access, int(data.get("expires_in", 3600))),
        account_id=extract_account_id(access),
    )
