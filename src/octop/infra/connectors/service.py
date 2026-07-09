"""Connector service — MCP config assembly and credential access."""

from __future__ import annotations

import time
from typing import Any

from octop.config import OctopConfig
from octop.infra.connectors.builder import build_http_mcp_spec
from octop.infra.connectors.catalog import get_catalog_entry
from octop.infra.connectors.crypto import decrypt_credentials, encrypt_credentials
from octop.infra.connectors.oauth import refresh_oauth_credentials
from octop.infra.db.repos.connectors import ConnectorRepo, ConnectorRow
from octop.infra.db.repos.secrets import SecretRepo


def list_user_connector_instances(
    repo: ConnectorRepo,
    user_id: int,
    *,
    active_only: bool = False,
    with_credentials: bool = False,
) -> list[ConnectorRow]:
    """List connector instances for *user_id* with optional filters."""
    rows = repo.list_by_user(user_id)
    if active_only:
        rows = [r for r in rows if r.status == "active"]
    if with_credentials:
        rows = [r for r in rows if r.has_credentials]
    return rows


class ConnectorService:
    def __init__(
        self,
        *,
        repo: ConnectorRepo,
        secret_repo: SecretRepo,
        settings_repo: Any,
        config: OctopConfig,
    ) -> None:
        self._repo = repo
        self._secret_repo = secret_repo
        self._settings_repo = settings_repo
        self._config = config

    def list_user_instances(
        self,
        user_id: int,
        *,
        active_only: bool = False,
        with_credentials: bool = False,
    ) -> list[ConnectorRow]:
        return list_user_connector_instances(
            self._repo,
            user_id,
            active_only=active_only,
            with_credentials=with_credentials,
        )

    def decrypt(self, instance_id: str) -> dict[str, Any]:
        row = self._repo.get(instance_id)
        if row is None or not row.credential_blob:
            return {}
        return decrypt_credentials(self._secret_repo, row.credential_blob)

    def encrypt_and_store(
        self,
        *,
        instance_id: str,
        payload: dict[str, Any],
    ) -> None:
        expires_at = payload.get("expires_at")
        exp = int(expires_at) if expires_at is not None else None
        blob = encrypt_credentials(self._secret_repo, payload)
        self._repo.upsert_credentials(instance_id=instance_id, blob=blob, expires_at=exp)

    async def ensure_fresh_credentials(
        self,
        instance_id: str,
        kind: str,
    ) -> dict[str, Any]:
        creds = self.decrypt(instance_id)
        entry = get_catalog_entry(kind)
        if entry is None or entry.auth_kind != "oauth2":
            return creds
        expires_at = creds.get("expires_at")
        if expires_at and int(expires_at) > int(time.time()) + 120:
            return creds
        refresh = str(creds.get("refresh_token") or "")
        if not refresh:
            return creds
        try:
            refreshed = await refresh_oauth_credentials(
                kind=kind,
                creds=creds,
                settings_repo=self._settings_repo,
            )
        except Exception:
            return creds
        creds.update(refreshed)
        self.encrypt_and_store(instance_id=instance_id, payload=creds)
        return creds

    async def mcp_configs_for_user(self, user_id: int) -> dict[str, Any]:
        configs: dict[str, Any] = {}
        for inst in self._repo.list_by_user(user_id):
            if inst.status != "active":
                continue
            entry = get_catalog_entry(inst.kind)
            if entry is None:
                continue
            creds = await self.ensure_fresh_credentials(inst.instance_id, inst.kind)
            if not creds:
                continue
            configs[inst.mcp_server_name] = build_http_mcp_spec(
                entry=entry,
                instance_id=inst.instance_id,
                creds=creds,
                config=self._config,
            )
        return configs

    def verify_internal_token(self, instance_id: str, token: str) -> dict[str, Any] | None:
        creds = self.decrypt(instance_id)
        expected = str(creds.get("internal_token") or "")
        if not expected or expected != token:
            return None
        return creds
