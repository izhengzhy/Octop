"""Experts router — expose the bundled scene templates.

GET /api/experts             → summaries (id, label, description, …)
GET /api/experts/{id}        → template metadata + lazy ``file_contents``
POST /api/agents/from-expert/{id} → create agent and seed workspace files
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from octop.api.deps import current_user, get_server
from octop.infra.agents.experts.catalog import (
    build_create_spec_from_expert,
    preview_file_paths,
)
from octop.infra.errors import ErrorCode, OctopError
from octop.infra.utils.locale import resolve_user_locale

router = APIRouter()


class FromExpertBody(BaseModel):
    name: str | None = None
    description: str | None = None
    providers: list[str] | None = None
    default_model: str | None = None
    backend: dict[str, Any] | None = None


def _quick_prompt_dict(p: Any) -> dict[str, Any]:
    return {
        "title": {"zh": p.title_zh, "en": p.title_en},
        "description": {"zh": p.description_zh, "en": p.description_en},
        "prompt": {"zh": p.prompt_zh, "en": p.prompt_en},
        "color": p.color,
        "icon_name": p.icon_name,
    }


def _summary_dict(s: Any) -> dict[str, Any]:
    return {
        "id": s.id,
        "label": {"zh": s.label_zh, "en": s.label_en},
        "description": {"zh": s.description_zh, "en": s.description_en},
        "welcome_message": {
            "zh": s.welcome_message_zh,
            "en": s.welcome_message_en,
        },
        "icon_name": s.icon_name,
        "color": s.color,
        "quick_prompts": [_quick_prompt_dict(p) for p in getattr(s, "quick_prompts", ())],
    }


def _expert_dict(
    e: Any,
    catalog: Any,
    *,
    include_file_contents: bool = False,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        **_summary_dict(e.summary),
        "files": list(e.files),
        "prompt_files": list(e.prompt_files),
        "quick_prompts": [_quick_prompt_dict(p) for p in getattr(e, "quick_prompts", ())],
    }
    if include_file_contents:
        result["file_contents"] = catalog.read_file_contents(
            e.summary.id,
            paths=preview_file_paths(e),
        )
    return result


@router.get("/experts")
async def list_experts(
    _: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> list[dict[str, Any]]:
    catalog = server.expert_catalog
    if catalog is None:
        return []
    return [_summary_dict(s) for s in catalog.list_summaries()]


@router.get("/experts/{expert_id}")
async def get_expert(
    expert_id: str,
    _: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    catalog = server.expert_catalog
    expert = None if catalog is None else catalog.get(expert_id)
    if expert is None:
        raise OctopError(ErrorCode.NOT_FOUND, f"expert {expert_id!r} not found")
    return _expert_dict(expert, catalog, include_file_contents=True)


@router.post("/agents/from-expert/{expert_id}", status_code=201)
async def create_agent_from_expert(
    expert_id: str,
    body: FromExpertBody,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    """Create an agent with the expert template workspace files."""
    catalog = server.expert_catalog
    expert = None if catalog is None else catalog.get(expert_id)
    if expert is None:
        raise OctopError(ErrorCode.NOT_FOUND, f"expert {expert_id!r} not found")
    assert server.app_runtime is not None

    config_extra: dict[str, Any] = {}
    if body.providers:
        config_extra["providers"] = list(body.providers)
    if body.backend:
        config_extra["backend"] = body.backend

    locale = resolve_user_locale(
        user_repo=server.services.user_repo,
        user_id=user.id,
    )
    spec = build_create_spec_from_expert(
        expert_id=expert_id,
        expert=expert,
        user_id=user.id,
        name=body.name,
        description=body.description,
        locale=locale,
        default_model=body.default_model,
        config_extra=config_extra or None,
    )
    row = await server.app_runtime.agent_registry.create(spec, defer_bootstrap=True)
    return {
        "id": row.id,
        "agent_id": row.agent_id,
        "user_id": row.user_id,
        "name": row.name,
        "description": row.description,
        "default_model": row.default_model,
        "state": row.last_state or "unknown",
        "expert_id": expert_id,
        "icon_name": expert.summary.icon_name,
        "color": expert.summary.color,
        "bootstrap_pending": not server.app_runtime.agent_registry.is_bootstrapped(row.agent_id),
    }
