"""Integration tests for GET /api/agents/{id}/skills/hub/search
and POST /api/agents/{id}/skills/hub/install."""

from __future__ import annotations

from typing import Any

import pytest


@pytest.fixture
async def env(env_with_main_agent):
    yield env_with_main_agent


# --- auth guard tests -------------------------------------------------------


async def test_hub_search_requires_auth(env: Any) -> None:
    c, _srv, _auth, aid = env
    r = await c.get(f"/api/agents/{aid}/skills/hub/search")
    assert r.status_code not in (200,), f"Expected auth failure, got {r.status_code}"


async def test_hub_install_requires_auth(env: Any) -> None:
    c, _srv, _auth, aid = env
    r = await c.post(
        f"/api/agents/{aid}/skills/hub/install",
        json={"skill_name": "file-reader", "enable": True},
    )
    assert r.status_code not in (200, 201), f"Expected auth failure, got {r.status_code}"


# --- authenticated search tests ---------------------------------------------


async def test_hub_search_returns_list(env: Any) -> None:
    """Authenticated GET → 200 and response body is a list.

    The skillhub CLI may not be installed in CI, in which case the server
    returns a 5xx.  Both outcomes are acceptable; what we must never see
    is a non-list 200 or an auth error.
    """
    c, _srv, auth, aid = env
    r = await c.get(f"/api/agents/{aid}/skills/hub/search", headers=auth)
    if r.status_code == 200:
        assert isinstance(r.json(), list), "200 response body must be a list"
    else:
        # 502/504 when skillhub CLI is absent — that is fine
        assert r.status_code in (502, 504), f"Unexpected status {r.status_code}: {r.text}"


async def test_hub_search_with_query(env: Any) -> None:
    """Authenticated GET with q=file-reader → 200 (list) or 5xx if CLI absent."""
    c, _srv, auth, aid = env
    r = await c.get(
        f"/api/agents/{aid}/skills/hub/search",
        headers=auth,
        params={"q": "file-reader"},
    )
    if r.status_code == 200:
        assert isinstance(r.json(), list), "200 response body must be a list"
    else:
        assert r.status_code in (502, 504), f"Unexpected status {r.status_code}: {r.text}"


async def test_hub_rankings_returns_dict(env: Any) -> None:
    """Authenticated GET rankings → 200 (dict) or 5xx if CLI absent."""
    c, _srv, auth, aid = env
    r = await c.get(
        f"/api/agents/{aid}/skills/hub/rankings",
        headers=auth,
        params={"type": "hot"},
    )
    if r.status_code == 200:
        body = r.json()
        assert isinstance(body, dict), "200 response body must be a dict"
        assert "skills" in body, "rankings response must include skills list"
    else:
        assert r.status_code in (502, 504), f"Unexpected status {r.status_code}: {r.text}"


# --- authenticated install tests --------------------------------------------


async def test_hub_install_unknown_skill(env: Any) -> None:
    """POST with a nonexistent skill → 4xx (400/404) or 5xx if CLI absent."""
    c, _srv, auth, aid = env
    r = await c.post(
        f"/api/agents/{aid}/skills/hub/install",
        headers=auth,
        json={"skill_name": "nonexistent-xyz-skill-abc123", "enable": True},
    )
    # 400 for bad name validation, 404 if skillhub says not found,
    # 502/504 if skillhub CLI is absent or network unavailable
    assert r.status_code != 200, f"Expected non-200, got {r.status_code}"
    assert r.status_code in (400, 404, 502, 504), f"Unexpected status {r.status_code}: {r.text}"
