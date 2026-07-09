"""Octop-specific storage backend probes (docker + row → harness probe)."""

from __future__ import annotations

import json
import logging
from typing import Any

from harness_agent.backends.probe import probe_backend

from octop.infra.backend.adapter import row_to_backend_spec
from octop.infra.db.repos.backends import BackendRow

logger = logging.getLogger(__name__)


def row_for_probe(
    *,
    kind: str,
    endpoint: str | None = None,
    access_key: str | None = None,
    secret_key: str | None = None,
    bucket: str | None = None,
    region: str | None = None,
    config_json: str | None = None,
    base: BackendRow | None = None,
) -> BackendRow:
    """Build a :class:`BackendRow` for probing from form fields (+ optional stored row)."""
    if base is None:
        return BackendRow(
            id=0,
            name="probe",
            kind=kind,
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            bucket=bucket,
            region=region,
            config_json=config_json,
            note=None,
            enabled=1,
            created_at=0,
            updated_at=0,
        )
    return BackendRow(
        id=base.id,
        name=base.name,
        kind=kind or base.kind,
        endpoint=endpoint if endpoint is not None else base.endpoint,
        access_key=access_key if access_key else base.access_key,
        secret_key=secret_key if secret_key else base.secret_key,
        bucket=bucket if bucket is not None else base.bucket,
        region=region if region is not None else base.region,
        config_json=config_json if config_json is not None else base.config_json,
        note=base.note,
        enabled=base.enabled,
        created_at=base.created_at,
        updated_at=base.updated_at,
    )


def probe_storage_backend(row: BackendRow) -> dict[str, Any]:
    """Return ``{ok: bool, message?: str, message_key?: str}`` after a probe."""
    kind = (row.kind or "").lower()

    if kind == "docker":
        return _probe_docker(row)

    spec = row_to_backend_spec(row)
    if spec is None:
        return {"ok": False, "message": "configuration incomplete"}

    if kind == "postgres" and not spec.get("connection_string"):
        if not row.endpoint:
            return {"ok": False, "message": "host/endpoint not configured"}
        return {"ok": True, "message": "postgres configuration present (no file round-trip)"}

    return probe_backend(spec)


def _probe_docker(row: BackendRow) -> dict[str, Any]:
    if row.config_json:
        try:
            cfg = json.loads(row.config_json)
            if isinstance(cfg, dict) and cfg.get("image"):
                return {"ok": True, "message": "docker image configured"}
        except Exception:
            pass
    if row.bucket:
        return {"ok": True, "message": f"docker image configured: {row.bucket}"}
    return {"ok": False, "message": "docker image not configured"}
