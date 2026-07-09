"""Per-agent memory dashboard router.

Mounts at ``/api/agents/{agent_id}/memory/*`` and forwards each
endpoint to a single JSON-RPC method on the agent's
``harness_memory.Bridge``. The router itself contains no business
logic — every handler is one ``call_memory_rpc(...)`` call.

Surface (mirrors the design doc §6.2):

* ``POST .../atoms/list``                       → ``list_atoms``
* ``GET  .../atoms/{atom_id}``                  → ``memory_get`` (path projection)
* ``POST .../atoms/{atom_id}:deprecate``        → ``deprecate_atom``
* ``POST .../entities/list``                    → ``list_entities``
* ``GET  .../entities/{entity_id}``             → ``memory_get`` (page projection, may be empty)
* ``POST .../episodes/list``                    → ``list_episodes``
* ``POST .../journal/list``                     → ``list_journal``
* ``POST .../candidates/list``                  → ``list_candidates``
* ``GET  .../raw_events/{event_id}``            → ``get_raw_event``
* ``GET  .../candidates/{candidate_id}``        → ``get_candidate``
* ``POST .../candidates/{id}:promote``          → ``promote_candidate``
* ``POST .../candidates/{id}:reject``           → ``reject_candidate``
* ``GET  .../stats/counts``                     → ``stats_counts``
* ``GET  .../stats/growth?days=N``              → ``stats_growth``
* ``GET  .../stats/atom_kinds``                 → ``stats_atom_kinds``
* ``GET  .../journal/recent?limit=N``           → ``recent_journal``
* ``GET  .../terminal/about_me?limit=N``        → ``terminal_about_me``
* ``GET  .../terminal/current_focus``           → ``terminal_current_focus``
* ``GET  .../terminal/things_you_told_me``      → ``terminal_things_you_told_me``
* ``GET  .../terminal/recent_stories``          → ``terminal_recent_stories``
* ``GET  .../terminal/entities``                → ``terminal_entities``
"""

from __future__ import annotations

import logging
from typing import Any, cast

from fastapi import APIRouter, Body, Depends, Query
from pydantic import BaseModel, Field

from octop.api.common.memory_client import call_memory_rpc
from octop.api.deps import current_user, get_server

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------


class _ListAtomsBody(BaseModel):
    """Request body for ``POST .../atoms/list``.

    Mirrors the bridge ``list_atoms`` params. All fields optional.
    """

    entity_id: str | None = None
    candidate_type: str | None = Field(
        default=None,
        description="One of Fact / Decision / Task / Preference / ConflictCandidate",
    )
    importance_min: str | None = Field(default=None, description="low / medium / high")
    include_deprecated: bool = False
    query: str | None = None
    order_by: str | None = Field(default=None, description="created_at / occurred_at / importance")
    order: str | None = Field(default=None, description="asc / desc")
    offset: int | None = None
    limit: int | None = None


class _ListEntitiesBody(BaseModel):
    entity_type: str | None = None
    query: str | None = None
    order_by: str | None = None
    order: str | None = None
    offset: int | None = None
    limit: int | None = None


class _ListEpisodesBody(BaseModel):
    emotion: str | None = None
    intensity_min: int | None = Field(default=None, ge=1, le=5)
    date_from: str | None = None
    date_to: str | None = None
    topic: str | None = None
    query: str | None = None
    offset: int | None = None
    limit: int | None = None


class _ListJournalBody(BaseModel):
    action: str | None = None
    target_type: str | None = Field(default=None, description="atom / entity / candidate")
    actor: str | None = None
    time_from: str | None = None
    time_to: str | None = None
    target_entity_id: str | None = None
    target_atom_id: str | None = None
    target_candidate_id: str | None = None
    offset: int | None = None
    limit: int | None = None


class _ListCandidatesBody(BaseModel):
    """Request body for ``POST .../candidates/list``.

    Mirrors the bridge ``list_candidates`` params. All fields optional;
    the bridge defaults ``status`` to ``pending`` so the empty body
    returns the work queue.
    """

    status: str | None = Field(
        default=None,
        description="pending / needs_review / conflict / promoted / rejected",
    )
    candidate_type: str | None = Field(
        default=None,
        description="One of Fact / Decision / Task / Preference / ConflictCandidate",
    )
    session_id: str | None = None
    target_entity_id: str | None = None
    time_from: str | None = None
    time_to: str | None = None
    query: str | None = None
    offset: int | None = None
    limit: int | None = None


class _RejectCandidateBody(BaseModel):
    reason: str | None = None
    actor: str | None = Field(default=None, description="user / auto / rule (defaults user)")


class _DeprecateAtomBody(BaseModel):
    reason: str | None = None
    actor: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_none(payload: dict[str, Any]) -> dict[str, Any]:
    """Remove ``None`` keys before forwarding so the bridge sees a clean dict.

    The bridge handlers treat ``None`` and "missing" identically; we
    drop them to keep the payload smaller and to avoid surprising
    handler validation that special-cases ``param is None``.
    """
    return {k: v for k, v in payload.items() if v is not None}


# ---------------------------------------------------------------------------
# Listings
# ---------------------------------------------------------------------------


@router.post("/agents/{agent_id}/memory/atoms/list")
async def list_atoms(
    agent_id: str,
    body: _ListAtomsBody = Body(default_factory=_ListAtomsBody),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="list_atoms",
            params=_strip_none(body.model_dump()),
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.post("/agents/{agent_id}/memory/entities/list")
async def list_entities(
    agent_id: str,
    body: _ListEntitiesBody = Body(default_factory=_ListEntitiesBody),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="list_entities",
            params=_strip_none(body.model_dump()),
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.post("/agents/{agent_id}/memory/episodes/list")
async def list_episodes(
    agent_id: str,
    body: _ListEpisodesBody = Body(default_factory=_ListEpisodesBody),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="list_episodes",
            params=_strip_none(body.model_dump()),
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.post("/agents/{agent_id}/memory/journal/list")
async def list_journal(
    agent_id: str,
    body: _ListJournalBody = Body(default_factory=_ListJournalBody),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="list_journal",
            params=_strip_none(body.model_dump()),
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.post("/agents/{agent_id}/memory/candidates/list")
async def list_candidates(
    agent_id: str,
    body: _ListCandidatesBody = Body(default_factory=_ListCandidatesBody),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="list_candidates",
            params=_strip_none(body.model_dump()),
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


# ---------------------------------------------------------------------------
# Single-row fetches
# ---------------------------------------------------------------------------


@router.get("/agents/{agent_id}/memory/raw_events/{event_id}")
async def get_raw_event(
    agent_id: str,
    event_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="get_raw_event",
            params={"event_id": event_id},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.get("/agents/{agent_id}/memory/candidates/{candidate_id}")
async def get_candidate(
    agent_id: str,
    candidate_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="get_candidate",
            params={"candidate_id": candidate_id},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.get("/agents/{agent_id}/memory/atoms/{atom_id}")
async def get_atom(
    agent_id: str,
    atom_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="get_atom",
            params={"atom_id": atom_id},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.get("/agents/{agent_id}/memory/entities/{entity_id}")
async def get_entity(
    agent_id: str,
    entity_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="get_entity",
            params={"entity_id": entity_id},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.get("/agents/{agent_id}/memory/episodes/{episode_id}")
async def get_episode(
    agent_id: str,
    episode_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="get_episode",
            params={"episode_id": episode_id},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


# ---------------------------------------------------------------------------
# Stats / overview
# ---------------------------------------------------------------------------


@router.get("/agents/{agent_id}/memory/stats/counts")
async def stats_counts(
    agent_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="stats_counts",
            params={},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.get("/agents/{agent_id}/memory/stats/growth")
async def stats_growth(
    agent_id: str,
    days: int = Query(default=7, ge=1, le=90),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="stats_growth",
            params={"days": days},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.get("/agents/{agent_id}/memory/stats/atom_kinds")
async def stats_atom_kinds(
    agent_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="stats_atom_kinds",
            params={},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.get("/agents/{agent_id}/memory/journal/recent")
async def recent_journal(
    agent_id: str,
    limit: int = Query(default=5, ge=1, le=100),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="recent_journal",
            params={"limit": limit},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


# ---------------------------------------------------------------------------
# Write actions
# ---------------------------------------------------------------------------


@router.post("/agents/{agent_id}/memory/candidates/{candidate_id}:promote")
async def promote_candidate(
    agent_id: str,
    candidate_id: str,
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="promote_candidate",
            params={"candidate_id": candidate_id},
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.post("/agents/{agent_id}/memory/candidates/{candidate_id}:reject")
async def reject_candidate(
    agent_id: str,
    candidate_id: str,
    body: _RejectCandidateBody = Body(default_factory=_RejectCandidateBody),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    params = _strip_none({"candidate_id": candidate_id, **body.model_dump()})
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="reject_candidate",
            params=params,
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


@router.post("/agents/{agent_id}/memory/atoms/{atom_id}:deprecate")
async def deprecate_atom(
    agent_id: str,
    atom_id: str,
    body: _DeprecateAtomBody = Body(default_factory=_DeprecateAtomBody),
    as_user: int | None = None,
    user: Any = Depends(current_user),
    server: Any = Depends(get_server),
) -> dict[str, Any]:
    params = _strip_none({"atom_id": atom_id, **body.model_dump()})
    return cast(
        dict[str, Any],
        call_memory_rpc(
            agent_id=agent_id,
            method="deprecate_atom",
            params=params,
            user=user,
            as_user=as_user,
            server=server,
        ),
    )


# ---------------------------------------------------------------------------
# Terminal aggregator endpoints
# ---------------------------------------------------------------------------


def _terminal_endpoint(method_name: str) -> Any:
    """Build a no-body terminal_* endpoint with a ``limit`` query param.

    The 5 terminal cards have the same shape; this factory keeps the
    router compact without introducing a second router-mounting layer.
    """

    async def _handler(
        agent_id: str,
        limit: int = Query(default=5, ge=1, le=20),
        as_user: int | None = None,
        user: Any = Depends(current_user),
        server: Any = Depends(get_server),
    ) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            call_memory_rpc(
                agent_id=agent_id,
                method=method_name,
                params={"limit": limit},
                user=user,
                as_user=as_user,
                server=server,
            ),
        )

    _handler.__name__ = method_name
    return _handler


router.add_api_route(
    "/agents/{agent_id}/memory/terminal/about_me",
    _terminal_endpoint("terminal_about_me"),
    methods=["GET"],
)
router.add_api_route(
    "/agents/{agent_id}/memory/terminal/current_focus",
    _terminal_endpoint("terminal_current_focus"),
    methods=["GET"],
)
router.add_api_route(
    "/agents/{agent_id}/memory/terminal/things_you_told_me",
    _terminal_endpoint("terminal_things_you_told_me"),
    methods=["GET"],
)
router.add_api_route(
    "/agents/{agent_id}/memory/terminal/recent_stories",
    _terminal_endpoint("terminal_recent_stories"),
    methods=["GET"],
)
router.add_api_route(
    "/agents/{agent_id}/memory/terminal/entities",
    _terminal_endpoint("terminal_entities"),
    methods=["GET"],
)


__all__ = ["router"]
