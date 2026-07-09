"""Unit tests for SkillHub install error mapping."""

from __future__ import annotations

from fastapi import HTTPException

from octop.api.routers.skills import (
    _map_skillhub_install_error,
    _skillhub_rankings_args,
    _skillhub_stderr_suggests_upgrade,
)


def test_map_install_error_http_404() -> None:
    err = (
        '[skillhub] info: "agent-browser" not in index, using remote registry exact match\n'
        "Error: Download failed: HTTP 404 for https://api.skillhub.cn/api/v1/download?slug=agent-browser"
    )
    exc = _map_skillhub_install_error(err, "agent-browser")
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 404
    assert "agent-browser" in str(exc.detail)


def test_map_install_error_not_found() -> None:
    exc = _map_skillhub_install_error("skill nonexistent-xyz not found", "nonexistent-xyz")
    assert isinstance(exc, HTTPException)
    assert exc.status_code == 404


def test_map_install_error_unknown_returns_none() -> None:
    assert _map_skillhub_install_error("network timeout", "foo") is None


def test_stderr_suggests_upgrade() -> None:
    assert _skillhub_stderr_suggests_upgrade(
        "[skillhub] 发现新版本 2026.6.18（当前 2026.6.17）。运行 `skillhub self-upgrade` 进行升级。"
    )
    assert _skillhub_stderr_suggests_upgrade(
        "skills_store_cli.py: error: argument command: invalid choice: 'rankings'"
    )
    assert not _skillhub_stderr_suggests_upgrade("Download failed: HTTP 404")


def test_skillhub_rankings_args() -> None:
    assert _skillhub_rankings_args("hot") == ["skill", "rankings", "--type", "hot"]
    assert _skillhub_rankings_args("all", host="https://api.example.com") == [
        "skill",
        "rankings",
        "--type",
        "all",
        "--host",
        "https://api.example.com",
    ]
