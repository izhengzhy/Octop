"""Unit tests for skills.sh / GitHub raw bundle resolution."""

from __future__ import annotations

from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from octop.infra.agents.skills_hub import resolve_bundle_from_url

FIND_SKILLS_MD = """---
name: find-skills
description: Discover and install skills
---

# Find Skills
"""


def test_resolve_skills_sh_url_uses_raw_github_without_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    requested_urls: list[str] = []

    def _fake_http_text_get(url: str, params: dict | None = None) -> str:
        del params
        requested_urls.append(url)
        if url.endswith("/skills/find-skills/SKILL.md"):
            return FIND_SKILLS_MD
        raise AssertionError(f"unexpected raw fetch: {url}")

    with patch(
        "octop.infra.agents.skills_hub._http_text_get",
        side_effect=_fake_http_text_get,
    ):
        resolved = resolve_bundle_from_url(
            bundle_url="https://skills.sh/vercel-labs/skills/find-skills",
        )

    assert resolved.name == "find-skills"
    assert resolved.uploads[0][0] == "skills/find-skills/SKILL.md"
    assert b"Find Skills" in resolved.uploads[0][1]
    assert requested_urls == [
        "https://raw.githubusercontent.com/vercel-labs/skills/main/skills/find-skills/SKILL.md",
    ]


def test_resolve_skills_sh_url_falls_back_to_second_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GH_TOKEN", raising=False)

    def _fake_http_text_get(url: str, params: dict | None = None) -> str:
        del params
        if "/main/" in url:
            raise HTTPError(url, 404, "Not Found", None, None)
        if url.endswith("/skills/find-skills/SKILL.md"):
            return FIND_SKILLS_MD
        raise AssertionError(f"unexpected raw fetch: {url}")

    with patch(
        "octop.infra.agents.skills_hub._http_text_get",
        side_effect=_fake_http_text_get,
    ):
        resolved = resolve_bundle_from_url(
            bundle_url="https://skills.sh/vercel-labs/skills/find-skills",
        )

    assert resolved.name == "find-skills"
